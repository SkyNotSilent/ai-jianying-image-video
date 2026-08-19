import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from src.api import routes
from src.api import task_executor as task_executor_module
from src.api.task_executor import TaskExecutor
from src.database import sqlite_client as sqlite_client_module
from src.database.sqlite_client import SQLiteClient


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", tmp_path / "local.db")
    return SQLiteClient()


class CountingPromptAgent:
    def __init__(self, result="new prompt"):
        self.result = result
        self.calls = []

    def generate_prompt(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class ForbiddenGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("unexpected media generation")


class PromptOnlyPipeline:
    instances = []

    def __init__(self, **_kwargs):
        self.image_prompt_agent = CountingPromptAgent()
        self.image_generator = ForbiddenGenerator()
        self.voiceover_generator = ForbiddenGenerator()
        self.__class__.instances.append(self)


def _create_review_task(db, task_id, *, voice="mimo:冰糖"):
    db.create_task(
        task_id,
        "项目文案",
        "知识科普|电影质感",
        120,
        ratio="16:9",
        voice_type=voice,
        execution_mode="review_first",
    )
    db.save_task_checkpoint(
        task_id,
        script_text="第一段。第二段。第三段。",
        summary="全文摘要",
        workflow_phase="planning",
    )
    db.update_task_workflow(
        task_id,
        "planning",
        status="interrupted",
        current_step="image_prompt_generation",
    )


def _force_segment_timestamp(db, task_id, segment_index, value):
    conn = db._get_conn()
    try:
        conn.execute(
            "UPDATE task_segments SET updated_at=? WHERE task_id=? AND segment_index=?",
            (value, task_id, segment_index),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("target_has_image", "expected_image_status"),
    [(False, "pending"), (True, "stale")],
)
def test_single_prompt_regeneration_calls_only_one_llm_and_preserves_other_assets(
    tmp_path,
    temp_db,
    monkeypatch,
    target_has_image,
    expected_image_status,
):
    task_id = f"prompt-exact-{int(target_has_image)}"
    _create_review_task(temp_db, task_id)
    segment_rows = []
    file_signatures = {}
    for index in range(3):
        image = tmp_path / f"image-{index}.png"
        audio = tmp_path / f"audio-{index}.wav"
        if index != 1 or target_has_image:
            image.write_bytes(f"image-{index}".encode())
        audio.write_bytes(f"audio-{index}".encode())
        if image.exists():
            file_signatures[str(image)] = image.stat().st_mtime_ns
        file_signatures[str(audio)] = audio.stat().st_mtime_ns
        segment_rows.append(
            {
                "segment_index": index,
                "text": f"第 {index + 1} 段",
                "image_prompt": "" if index == 1 else f"prompt-{index}",
                "prompt_status": "failed" if index == 1 else "completed",
                "prompt_error": "old prompt failure" if index == 1 else None,
                "image_path": str(image) if image.exists() else None,
                "image_status": (
                    "failed" if index == 1 and not target_has_image else "completed"
                ),
                "audio_path": str(audio),
                "audio_status": "completed",
            }
        )
    temp_db.save_segments(task_id, segment_rows)
    _force_segment_timestamp(temp_db, task_id, 0, "2001-01-01 00:00:00")
    _force_segment_timestamp(temp_db, task_id, 2, "2001-01-03 00:00:00")
    before = {row["segment_index"]: row for row in temp_db.get_segments(task_id)}
    task_row = temp_db.get_task(task_id)
    target = {
        "segment_index": 1,
        "asset_type": "prompt",
        "mode": "regenerate",
        "status": "processing",
        "version": before[1]["updated_at"],
        "plan_version": int(task_row.get("plan_version") or 0),
        "origin_status": "interrupted",
        "origin_phase": "planning",
    }
    created = temp_db.create_task_operation(
        task_id,
        "regenerate_prompt",
        f"prompt-key-{target_has_image}",
        "snapshot",
        [target],
    )
    operation_id = created["operation"]["operation_id"]
    assert temp_db.start_task_operation(
        operation_id,
        task_id,
        operation_targets=[target],
        workflow_phase="planning",
        current_step="image_prompt_generation",
        mark_prompt_targets_processing=True,
    )

    PromptOnlyPipeline.instances.clear()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(task_executor_module, "db_client", temp_db)
    monkeypatch.setattr(task_executor_module.Config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        task_executor_module,
        "task_manager",
        SimpleNamespace(invalidate_task_cache=lambda _task_id: None),
    )
    executor = TaskExecutor(pipeline_factory=PromptOnlyPipeline)
    executor._run_prompt_regeneration(task_id, operation_id, target)

    pipeline = PromptOnlyPipeline.instances[-1]
    assert len(pipeline.image_prompt_agent.calls) == 1
    assert pipeline.image_prompt_agent.calls[0] == {
        "segment_text": "第 2 段",
        "summary": "全文摘要",
        "style": "电影质感",
        "aspect_ratio": "16:9",
    }
    assert pipeline.image_generator.calls == []
    assert pipeline.voiceover_generator.calls == []

    after = {row["segment_index"]: row for row in temp_db.get_segments(task_id)}
    assert after[1]["image_prompt"] == "new prompt"
    assert after[1]["prompt_status"] == "completed"
    assert after[1]["image_status"] == expected_image_status
    assert after[1]["audio_path"] == before[1]["audio_path"]
    for unaffected in (0, 2):
        assert after[unaffected]["image_path"] == before[unaffected]["image_path"]
        assert after[unaffected]["audio_path"] == before[unaffected]["audio_path"]
        assert after[unaffected]["updated_at"] == before[unaffected]["updated_at"]
    for path, mtime_ns in file_signatures.items():
        assert Path(path).stat().st_mtime_ns == mtime_ns
    operation = temp_db.get_task_operation(operation_id)
    assert operation["state"] == "completed"
    assert operation["completed_count"] == 1
    assert operation["failed_count"] == 0


def test_prompt_route_is_idempotent_and_conflicts_with_other_target(
    temp_db, monkeypatch
):
    _create_review_task(temp_db, "prompt-route")
    temp_db.save_segments(
        "prompt-route",
        [
            {
                "segment_index": index,
                "text": f"第 {index + 1} 段",
                "image_prompt": "",
                "prompt_status": "failed",
                "image_status": "failed",
                "audio_status": "pending",
            }
            for index in range(2)
        ],
    )
    starts = []

    def start_prompt(task_id, operation_id, target):
        starts.append((task_id, operation_id, target))
        return "started"

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_runtime, "is_running", lambda _task_id: False)
    monkeypatch.setattr(
        routes,
        "task_executor",
        SimpleNamespace(regenerate_prompt=start_prompt),
    )
    task_row = temp_db.get_task("prompt-route")
    segments = temp_db.get_segments("prompt-route")
    snapshot = routes._plan_fingerprint(task_row, segments)

    first_response = Response()
    first = asyncio.run(
        routes.regenerate_segment_prompt(
            "prompt-route", 0, first_response, {"snapshot_key": snapshot}
        )
    )
    duplicate_response = Response()
    duplicate = asyncio.run(
        routes.regenerate_segment_prompt(
            "prompt-route", 0, duplicate_response, {"snapshot_key": snapshot}
        )
    )

    assert first_response.status_code == 202
    assert duplicate_response.status_code == 200
    assert first["operation_id"] == duplicate["operation_id"]
    assert len(starts) == 1

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            routes.regenerate_segment_prompt(
                "prompt-route", 1, Response(), {"snapshot_key": snapshot}
            )
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "operation_running"

    with pytest.raises(HTTPException) as stale_exc:
        asyncio.run(
            routes.regenerate_segment_prompt(
                "prompt-route", 0, Response(), {"snapshot_key": "stale-snapshot"}
            )
        )
    assert stale_exc.value.status_code == 409
    assert stale_exc.value.detail["code"] == "conflict"
    assert len(starts) == 1


def test_orphaned_prompt_operation_becomes_retryable_without_touching_media(
    tmp_path, temp_db
):
    task_id = "prompt-orphan"
    _create_review_task(temp_db, task_id)
    image = tmp_path / "orphan-image.png"
    audio = tmp_path / "orphan-audio.wav"
    image.write_bytes(b"image")
    audio.write_bytes(b"audio")
    temp_db.save_segments(
        task_id,
        [{
            "segment_index": 0,
            "text": "中断分镜",
            "image_prompt": "old prompt",
            "prompt_status": "completed",
            "image_path": str(image),
            "image_status": "completed",
            "audio_path": str(audio),
            "audio_status": "completed",
        }],
    )
    target = {
        "segment_index": 0,
        "asset_type": "prompt",
        "mode": "regenerate",
        "status": "processing",
    }
    created = temp_db.create_task_operation(
        task_id,
        "regenerate_prompt",
        "orphan-prompt-key",
        "snapshot",
        [target],
    )
    operation_id = created["operation"]["operation_id"]
    assert temp_db.start_task_operation(
        operation_id,
        task_id,
        operation_targets=[target],
        workflow_phase="planning",
        current_step="image_prompt_generation",
        mark_prompt_targets_processing=True,
    )

    interrupted = temp_db.interrupt_orphaned_task_operation(task_id)

    assert interrupted["state"] == "interrupted"
    segment = temp_db.get_segments(task_id)[0]
    assert segment["prompt_status"] == "failed"
    assert segment["prompt_error"]
    assert segment["image_path"] == str(image)
    assert segment["audio_path"] == str(audio)
    assert image.read_bytes() == b"image"
    assert audio.read_bytes() == b"audio"


class VoiceRefreshGenerator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.calls = []

    def generate(self, text, filename=None, **kwargs):
        self.calls.append({"text": text, "filename": filename, **kwargs})
        path = self.output_dir / "audio" / f"{filename}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
        return str(path)


class VoiceRefreshPipeline:
    instances = []

    def __init__(self, output_dir, **_kwargs):
        self.image_generator = ForbiddenGenerator()
        self.voiceover_generator = VoiceRefreshGenerator(output_dir)
        self.__class__.instances.append(self)


class FakeUploader:
    def upload(self, _path, storage_path=None):
        return f"/media/{storage_path}"


def test_global_voice_refresh_excludes_segment_voice_override(
    tmp_path, temp_db, monkeypatch
):
    task_id = "voice-refresh"
    _create_review_task(temp_db, task_id, voice="mimo:冰糖")
    rows = []
    for index in range(3):
        image = tmp_path / f"voice-image-{index}.png"
        audio = tmp_path / f"voice-audio-{index}.wav"
        image.write_bytes(b"image")
        audio.write_bytes(f"old-{index}".encode())
        rows.append(
            {
                "segment_index": index,
                "text": f"第 {index + 1} 段",
                "image_prompt": f"prompt-{index}",
                "prompt_status": "completed",
                "image_path": str(image),
                "image_status": "completed",
                "audio_path": str(audio),
                "audio_status": "completed",
                "audio_voice_type": "mimo:茉莉" if index == 1 else "",
            }
        )
    temp_db.save_segments(task_id, rows)
    _force_segment_timestamp(temp_db, task_id, 1, "2002-02-02 00:00:00")
    override_before = temp_db.get_segments(task_id)[1]
    override_path = Path(override_before["audio_path"])
    override_mtime = override_path.stat().st_mtime_ns

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(
        routes,
        "task_manager",
        SimpleNamespace(invalidate_task_cache=lambda _task_id: None),
    )
    task_row = temp_db.get_task(task_id)
    updated = asyncio.run(
        routes.update_task_workspace_settings(
            task_id,
            {
                "voice_type": "mimo:苏打",
                "expected_plan_version": int(task_row.get("plan_version") or 0),
            },
        )
    )
    assert updated["plan_version"] == 1
    changed_segments = temp_db.get_segments(task_id)
    stale_targets = routes._workspace_stale_targets(changed_segments)
    assert [(item["segment_index"], item["asset_type"]) for item in stale_targets] == [
        (0, "audio"),
        (2, "audio"),
    ]
    resolved = routes._resolve_retry_targets(
        changed_segments, "selected", stale_targets
    )
    created = temp_db.create_task_operation(
        task_id,
        "retry_assets",
        "voice-refresh-key",
        updated["snapshot_key"],
        resolved,
    )
    operation_id = created["operation"]["operation_id"]
    processing = [{**item, "status": "processing"} for item in resolved]
    assert temp_db.start_task_operation(
        operation_id,
        task_id,
        operation_targets=processing,
        workflow_phase="repairing_assets",
        current_step="asset_repair",
        mark_asset_targets_processing=True,
    )

    VoiceRefreshPipeline.instances.clear()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(task_executor_module, "db_client", temp_db)
    monkeypatch.setattr(task_executor_module.Config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        task_executor_module,
        "task_manager",
        SimpleNamespace(invalidate_task_cache=lambda _task_id: None),
    )
    monkeypatch.setattr(task_executor_module, "LocalUploader", FakeUploader)
    monkeypatch.setattr(
        task_executor_module.Config,
        "generation_config",
        classmethod(
            lambda cls: {
                "image_concurrency": 1,
                "tts_concurrency": 2,
                "prompt_concurrency": 1,
            }
        ),
    )
    executor = TaskExecutor(pipeline_factory=VoiceRefreshPipeline)
    executor._run_asset_retry(task_id, operation_id, processing)

    pipeline = VoiceRefreshPipeline.instances[-1]
    assert pipeline.image_generator.calls == []
    assert len(pipeline.voiceover_generator.calls) == 2
    assert {call["text"] for call in pipeline.voiceover_generator.calls} == {
        "第 1 段",
        "第 3 段",
    }
    assert {call["voice_type"] for call in pipeline.voiceover_generator.calls} == {
        "mimo:苏打"
    }
    override_after = temp_db.get_segments(task_id)[1]
    assert override_after["audio_path"] == override_before["audio_path"]
    assert override_after["audio_voice_type"] == "mimo:茉莉"
    assert override_after["updated_at"] == override_before["updated_at"]
    assert override_path.stat().st_mtime_ns == override_mtime


def test_legacy_rebuild_delegates_to_force_finalize_operation(
    tmp_path, temp_db, monkeypatch
):
    task_id = "legacy-rebuild"
    _create_review_task(temp_db, task_id)
    image = tmp_path / "rebuild.png"
    audio = tmp_path / "rebuild.wav"
    draft = tmp_path / "old-draft"
    image.write_bytes(b"image")
    audio.write_bytes(b"audio")
    draft.mkdir()
    temp_db.save_segments(
        task_id,
        [{
            "segment_index": 0,
            "text": "唯一分镜",
            "image_prompt": "prompt",
            "prompt_status": "completed",
            "image_path": str(image),
            "image_status": "completed",
            "audio_path": str(audio),
            "audio_status": "completed",
        }],
    )
    temp_db.save_task_result(task_id, str(draft), 1)
    task = SimpleNamespace(task_id=task_id)
    starts = []

    def start_finalize(got_task_id, operation_id):
        starts.append((got_task_id, operation_id))
        return "started"

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(
        routes,
        "task_manager",
        SimpleNamespace(get_task=lambda _task_id: task),
    )
    monkeypatch.setattr(routes.task_runtime, "is_running", lambda _task_id: False)
    monkeypatch.setattr(
        routes,
        "task_executor",
        SimpleNamespace(finalize_task=start_finalize),
    )
    response = Response()
    result = asyncio.run(routes.rebuild_draft(task_id, response))
    duplicate_response = Response()
    duplicate = asyncio.run(routes.rebuild_draft(task_id, duplicate_response))

    assert response.status_code == 202
    assert duplicate_response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert result["kind"] == "finalize"
    assert result["targets"][0]["mode"] == "rebuild"
    assert duplicate["operation_id"] == result["operation_id"]
    assert len(starts) == 1


def test_legacy_regenerate_image_delegates_to_one_exact_asset_target(
    temp_db, monkeypatch
):
    task_id = "legacy-image"
    _create_review_task(temp_db, task_id)
    temp_db.save_segments(
        task_id,
        [{
            "segment_index": 3,
            "text": "需要重生图片",
            "image_prompt": "existing prompt",
            "prompt_status": "completed",
            "image_status": "failed",
            "audio_status": "pending",
        }],
    )
    starts = []

    def start_retry(got_task_id, operation_id, targets):
        starts.append((got_task_id, operation_id, targets))
        return "started"

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_runtime, "is_running", lambda _task_id: False)
    monkeypatch.setattr(
        routes,
        "task_executor",
        SimpleNamespace(retry_assets=start_retry),
    )
    response = Response()
    result = asyncio.run(routes.regenerate_image(task_id, 3, response))

    assert response.status_code == 202
    assert response.headers["deprecation"] == "true"
    assert result["kind"] == "retry_assets"
    assert len(starts) == 1
    assert starts[0][2] == [{
        "segment_index": 3,
        "asset_type": "image",
        "mode": "retry",
        "status": "pending",
        "error": None,
        "version": temp_db.get_segments(task_id)[0]["updated_at"],
    }]
