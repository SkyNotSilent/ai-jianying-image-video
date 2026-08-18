import asyncio
import io
import json
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from src.api import routes
from src.api.models import RegenerateAudioRequest, TTSOptions
from src.api.task_manager import TaskManager
from src.database import sqlite_client as sqlite_client_module
from src.database.sqlite_client import SQLiteClient
from src.draft.voice_preview import PRESET_VOICE_PREVIEW_TEXT


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", tmp_path / "local.db")
    return SQLiteClient()


@pytest.fixture
def tts_config():
    return {
        "provider": "mimo",
        "enabled_providers": ["doubao", "mimo"],
        "preview_text": "这是试听。",
        "auth_method": "api_key",
        "api_url": "https://doubao.invalid/tts",
        "api_key": "doubao-key",
        "cluster": "volcano_tts",
        "default_voice": "zh_male_jieshuoxiaoming_moon_bigtts",
        "speed_level": "normal",
        "volume_ratio": 1.0,
        "mimo": {
            "base_url": "https://mimo.invalid/v1",
            "api_key": "mimo-key",
            "model": "mimo-v2.5-tts",
            "clone_model": "mimo-v2.5-tts-voiceclone",
            "default_voice": "冰糖",
            "format": "wav",
            "style_prompt": "自然清晰",
            "speed_level": "normal",
        },
    }


def wav_bytes(seconds=0.05):
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(b"\x01\x00" * int(seconds * 24000))
    return target.getvalue()


def test_tts_models_validate_five_speed_levels_and_provider_fields():
    options = TTSOptions(speed_level="fast", volume_ratio=1.8, style_prompt="有感情")
    assert options.speed_level == "fast"
    assert options.volume_ratio == 1.8
    with pytest.raises(Exception):
        TTSOptions(speed_level="impossible")
    with pytest.raises(Exception):
        TTSOptions(volume_ratio=3)


def test_catalog_endpoint_filters_providers_and_bulk_availability(
    temp_db, monkeypatch, tts_config
):
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.Config, "tts_config", classmethod(lambda cls: tts_config))

    mimo = asyncio.run(routes.get_voices(provider="mimo", include_disabled=True))
    assert len([voice for voice in mimo if voice["kind"] == "preset"]) == 9
    assert all(voice["provider"] == "mimo" for voice in mimo)

    result = asyncio.run(
        routes.update_voice_availability(
            {"voice_keys": ["mimo:茉莉", "doubao:zh_male_jieshuoxiaoming_moon_bigtts"]}
        )
    )
    assert result["enabled_voice_keys"] == [
        "doubao:zh_male_jieshuoxiaoming_moon_bigtts",
        "mimo:茉莉",
    ]
    enabled = asyncio.run(routes.get_voices(provider=None, include_disabled=False))
    assert {voice["id"] for voice in enabled} == set(result["enabled_voice_keys"])


def test_preset_preview_endpoint_uses_fixed_copy_and_options(tmp_path, temp_db, monkeypatch, tts_config):
    captured = {}

    class FakePreviewService:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def generate(self, voice_type, text, tts_options, config_override=None):
            captured.update({
                "voice_type": voice_type,
                "text": text,
                "tts_options": tts_options,
                "config_override": config_override,
            })
            return {"url": "/media/_voice_previews/one.wav", "path": str(tmp_path / "one.wav"), "cached": False}

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes, "VoicePreviewService", FakePreviewService)
    monkeypatch.setattr(routes.Config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(routes.Config, "tts_config", classmethod(lambda cls: tts_config))

    result = asyncio.run(
        routes.preview_voice(
            {
                "voice_type": "mimo:冰糖",
                "text": "未保存配置试听",
                "tts_options": {"speed_level": "slow"},
                "config_override": {"mimo": {"style_prompt": "轻松"}},
            }
        )
    )
    assert result["url"].endswith("one.wav")
    assert captured["text"] == PRESET_VOICE_PREVIEW_TEXT
    assert captured["tts_options"] == {"speed_level": "slow"}
    assert captured["config_override"] == {"mimo": {"style_prompt": "轻松"}}


def test_confirming_voice_does_not_rewrite_legacy_single_value_style(temp_db, monkeypatch):
    temp_db.create_task(
        "legacy-style-task",
        "原始文案",
        "cinematic",
        200,
        execution_mode="review_first",
        script_policy="verbatim",
    )
    temp_db.save_segments(
        "legacy-style-task",
        [{"segment_index": 0, "text": "第一段", "image_prompt": "已有提示词"}],
    )
    temp_db.update_task_workflow(
        "legacy-style-task", "awaiting_confirmation", status="awaiting_confirmation"
    )
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_manager, "invalidate_task_cache", lambda _task_id: None)

    result = asyncio.run(
        routes.update_task_workspace_settings(
            "legacy-style-task",
            {
                "voice_type": "mimo:冰糖",
                "tts_options": {"speed_level": "normal"},
                "voice_confirmed": True,
                "expected_plan_version": 0,
            },
        )
    )

    task = temp_db.get_task("legacy-style-task")
    segment = temp_db.get_segments("legacy-style-task")[0]
    assert result["stage"] != "planning"
    assert task["style"] == "cinematic"
    assert segment["image_prompt"] == "已有提示词"
    assert segment["prompt_status"] == "completed"


def test_workspace_reports_progressive_planning_step_and_prompt_counts(
    temp_db, monkeypatch
):
    temp_db.create_task(
        "planning-task",
        "原始主题",
        "知识科普|电影质感",
        200,
        execution_mode="review_first",
    )
    temp_db.update_task_status("planning-task", "processing", "text_generation")
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_manager, "fail_stale_task_data", lambda _row: False)
    request = Request({
        "type": "http",
        "scheme": "http",
        "server": ("testserver", 80),
        "path": "/workspace",
        "headers": [],
    })

    text_stage = asyncio.run(routes.get_task_workspace("planning-task", request))
    assert text_stage["planning_step"] == "text_generation"
    assert text_stage["script_text"] == ""
    assert text_stage["progress"]["prompts_total"] == 0

    temp_db.save_task_checkpoint(
        "planning-task", script_text="完整文案", summary="摘要", input_mode="theme"
    )
    temp_db.save_segments(
        "planning-task",
        [
            {"segment_index": 0, "text": "第一段", "image_prompt": "prompt", "prompt_status": "completed"},
            {"segment_index": 1, "text": "第二段", "prompt_status": "processing"},
            {"segment_index": 2, "text": "第三段", "prompt_status": "failed", "prompt_error": "failed"},
        ],
    )
    temp_db.update_task_status(
        "planning-task", "processing", "image_prompt_generation"
    )

    prompt_stage = asyncio.run(routes.get_task_workspace("planning-task", request))
    assert prompt_stage["planning_step"] == "image_prompt_generation"
    assert prompt_stage["script_text"] == "完整文案"
    assert prompt_stage["progress"] == {
        "prompts_ready": 1,
        "prompts_total": 3,
        "prompts_processing": 1,
        "prompts_failed": 1,
        "images_ready": 0,
        "audio_ready": 0,
    }
    assert prompt_stage["voice_confirmed"] is False


@pytest.mark.parametrize(
    ("task_id", "workflow_phase", "current_step", "with_segments"),
    [
        ("asset-interrupted", "generating_assets", "image_generation", True),
        ("text-interrupted", "planning", "text_generation", False),
    ],
)
def test_workspace_interruption_overrides_stale_workflow_phase_and_can_resume(
    temp_db,
    monkeypatch,
    task_id,
    workflow_phase,
    current_step,
    with_segments,
):
    temp_db.create_task(
        task_id,
        "原始主题",
        "知识科普|电影质感",
        200,
        execution_mode="review_first",
    )
    if with_segments:
        temp_db.save_segments(
            task_id,
            [{"segment_index": 0, "text": "第一段", "image_prompt": "prompt"}],
        )
    temp_db.update_task_workflow(
        task_id,
        workflow_phase,
        status="interrupted",
        current_step=current_step,
    )
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_manager, "fail_stale_task_data", lambda _row: False)
    request = Request({
        "type": "http",
        "scheme": "http",
        "server": ("testserver", 80),
        "path": "/workspace",
        "headers": [],
    })

    workspace = asyncio.run(routes.get_task_workspace(task_id, request))

    assert workspace["stage"] == "interrupted"
    assert workspace["planning_step"] is None
    assert workspace["can_resume"] is True


def test_workspace_reports_recovery_and_delivery_capabilities_from_real_files(
    tmp_path, temp_db, monkeypatch
):
    image = tmp_path / "segment.png"
    audio = tmp_path / "segment.wav"
    draft = tmp_path / "draft"
    audio.write_bytes(b"audio")
    draft.mkdir()
    temp_db.create_task(
        "asset-health",
        "原始主题",
        "知识科普|电影质感",
        200,
        execution_mode="review_first",
    )
    temp_db.save_task_checkpoint(
        "asset-health",
        script_text="第一段",
        summary="摘要",
        input_mode="theme",
        workflow_phase="ready",
        voice_confirmed=1,
    )
    temp_db.save_segments(
        "asset-health",
        [{
            "segment_index": 0,
            "text": "第一段",
            "image_prompt": "prompt",
            "image_path": str(image),
            "image_url": "http://testserver/files/segment.png",
            "image_status": "completed",
            "audio_path": str(audio),
            "audio_url": "http://testserver/files/segment.wav",
            "audio_status": "completed",
        }],
    )
    temp_db.save_task_result("asset-health", str(draft), 1)
    temp_db.update_task_workflow(
        "asset-health", "ready", status="completed", current_step="completed"
    )
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_manager, "invalidate_task_cache", lambda _task_id: None)
    monkeypatch.setattr(routes.task_manager, "fail_stale_task_data", lambda _row: False)
    request = Request({
        "type": "http",
        "scheme": "http",
        "server": ("testserver", 80),
        "path": "/workspace",
        "headers": [],
    })

    missing_image = asyncio.run(routes.get_task_workspace("asset-health", request))

    assert missing_image["stage"] == "interrupted"
    assert missing_image["segments"][0]["image_status"] == "failed"
    assert missing_image["health"]["missing_images"] == 1
    assert missing_image["recovery"]["mode"] == "retry_assets"
    assert missing_image["capabilities"] == {
        "instant_preview": False,
        "full_video": False,
        "enter_export": True,
        "material_export": True,
    }
    assert temp_db.get_task("asset-health")["status"] == "interrupted"

    image.write_bytes(b"image")
    temp_db.update_task_workflow(
        "asset-health", "generating_assets", status="interrupted", current_step="draft_building"
    )
    draft.rmdir()

    assets_complete = asyncio.run(routes.get_task_workspace("asset-health", request))

    assert assets_complete["health"]["assets_complete"] is True
    assert assets_complete["recovery"]["mode"] == "finalize"
    assert assets_complete["capabilities"]["enter_export"] is True
    assert assets_complete["capabilities"]["full_video"] is False


def test_resegment_moves_task_to_planning_before_resuming(temp_db, monkeypatch):
    temp_db.create_task(
        "resegment-state",
        "原始主题",
        "知识科普|电影质感",
        200,
        execution_mode="review_first",
    )
    temp_db.save_task_checkpoint(
        "resegment-state",
        script_text="第一句。第二句。",
        workflow_phase="awaiting_confirmation",
    )
    temp_db.save_segments(
        "resegment-state",
        [{"segment_index": 0, "text": "旧分镜", "image_prompt": "old"}],
    )
    temp_db.update_task_workflow(
        "resegment-state",
        "awaiting_confirmation",
        status="awaiting_confirmation",
        current_step="awaiting_confirmation",
    )
    observed = {}
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.task_manager, "invalidate_task_cache", lambda _task_id: None)

    def resume(task_id):
        observed.update(temp_db.get_task(task_id))
        return "started"

    monkeypatch.setattr(routes.task_executor, "resume_task", resume)

    result = asyncio.run(routes.resegment_task_workspace(
        "resegment-state",
        {"script_text": "第一句。第二句。", "expected_plan_version": 0},
    ))

    assert result["outcome"] == "started"
    assert observed["status"] == "interrupted"
    assert observed["workflow_phase"] == "planning"
    assert observed["current_step"] == "image_prompt_generation"


def test_new_task_accepts_known_preset_even_when_legacy_checkmark_is_off(
    temp_db, monkeypatch, tts_config
):
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.Config, "tts_config", classmethod(lambda cls: tts_config))

    voice_key = "doubao:zh_male_chenwendongge_moon_bigtts"
    assert temp_db.find_tts_voice("doubao", "zh_male_chenwendongge_moon_bigtts")["is_enabled"] is False
    assert routes._resolve_new_task_voice(voice_key) == voice_key


def test_preview_reports_provider_authorization_instead_of_generic_failure(
    tmp_path, temp_db, monkeypatch, tts_config
):
    class ForbiddenPreviewService:
        def __init__(self, **_kwargs):
            pass

        def generate(self, *_args, **_kwargs):
            error = RuntimeError("forbidden")
            error.response = SimpleNamespace(status_code=403)
            raise error

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes, "VoicePreviewService", ForbiddenPreviewService)
    monkeypatch.setattr(routes.Config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(routes.Config, "tts_config", classmethod(lambda cls: tts_config))

    with pytest.raises(HTTPException) as caught:
        asyncio.run(routes.preview_voice({"voice_type": "doubao:missing-permission"}))
    assert caught.value.status_code == 409
    assert "未授权该音色" in caught.value.detail


def test_clone_multipart_lifecycle_requires_preview_before_enable(
    tmp_path, temp_db, monkeypatch, tts_config
):
    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes.Config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(routes.Config, "tts_config", classmethod(lambda cls: tts_config))
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(wav_bytes()))

    created = asyncio.run(routes.create_voice_clone("Creator", True, upload))
    clone_id = created["clone_id"]
    assert created["status"] == "draft"
    with pytest.raises(HTTPException, match="试听"):
        asyncio.run(routes.update_voice_clone(clone_id, {"is_enabled": True}))

    class FakePreviewService:
        def __init__(self, **kwargs):
            self.root = tmp_path / "data" / "media" / "_voice_previews"
            self.root.mkdir(parents=True, exist_ok=True)

        def generate(self, *args, **kwargs):
            path = self.root / "clone.wav"
            path.write_bytes(wav_bytes())
            return {"url": "/media/_voice_previews/clone.wav", "path": str(path), "cached": False}

    monkeypatch.setattr(routes, "VoicePreviewService", FakePreviewService)
    ready = asyncio.run(routes.preview_voice_clone(clone_id, {"text": "这是我的声音"}))
    assert ready["clone"]["status"] == "ready"

    enabled = asyncio.run(routes.update_voice_clone(clone_id, {"is_enabled": True}))
    assert enabled["is_enabled"] is True
    renamed = asyncio.run(routes.update_voice_clone(clone_id, {"name": "Creator 2"}))
    assert renamed["name"] == "Creator 2"

    deleted = asyncio.run(routes.delete_voice_clone(clone_id))
    assert deleted["outcome"] == "deleted"


def test_task_manager_persists_voice_and_tts_option_snapshot(
    temp_db, monkeypatch
):
    from src.api import task_manager as task_manager_module

    monkeypatch.setattr(task_manager_module, "db_client", temp_db)
    manager = TaskManager()
    task_id = manager.create_task(
        "文案",
        "知识科普",
        100,
        voice_type="mimo:冰糖",
        tts_options={"speed_level": "slow", "style_prompt": "平静"},
    )

    row = temp_db.get_task(task_id)
    assert row["voice_type"] == "mimo:冰糖"
    assert json.loads(row["tts_options_json"]) == {
        "speed_level": "slow",
        "style_prompt": "平静",
    }
    assert manager.get_task(task_id).to_response().tts_options.speed_level == "slow"


def test_segment_audio_snapshot_columns_round_trip(temp_db):
    temp_db.create_task(
        "task-1",
        "文案",
        "知识科普",
        100,
        voice_type="mimo:冰糖",
        tts_options={"speed_level": "normal"},
    )
    temp_db.save_segments("task-1", [{"segment_index": 0, "text": "第一段"}])
    assert temp_db.update_segment(
        "task-1",
        0,
        {
            "audio_voice_type": "doubao:zh_male_jieshuoxiaoming_moon_bigtts",
            "audio_tts_options_json": json.dumps({"speed_level": "fast"}),
        },
    )
    segment = temp_db.get_segments("task-1")[0]
    assert segment["audio_voice_type"].startswith("doubao:")
    assert json.loads(segment["audio_tts_options_json"])["speed_level"] == "fast"


def test_regenerate_audio_request_keeps_query_compatibility_shape():
    body = RegenerateAudioRequest(
        voice_type="mimo:茉莉",
        tts_options=TTSOptions(speed_level="very_slow"),
    )
    assert body.voice_type == "mimo:茉莉"
    assert body.tts_options.speed_level == "very_slow"


def test_regenerate_audio_accepts_legacy_query_and_saves_segment_snapshot(
    tmp_path, temp_db, monkeypatch, tts_config
):
    from src.core import pipeline as pipeline_module
    from src.utils import local_uploader as uploader_module

    temp_db.create_task(
        "task-query",
        "文案",
        "知识科普",
        100,
        ratio="16:9",
        voice_type="mimo:冰糖",
        tts_options={"speed_level": "slow", "style_prompt": "平静"},
    )
    temp_db.save_segments(
        "task-query",
        [{
            "segment_index": 4,
            "text": "这是第一段",
            "audio_status": "failed",
            "audio_error": "previous failure",
        }],
    )
    task = SimpleNamespace(
        task_id="task-query",
        theme="文案",
        ratio="16:9",
        voice_type="mimo:冰糖",
        tts_options={"speed_level": "slow", "style_prompt": "平静"},
        result=None,
    )
    captured = {}

    class FakeGenerator:
        def generate(self, text, filename=None, **kwargs):
            captured.update({"text": text, "filename": filename, **kwargs})
            target = tmp_path / f"{filename}.wav"
            target.write_bytes(wav_bytes())
            return str(target)

    class FakePipeline:
        def __init__(self, **kwargs):
            self.voiceover_generator = FakeGenerator()

    class FakeUploader:
        def upload(self, path, storage_path):
            return f"/media/{storage_path}"

    monkeypatch.setattr(routes, "mysql_client", temp_db)
    monkeypatch.setattr(routes, "task_manager", SimpleNamespace(get_task=lambda _task_id: task))
    monkeypatch.setattr(routes.Config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(routes.Config, "tts_config", classmethod(lambda cls: tts_config))
    monkeypatch.setattr(pipeline_module, "VideoEditorPipeline", FakePipeline)
    monkeypatch.setattr(uploader_module, "LocalUploader", FakeUploader)

    result = asyncio.run(
        routes.regenerate_audio(
            "task-query",
            4,
            payload=None,
            voice_type="doubao:zh_male_jieshuoxiaoming_moon_bigtts",
        )
    )

    assert result["voice_type"].startswith("doubao:")
    assert captured["voice_type"] == result["voice_type"]
    assert captured["speed_level"] == "slow"
    segment = temp_db.get_segments("task-query")[0]
    assert segment["audio_voice_type"] == result["voice_type"]
    assert json.loads(segment["audio_tts_options_json"])["volume_ratio"] == 1.0
    assert segment["audio_status"] == "completed"
    assert segment["audio_error"] is None


def test_workspace_mutations_are_rejected_while_generation_is_running(
    temp_db, monkeypatch
):
    temp_db.create_task(
        "running-task",
        "文案",
        "知识科普|电影质感",
        100,
        execution_mode="review_first",
    )
    temp_db.update_task_workflow(
        "running-task", "planning", status="processing", current_step="text_generation"
    )
    monkeypatch.setattr(routes, "mysql_client", temp_db)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes.update_task_workspace_settings(
            "running-task",
            {"voice_type": "mimo:冰糖", "voice_confirmed": True},
        ))

    assert exc_info.value.status_code == 409
    assert "正在生成" in exc_info.value.detail
