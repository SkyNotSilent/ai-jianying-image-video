import json

from src.config import Config


def test_old_mimo_config_is_inferred_without_losing_credentials():
    config = {
        "llm": {
            "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
            "api_key": "secret",
            "model": "mimo-v2.5-pro",
            "protocol": "openai",
        }
    }

    Config._normalize_llm_config(config)

    assert config["llm"]["provider"] == "mimo"
    assert config["llm"]["model"] == "openai/mimo-v2.5-pro"
    assert config["llm"]["api_key"] == "secret"


def test_unknown_legacy_endpoint_falls_back_to_custom():
    config = {
        "llm": {
            "base_url": "https://private.test/v1",
            "api_key": "key",
            "model": "private-model",
            "protocol": "anthropic",
        }
    }

    Config._normalize_llm_config(config)

    assert config["llm"]["provider"] == "custom"
    assert config["llm"]["model"] == "private-model"
    assert config["llm"]["protocol"] == "anthropic"


def test_provider_options_are_allowlisted():
    config = {
        "llm": {
            "provider": "bedrock",
            "model": "bedrock/anthropic.claude-test",
            "provider_options": {
                "aws_region_name": "us-east-1",
                "unsafe": "drop",
            },
        }
    }

    Config._normalize_llm_config(config)

    assert config["llm"]["provider_options"] == {
        "aws_region_name": "us-east-1"
    }


def test_invalid_explicit_provider_is_reinferred_from_model():
    config = {
        "llm": {
            "provider": "not-a-provider",
            "model": "deepseek/deepseek-chat",
        }
    }

    Config._normalize_llm_config(config)

    assert config["llm"]["provider"] == "deepseek"


def test_save_model_config_persists_normalized_llm_and_other_defaults(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(Config, "CONFIG_FILE", config_file)
    monkeypatch.setattr(Config, "LEGACY_CONFIG_FILE", tmp_path / "legacy.json")

    Config.save_model_config(
        {
            "llm": {
                "provider": "bedrock",
                "base_url": "",
                "model": "anthropic.claude-test",
                "provider_options": {
                    "aws_region_name": "us-west-2",
                    "unsafe": "drop",
                },
            }
        }
    )

    persisted = json.loads(config_file.read_text(encoding="utf-8"))
    assert persisted["llm"]["provider"] == "bedrock"
    assert persisted["llm"]["model"] == "bedrock/anthropic.claude-test"
    assert persisted["llm"]["provider_options"] == {
        "aws_region_name": "us-west-2"
    }
    assert persisted["tts"]["mimo"]["model"] == Config.MIMO_TTS_MODEL
    assert persisted["image"]["model"] == Config.SEEDREAM_MODEL
    assert persisted["generation"]["image_concurrency"] == 1
