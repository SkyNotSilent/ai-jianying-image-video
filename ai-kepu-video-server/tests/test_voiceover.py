import base64
import logging
import wave
from pathlib import Path

import pytest

from src.draft.voice_preview import VoicePreviewService
from src.draft.voiceover import VoiceOverGenerator


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def wav_bytes(seconds=0.05, sample_rate=24000):
    import io

    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x01\x00" * int(seconds * sample_rate))
    return target.getvalue()


@pytest.fixture
def tts_config():
    return {
        "provider": "doubao",
        "enabled_providers": ["doubao", "mimo"],
        "auth_method": "api_key",
        "api_url": "https://doubao.invalid/tts",
        "api_key": "doubao-key",
        "cluster": "volcano_tts",
        "default_voice": "zh_male_yangguangxiaolei_moon_bigtts",
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


def test_routes_doubao_per_call_and_maps_speed_volume(tmp_path, monkeypatch, tts_config):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse({"code": 3000, "data": base64.b64encode(wav_bytes()).decode()})

    monkeypatch.setattr("src.draft.voiceover.requests.post", fake_post)
    generator = VoiceOverGenerator(str(tmp_path), tts_config=tts_config)

    result = generator.generate(
        "测试语音",
        filename="doubao",
        voice_type="doubao:zh_female_shuangkuaisisi_moon_bigtts",
        speed_level="very_fast",
        volume_ratio=1.8,
    )

    assert Path(result).exists()
    assert captured["url"] == "https://doubao.invalid/tts"
    assert captured["json"]["audio"] == {
        "voice_type": "zh_female_shuangkuaisisi_moon_bigtts",
        "encoding": "wav",
        "rate": 24000,
        "speed_ratio": 1.75,
        "volume_ratio": 1.8,
    }


def test_routes_mimo_and_combines_style_with_speed_instruction(tmp_path, monkeypatch, tts_config):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        audio = base64.b64encode(wav_bytes()).decode()
        return FakeResponse({"choices": [{"message": {"audio": {"data": audio}}}]})

    monkeypatch.setattr("src.draft.voiceover.requests.post", fake_post)
    generator = VoiceOverGenerator(str(tmp_path), tts_config=tts_config)
    generator.generate(
        "一段中文",
        filename="mimo",
        voice_type="mimo:茉莉",
        speed_level="slow",
        style_prompt="温柔有感情",
    )

    payload = captured["json"]
    assert captured["url"] == "https://mimo.invalid/v1/chat/completions"
    assert payload["model"] == "mimo-v2.5-tts"
    assert payload["audio"]["voice"] == "茉莉"
    assert payload["messages"][0]["role"] == "user"
    assert "温柔有感情" in payload["messages"][0]["content"]
    assert "语速偏慢" in payload["messages"][0]["content"]


def test_clone_uses_clone_model_and_in_memory_reference_without_logging_it(
    tmp_path, monkeypatch, tts_config, caplog
):
    captured = {}
    secret_data_url = "data:audio/wav;base64,DO_NOT_LOG_THIS_REFERENCE"

    class FakeCloneStore:
        def reference_data_url(self, clone_id):
            assert clone_id == "abc123"
            return secret_data_url

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        audio = base64.b64encode(wav_bytes()).decode()
        return FakeResponse({"choices": [{"message": {"audio": {"data": audio}}}]})

    monkeypatch.setattr("src.draft.voiceover.requests.post", fake_post)
    generator = VoiceOverGenerator(
        str(tmp_path), tts_config=tts_config, clone_store=FakeCloneStore()
    )
    with caplog.at_level(logging.DEBUG):
        generator.generate(
            "克隆试听", filename="clone", voice_type="mimo-clone:abc123"
        )

    payload = captured["json"]
    assert payload["model"] == "mimo-v2.5-tts-voiceclone"
    assert payload["audio"]["voice"] == secret_data_url
    assert secret_data_url not in caplog.text
    assert "DO_NOT_LOG_THIS_REFERENCE" not in caplog.text


def test_preview_cache_reuses_identical_input_and_invalidates_changes(
    tmp_path, monkeypatch, tts_config
):
    calls = []

    def fake_generate(self, text, filename=None, **kwargs):
        calls.append({"text": text, "filename": filename, **kwargs})
        target = self.output_dir / f"{filename}.wav"
        target.write_bytes(wav_bytes())
        return str(target)

    monkeypatch.setattr(VoiceOverGenerator, "generate", fake_generate)
    service = VoicePreviewService(base_dir=tmp_path, tts_config=tts_config)

    first = service.generate("mimo:冰糖", "你好", {"speed_level": "normal"})
    second = service.generate("mimo:冰糖", "你好", {"speed_level": "normal"})
    changed_text = service.generate("mimo:冰糖", "你好呀", {"speed_level": "normal"})
    changed_voice = service.generate("mimo:茉莉", "你好", {"speed_level": "normal"})
    changed_options = service.generate("mimo:冰糖", "你好", {"speed_level": "fast"})
    changed_model = service.generate(
        "mimo:冰糖",
        "你好",
        {"speed_level": "normal"},
        config_override={"mimo": {**tts_config["mimo"], "model": "mimo-next"}},
    )

    assert first["cached"] is False
    assert second == {**first, "cached": True}
    assert len(calls) == 5
    assert len({
        first["path"], changed_text["path"], changed_voice["path"],
        changed_options["path"], changed_model["path"],
    }) == 5
    assert first["url"].startswith("/media/_voice_previews/")
