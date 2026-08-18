import wave

from src.draft import voice_preview
from src.draft.voice_preview import PRESET_VOICE_PREVIEW_TEXT, VoicePreviewService


def test_preset_preview_is_cached_per_voice_and_tts_options(tmp_path, monkeypatch):
    calls = []

    class FakeGenerator:
        def __init__(self, output_dir, **_kwargs):
            self.output_dir = tmp_path / "data" / "media" / "_voice_previews"

        def generate(self, text, filename, **kwargs):
            calls.append({"text": text, "filename": filename, **kwargs})
            target = self.output_dir / f"{filename}.wav"
            with wave.open(str(target), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(24000)
                output.writeframes(b"\x01\x00" * 2400)
            return str(target)

    monkeypatch.setattr(voice_preview, "VoiceOverGenerator", FakeGenerator)
    service = VoicePreviewService(
        base_dir=tmp_path,
        tts_config={
            "provider": "mimo",
            "mimo": {"speed_level": "fast", "style_prompt": "激动"},
        },
    )

    first = service.generate(
        "mimo:冰糖",
        "用户传入的文案",
        {"speed_level": "very_fast", "style_prompt": "夸张"},
    )
    second = service.generate(
        "mimo:冰糖",
        "另一段文案",
        {"speed_level": "very_fast", "style_prompt": "夸张"},
    )
    slower = service.generate(
        "mimo:冰糖",
        "仍然使用固定试听文案",
        {"speed_level": "slow", "style_prompt": "沉稳"},
    )

    assert first["url"] == second["url"]
    assert slower["url"] != first["url"]
    assert first["cached"] is False
    assert second["cached"] is True
    assert slower["cached"] is False
    assert len(calls) == 2
    assert calls[0]["text"] == PRESET_VOICE_PREVIEW_TEXT
    assert calls[0]["speed_level"] == "very_fast"
    assert calls[0]["style_prompt"] == "夸张"
    assert calls[1]["speed_level"] == "slow"
    assert calls[1]["style_prompt"] == "沉稳"
