from pathlib import Path
from types import SimpleNamespace

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
