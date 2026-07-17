import asyncio

import pytest
import requests
from fastapi import HTTPException

from src.api import routes
from src.text.provider_models import ProviderModelSyncError, refresh_provider_models


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_openai_sync_normalizes_and_merges_account_models():
    calls = []

    result = refresh_provider_models(
        "mimo",
        {"base_url": "https://mimo.test/v1", "api_key": "secret"},
        request_get=lambda url, **kwargs: calls.append((url, kwargs))
        or FakeResponse(
            {"data": [{"id": "mimo-v2.5-pro", "name": "MiMo Pro"}]}
        ),
    )

    assert calls[0][0] == "https://mimo.test/v1/models"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"
    assert calls[0][1]["timeout"] == 20
    assert result["provider"] == "mimo"
    assert result["models_url"] == "https://mimo.test/v1/models"
    assert result["models"][0]["id"] == "openai/mimo-v2.5-pro"
    assert result["models"][0]["label"] == "MiMo V2.5 Pro"
    assert result["models"][0]["sources"] == ["project", "account"]


def test_custom_anthropic_sync_uses_messages_provider_headers():
    calls = []

    result = refresh_provider_models(
        "custom",
        {
            "protocol": "anthropic",
            "base_url": "https://anthropic.test",
            "api_key": "secret",
        },
        request_get=lambda url, **kwargs: calls.append((url, kwargs))
        or FakeResponse({"data": [{"id": "claude-test"}]}),
    )

    assert calls == [
        (
            "https://anthropic.test/v1/models",
            {
                "headers": {
                    "Accept": "application/json",
                    "x-api-key": "secret",
                    "anthropic-version": "2023-06-01",
                },
                "timeout": 20,
            },
        )
    ]
    assert result["models"][0]["id"] == "anthropic/claude-test"
    assert result["models"][0]["sources"] == ["account"]


def test_ollama_sync_reads_tags_without_api_key():
    calls = []

    result = refresh_provider_models(
        "ollama",
        {"base_url": "http://localhost:11434"},
        request_get=lambda url, **kwargs: calls.append((url, kwargs))
        or FakeResponse({"models": [{"name": "qwen3:8b"}]}),
    )

    assert calls == [
        (
            "http://localhost:11434/api/tags",
            {"headers": {"Accept": "application/json"}, "timeout": 20},
        )
    ]
    assert result["models"][0]["id"] == "ollama/qwen3:8b"


def test_failed_sync_does_not_expose_secret_or_response_body():
    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "mimo",
            {
                "base_url": "https://mimo.test/v1?token=URL-TOP-SECRET",
                "api_key": "TOP-SECRET",
            },
            request_get=lambda *_args, **_kwargs: FakeResponse(
                {"error": "TOP-SECRET", "headers": "PRIVATE-HEADER"}, 401
            ),
        )

    assert error.value.kind == "credentials"
    assert error.value.status_code == 401
    assert str(error.value) == error.value.public_message
    assert "TOP-SECRET" not in str(error.value)
    assert "URL-TOP-SECRET" not in str(error.value)
    assert "PRIVATE-HEADER" not in str(error.value)


def test_malformed_url_is_rejected_without_exposing_query_values():
    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "custom",
            {
                "protocol": "openai",
                "base_url": "https://[invalid?token=URL-TOP-SECRET",
                "api_key": "TOP-SECRET",
            },
            request_get=lambda *_args, **_kwargs: pytest.fail(
                "invalid URLs must not be requested"
            ),
        )

    assert error.value.kind == "invalid_response"
    assert error.value.status_code == 400
    assert "URL-TOP-SECRET" not in str(error.value)
    assert "TOP-SECRET" not in str(error.value)
    assert error.value.__context__ is None


def test_network_failure_is_sanitized_and_drops_exception_context():
    secret = "NETWORK-TOP-SECRET"

    def fail_request(*_args, **_kwargs):
        raise requests.RequestException(f"failed https://host.test/?key={secret}")

    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "custom",
            {
                "protocol": "openai",
                "base_url": "https://host.test/v1",
                "api_key": secret,
            },
            request_get=fail_request,
        )

    assert error.value.kind == "network"
    assert error.value.status_code == 502
    assert secret not in str(error.value)
    assert error.value.__context__ is None


@pytest.mark.parametrize(
    ("status_code", "expected_kind", "expected_status"),
    [(429, "rate_limit", 429), (503, "network", 502)],
)
def test_http_failures_map_to_public_error_kinds(
    status_code, expected_kind, expected_status
):
    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "mimo",
            {"base_url": "https://mimo.test/v1", "api_key": "secret"},
            request_get=lambda *_args, **_kwargs: FakeResponse({}, status_code),
        )

    assert error.value.kind == expected_kind
    assert error.value.status_code == expected_status


@pytest.mark.parametrize(
    "payload",
    [ValueError("not json"), {"data": []}, {"data": [None, {"missing": "id"}]}],
)
def test_invalid_or_empty_model_payload_is_rejected(payload):
    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "mimo",
            {"base_url": "https://mimo.test/v1", "api_key": "secret"},
            request_get=lambda *_args, **_kwargs: FakeResponse(payload),
        )

    assert error.value.kind == "invalid_response"
    assert error.value.status_code == 502
    assert error.value.__context__ is None


def test_provider_routes_return_catalog_fallback_and_404():
    providers = asyncio.run(routes.get_llm_providers())
    assert {provider["id"] for provider in providers["providers"]} >= {
        "custom",
        "mimo",
        "ollama",
    }

    models = asyncio.run(routes.get_llm_provider_models("mimo"))
    assert models["provider"] == "mimo"
    assert models["models"][0]["id"] == "openai/mimo-v2.5-pro"
    assert "project" in models["models"][0]["sources"]

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.get_llm_provider_models("provider-does-not-exist"))
    assert error.value.status_code == 404
    assert error.value.detail == "生文服务商不存在"


def test_refresh_route_maps_unsupported_provider_to_400():
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.refresh_llm_provider_models("deepseek", {}))

    assert error.value.status_code == 400
    assert error.value.detail == "该生文服务商不支持同步模型列表"


def test_refresh_route_delegates_to_sync_service(monkeypatch):
    calls = []
    expected = {"provider": "mimo", "models": []}

    def fake_refresh(provider_id, payload):
        calls.append((provider_id, payload))
        return expected

    monkeypatch.setattr(routes, "refresh_provider_models", fake_refresh)

    result = asyncio.run(
        routes.refresh_llm_provider_models(
            "mimo", {"base_url": "https://mimo.test/v1", "api_key": "secret"}
        )
    )

    assert result is expected
    assert calls == [
        (
            "mimo",
            {"base_url": "https://mimo.test/v1", "api_key": "secret"},
        )
    ]


def test_legacy_config_models_delegates_to_custom_and_keeps_raw_model_ids(
    monkeypatch,
):
    calls = []

    def fake_refresh(provider_id, payload):
        calls.append((provider_id, payload))
        return {
            "provider": "custom",
            "models_url": "https://image.test/v1/models",
            "models": [
                {
                    "id": "openai/agnes-image-2.1-flash",
                    "label": "Agnes Image",
                    "sources": ["account"],
                }
            ],
        }

    monkeypatch.setattr(routes, "refresh_provider_models", fake_refresh)
    payload = {
        "api_url": "https://image.test/v1/images/generations",
        "api_key": "secret",
    }

    result = asyncio.run(routes.fetch_config_models(payload))

    assert calls == [
        (
            "custom",
            payload,
        )
    ]
    assert result == {
        "models_url": "https://image.test/v1/models",
        "models": [{"id": "agnes-image-2.1-flash", "label": "Agnes Image"}],
    }
