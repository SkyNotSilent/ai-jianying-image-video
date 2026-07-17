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


def test_catalog_filters_non_text_models_and_returns_canonical_ids():
    providers = list_llm_providers(FAKE_MODELS)
    assert {item["id"] for item in providers} >= {"deepseek", "anthropic", "mimo"}

    models = list_provider_models("deepseek", FAKE_MODELS)
    assert [item["id"] for item in models] == ["deepseek/deepseek-chat"]
    assert models[0]["sources"] == ["catalog"]


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
