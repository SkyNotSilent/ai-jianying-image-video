import sqlite3
from pathlib import Path

import pytest

from src.api import task_executor as task_executor_module
from src.api import task_manager as task_manager_module
from src.api.models import TaskStatus
from src.api.task_executor import TaskExecutor
from src.api.task_manager import Task, TaskManager
from src.api.task_runtime import TaskCancellation, TaskRuntimeRegistry
from src.database import sqlite_client as sqlite_client_module
from src.database.sqlite_client import SQLiteClient


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", tmp_path / "local.db")
    return SQLiteClient()


@pytest.fixture
def task_manager(temp_db, monkeypatch):
    monkeypatch.setattr(task_manager_module, "db_client", temp_db)
    return TaskManager()


@pytest.fixture
def executor_db(temp_db, task_manager, monkeypatch):
    monkeypatch.setattr(task_executor_module, "db_client", temp_db, raising=False)
    monkeypatch.setattr(task_executor_module, "task_manager", task_manager)
    return temp_db


class FakeScriptRewriter:
    def __init__(self, cancellation=None):
        self.calls = 0
        self.cancellation = cancellation

    def rewrite(self, *args, **kwargs):
        self.calls += 1
        if self.cancellation:
            self.cancellation.cancel()
        return {"script": "第一段。第二段。", "summary": "摘要"}


class FakeTextSegmenter:
    def __init__(self):
        self.calls = 0

    def split(self, article):
        self.calls += 1
        return ["第一段", "第二段"]


class FakePromptAgent:
    def __init__(self, failure_call=None, before_call=None):
        self.calls = 0
        self.failure_call = failure_call
        self.before_call = before_call

    def generate_prompt(self, **kwargs):
        self.calls += 1
        if self.before_call:
            self.before_call(self.calls)
        if self.calls == self.failure_call:
            raise RuntimeError("prompt failed")
        return f"prompt-{self.calls - 1}"


class FakeAssetGenerator:
    def __init__(self, output_dir, suffix, fail=False):
        self.output_dir = Path(output_dir)
        self.suffix = suffix
        self.fail = fail
        self.calls = []

    def generate(self, value, **kwargs):
        index = kwargs.get("index")
        if index is None:
            index = int(kwargs["filename"].split("_")[-1])
        self.calls.append(index)
        if self.fail:
            raise RuntimeError(f"{self.suffix} failed")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"seg_{index:03d}.{self.suffix}"
        path.write_bytes(self.suffix.encode())
        return str(path)


class FakeDraftBuilder:
    def __init__(self):
        self.calls = 0

    def build(self, **kwargs):
        self.calls += 1
        return str(Path(kwargs["output_dir"]) / "draft")


class FakePipeline:
    def __init__(self, output_dir, prompt_failure_call=None, fail_assets=False,
                 cancellation=None, before_prompt_call=None):
        self.output_dir = output_dir
        self.script_rewriter = FakeScriptRewriter(cancellation=cancellation)
        self.text_segmenter = FakeTextSegmenter()
        self.image_prompt_agent = FakePromptAgent(
            prompt_failure_call, before_call=before_prompt_call
        )
        self.image_generator = FakeAssetGenerator(
            Path(output_dir) / "images", "png", fail=fail_assets
        )
        self.voiceover_generator = FakeAssetGenerator(
            Path(output_dir) / "voiceovers", "wav", fail=fail_assets
        )
        self.draft_builder = FakeDraftBuilder()
        self.article = ""
        self.summary = ""
        self.segments = []
        self.image_prompts = []
        self.media_paths = []
        self.voiceover_files = []


def create_task(db, task_id="task-1", status="pending"):
    db.create_task(
        task_id, "原始内容", "知识科普|电影质感", 100, name="恢复测试"
    )
    if status != "pending":
        db.update_task_status(task_id, status, "image_generation")


def test_checkpoint_round_trip(temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)

    assert temp_db.save_task_checkpoint(
        "task-1", script_text="完整脚本", summary="摘要", input_mode="theme"
    )

    row = temp_db.get_task("task-1")
    assert row["script_text"] == "完整脚本"
    assert row["summary"] == "摘要"
    assert row["input_mode"] == "theme"


def test_checkpoint_migration_preserves_existing_task(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            name TEXT,
            theme TEXT NOT NULL,
            style TEXT NOT NULL DEFAULT '温暖感人',
            length INTEGER NOT NULL DEFAULT 300,
            ratio TEXT NOT NULL DEFAULT '16:9',
            voice_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT DEFAULT 'pending',
            error TEXT,
            extract_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            completed_at TEXT
        );
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO tasks (task_id, theme, style, length)
        VALUES ('legacy-task', '已有任务', '知识科普|电影质感', 100);
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", db_path)

    row = SQLiteClient().get_task("legacy-task")

    assert row["theme"] == "已有任务"
    assert row["script_text"] is None
    assert row["summary"] is None
    assert row["input_mode"] == "script"


def test_checkpoint_migration_recovers_from_partial_column_application(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "partial-migration.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            name TEXT,
            theme TEXT NOT NULL,
            style TEXT NOT NULL DEFAULT '温暖感人',
            length INTEGER NOT NULL DEFAULT 300,
            ratio TEXT NOT NULL DEFAULT '16:9',
            voice_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT DEFAULT 'pending',
            error TEXT,
            extract_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            completed_at TEXT,
            script_text TEXT
        );
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO tasks (task_id, theme, style, length, script_text)
        VALUES (
            'partial-task', '部分迁移任务', '知识科普|电影质感', 100, '已保存脚本'
        );
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", db_path)

    client = SQLiteClient()
    row = client.get_task("partial-task")

    assert row is not None
    assert row["theme"] == "部分迁移任务"
    assert row["script_text"] == "已保存脚本"
    assert row["summary"] is None
    assert row["input_mode"] == "script"
    with client.get_connection() as connection:
        columns = {
            column["name"] for column in connection.execute("PRAGMA table_info(tasks)")
        }
        marker = connection.execute(
            "SELECT version FROM schema_migrations WHERE version=?",
            ("20260711_task_recovery_checkpoints",),
        ).fetchone()
    assert {"script_text", "summary", "input_mode"}.issubset(columns)
    assert marker["version"] == "20260711_task_recovery_checkpoints"


def test_segment_checkpoint_updates_only_allowed_fields(temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)
    temp_db.save_segments(
        "task-1",
        [{"segment_index": 0, "text": "第一段", "image_status": "pending"}],
    )

    assert temp_db.update_segment_checkpoint(
        "task-1",
        0,
        image_prompt="画面提示词",
        image_status="completed",
        unsupported="ignored",
    )

    row = temp_db.get_segments("task-1")[0]
    assert row["image_prompt"] == "画面提示词"
    assert row["image_status"] == "completed"


def test_orphaned_processing_task_becomes_interrupted(task_manager, temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)
    temp_db.update_task_status("task-1", "processing", "image_generation")
    temp_db.save_segments(
        "task-1",
        [{"segment_index": 0, "text": "已保存分镜", "image_status": "completed"}],
    )
    asset = temp_db.save_task_asset(
        "task-1", "image", "generated", segment_index=0, path="saved.png"
    )

    assert task_manager.mark_orphaned_tasks_interrupted() == 1

    row = temp_db.get_task("task-1")
    assert row["status"] == "interrupted"
    assert row["current_step"] == "image_generation"
    assert row["error"] == "服务重启导致任务中断，可继续生成"
    assert temp_db.get_segments("task-1")[0]["text"] == "已保存分镜"
    assert temp_db.list_task_assets("task-1")[0]["asset_id"] == asset["asset_id"]


def test_interrupted_status_keeps_progress_in_task_response():
    task = Task("task-1", "主题", "知识科普|电影质感", 100)
    task.status = TaskStatus.INTERRUPTED

    assert TaskStatus.DELETING.value == "deleting"
    assert task.to_response().progress is not None


def test_deleting_tasks_are_hidden_from_default_and_explicit_lists(
    task_manager, temp_db
):
    temp_db.create_task("visible-task", "可见任务", "知识科普|电影质感", 100)
    temp_db.update_task_status("visible-task", "completed", "video_synthesis")
    temp_db.create_task("deleting-task", "删除中任务", "知识科普|电影质感", 100)
    temp_db.update_task_status("deleting-task", "deleting", "image_generation")

    assert [row["task_id"] for row in task_manager.list_tasks()] == ["visible-task"]
    assert task_manager.list_tasks(status="deleting") == []
    assert [
        row["task_id"] for row in temp_db.list_tasks(status="deleting")
    ] == ["deleting-task"]


def test_deleting_tasks_do_not_consume_default_pagination(task_manager, temp_db):
    tasks = [
        ("visible-task", "completed", "2026-07-11 12:00:00"),
        ("deleting-task-1", "deleting", "2026-07-11 12:02:00"),
        ("deleting-task-2", "deleting", "2026-07-11 12:01:00"),
    ]
    for task_id, status, created_at in tasks:
        temp_db.create_task(task_id, task_id, "知识科普|电影质感", 100)
        temp_db.update_task_status(task_id, status, "image_generation")
        with temp_db.get_connection() as connection:
            connection.execute(
                "UPDATE tasks SET created_at=? WHERE task_id=?",
                (created_at, task_id),
            )

    rows = task_manager.list_tasks(limit=1, offset=0)

    assert [row["task_id"] for row in rows] == ["visible-task"]


def test_resume_selection_skips_valid_completed_assets(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"png")
    segments = [
        {
            "segment_index": 0,
            "image_prompt": "已有提示词",
            "image_path": str(image),
            "image_status": "completed",
        },
        {
            "segment_index": 1,
            "image_prompt": "",
            "image_path": None,
            "image_status": "pending",
        },
    ]

    work = task_executor_module.build_resume_work(segments)

    assert work.prompt_indexes == [1]
    assert work.image_indexes == [1]


def test_completed_status_with_missing_file_is_regenerated(tmp_path):
    segments = [
        {
            "segment_index": 0,
            "text": "第一段",
            "image_prompt": "提示词",
            "image_path": str(tmp_path / "missing.png"),
            "image_status": "completed",
            "audio_path": str(tmp_path / "missing.wav"),
            "audio_status": "completed",
        }
    ]

    work = task_executor_module.build_resume_work(segments)

    assert work.image_indexes == [0]
    assert work.audio_indexes == [0]
    assert work.media_paths == [None]
    assert work.voiceover_files == [None]


def test_each_prompt_is_persisted_before_the_next_model_call(
    executor_db, monkeypatch
):
    create_task(executor_db)
    pipeline = FakePipeline(
        output_dir="unused", prompt_failure_call=2
    )
    executor = TaskExecutor(pipeline_factory=lambda **kwargs: pipeline)
    cancellation = TaskCancellation()

    executor.run_inline("task-1", cancellation=cancellation)

    rows = executor_db.get_segments("task-1")
    assert rows[0]["image_prompt"] == "prompt-0"
    assert rows[1]["image_prompt"] in {None, ""}
    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.draft_builder.calls == 0


def test_script_and_initial_segments_are_saved_before_prompt_generation(
    executor_db
):
    create_task(executor_db)

    def assert_initial_rows(call_number):
        rows = executor_db.get_segments("task-1")
        assert call_number == 1
        assert [row["text"] for row in rows] == ["第一段", "第二段"]
        assert [row["image_status"] for row in rows] == ["pending", "pending"]
        assert [row["audio_status"] for row in rows] == ["pending", "pending"]

    pipeline = FakePipeline(
        output_dir="unused",
        prompt_failure_call=1,
        before_prompt_call=assert_initial_rows,
    )

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    task = executor_db.get_task("task-1")
    rows = executor_db.get_segments("task-1")
    assert task["script_text"] == "第一段。第二段。"
    assert task["summary"] == "摘要"
    assert [row["text"] for row in rows] == ["第一段", "第二段"]


def test_resume_reuses_segments_and_submits_only_missing_assets(
    executor_db, tmp_path
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="已保存脚本", summary="已保存摘要", input_mode="script"
    )
    image = tmp_path / "legacy" / "images" / "seg_000.png"
    audio = tmp_path / "legacy" / "voiceovers" / "seg_000.wav"
    image.parent.mkdir(parents=True)
    audio.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    audio.write_bytes(b"wav")
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 0,
                "text": "已有分镜",
                "image_prompt": "已有提示词",
                "image_path": str(image),
                "image_status": "completed",
                "audio_path": str(audio),
                "audio_status": "completed",
            },
            {
                "segment_index": 1,
                "text": "待恢复分镜",
                "image_prompt": "待恢复提示词",
                "image_status": "pending",
                "audio_status": "pending",
            },
        ],
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "legacy"), fail_assets=True)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert pipeline.script_rewriter.calls == 0
    assert pipeline.text_segmenter.calls == 0
    assert pipeline.image_prompt_agent.calls == 0
    assert pipeline.image_generator.calls == [1]
    assert pipeline.voiceover_generator.calls == [1]
    assert pipeline.draft_builder.calls == 0
    assert executor_db.get_segments("task-1")[0]["image_path"] == str(image)


def test_missing_prompt_does_not_resubmit_valid_completed_image(
    executor_db, tmp_path
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    image = tmp_path / "legacy" / "images" / "seg_000.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 0,
                "text": "已有分镜",
                "image_prompt": "",
                "image_path": str(image),
                "image_status": "completed",
                "audio_status": "pending",
            }
        ],
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "legacy"), fail_assets=True)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    row = executor_db.get_segments("task-1")[0]
    assert pipeline.image_prompt_agent.calls == 1
    assert pipeline.image_generator.calls == []
    assert pipeline.voiceover_generator.calls == [0]
    assert row["image_status"] == "completed"
    assert row["image_path"] == str(image)


def test_prompt_failure_preserves_valid_completed_image_checkpoint(
    executor_db, tmp_path
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    image = tmp_path / "legacy" / "images" / "seg_000.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 0,
                "text": "已有分镜",
                "image_prompt": "",
                "image_path": str(image),
                "image_status": "completed",
                "audio_status": "pending",
            }
        ],
    )
    pipeline = FakePipeline(
        output_dir=str(tmp_path / "legacy"), prompt_failure_call=1
    )

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    row = executor_db.get_segments("task-1")[0]
    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert row["image_status"] == "completed"
    assert row["image_path"] == str(image)


def test_provider_item_failures_interrupt_before_draft(executor_db):
    create_task(executor_db)
    pipeline = FakePipeline(output_dir="unused", fail_assets=True)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    rows = executor_db.get_segments("task-1")
    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert all(row["image_status"] == "failed" for row in rows)
    assert all(row["audio_status"] == "failed" for row in rows)
    assert all(row["image_error"] == "png failed" for row in rows)
    assert all(row["audio_error"] == "wav failed" for row in rows)
    assert pipeline.draft_builder.calls == 0


def test_cancellation_at_real_stage_boundary_marks_task_interrupted(
    executor_db
):
    create_task(executor_db)
    cancellation = TaskCancellation()
    pipeline = FakePipeline(output_dir="unused", cancellation=cancellation)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=cancellation
    )

    task = executor_db.get_task("task-1")
    assert task["status"] == "interrupted"
    assert task["script_text"] == "第一段。第二段。"
    assert pipeline.text_segmenter.calls == 0
    assert pipeline.draft_builder.calls == 0


def test_cancellation_does_not_overwrite_deleting_status(executor_db):
    create_task(executor_db, status="deleting")
    cancellation = TaskCancellation()
    cancellation.cancel()

    TaskExecutor(pipeline_factory=FakePipeline).run_inline(
        "task-1", cancellation=cancellation
    )

    assert executor_db.get_task("task-1")["status"] == "deleting"


def test_new_task_uses_task_owned_output_directory(executor_db, tmp_path, monkeypatch):
    create_task(executor_db)
    created = []

    def pipeline_factory(**kwargs):
        created.append(kwargs)
        return FakePipeline(kwargs["output_dir"], prompt_failure_call=1)

    monkeypatch.chdir(tmp_path)
    TaskExecutor(pipeline_factory=pipeline_factory).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert Path(created[0]["output_dir"]) == Path("output/task-1/恢复测试")


def test_resume_uses_legacy_output_directory_from_persisted_path(
    executor_db, tmp_path
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    legacy_image = tmp_path / "old-project" / "images" / "seg_000.png"
    legacy_image.parent.mkdir(parents=True)
    legacy_image.write_bytes(b"png")
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 0,
                "text": "第一段",
                "image_prompt": "",
                "image_path": str(legacy_image),
                "image_status": "completed",
                "audio_status": "pending",
            }
        ],
    )
    created = []

    def pipeline_factory(**kwargs):
        created.append(kwargs)
        return FakePipeline(kwargs["output_dir"], prompt_failure_call=1)

    TaskExecutor(pipeline_factory=pipeline_factory).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert Path(created[0]["output_dir"]) == tmp_path / "old-project"


def test_resume_task_reports_lifecycle_outcomes(
    executor_db, monkeypatch
):
    create_task(executor_db, "recoverable", status="interrupted")
    executor_db.save_task_checkpoint(
        "recoverable", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "recoverable", [{"segment_index": 0, "text": "第一段"}]
    )
    create_task(executor_db, "completed", status="completed")
    create_task(executor_db, "empty", status="interrupted")
    registry = TaskRuntimeRegistry()
    threads = []

    class DeferredThread:
        def __init__(self, target, args):
            self.target = target
            self.args = args
            self.daemon = False
            threads.append(self)

        def start(self):
            pass

    monkeypatch.setattr(task_executor_module, "task_runtime", registry)
    monkeypatch.setattr(task_executor_module, "Thread", DeferredThread)
    executor = TaskExecutor(pipeline_factory=FakePipeline)

    assert executor.resume_task("completed") == "already_completed"
    assert executor.resume_task("missing") == "not_recoverable"
    assert executor.resume_task("empty") == "not_recoverable"
    assert executor.resume_task("recoverable") == "started"
    assert executor.resume_task("recoverable") == "already_running"
    assert len(threads) == 1
    assert threads[0].daemon
