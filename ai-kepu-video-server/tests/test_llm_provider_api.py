import asyncio
import logging

import pytest
import requests
from fastapi import HTTPException

from src.api import routes
from src.text import provider_models
from src.text.provider_models import ProviderModelSyncError, refresh_provider_models


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def production_traceback_locals(error, filename):
    frames = []
    traceback = error.__traceback__
    while traceback:
        frame = traceback.tb_frame
        if frame.f_code.co_filename.endswith(filename):
            frames.append((frame.f_code.co_name, dict(frame.f_locals)))
        traceback = traceback.tb_next
    return frames


def assert_traceback_has_no_markers(error, filename, markers):
    frames = production_traceback_locals(error, filename)
    assert frames
    rendered_locals = "\n".join(
        f"{function}: {values!r}" for function, values in frames
    )
    for marker in markers:
        assert marker not in rendered_locals
    return frames


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
    assert result["synced"] is True
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


def test_sync_error_traceback_drops_all_sensitive_request_locals():
    markers = {
        "DRAFT-TOP-SECRET",
        "URL-QUERY-TOP-SECRET",
        "PRIVATE-HEADER-TOP-SECRET",
        "RESPONSE-BODY-TOP-SECRET",
    }

    class SensitiveResponse(FakeResponse):
        headers = {"X-Private": "PRIVATE-HEADER-TOP-SECRET"}

        def __repr__(self):
            return (
                "SensitiveResponse("
                f"payload={self._payload!r}, headers={self.headers!r})"
            )

    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "mimo",
            {
                "base_url": (
                    "https://mimo.test/v1?token=URL-QUERY-TOP-SECRET"
                ),
                "api_key": "DRAFT-TOP-SECRET",
            },
            request_get=lambda *_args, **_kwargs: SensitiveResponse(
                {"error": "RESPONSE-BODY-TOP-SECRET"}, 401
            ),
        )

    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    frames = assert_traceback_has_no_markers(
        error.value, "/src/text/provider_models.py", markers
    )
    public_frame = next(
        values for function, values in frames
        if function == "refresh_provider_models"
    )
    for local_name in (
        "draft",
        "request_get",
        "base_url",
        "api_key",
        "headers",
        "response",
        "response_payload",
    ):
        assert public_frame.get(local_name) is None


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
    [(429, "rate_limit", 429), (503, "invalid_response", 502)],
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


def test_response_without_json_reader_is_invalid_response():
    class MissingJsonResponse:
        status_code = 200

    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models(
            "mimo",
            {"base_url": "https://mimo.test/v1", "api_key": "secret"},
            request_get=lambda *_args, **_kwargs: MissingJsonResponse(),
        )

    assert error.value.kind == "invalid_response"
    assert error.value.status_code == 502


@pytest.mark.parametrize("failure_stage", ["request", "merge"])
def test_unknown_internal_failure_is_safe_and_not_mislabeled_network(
    failure_stage, monkeypatch, caplog
):
    markers = {
        "INTERNAL-API-KEY-TOP-SECRET",
        "INTERNAL-URL-TOP-SECRET",
        "INTERNAL-HEADER-TOP-SECRET",
        "INTERNAL-BODY-TOP-SECRET",
    }

    class InjectedInternalError(RuntimeError):
        pass

    class SensitiveResponse(FakeResponse):
        headers = {"X-Private": "INTERNAL-HEADER-TOP-SECRET"}

        def __repr__(self):
            return (
                "SensitiveResponse("
                f"payload={self._payload!r}, headers={self.headers!r})"
            )

    def fail_internal(*_args, **_kwargs):
        raise InjectedInternalError(
            "INTERNAL-BODY-TOP-SECRET INTERNAL-API-KEY-TOP-SECRET"
        )

    if failure_stage == "merge":
        monkeypatch.setattr(provider_models, "_merge_models", fail_internal)
        request_get = lambda *_args, **_kwargs: SensitiveResponse(
            {"data": [{"id": "mimo-v2.5-pro"}]}
        )
    else:
        request_get = fail_internal

    with caplog.at_level(logging.ERROR, logger="src.text.provider_models"):
        with pytest.raises(ProviderModelSyncError) as error:
            refresh_provider_models(
                "mimo",
                {
                    "base_url": (
                        "https://mimo.test/v1?token=INTERNAL-URL-TOP-SECRET"
                    ),
                    "api_key": "INTERNAL-API-KEY-TOP-SECRET",
                },
                request_get=request_get,
            )

    assert error.value.kind == "internal"
    assert error.value.status_code == 500
    assert error.value.correlation_id
    assert error.value.correlation_id in str(error.value)
    assert error.value.correlation_id in caplog.text
    assert "unexpected_internal" in caplog.text
    assert "InjectedInternalError" not in caplog.text
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert_traceback_has_no_markers(
        error.value, "/src/text/provider_models.py", markers
    )
    for marker in markers:
        assert marker not in str(error.value)
        assert marker not in caplog.text


def test_dynamic_secret_exception_class_name_is_never_logged(
    monkeypatch, caplog
):
    class_name_marker = "DYNAMIC_EXCEPTION_CLASS_TOP_SECRET"
    message_marker = "DYNAMIC_EXCEPTION_MESSAGE_TOP_SECRET"
    api_key_marker = "DYNAMIC_EXCEPTION_API_KEY_TOP_SECRET"
    url_marker = "DYNAMIC_EXCEPTION_URL_TOP_SECRET"
    secret_exception = type(class_name_marker, (RuntimeError,), {})

    def fail_merge(*_args, **_kwargs):
        raise secret_exception(message_marker)

    monkeypatch.setattr(provider_models, "_merge_models", fail_merge)
    with caplog.at_level(logging.ERROR, logger="src.text.provider_models"):
        with pytest.raises(ProviderModelSyncError) as error:
            refresh_provider_models(
                "mimo",
                {
                    "base_url": f"https://mimo.test/v1?token={url_marker}",
                    "api_key": api_key_marker,
                },
                request_get=lambda *_args, **_kwargs: FakeResponse(
                    {"data": [{"id": "mimo-v2.5-pro"}]}
                ),
            )

    markers = {
        class_name_marker,
        message_marker,
        api_key_marker,
        url_marker,
    }
    assert error.value.kind == "internal"
    assert error.value.correlation_id in caplog.text
    assert "unexpected_internal" in caplog.text
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert_traceback_has_no_markers(
        error.value, "/src/text/provider_models.py", markers
    )
    for marker in markers:
        assert marker not in caplog.text
        assert marker not in str(error.value)


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


@pytest.mark.parametrize(
    ("route_call", "payload_local"),
    [
        (
            lambda payload: routes.refresh_llm_provider_models("mimo", payload),
            "payload",
        ),
        (lambda payload: routes.fetch_config_models(payload), "config"),
    ],
)
def test_route_error_traceback_unlinks_sync_error_and_drops_payload(
    monkeypatch, route_call, payload_local
):
    markers = {
        "ROUTE-API-KEY-TOP-SECRET",
        "ROUTE-URL-TOP-SECRET",
        "ROUTE-HEADER-TOP-SECRET",
        "ROUTE-BODY-TOP-SECRET",
    }

    def fail_refresh(_provider_id, payload):
        headers = {
            "Authorization": f"Bearer {payload['api_key']}",
            "X-Private": "ROUTE-HEADER-TOP-SECRET",
        }
        response_body = {"error": "ROUTE-BODY-TOP-SECRET"}
        assert headers and response_body
        raise ProviderModelSyncError("credentials", "safe detail", 401)

    monkeypatch.setattr(routes, "refresh_provider_models", fail_refresh)
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            route_call(
                {
                    "base_url": (
                        "https://route.test/v1?token=ROUTE-URL-TOP-SECRET"
                    ),
                    "api_key": "ROUTE-API-KEY-TOP-SECRET",
                }
            )
        )

    assert error.value.status_code == 401
    assert error.value.detail == "safe detail"
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    frames = assert_traceback_has_no_markers(
        error.value, "/src/api/routes.py", markers
    )
    route_frame = next(
        values for function, values in frames
        if function in {"refresh_llm_provider_models", "fetch_config_models"}
    )
    assert route_frame.get(payload_local) is None


def test_refresh_route_delegates_to_sync_service(monkeypatch):
    calls = []
    expected = {"provider": "mimo", "models": [], "synced": True}

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
    assert result["synced"] is True
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
