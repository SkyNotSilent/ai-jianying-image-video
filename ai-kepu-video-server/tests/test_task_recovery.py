import sqlite3
import threading
from pathlib import Path

import pytest

from src.api import task_executor as task_executor_module
from src.api import task_manager as task_manager_module
from src.api.models import TaskStatus
from src.api.task_executor import TaskExecutor
from src.api.task_manager import Task, TaskManager
from src.api.task_runtime import TaskCancellation, TaskCancelled, TaskRuntimeRegistry
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
        self.on_generate = None
        self.cancel_indexes = set()

    def generate(self, value, **kwargs):
        index = kwargs.get("index")
        if index is None:
            index = int(kwargs["filename"].split("_")[-1])
        self.calls.append(index)
        if index in self.cancel_indexes:
            raise TaskCancelled(f"cancelled item {index}")
        if self.fail:
            raise RuntimeError(f"{self.suffix} failed")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"seg_{index:03d}.{self.suffix}"
        path.write_bytes(self.suffix.encode())
        if self.on_generate:
            self.on_generate(index)
        return str(path)


class FakeDraftBuilder:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def build(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return str(Path(kwargs["output_dir"]) / "draft")


class FakeUploader:
    def upload(self, path, storage_path=None):
        return f"/media/{storage_path or Path(path).name}"


class FakeFFmpegExporter:
    def __init__(self, **kwargs):
        pass

    def export(self, **kwargs):
        output_path = Path(kwargs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"mp4")


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


def test_segments_only_legacy_resume_reconstructs_script_without_rewrite(
    executor_db
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint("task-1", summary="已有摘要", input_mode="script")
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 4,
                "text": "第一段",
                "image_prompt": "提示一",
                "image_status": "pending",
                "audio_status": "pending",
            },
            {
                "segment_index": 8,
                "text": "第二段",
                "image_prompt": "提示二",
                "image_status": "pending",
                "audio_status": "pending",
            },
        ],
    )
    pipeline = FakePipeline(output_dir="unused", fail_assets=True)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    task = executor_db.get_task("task-1")
    assert pipeline.script_rewriter.calls == 0
    assert pipeline.text_segmenter.calls == 0
    assert pipeline.article == "第一段\n第二段"
    assert pipeline.summary == "已有摘要"
    assert task["script_text"] == "第一段\n第二段"
    assert task["summary"] == "已有摘要"


def test_dot_dot_project_name_stays_inside_task_output(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db)
    with executor_db.get_connection() as connection:
        connection.execute(
            "UPDATE tasks SET name='..' WHERE task_id='task-1'"
        )
    created = []

    def pipeline_factory(**kwargs):
        created.append(kwargs)
        return FakePipeline(kwargs["output_dir"], prompt_failure_call=1)

    monkeypatch.chdir(tmp_path)
    TaskExecutor(pipeline_factory=pipeline_factory).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    task_root = (tmp_path / "output" / "task-1").resolve()
    output_dir = Path(created[0]["output_dir"]).resolve()
    assert output_dir == task_root / "task"
    assert output_dir.is_relative_to(task_root)


def test_script_checkpoint_false_stops_before_segmentation(
    executor_db, monkeypatch
):
    create_task(executor_db)
    pipeline = FakePipeline(output_dir="unused", fail_assets=True)
    monkeypatch.setattr(executor_db, "save_task_checkpoint", lambda *a, **k: False)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.script_rewriter.calls == 1
    assert pipeline.text_segmenter.calls == 0
    assert pipeline.image_prompt_agent.calls == 0
    assert pipeline.image_generator.calls == []
    assert pipeline.voiceover_generator.calls == []


def test_initial_segments_checkpoint_false_stops_before_prompt_provider(
    executor_db, monkeypatch
):
    create_task(executor_db)
    pipeline = FakePipeline(output_dir="unused")
    pipeline.draft_builder = FakeDraftBuilder(RuntimeError("draft should not run"))
    monkeypatch.setattr(executor_db, "save_segments", lambda *a, **k: False)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.text_segmenter.calls == 1
    assert pipeline.image_prompt_agent.calls == 0
    assert pipeline.image_generator.calls == []
    assert pipeline.voiceover_generator.calls == []
    assert pipeline.draft_builder.calls == 0


def test_prompt_checkpoint_false_stops_before_next_prompt_and_assets(
    executor_db, monkeypatch
):
    create_task(executor_db)
    pipeline = FakePipeline(output_dir="unused", fail_assets=True)
    original_update = executor_db.update_segment

    def fail_prompt_checkpoint(task_id, segment_index, updates):
        if "image_prompt" in updates:
            return False
        return original_update(task_id, segment_index, updates)

    monkeypatch.setattr(executor_db, "update_segment", fail_prompt_checkpoint)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.image_prompt_agent.calls == 1
    assert pipeline.image_generator.calls == []
    assert pipeline.voiceover_generator.calls == []
    assert pipeline.draft_builder.calls == 0


def test_sparse_legacy_segment_indexes_are_used_for_db_rows_and_assets(
    executor_db
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 5,
                "text": "第五段",
                "image_prompt": "提示五",
                "image_status": "pending",
                "audio_status": "pending",
            },
            {
                "segment_index": 9,
                "text": "第九段",
                "image_prompt": "提示九",
                "image_status": "pending",
                "audio_status": "pending",
            },
        ],
    )
    pipeline = FakePipeline(output_dir="unused", fail_assets=True)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    rows = executor_db.get_segments("task-1")
    assets = executor_db.list_task_assets("task-1")
    assert [row["segment_index"] for row in rows] == [5, 9]
    assert all(row["image_status"] == "failed" for row in rows)
    assert all(row["audio_status"] == "failed" for row in rows)
    assert {asset["segment_index"] for asset in assets} == {5, 9}
    assert pipeline.image_generator.calls == [0, 1]
    assert pipeline.voiceover_generator.calls == [0, 1]


def test_stage_cancellation_drains_and_persists_all_submitted_assets(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": index,
                "text": f"第{index}段",
                "image_prompt": f"提示{index}",
                "image_status": "pending",
                "audio_status": "pending",
            }
            for index in range(2)
        ],
    )
    cancellation = TaskCancellation()
    pipeline = FakePipeline(output_dir=str(tmp_path / "generated"))
    image_calls_started = threading.Barrier(2)

    def cancel_after_both_image_calls_started(index):
        image_calls_started.wait(timeout=1)
        if index == 0:
            cancellation.cancel()

    pipeline.image_generator.on_generate = cancel_after_both_image_calls_started
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)
    monkeypatch.setattr(
        task_executor_module.Config,
        "generation_config",
        lambda: {"tts_concurrency": 2, "image_concurrency": 2},
    )

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=cancellation
    )

    rows = executor_db.get_segments("task-1")
    assets = executor_db.list_task_assets("task-1")
    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.draft_builder.calls == 0
    assert sorted(pipeline.image_generator.calls) == [0, 1]
    assert sorted(pipeline.voiceover_generator.calls) == [0, 1]
    assert all(row["image_status"] == "completed" for row in rows)
    assert all(row["audio_status"] == "completed" for row in rows)
    assert len(assets) == 4
    assert all(asset["status"] == "completed" for asset in assets)


def test_resume_processing_transition_clears_stale_task_error(
    executor_db, task_manager
):
    create_task(executor_db, status="interrupted")
    executor_db.update_task_status(
        "task-1", "interrupted", "image_prompt_generation", "旧任务错误"
    )

    task_manager.update_task_status("task-1", TaskStatus.PROCESSING)

    assert executor_db.get_task("task-1")["error"] is None


def test_explicit_none_clears_only_segment_error_columns(temp_db):
    create_task(temp_db)
    temp_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 0,
                "text": "第一段",
                "image_path": "keep.png",
                "image_error": "旧图片错误",
                "audio_error": "旧音频错误",
            }
        ],
    )

    assert temp_db.update_segment(
        "task-1",
        0,
        {"image_path": None, "image_error": None, "audio_error": None},
    )

    row = temp_db.get_segments("task-1")[0]
    assert row["image_path"] == "keep.png"
    assert row["image_error"] is None
    assert row["audio_error"] is None


def test_successful_retry_clears_segment_and_task_asset_errors(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "task-1",
        [
            {
                "segment_index": 0,
                "text": "第一段",
                "image_prompt": "提示词",
                "image_status": "failed",
                "image_error": "旧图片错误",
                "audio_status": "failed",
                "audio_error": "旧音频错误",
            }
        ],
    )
    executor_db.save_task_asset(
        "task-1",
        "image",
        "generated",
        segment_index=0,
        status="failed",
        error_message="旧图片错误",
    )
    executor_db.save_task_asset(
        "task-1",
        "audio",
        "generated",
        segment_index=0,
        status="failed",
        error_message="旧音频错误",
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "generated"))
    pipeline.draft_builder = FakeDraftBuilder(RuntimeError("stop after assets"))
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    row = executor_db.get_segments("task-1")[0]
    assets = executor_db.list_task_assets("task-1")
    assert row["image_status"] == "completed"
    assert row["audio_status"] == "completed"
    assert row["image_error"] is None
    assert row["audio_error"] is None
    assert len(assets) == 2
    assert all(asset["status"] == "completed" for asset in assets)
    assert all(asset["error_message"] is None for asset in assets)
    assert all(asset["path"] for asset in assets)


def test_asset_segment_row_false_interrupts_before_draft(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "task-1",
        [{
            "segment_index": 0,
            "text": "第一段",
            "image_prompt": "提示词",
            "image_status": "pending",
            "audio_status": "pending",
        }],
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "generated"))
    pipeline.draft_builder = FakeDraftBuilder(RuntimeError("draft reached"))
    original_update = executor_db.update_segment

    def fail_asset_row(task_id, segment_index, updates):
        if "image_path" in updates or "audio_path" in updates:
            return False
        return original_update(task_id, segment_index, updates)

    monkeypatch.setattr(executor_db, "update_segment", fail_asset_row)
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.draft_builder.calls == 0


def test_asset_record_falsey_interrupts_before_draft(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "task-1",
        [{
            "segment_index": 0,
            "text": "第一段",
            "image_prompt": "提示词",
            "image_status": "pending",
            "audio_status": "pending",
        }],
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "generated"))
    pipeline.draft_builder = FakeDraftBuilder(RuntimeError("draft reached"))
    monkeypatch.setattr(executor_db, "save_task_asset", lambda *a, **k: {})
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.draft_builder.calls == 0


def test_final_segments_save_false_prevents_result_and_completion(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    executor_db.save_segments(
        "task-1",
        [{
            "segment_index": 0,
            "text": "第一段",
            "image_prompt": "提示词",
            "image_status": "pending",
            "audio_status": "pending",
        }],
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "generated"))
    monkeypatch.setattr(executor_db, "save_segments", lambda *a, **k: False)
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)
    monkeypatch.setattr(task_executor_module, "FFmpegExporter", FakeFFmpegExporter)

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    task = executor_db.get_task("task-1")
    assert pipeline.draft_builder.calls == 1
    assert task["status"] == "interrupted"
    assert task.get("result") is None


def test_reused_valid_assets_clear_stale_segment_and_asset_errors(
    executor_db, tmp_path
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    image = tmp_path / "legacy" / "images" / "seg.png"
    audio = tmp_path / "legacy" / "voiceovers" / "seg.wav"
    image.parent.mkdir(parents=True)
    audio.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    audio.write_bytes(b"wav")
    executor_db.save_segments(
        "task-1",
        [{
            "segment_index": 7,
            "text": "已有分镜",
            "image_prompt": "已有提示词",
            "image_path": str(image),
            "image_status": "completed",
            "image_error": "旧图片错误",
            "audio_path": str(audio),
            "audio_status": "completed",
            "audio_error": "旧音频错误",
        }],
    )
    executor_db.save_task_asset(
        "task-1", "image", "generated", path=str(image), segment_index=7,
        status="completed", error_message="旧图片错误",
    )
    executor_db.save_task_asset(
        "task-1", "audio", "generated", path=str(audio), segment_index=7,
        status="completed", error_message="旧音频错误",
    )
    pipeline = FakePipeline(output_dir=str(tmp_path / "legacy"))
    pipeline.draft_builder = FakeDraftBuilder(RuntimeError("stop after reuse"))

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    row = executor_db.get_segments("task-1")[0]
    assets = executor_db.list_task_assets("task-1")
    assert pipeline.image_generator.calls == []
    assert pipeline.voiceover_generator.calls == []
    assert row["image_error"] is None
    assert row["audio_error"] is None
    assert len(assets) == 2
    assert all(asset["status"] == "completed" for asset in assets)
    assert all(asset["error_message"] is None for asset in assets)


def test_task_cancelled_future_does_not_drop_other_successful_result(
    executor_db, tmp_path, monkeypatch
):
    create_task(executor_db, status="interrupted")
    executor_db.save_task_checkpoint(
        "task-1", script_text="脚本", summary="摘要", input_mode="script"
    )
    segments = []
    for index in range(2):
        audio = tmp_path / "legacy" / "voiceovers" / f"seg_{index}.wav"
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"wav")
        segments.append({
            "segment_index": index,
            "text": f"第{index}段",
            "image_prompt": f"提示{index}",
            "image_status": "pending",
            "audio_path": str(audio),
            "audio_status": "completed",
        })
    executor_db.save_segments("task-1", segments)
    pipeline = FakePipeline(output_dir=str(tmp_path / "generated"))
    pipeline.image_generator.cancel_indexes = {0}
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)
    monkeypatch.setattr(
        task_executor_module.Config,
        "generation_config",
        lambda: {"tts_concurrency": 1, "image_concurrency": 1},
    )

    TaskExecutor(pipeline_factory=lambda **kwargs: pipeline).run_inline(
        "task-1", cancellation=TaskCancellation()
    )

    rows = executor_db.get_segments("task-1")
    image_assets = executor_db.list_task_assets("task-1", asset_type="image")
    assert pipeline.image_generator.calls == [0, 1]
    assert rows[0]["image_status"] == "pending"
    assert rows[1]["image_status"] == "completed"
    assert [asset["segment_index"] for asset in image_assets] == [1]
    assert executor_db.get_task("task-1")["status"] == "interrupted"
    assert pipeline.draft_builder.calls == 0
