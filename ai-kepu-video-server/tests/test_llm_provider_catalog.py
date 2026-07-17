import json

import httpx

from src.text import provider_catalog
from src.text.provider_catalog import (
    canonical_model_id,
    get_provider,
    infer_provider,
    list_llm_providers,
    list_provider_models,
    sanitize_provider_options,
    should_pass_base_url,
)


FAKE_MODELS = {
    "deepseek-chat": {
        "litellm_provider": "deepseek",
        "mode": "chat",
        "max_input_tokens": 64000,
    },
    "deepseek-embedding": {
        "litellm_provider": "deepseek",
        "mode": "embedding",
    },
    "claude-test": {
        "litellm_provider": "anthropic",
        "mode": "chat",
    },
}


def test_loader_reads_distribution_backup_without_http(tmp_path, monkeypatch):
    local_models = {
        "local-chat": {
            "litellm_provider": "local-provider",
            "mode": "chat",
        }
    }
    backup_path = tmp_path / "model_prices_and_context_window_backup.json"
    backup_path.write_text(json.dumps(local_models), encoding="utf-8")

    class FakeDistribution:
        def locate_file(self, path):
            assert str(path) == "litellm/model_prices_and_context_window_backup.json"
            return backup_path

    monkeypatch.setattr(
        provider_catalog,
        "distribution",
        lambda package: FakeDistribution() if package == "litellm" else None,
        raising=False,
    )

    http_calls = []

    def block_http(*args, **kwargs):
        http_calls.append((args, kwargs))
        raise AssertionError("provider catalog loader must not use HTTP")

    monkeypatch.setattr(httpx, "get", block_http)
    provider_catalog._load_litellm_model_cost.cache_clear()
    try:
        assert provider_catalog._load_litellm_model_cost() == local_models
        assert http_calls == []
    finally:
        provider_catalog._load_litellm_model_cost.cache_clear()


def test_catalog_filters_non_text_models_and_returns_canonical_ids():
    providers = list_llm_providers(FAKE_MODELS)
    assert {item["id"] for item in providers} >= {"deepseek", "anthropic", "mimo"}

    models = list_provider_models("deepseek", FAKE_MODELS)
    assert [item["id"] for item in models] == ["deepseek/deepseek-chat"]
    assert models[0]["sources"] == ["catalog"]


def test_catalog_deduplicates_bare_and_prefixed_model_keys_deterministically():
    bare = {
        "litellm_provider": "deepseek",
        "mode": "chat",
        "display_name": "Bare entry",
        "max_input_tokens": 64000,
    }
    prefixed = {
        "litellm_provider": "deepseek",
        "mode": "chat",
        "display_name": "Canonical entry",
        "max_output_tokens": 8192,
    }

    bare_first = list_provider_models(
        "deepseek",
        {
            "deepseek-chat": bare,
            "deepseek/deepseek-chat": prefixed,
        },
    )
    prefixed_first = list_provider_models(
        "deepseek",
        {
            "deepseek/deepseek-chat": prefixed,
            "deepseek-chat": bare,
        },
    )

    assert bare_first == prefixed_first
    assert [item["id"] for item in bare_first] == ["deepseek/deepseek-chat"]
    assert bare_first[0]["label"] == "Canonical entry"
    assert bare_first[0]["max_input_tokens"] == 64000
    assert bare_first[0]["max_output_tokens"] == 8192


def test_project_mimo_extension_is_selectable_without_catalog_entry():
    provider = get_provider("mimo", FAKE_MODELS)
    assert provider["group"] == "project"
    assert provider["default_base_url"] == "https://token-plan-sgp.xiaomimimo.com/v1"
    assert list_provider_models("mimo", FAKE_MODELS)[0]["id"] == "openai/mimo-v2.5-pro"


def test_special_credentials_and_option_allowlist_are_declared():
    bedrock = get_provider("bedrock", FAKE_MODELS)
    assert [field["id"] for field in bedrock["credential_fields"]] == [
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_region_name",
    ]
    assert sanitize_provider_options(
        "bedrock", {"aws_region_name": "us-east-1", "unexpected": "drop-me"}
    ) == {"aws_region_name": "us-east-1"}


def test_inference_prefers_model_prefix_then_known_base_url():
    assert infer_provider({"model": "deepseek/deepseek-chat"}) == "deepseek"
    assert (
        infer_provider(
            {
                "model": "mimo-v2.5-pro",
                "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
            }
        )
        == "mimo"
    )
    assert (
        infer_provider(
            {"model": "private-model", "base_url": "https://private.test/v1"}
        )
        == "custom"
    )


def test_canonical_model_ids_only_add_missing_provider_prefixes():
    assert canonical_model_id("deepseek", "deepseek-chat") == "deepseek/deepseek-chat"
    assert (
        canonical_model_id("anthropic", "anthropic/claude-test")
        == "anthropic/claude-test"
    )


def test_base_url_is_passed_for_compatible_and_overridden_known_providers():
    assert should_pass_base_url("custom", "") is True
    assert should_pass_base_url("mimo", "https://example.test/v1") is True
    assert should_pass_base_url("ollama", "http://localhost:11434") is True
    assert should_pass_base_url("deepseek", "https://example.test/v1") is True
    assert should_pass_base_url("deepseek", "") is False
    assert should_pass_base_url("not-registered", "https://example.test/v1") is False
