"""Local LiteLLM provider and model metadata registry."""

import json
from copy import deepcopy
from functools import lru_cache
from importlib.metadata import distribution
from pathlib import Path
from typing import Any, Mapping, Optional


TEXT_MODES = {"chat", "completion"}

PROJECT_MODELS = {
    "mimo": [
        {
            "id": "openai/mimo-v2.5-pro",
            "label": "MiMo V2.5 Pro",
            "sources": ["project"],
        }
    ],
}

PROVIDER_OVERRIDES = {
    "custom": {
        "name": "自定义兼容接口",
        "group": "all",
        "litellm_provider": "openai",
        "connection_mode": "custom",
        "compatibility_protocol": "openai",
        "default_base_url": "",
        "recommended_model": "",
        "credential_fields": [
            {
                "id": "base_url",
                "label": "Base URL",
                "required": True,
                "secret": False,
            },
            {
                "id": "api_key",
                "label": "API Key",
                "required": True,
                "secret": True,
            },
            {
                "id": "model",
                "label": "Model",
                "required": True,
                "secret": False,
            },
        ],
        "supports_live_models": True,
        "live_models_adapter": "openai",
        "config_status": "ready",
    },
    "mimo": {
        "name": "小米 MiMo",
        "group": "project",
        "litellm_provider": "openai",
        "connection_mode": "openai_compatible",
        "compatibility_protocol": "openai",
        "default_base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
        "recommended_model": "openai/mimo-v2.5-pro",
        "credential_fields": [
            {
                "id": "api_key",
                "label": "API Key",
                "required": True,
                "secret": True,
            }
        ],
        "supports_live_models": True,
        "live_models_adapter": "openai",
        "config_status": "ready",
    },
    "openai": {
        "name": "OpenAI",
        "group": "recommended",
        "config_status": "ready",
    },
    "anthropic": {
        "name": "Anthropic",
        "group": "recommended",
        "compatibility_protocol": "anthropic",
        "config_status": "ready",
    },
    "deepseek": {
        "name": "DeepSeek",
        "group": "recommended",
        "default_base_url": "https://api.deepseek.com",
        "config_status": "ready",
    },
    "dashscope": {
        "name": "通义千问",
        "group": "recommended",
        "config_status": "ready",
    },
    "zai": {
        "name": "智谱 GLM",
        "group": "recommended",
        "config_status": "ready",
    },
    "openrouter": {
        "name": "OpenRouter",
        "group": "recommended",
        "config_status": "ready",
    },
    "ollama": {
        "name": "Ollama",
        "group": "recommended",
        "default_base_url": "http://localhost:11434",
        "credential_fields": [],
        "supports_live_models": True,
        "live_models_adapter": "ollama",
        "config_status": "ready",
    },
    "azure": {
        "name": "Azure OpenAI",
        "credential_fields": [
            {
                "id": "api_key",
                "label": "API Key",
                "required": True,
                "secret": True,
            },
            {
                "id": "api_version",
                "label": "API Version",
                "required": True,
                "secret": False,
            },
        ],
        "allowed_provider_options": ["api_version"],
        "config_status": "advanced",
    },
    "bedrock": {
        "name": "Amazon Bedrock",
        "credential_fields": [
            {
                "id": "aws_access_key_id",
                "label": "Access Key ID",
                "required": True,
                "secret": True,
            },
            {
                "id": "aws_secret_access_key",
                "label": "Secret Access Key",
                "required": True,
                "secret": True,
            },
            {
                "id": "aws_region_name",
                "label": "Region",
                "required": True,
                "secret": False,
            },
        ],
        "allowed_provider_options": [
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_region_name",
        ],
        "config_status": "ready",
    },
}


_GENERIC_API_KEY_FIELD = {
    "id": "api_key",
    "label": "API Key",
    "required": True,
    "secret": True,
}
_GROUP_ORDER = {"recommended": 0, "project": 1, "all": 2}
_BASE_URL_PROVIDERS = {"custom", "mimo", "ollama"}


@lru_cache(maxsize=1)
def _load_litellm_model_cost() -> Mapping[str, Any]:
    """Load LiteLLM's bundled backup catalog without importing LiteLLM."""

    try:
        backup_path = distribution("litellm").locate_file(
            "litellm/model_prices_and_context_window_backup.json"
        )
        model_cost = json.loads(Path(backup_path).read_text(encoding="utf-8"))
        if isinstance(model_cost, Mapping):
            return model_cost
    except Exception:
        pass
    return {}


def canonical_model_id(provider_id: str, model_id: str) -> str:
    """Return the LiteLLM-prefixed ID unless the model already has a prefix."""

    if "/" in model_id:
        return model_id
    return f"{provider_id}/{model_id}"


def _humanize(identifier: str) -> str:
    words = identifier.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words) or identifier


def _model_map(model_cost: Optional[Mapping] = None) -> Mapping:
    return _load_litellm_model_cost() if model_cost is None else model_cost


def _catalog_models(model_cost: Optional[Mapping] = None) -> dict[str, list[dict]]:
    models_by_provider: dict[str, dict[str, dict]] = {}
    for raw_model_id, metadata in _model_map(model_cost).items():
        if not isinstance(raw_model_id, str) or not isinstance(metadata, Mapping):
            continue
        mode = str(metadata.get("mode") or "").lower()
        provider_id = str(metadata.get("litellm_provider") or "").strip().lower()
        if mode not in TEXT_MODES or not provider_id:
            continue

        model_id = canonical_model_id(provider_id, raw_model_id)
        item = dict(metadata)
        item.update(
            {
                "id": model_id,
                "label": metadata.get("display_name") or raw_model_id,
                "sources": ["catalog"],
            }
        )
        provider_models = models_by_provider.setdefault(provider_id, {})
        existing = provider_models.get(model_id)
        if existing is None:
            provider_models[model_id] = item
        elif raw_model_id == model_id:
            provider_models[model_id] = {**existing, **item}
        else:
            provider_models[model_id] = {**item, **existing}
    return {
        provider_id: list(provider_models.values())
        for provider_id, provider_models in models_by_provider.items()
    }


def _models_by_provider(model_cost: Optional[Mapping] = None) -> dict[str, list[dict]]:
    models_by_provider = _catalog_models(model_cost)
    for provider_id, project_models in PROJECT_MODELS.items():
        indexed = {
            model["id"]: model for model in models_by_provider.setdefault(provider_id, [])
        }
        for project_model in project_models:
            model = deepcopy(project_model)
            existing = indexed.get(model["id"])
            if existing is None:
                models_by_provider[provider_id].append(model)
                indexed[model["id"]] = model
                continue

            sources = list(existing.get("sources") or [])
            for source in model.get("sources") or []:
                if source not in sources:
                    sources.append(source)
            existing.update(model)
            existing["sources"] = sources

    for models in models_by_provider.values():
        models.sort(key=lambda item: (str(item.get("label", "")).casefold(), item["id"]))
    return models_by_provider


def _provider_record(provider_id: str, models: list[dict]) -> dict:
    provider = {
        "id": provider_id,
        "name": _humanize(provider_id),
        "group": "all",
        "litellm_provider": provider_id,
        "connection_mode": "litellm",
        "compatibility_protocol": "",
        "default_base_url": "",
        "recommended_model": models[0]["id"] if models else "",
        "credential_fields": [deepcopy(_GENERIC_API_KEY_FIELD)],
        "supports_live_models": False,
        "live_models_adapter": None,
        "allowed_provider_options": [],
        "config_status": "advanced",
    }
    provider.update(deepcopy(PROVIDER_OVERRIDES.get(provider_id, {})))
    return provider


def list_llm_providers(model_cost: Optional[Mapping] = None) -> list[dict]:
    """List local overlays plus text providers discovered from LiteLLM metadata."""

    models_by_provider = _models_by_provider(model_cost)
    provider_ids = set(models_by_provider) | set(PROVIDER_OVERRIDES)
    providers = [
        _provider_record(provider_id, models_by_provider.get(provider_id, []))
        for provider_id in provider_ids
    ]
    providers.sort(
        key=lambda provider: (
            _GROUP_ORDER.get(provider["group"], len(_GROUP_ORDER)),
            provider["name"].casefold(),
        )
    )
    return providers


def list_provider_models(
    provider_id: str, model_cost: Optional[Mapping] = None
) -> list[dict]:
    """List selectable text models for one registry provider."""

    return deepcopy(_models_by_provider(model_cost).get(provider_id, []))


def get_provider(
    provider_id: str, model_cost: Optional[Mapping] = None
) -> Optional[dict]:
    """Return one provider definition, or ``None`` when it is unknown."""

    for provider in list_llm_providers(model_cost):
        if provider["id"] == provider_id:
            return provider
    return None


def infer_provider(config: Mapping[str, Any]) -> str:
    """Infer a registry provider from an existing LLM configuration."""

    explicit_provider = str(config.get("provider") or "").strip().lower()
    if explicit_provider:
        return explicit_provider

    model_id = str(config.get("model") or "").strip()
    if "/" in model_id:
        provider_id = model_id.split("/", 1)[0].strip().lower()
        if provider_id:
            return provider_id

    base_url = str(config.get("base_url") or config.get("api_url") or "").strip()
    normalized_url = base_url.rstrip("/").lower()
    if normalized_url:
        for provider_id, override in PROVIDER_OVERRIDES.items():
            default_url = str(override.get("default_base_url") or "").rstrip("/").lower()
            if default_url and (
                normalized_url == default_url
                or normalized_url.startswith(f"{default_url}/")
            ):
                return provider_id
    return "custom"


def sanitize_provider_options(
    provider_id: str, options: Mapping[str, Any]
) -> dict:
    """Keep only provider-specific options declared safe by the registry."""

    allowed = set(
        PROVIDER_OVERRIDES.get(provider_id, {}).get("allowed_provider_options", [])
    )
    return {key: value for key, value in options.items() if key in allowed}


def should_pass_base_url(provider_id: str, base_url: str) -> bool:
    """Return whether a configured URL should be forwarded to LiteLLM."""

    if provider_id in _BASE_URL_PROVIDERS:
        return True
    if provider_id not in PROVIDER_OVERRIDES:
        return False

    configured_url = str(base_url or "").strip().rstrip("/")
    if not configured_url:
        return False
    default_url = str(
        PROVIDER_OVERRIDES[provider_id].get("default_base_url") or ""
    ).strip().rstrip("/")
    return configured_url != default_url
