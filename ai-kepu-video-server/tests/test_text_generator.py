import logging
import sys
import traceback
from types import SimpleNamespace

import pytest

from src.config import Config
from src.text.generator import ArticleGenerator


def make_generator(monkeypatch, tmp_path, config):
    monkeypatch.setattr(Config, "llm_config", classmethod(lambda cls: config))
    return ArticleGenerator(config_path=str(tmp_path / "missing.json"))


def test_canonical_provider_model_is_not_reprefixed(monkeypatch, tmp_path):
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "deepseek",
            "model": "deepseek/deepseek-chat",
            "api_key": "key",
            "base_url": "https://api.deepseek.com",
            "protocol": "openai",
            "provider_options": {},
        },
    )

    kwargs = generator._build_completion_kwargs(
        [{"role": "user", "content": "hi"}], 100
    )

    assert kwargs["model"] == "deepseek/deepseek-chat"
    assert "api_base" not in kwargs


def test_project_compatible_provider_passes_base_url(monkeypatch, tmp_path):
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "mimo",
            "model": "openai/mimo-v2.5-pro",
            "api_key": "key",
            "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
            "protocol": "openai",
            "provider_options": {},
        },
    )

    assert generator._build_completion_kwargs([], 100)["api_base"].endswith("/v1")


def test_custom_legacy_model_keeps_protocol_prefix(monkeypatch, tmp_path):
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "custom",
            "model": "private-model",
            "api_key": "key",
            "base_url": "https://private.test/v1",
            "protocol": "anthropic",
            "provider_options": {},
        },
    )

    kwargs = generator._build_completion_kwargs([], 100)

    assert kwargs["model"] == "anthropic/private-model"
    assert kwargs["api_base"] == "https://private.test/v1"


def test_non_custom_bare_model_is_not_protocol_prefixed(monkeypatch, tmp_path):
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "key",
            "base_url": "https://api.deepseek.com",
            "protocol": "openai",
            "provider_options": {},
        },
    )

    assert generator._build_completion_kwargs([], 100)["model"] == "deepseek-chat"


def test_allowlisted_cloud_options_reach_litellm(monkeypatch, tmp_path):
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "bedrock",
            "model": "bedrock/anthropic.claude-test",
            "api_key": "",
            "base_url": "",
            "protocol": "openai",
            "provider_options": {"aws_region_name": "us-east-1"},
        },
    )

    assert (
        generator._build_completion_kwargs([], 100)["aws_region_name"]
        == "us-east-1"
    )


def test_retry_logs_do_not_expose_secrets(monkeypatch, tmp_path, caplog):
    secret = "super-secret-api-key"
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "custom",
            "model": "private-model",
            "api_key": secret,
            "base_url": "https://private.test/v1",
            "protocol": "openai",
            "provider_options": {},
        },
    )
    attempts = 0

    def fail_completion(**kwargs):
        nonlocal attempts
        attempts += 1
        assert kwargs["api_key"] == secret
        raise RuntimeError(f"request failed with api_key={secret}")

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(completion=fail_completion),
    )
    monkeypatch.setattr("time.sleep", lambda _: None)

    with caplog.at_level(logging.WARNING, logger="src.text.generator"):
        with pytest.raises(RuntimeError) as exc_info:
            generator._call_api([], 100)

    error = exc_info.value
    rendered_traceback = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    rendered_context = str(error.__context__ or "")

    assert attempts == 3
    assert str(error) == "LLM API 调用失败，请检查模型配置或稍后重试"
    assert secret not in caplog.text
    assert secret not in str(error)
    assert secret not in rendered_traceback
    assert secret not in rendered_context
    assert error.__context__ is None
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
