import logging
import sys
import traceback
from types import SimpleNamespace

import pytest

from src.config import Config
from src.text import generator as generator_module
from src.text.generator import ArticleGenerator


def make_generator(monkeypatch, tmp_path, config):
    monkeypatch.setattr(Config, "llm_config", classmethod(lambda cls: config))
    return ArticleGenerator(config_path=str(tmp_path / "missing.json"))


def generator_traceback_locals(error):
    frames = []
    current = error.__traceback__
    while current:
        frame = current.tb_frame
        if frame.f_code.co_filename.endswith("/src/text/generator.py"):
            frames.append((frame.f_code.co_name, dict(frame.f_locals)))
        current = current.tb_next
    return frames


def render_local_object_graph(value, seen=None):
    seen = seen or set()
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return repr(value)
    identity = id(value)
    if identity in seen:
        return "<circular>"
    seen.add(identity)
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{render_local_object_graph(key, seen)}: "
            f"{render_local_object_graph(item, seen)}"
            for key, item in value.items()
        ) + "}"
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(
            render_local_object_graph(item, seen) for item in value
        ) + "]"
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return f"{type(value).__name__}" + render_local_object_graph(
            attributes, seen
        )
    return repr(value)


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


def test_rate_limit_retry_uses_retry_after_and_shared_throttle(monkeypatch):
    attempts = 0
    pauses = []
    waits = []

    def completion(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            error = RuntimeError("rate limited")
            error.response = SimpleNamespace(
                status_code=429, headers={"Retry-After": "7"}
            )
            raise error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )

    monkeypatch.setattr(generator_module, "_pause_llm_requests", pauses.append)
    monkeypatch.setattr(generator_module, "_wait_for_llm_throttle", lambda: waits.append(True))

    content, failure = generator_module._run_completion_with_retries(completion, {})

    assert content == "ok"
    assert failure is None
    assert attempts == 2
    assert pauses == [7.0]
    assert len(waits) == 3


@pytest.mark.parametrize(
    "entrypoint", ["direct", "generate", "generate_image_prompts"]
)
def test_retry_logs_do_not_expose_secrets(
    monkeypatch, tmp_path, caplog, entrypoint
):
    secret = "GENERATOR-API-KEY-TOP-SECRET"
    option_secret = "GENERATOR-PROVIDER-OPTION-TOP-SECRET"
    url_secret = "GENERATOR-URL-TOP-SECRET"
    generator = make_generator(
        monkeypatch,
        tmp_path,
        {
            "provider": "custom",
            "model": "private-model",
            "api_key": secret,
            "base_url": f"https://private.test/v1?token={url_secret}",
            "protocol": "openai",
            "provider_options": {"api_version": option_secret},
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
            if entrypoint == "generate":
                generator.generate("traceback safety")
            elif entrypoint == "generate_image_prompts":
                generator.generate_image_prompts(["traceback safety"])
            else:
                generator._call_api([], 100)

    error = exc_info.value
    rendered_traceback = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    rendered_context = str(error.__context__ or "")
    product_frames = generator_traceback_locals(error)
    rendered_locals = "\n".join(
        f"{function}: {render_local_object_graph(values)}"
        for function, values in product_frames
    )

    assert attempts == 3
    assert product_frames
    assert str(error) == "LLM API 调用失败，请检查模型配置或稍后重试"
    assert secret not in caplog.text
    assert secret not in str(error)
    assert secret not in rendered_traceback
    assert secret not in rendered_context
    assert error.__context__ is None
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    for marker in (secret, option_secret, url_secret):
        assert marker not in caplog.text
        assert marker not in rendered_traceback
        assert marker not in rendered_context
        assert marker not in rendered_locals
