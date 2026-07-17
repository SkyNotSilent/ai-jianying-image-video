"""Live model discovery for the provider catalog."""

from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import Any, Mapping
from urllib.parse import urlparse, urlunparse
import uuid

import requests

from src.text.provider_catalog import (
    canonical_model_id,
    get_provider,
    list_provider_models,
)

logger = logging.getLogger(__name__)


class ProviderModelSyncError(Exception):
    """A model synchronization failure safe to return through the API."""

    def __init__(
        self,
        kind: str,
        public_message: str,
        status_code: int,
        correlation_id: str = "",
    ):
        self.kind = kind
        self.public_message = public_message
        self.status_code = status_code
        self.correlation_id = correlation_id
        super().__init__(public_message)


@dataclass(frozen=True)
class _SafeSyncFailure:
    kind: str
    public_message: str
    status_code: int
    correlation_id: str = ""


_KNOWN_ENDPOINT_SUFFIXES = (
    "/chat/completions",
    "/images/generations",
    "/completions",
    "/responses",
    "/messages",
)


def _failure(
    kind: str,
    public_message: str,
    status_code: int,
    correlation_id: str = "",
):
    return _SafeSyncFailure(kind, public_message, status_code, correlation_id)


def _internal_failure():
    correlation_id = uuid.uuid4().hex[:12]
    try:
        logger.error(
            "Provider model sync failure=unexpected_internal correlation_id=%s",
            correlation_id,
        )
    except Exception:
        pass
    return _failure(
        "internal",
        f"模型列表同步失败，请稍后重试（参考编号：{correlation_id}）",
        500,
        correlation_id,
    )


def _base_parts(base_url: str):
    value = str(base_url or "").strip()
    if not value:
        return None, "", _failure(
            "invalid_response", "请先填写 Base URL", 400
        )

    try:
        parsed = urlparse(value)
    except ValueError:
        return None, "", _failure(
            "invalid_response", "Base URL 必须是 http:// 或 https:// 开头的完整地址", 400
        )
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        return None, "", _failure(
            "invalid_response", "Base URL 必须是 http:// 或 https:// 开头的完整地址", 400
        )

    path = (parsed.path or "").rstrip("/")
    for suffix in _KNOWN_ENDPOINT_SUFFIXES:
        if path.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break
    return parsed, path, None


def _models_url(base_url: str, adapter: str):
    parsed, path, failure = _base_parts(base_url)
    if failure:
        return None, failure

    if adapter == "ollama":
        if path.endswith("/api/tags"):
            models_path = path
        elif path.endswith("/api"):
            models_path = f"{path}/tags"
        else:
            models_path = f"{path}/api/tags" if path else "/api/tags"
    elif adapter == "anthropic":
        if path.endswith("/models"):
            models_path = path
        elif path.endswith("/v1"):
            models_path = f"{path}/models"
        elif not path:
            models_path = "/v1/models"
        else:
            models_path = f"{path}/models"
    else:
        models_path = path if path.endswith("/models") else (
            f"{path}/models" if path else "/models"
        )

    return (
        urlunparse((parsed.scheme, parsed.netloc, models_path, "", "", "")),
        None,
    )


def _adapter_for(provider_id: str, provider: Mapping[str, Any], draft: Mapping):
    adapter = provider.get("live_models_adapter")
    if provider_id == "custom":
        adapter = str(draft.get("protocol") or "openai").strip().lower()
    if adapter not in {"openai", "anthropic", "ollama"}:
        return None, _failure(
            "unsupported", "该生文服务商不支持同步模型列表", 400
        )
    return str(adapter), None


def _account_models(payload: Any, adapter: str, canonical_provider: str) -> list[dict]:
    if isinstance(payload, Mapping):
        raw_items = payload.get("models") if adapter == "ollama" else payload.get("data")
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = None

    if not isinstance(raw_items, list):
        return []

    models = {}
    for item in raw_items:
        if isinstance(item, str):
            raw_id = item
            label = item
        elif isinstance(item, Mapping):
            raw_id = (
                item.get("id")
                or item.get("model")
                or item.get("name")
                or item.get("model_name")
            )
            label = (
                item.get("display_name")
                or item.get("label")
                or item.get("name")
                or raw_id
            )
        else:
            continue

        raw_id = str(raw_id or "").strip()
        if not raw_id:
            continue
        model_id = canonical_model_id(canonical_provider, raw_id)
        models.setdefault(
            model_id,
            {
                "id": model_id,
                "label": str(label or raw_id),
                "sources": ["account"],
            },
        )
    return list(models.values())


def _merge_models(local_models: list[dict], account_models: list[dict]) -> list[dict]:
    merged = {
        model["id"]: deepcopy(model)
        for model in local_models
        if isinstance(model, Mapping) and model.get("id")
    }
    for account_model in account_models:
        existing = merged.get(account_model["id"])
        if existing is None:
            merged[account_model["id"]] = deepcopy(account_model)
            continue

        local_label = existing.get("label")
        sources = list(existing.get("sources") or [])
        for source in account_model.get("sources") or []:
            if source not in sources:
                sources.append(source)
        existing.update(account_model)
        if local_label:
            existing["label"] = local_label
        existing["sources"] = sources

    return sorted(
        merged.values(),
        key=lambda model: (
            0 if "account" in (model.get("sources") or []) else 1,
            str(model.get("label") or "").casefold(),
            str(model.get("id") or ""),
        ),
    )


def _refresh_provider_models_internal(
    provider_id: str,
    draft: Mapping,
    request_get,
):
    """Return either a completed response or a traceback-free error description."""

    try:
        provider_id = str(provider_id or "").strip().lower()
        provider = get_provider(provider_id)
        if provider is None:
            return None, _failure("unsupported", "生文服务商不存在", 404)
        if not provider.get("supports_live_models"):
            return None, _failure(
                "unsupported", "该生文服务商不支持同步模型列表", 400
            )

        draft = draft if isinstance(draft, Mapping) else {}
        adapter, failure = _adapter_for(provider_id, provider, draft)
        if failure:
            return None, failure
        base_url = (
            draft.get("base_url")
            or draft.get("api_url")
            or provider.get("default_base_url")
        )
        api_key = str(
            draft.get("api_key") or draft.get("token") or ""
        ).strip()
        if adapter in {"openai", "anthropic"} and not api_key:
            return None, _failure("credentials", "请先填写 API Key", 400)

        models_url, failure = _models_url(str(base_url or ""), adapter)
        if failure:
            return None, failure
        headers = {"Accept": "application/json"}
        if adapter == "anthropic":
            headers.update(
                {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                }
            )
        elif adapter == "openai" and api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = request_get(models_url, headers=headers, timeout=20)
        except requests.RequestException:
            return None, _failure(
                "network",
                "模型列表请求失败，请检查服务地址或稍后重试",
                502,
            )
        except Exception:
            return None, _internal_failure()

        status_code = getattr(response, "status_code", 0)
        if status_code in {401, 403}:
            return None, _failure(
                "credentials", "模型列表认证失败，请检查 API Key", 401
            )
        if status_code == 429:
            return None, _failure(
                "rate_limit", "模型列表同步请求过于频繁，请稍后重试", 429
            )
        if (
            not isinstance(status_code, int)
            or status_code < 200
            or status_code >= 400
        ):
            return None, _failure(
                "invalid_response", "模型列表服务返回了无效状态", 502
            )

        json_reader = getattr(response, "json", None)
        if not callable(json_reader):
            return None, _failure(
                "invalid_response", "模型列表接口没有返回有效 JSON", 502
            )
        try:
            response_payload = json_reader()
        except (TypeError, ValueError):
            return None, _failure(
                "invalid_response", "模型列表接口没有返回有效 JSON", 502
            )

        canonical_provider = (
            adapter
            if provider_id == "custom"
            else provider.get("litellm_provider")
        )
        account_models = _account_models(
            response_payload, adapter, str(canonical_provider or provider_id)
        )
        if not account_models:
            return None, _failure(
                "invalid_response", "没有从响应中解析到模型列表", 502
            )

        return {
            "provider": provider_id,
            "models_url": models_url,
            "models": _merge_models(
                list_provider_models(provider_id), account_models
            ),
        }, None
    except Exception:
        return None, _internal_failure()


def refresh_provider_models(
    provider_id: str,
    draft: Mapping,
    request_get=requests.get,
) -> dict:
    """Fetch account models without retaining sensitive failure state."""

    result, failure = _refresh_provider_models_internal(
        provider_id, draft, request_get
    )
    provider_id = None
    draft = None
    request_get = None
    if failure is None:
        return result

    kind = failure.kind
    public_message = failure.public_message
    status_code = failure.status_code
    correlation_id = failure.correlation_id
    failure = None
    result = None
    raise ProviderModelSyncError(
        kind, public_message, status_code, correlation_id
    ) from None
