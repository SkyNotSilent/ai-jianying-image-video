import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.api import routes
from src.export import ffmpeg_exporter as ffmpeg_module
from src.utils import local_uploader as uploader_module


class FakeFFmpegExporter:
    calls = 0

    def __init__(self, **kwargs):
        pass

    @staticmethod
    def get_render_config(config_path="config/settings.json", canvas=None):
        return {"canvas": canvas or {}, "subtitle": {"font": "test"}, "fps": 30}

    def export(self, **kwargs):
        type(self).calls += 1
        output = Path(kwargs["output_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"mp4")


class FakeUploader:
    def upload(self, path, storage_path=None):
        return f"/media/{storage_path or Path(path).name}"


def test_mp4_render_is_reused_and_asset_replacement_makes_it_stale(tmp_path, monkeypatch):
    FakeFFmpegExporter.calls = 0
    draft = tmp_path / "draft"
    draft.mkdir()
    image = tmp_path / "image.png"
    image.write_bytes(b"image-v1")
    segments = [{
        "segment_index": 0,
        "text": "第一段",
        "image_path": str(image),
        "audio_path": None,
        "duration": 4,
    }]
    task = SimpleNamespace(
        task_id="task-1",
        ratio="16:9",
        theme="测试",
        result=SimpleNamespace(draft_path=str(draft), video_url=None, draft_url=None),
    )

    monkeypatch.setattr(ffmpeg_module, "FFmpegExporter", FakeFFmpegExporter)
    monkeypatch.setattr(uploader_module, "LocalUploader", FakeUploader)
    monkeypatch.setattr(routes.mysql_client, "get_task", lambda task_id: {"ratio": "16:9"})
    monkeypatch.setattr(routes.mysql_client, "get_segments", lambda task_id: segments)
    monkeypatch.setattr(routes, "_set_task_result_preserving", lambda *args, **kwargs: None)

    first = routes._export_mp4(task, segments, use_preview=True)
    second = routes._export_mp4(task, segments, use_preview=True)

    assert first["source"] == "rendered"
    assert second["source"] == "cached"
    assert FakeFFmpegExporter.calls == 1
    assert routes._preview_state(task, segments)["valid"] is True

    image.write_bytes(b"image-v2-is-different")
    stale = routes._preview_state(task, segments)
    assert stale["valid"] is False
    assert stale["reason"] == "stale"


def test_same_task_reuses_an_inflight_mp4_job():
    routes.EXPORT_JOBS.clear()
    first, first_created = routes._create_or_reuse_export_job("task-1", "mp4")
    second, second_created = routes._create_or_reuse_export_job("task-1", "mp4")

    assert first_created is True
    assert second_created is False
    assert second["job_id"] == first["job_id"]

    routes._update_export_job(first["job_id"], status="completed")
    third, third_created = routes._create_or_reuse_export_job("task-1", "mp4")
    assert third_created is True
    assert third["job_id"] != first["job_id"]


def test_cancel_pending_export_job_is_idempotent_and_worker_finishes_cancelled():
    routes.EXPORT_JOBS.clear()
    job = routes._create_export_job(
        "task-cancel",
        "mp4",
        {"auto_download": False},
    )

    requested = asyncio.run(
        routes.cancel_export_job("task-cancel", job["job_id"])
    )
    repeated = asyncio.run(
        routes.cancel_export_job("task-cancel", job["job_id"])
    )

    assert requested["cancel_requested"] is True
    assert requested["params"]["auto_download"] is False
    assert repeated["job_id"] == job["job_id"]
    routes._run_export_job(job["job_id"], "mp4", True, {})
    finished = routes._export_job_snapshot(job["job_id"])
    assert finished["status"] == "cancelled"
    assert finished["error"] is None
    assert finished["error_code"] == "cancelled"


def test_cancelled_mp4_render_keeps_previous_video(tmp_path, monkeypatch):
    from src.export import ffmpeg_exporter as ffmpeg_module

    draft = tmp_path / "draft"
    draft.mkdir()
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    task = SimpleNamespace(
        task_id="cancel-render",
        ratio="16:9",
        theme="测试",
        result=SimpleNamespace(draft_path=str(draft), video_url=None, draft_url=None),
    )
    previous = routes._official_video_path(task)
    previous.write_bytes(b"previous-valid-video")
    segments = [{
        "segment_index": 0,
        "text": "第一段",
        "image_path": str(image),
        "audio_path": None,
    }]

    class CancellingExporter(FakeFFmpegExporter):
        def export(self, **kwargs):
            Path(kwargs["output_path"]).write_bytes(b"partial-new-video")
            raise ffmpeg_module.RenderCancelled("cancelled")

    monkeypatch.setattr(ffmpeg_module, "FFmpegExporter", CancellingExporter)
    monkeypatch.setattr(routes.mysql_client, "get_task", lambda _task_id: {"ratio": "16:9"})
    monkeypatch.setattr(routes.mysql_client, "get_segments", lambda _task_id: segments)

    with pytest.raises(routes.ExportJobCancelled):
        routes._export_mp4(task, segments, use_preview=False)

    assert previous.read_bytes() == b"previous-valid-video"
    assert not list(draft.glob(".*.render.mp4"))


def test_preview_fingerprint_changes_when_plan_settings_make_media_stale(
    tmp_path, monkeypatch
):
    draft = tmp_path / "draft"
    draft.mkdir()
    image = tmp_path / "image.png"
    audio = tmp_path / "audio.wav"
    image.write_bytes(b"image")
    audio.write_bytes(b"audio")
    segments = [{
        "segment_index": 0,
        "text": "第一段",
        "image_prompt": "电影画面",
        "image_path": str(image),
        "image_status": "completed",
        "audio_path": str(audio),
        "audio_status": "completed",
        "audio_voice_type": "",
        "audio_tts_options_json": '{"speed_level":"normal"}',
    }]
    task = SimpleNamespace(
        task_id="plan-stale",
        ratio="16:9",
        theme="测试",
        result=SimpleNamespace(draft_path=str(draft), video_url=None, draft_url=None),
    )
    task_row = {
        "ratio": "16:9",
        "plan_version": 1,
        "style": "知识科普|电影质感",
        "voice_type": "mimo:冰糖",
        "tts_options_json": '{"speed_level":"normal"}',
    }
    monkeypatch.setattr(ffmpeg_module, "FFmpegExporter", FakeFFmpegExporter)
    monkeypatch.setattr(uploader_module, "LocalUploader", FakeUploader)
    monkeypatch.setattr(routes.mysql_client, "get_task", lambda _task_id: task_row)
    monkeypatch.setattr(routes.mysql_client, "get_segments", lambda _task_id: segments)
    monkeypatch.setattr(routes, "_set_task_result_preserving", lambda *args, **kwargs: None)

    routes._export_mp4(task, segments, use_preview=True)
    assert routes._preview_state(task, segments)["valid"] is True

    task_row.update({
        "plan_version": 2,
        "style": "知识科普|国风",
        "voice_type": "mimo:茉莉",
        "tts_options_json": '{"speed_level":"fast"}',
    })
    segments[0].update({
        "image_prompt": "国风画面",
        "image_status": "stale",
        "audio_status": "stale",
    })

    stale = routes._preview_state(task, segments)
    assert stale["valid"] is False
    assert stale["reason"] == "stale"
