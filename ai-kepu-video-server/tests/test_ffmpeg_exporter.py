import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.export.ffmpeg_exporter import FFmpegExporter


class TestFFmpegExporter(unittest.TestCase):
    def test_segment_clip_filter_covers_canvas_without_black_padding(self):
        exporter = FFmpegExporter(canvas={"width": 1920, "height": 1080, "fps": 30})
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd

            class Result:
                returncode = 0
                stderr = ""

            return Result()

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "image.png"
            audio_path = Path(tmp_dir) / "audio.wav"
            image_path.write_bytes(b"png")
            audio_path.write_bytes(b"wav")

            with patch("src.export.ffmpeg_exporter.subprocess.run", fake_run), patch.object(
                exporter, "_get_wav_duration_us", return_value=4_000_000
            ):
                output_path = exporter._build_segment_clip(
                    index=0,
                    image_path=str(image_path),
                    audio_path=str(audio_path),
                    text="测试字幕",
                    anim_type=0,
                    scale_end=1.05,
                    tmp_dir=tmp_dir,
                )

        vf = captured["cmd"][captured["cmd"].index("-vf") + 1]
        self.assertEqual(Path(output_path).name, "seg_0000.mp4")
        self.assertIn("force_original_aspect_ratio=increase", vf)
        self.assertIn("crop=", vf)
        self.assertNotIn("pad=", vf)
        self.assertNotIn(":black", vf)
        self.assertNotIn("fade=t=in", vf)
        self.assertNotIn("-af", captured["cmd"])
        self.assertNotIn("highpass", " ".join(captured["cmd"]))
        self.assertNotIn("afftdn", " ".join(captured["cmd"]))

    def test_render_config_versions_audio_pipeline_for_cache_invalidation(self):
        config = FFmpegExporter.get_render_config(canvas={"width": 1920, "height": 1080, "fps": 30})

        self.assertGreaterEqual(config["pipeline_version"], 2)
