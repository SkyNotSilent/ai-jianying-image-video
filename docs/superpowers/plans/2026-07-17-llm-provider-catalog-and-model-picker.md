# InsightCut LLM Provider Catalog and Model Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual LLM protocol/Base URL/model entry with a LiteLLM-backed provider catalog, searchable model selection, account model synchronization, and advanced custom overrides while preserving legacy configurations.

**Architecture:** A new Python provider registry owns provider metadata, project overlays, canonical model IDs, credential schemas, and live-model adapters. FastAPI exposes that registry to a small React data layer and focused provider/model picker components; `ArticleGenerator` consumes the same normalized provider configuration so UI and runtime routing cannot drift. Existing `protocol`, `base_url`, and unprefixed model fields remain migration inputs and the custom-compatible fallback.

**Tech Stack:** Python 3.9, FastAPI, LiteLLM, pytest, React 19, Vite 4, Node test runner, existing CSS system.

## Global Constraints

- Execute this plan in an isolated worktree created with `superpowers:using-git-worktrees`; use branch `codex/llm-provider-catalog` so the dirty main checkout remains untouched.
- Do not modify or commit the user's existing preview/subtitle changes or unrelated untracked files in the main checkout.
- Keep Python `litellm>=1.40.0`; do not add Vercel AI SDK, a second model SDK, or new frontend packages.
- Use the installed LiteLLM model metadata locally; do not make the settings page depend on the public LiteLLM Catalog API.
- Never log API keys, Authorization headers, provider secret fields, complete credential objects, or response bodies that may echo credentials.
- Do not assert a fixed provider/model total in tests; LiteLLM dependency updates may legitimately change those totals.
- Preserve old OpenAI-compatible and Anthropic-compatible configurations and only persist migrated fields after the user saves.
- Keep all generated/configured data local. No InsightCut-owned remote credential service is introduced.
- Keep `AGENTS.md` and `CLAUDE.md` byte-for-byte identical whenever either is changed.
- Preserve fixed ports: frontend `2001`, backend `2002`.

---

## File Map

### Backend

- Create `ai-kepu-video-server/src/text/provider_catalog.py`: local LiteLLM catalog access, project overlays, model normalization, provider inference, credential allowlists.
- Create `ai-kepu-video-server/src/text/provider_models.py`: provider-specific live model list requests and sanitized failures.
- Modify `ai-kepu-video-server/src/config.py`: add `llm.provider`/`provider_options` normalization and legacy inference.
- Modify `ai-kepu-video-server/src/text/generator.py`: build LiteLLM kwargs from normalized provider configuration.
- Modify `ai-kepu-video-server/src/api/routes.py`: expose provider/model endpoints and retain the legacy `/config/models` endpoint.
- Create `ai-kepu-video-server/tests/test_llm_provider_catalog.py`: provider and model metadata rules.
- Create `ai-kepu-video-server/tests/test_llm_config.py`: configuration migration and option filtering.
- Create `ai-kepu-video-server/tests/test_text_generator.py`: LiteLLM routing arguments.
- Create `ai-kepu-video-server/tests/test_llm_provider_api.py`: live synchronization and FastAPI route behavior.

### Frontend

- Create `ai-kepu-video-web/frontend/src/lib/llmProviderCatalog.js`: provider/model normalization, grouping, draft switching, readiness and refresh payloads.
- Create `ai-kepu-video-web/frontend/src/components/LlmProviderSettings.jsx`: controlled LLM settings section.
- Create `ai-kepu-video-web/frontend/src/components/ProviderCombobox.jsx`: searchable grouped provider selector.
- Create `ai-kepu-video-web/frontend/src/components/ModelCombobox.jsx`: searchable grouped model selector without free entry.
- Create `ai-kepu-video-web/frontend/src/components/AdvancedSettings.jsx`: accessible reusable advanced-details shell.
- Modify `ai-kepu-video-web/frontend/src/api/task.js`: provider catalog/model API clients.
- Modify `ai-kepu-video-web/frontend/src/lib/settingsConfig.js`: normalized LLM fields plus fixed Agnes/MiMo preset helpers.
- Modify `ai-kepu-video-web/frontend/src/pages/SettingsPage.jsx`: orchestration, provider draft cache, simplified image/TTS fields.
- Modify `ai-kepu-video-web/frontend/src/pages/delivery-pages.css`: provider/model picker and advanced-section styles.
- Create `ai-kepu-video-web/frontend/tests/llmProviderCatalog.test.mjs`: pure provider/model interaction tests.
- Modify `ai-kepu-video-web/frontend/tests/settingsConfig.test.mjs`: config and preset regression tests.

### Documentation

- Modify `ai-kepu-video-server/.env.example`: document optional `LLM_PROVIDER`.
- Modify `AGENTS.md` and `CLAUDE.md`: document provider registry, canonical model IDs, legacy fallback and credential safety.

---

### Task 1: Build the Local LiteLLM Provider Registry

**Files:**
- Create: `ai-kepu-video-server/src/text/provider_catalog.py`
- Create: `ai-kepu-video-server/tests/test_llm_provider_catalog.py`

**Interfaces:**
- Produces: `list_llm_providers(model_cost: Optional[Mapping] = None) -> list[dict]`
- Produces: `list_provider_models(provider_id: str, model_cost: Optional[Mapping] = None) -> list[dict]`
- Produces: `get_provider(provider_id: str, model_cost: Optional[Mapping] = None) -> Optional[dict]`
- Produces: `canonical_model_id(provider_id: str, model_id: str) -> str`
- Produces: `infer_provider(config: Mapping[str, Any]) -> str`
- Produces: `sanitize_provider_options(provider_id: str, options: Mapping[str, Any]) -> dict`
- Produces: `should_pass_base_url(provider_id: str, base_url: str) -> bool`

- [ ] **Step 1: Write failing provider catalog tests**

Create tests using a small injected model map so tests never import the whole external catalog:

```python
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
        "aws_access_key_id", "aws_secret_access_key", "aws_region_name"
    ]
    assert sanitize_provider_options("bedrock", {
        "aws_region_name": "us-east-1", "unexpected": "drop-me"
    }) == {"aws_region_name": "us-east-1"}

def test_inference_prefers_model_prefix_then_known_base_url():
    assert infer_provider({"model": "deepseek/deepseek-chat"}) == "deepseek"
    assert infer_provider({
        "model": "mimo-v2.5-pro",
        "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
    }) == "mimo"
    assert infer_provider({"model": "private-model", "base_url": "https://private.test/v1"}) == "custom"
```

- [ ] **Step 2: Run tests and verify the module is missing**

Run:

```bash
cd ai-kepu-video-server
source venv/bin/activate
pytest tests/test_llm_provider_catalog.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'src.text.provider_catalog'`.

- [ ] **Step 3: Implement the registry with lazy LiteLLM loading**

Use `mode in {"chat", "completion"}` as the text filter. Define explicit overlays for the common direct-config providers and special credential providers:

```python
TEXT_MODES = {"chat", "completion"}
PROJECT_MODELS = {
    "mimo": [{
        "id": "openai/mimo-v2.5-pro",
        "label": "MiMo V2.5 Pro",
        "sources": ["project"],
    }],
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
            {"id": "base_url", "label": "Base URL", "required": True, "secret": False},
            {"id": "api_key", "label": "API Key", "required": True, "secret": True},
            {"id": "model", "label": "Model", "required": True, "secret": False},
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
        "credential_fields": [{"id": "api_key", "label": "API Key", "required": True, "secret": True}],
        "supports_live_models": True,
        "live_models_adapter": "openai",
        "config_status": "ready",
    },
    "openai": {"name": "OpenAI", "group": "recommended", "config_status": "ready"},
    "anthropic": {"name": "Anthropic", "group": "recommended", "config_status": "ready"},
    "deepseek": {"name": "DeepSeek", "group": "recommended", "config_status": "ready"},
    "dashscope": {"name": "通义千问", "group": "recommended", "config_status": "ready"},
    "zai": {"name": "智谱 GLM", "group": "recommended", "config_status": "ready"},
    "openrouter": {"name": "OpenRouter", "group": "recommended", "config_status": "ready"},
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
            {"id": "api_key", "label": "API Key", "required": True, "secret": True},
            {"id": "api_version", "label": "API Version", "required": True, "secret": False},
        ],
        "allowed_provider_options": ["api_version"],
        "config_status": "ready",
    },
    "bedrock": {
        "name": "Amazon Bedrock",
        "credential_fields": [
            {"id": "aws_access_key_id", "label": "Access Key ID", "required": True, "secret": True},
            {"id": "aws_secret_access_key", "label": "Secret Access Key", "required": True, "secret": True},
            {"id": "aws_region_name", "label": "Region", "required": True, "secret": False},
        ],
        "allowed_provider_options": ["aws_access_key_id", "aws_secret_access_key", "aws_region_name"],
        "config_status": "ready",
    },
}
```

For providers discovered only from LiteLLM, return a humanized name, `group="all"`, a generic API Key field, and `config_status="advanced"`. Import `litellm` only inside an `@lru_cache(maxsize=1)` loader; if the import or model metadata read fails, return an empty model map so project overrides and the custom entry still render. Normalize catalog IDs by prefixing the LiteLLM provider only when the raw ID has no slash. Sort provider groups as `recommended`, `project`, `all`, then by display name. `should_pass_base_url()` returns true for `custom`, `mimo`, and `ollama`, and for any known provider whose non-empty configured URL differs from its Registry default.

- [ ] **Step 4: Run the focused catalog tests**

Run `pytest tests/test_llm_provider_catalog.py -q`.

Expected: all tests pass without network access and without asserting global catalog counts.

- [ ] **Step 5: Commit the catalog unit**

```bash
git add ai-kepu-video-server/src/text/provider_catalog.py ai-kepu-video-server/tests/test_llm_provider_catalog.py
git commit -m "feat: add LiteLLM provider catalog"
```

---

### Task 2: Normalize Provider-Aware LLM Configuration

**Files:**
- Modify: `ai-kepu-video-server/src/config.py:54-63,98-185,281-303`
- Create: `ai-kepu-video-server/tests/test_llm_config.py`

**Interfaces:**
- Consumes: `infer_provider`, `canonical_model_id`, `get_provider`, `sanitize_provider_options`
- Produces: normalized `Config.llm_config()` with `provider`, `model`, `provider_options`, legacy `protocol`, `base_url`, and `api_key`

- [ ] **Step 1: Write failing migration and persistence tests**

```python
def test_old_mimo_config_is_inferred_without_losing_credentials(monkeypatch):
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
    config = {"llm": {
        "base_url": "https://private.test/v1",
        "api_key": "key",
        "model": "private-model",
        "protocol": "anthropic",
    }}
    Config._normalize_llm_config(config)
    assert config["llm"]["provider"] == "custom"
    assert config["llm"]["model"] == "private-model"
    assert config["llm"]["protocol"] == "anthropic"

def test_provider_options_are_allowlisted():
    config = {"llm": {
        "provider": "bedrock",
        "model": "bedrock/anthropic.claude-test",
        "provider_options": {"aws_region_name": "us-east-1", "unsafe": "drop"},
    }}
    Config._normalize_llm_config(config)
    assert config["llm"]["provider_options"] == {"aws_region_name": "us-east-1"}
```

Add a temporary `CONFIG_FILE` test that calls `save_model_config()`, reads the JSON back, and asserts `provider` and sanitized `provider_options` persist while unrelated TTS/image defaults remain present.

- [ ] **Step 2: Run tests and confirm `_normalize_llm_config` is missing**

Run `pytest tests/test_llm_config.py -q`.

Expected: failures report `Config` has no attribute `_normalize_llm_config`.

- [ ] **Step 3: Add provider defaults and LLM normalization**

Add `LLM_PROVIDER = _env("LLM_PROVIDER", "")`. Include these defaults:

```python
"llm": {
    "provider": cls.LLM_PROVIDER,
    "base_url": cls.LLM_BASE_URL or cls.ANTHROPIC_BASE_URL,
    "api_key": cls.LLM_API_KEY or cls.ANTHROPIC_API_KEY,
    "model": cls.LLM_MODEL or cls.ANTHROPIC_MODEL,
    "protocol": cls.LLM_PROTOCOL,
    "provider_options": {},
}
```

Implement `_normalize_llm_config()` with this order:

1. Use a valid explicit provider, otherwise call `infer_provider(llm)`.
2. Normalize `protocol` to `openai` or `anthropic`; only custom/legacy routing consumes it.
3. Preserve explicit Base URL and API Key; fill the provider default Base URL only when empty.
4. Canonicalize models for known providers; preserve the raw model for `custom`.
5. Filter `provider_options` through `sanitize_provider_options()`.
6. Call `_normalize_llm_config()` before the existing TTS and generation normalizers.

- [ ] **Step 4: Run config and existing voice config tests**

Run:

```bash
pytest tests/test_llm_config.py tests/test_voice_catalog.py -q
```

Expected: all pass; TTS nested normalization behavior remains unchanged.

- [ ] **Step 5: Commit provider-aware config**

```bash
git add ai-kepu-video-server/src/config.py ai-kepu-video-server/tests/test_llm_config.py
git commit -m "feat: normalize provider-aware LLM config"
```

---

### Task 3: Route Article Generation Through the Selected LiteLLM Provider

**Files:**
- Modify: `ai-kepu-video-server/src/text/generator.py:15-100`
- Create: `ai-kepu-video-server/tests/test_text_generator.py`

**Interfaces:**
- Consumes: normalized `Config.llm_config()` and `should_pass_base_url()`
- Produces: `ArticleGenerator._build_completion_kwargs(messages: list, max_tokens: int) -> dict`

- [ ] **Step 1: Write failing routing tests without making API calls**

Patch `Config.llm_config` before constructing `ArticleGenerator` and assert only the kwargs builder:

```python
def make_generator(monkeypatch, tmp_path, config):
    monkeypatch.setattr(Config, "llm_config", classmethod(lambda cls: config))
    return ArticleGenerator(config_path=str(tmp_path / "missing.json"))

def test_canonical_provider_model_is_not_reprefixed(monkeypatch, tmp_path):
    generator = make_generator(monkeypatch, tmp_path, {
        "provider": "deepseek",
        "model": "deepseek/deepseek-chat",
        "api_key": "key",
        "base_url": "https://api.deepseek.com",
        "protocol": "openai",
        "provider_options": {},
    })
    kwargs = generator._build_completion_kwargs([{"role": "user", "content": "hi"}], 100)
    assert kwargs["model"] == "deepseek/deepseek-chat"
    assert "api_base" not in kwargs

def test_project_compatible_provider_passes_base_url(monkeypatch, tmp_path):
    generator = make_generator(monkeypatch, tmp_path, {
        "provider": "mimo",
        "model": "openai/mimo-v2.5-pro",
        "api_key": "key",
        "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
        "protocol": "openai",
        "provider_options": {},
    })
    assert generator._build_completion_kwargs([], 100)["api_base"].endswith("/v1")

def test_custom_legacy_model_keeps_protocol_prefix(monkeypatch, tmp_path):
    generator = make_generator(monkeypatch, tmp_path, {
        "provider": "custom", "model": "private-model", "api_key": "key",
        "base_url": "https://private.test/v1", "protocol": "anthropic",
        "provider_options": {},
    })
    kwargs = generator._build_completion_kwargs([], 100)
    assert kwargs["model"] == "anthropic/private-model"
    assert kwargs["api_base"] == "https://private.test/v1"

def test_allowlisted_cloud_options_reach_litellm(monkeypatch, tmp_path):
    generator = make_generator(monkeypatch, tmp_path, {
        "provider": "bedrock", "model": "bedrock/anthropic.claude-test",
        "api_key": "", "base_url": "", "protocol": "openai",
        "provider_options": {"aws_region_name": "us-east-1"},
    })
    assert generator._build_completion_kwargs([], 100)["aws_region_name"] == "us-east-1"
```

- [ ] **Step 2: Run the tests and verify the kwargs builder is missing**

Run `pytest tests/test_text_generator.py -q`.

Expected: failures report `_build_completion_kwargs` does not exist or current code forces the wrong base/model.

- [ ] **Step 3: Refactor generator initialization and kwargs creation**

Store raw normalized fields instead of prebuilding an HTTP endpoint:

```python
self.provider = self.llm_config.get("provider") or "custom"
self.protocol = (self.llm_config.get("protocol") or "openai").lower()
self.api_key = self.llm_config.get("api_key") or ""
self.model = self.llm_config.get("model") or Config.LLM_MODEL or Config.ANTHROPIC_MODEL
self.base_url = (self.llm_config.get("base_url") or "").rstrip("/")
self.provider_options = self.llm_config.get("provider_options") or {}
```

Implement `_build_completion_kwargs()` so canonical IDs remain unchanged, custom unprefixed IDs use the legacy protocol prefix, Base URL is included only when `should_pass_base_url()` returns true, and sanitized provider options are copied into the kwargs. Permit missing top-level `api_key` only when the selected provider's credential schema does not require it.

Change `_call_api()` to call this builder and retain the current three-attempt retry behavior.

- [ ] **Step 4: Run generator and relevant pipeline tests**

Run:

```bash
pytest tests/test_text_generator.py tests/test_task_recovery.py tests/test_task_runtime.py -q
```

Expected: all pass; no external LLM request is made.

- [ ] **Step 5: Commit runtime provider routing**

```bash
git add ai-kepu-video-server/src/text/generator.py ai-kepu-video-server/tests/test_text_generator.py
git commit -m "feat: route LLM calls by provider"
```

---

### Task 4: Expose Provider and Live Model APIs Safely

**Files:**
- Create: `ai-kepu-video-server/src/text/provider_models.py`
- Modify: `ai-kepu-video-server/src/api/routes.py:301-355,1230-1320`
- Create: `ai-kepu-video-server/tests/test_llm_provider_api.py`

**Interfaces:**
- Consumes: provider catalog functions from Task 1
- Produces: `refresh_provider_models(provider_id: str, draft: Mapping, request_get=requests.get) -> dict`
- Produces routes `get_llm_providers()`, `get_llm_provider_models(provider_id)`, `refresh_llm_provider_models(provider_id, payload)`

- [ ] **Step 1: Write failing synchronization service tests**

Use a fake response and inject `request_get`:

```python
class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
    def json(self):
        return self._payload

def test_openai_sync_normalizes_and_merges_account_models():
    calls = []
    result = refresh_provider_models("mimo", {
        "base_url": "https://mimo.test/v1", "api_key": "secret"
    }, request_get=lambda url, **kwargs: calls.append((url, kwargs)) or FakeResponse({
        "data": [{"id": "mimo-v2.5-pro", "name": "MiMo Pro"}]
    }))
    assert calls[0][0] == "https://mimo.test/v1/models"
    assert result["models"][0]["id"] == "openai/mimo-v2.5-pro"
    assert "account" in result["models"][0]["sources"]

def test_ollama_sync_reads_tags_without_api_key():
    result = refresh_provider_models("ollama", {"base_url": "http://localhost:11434"},
        request_get=lambda *_args, **_kwargs: FakeResponse({"models": [{"name": "qwen3:8b"}]}))
    assert result["models"][0]["id"] == "ollama/qwen3:8b"

def test_failed_sync_does_not_expose_secret_or_response_body():
    with pytest.raises(ProviderModelSyncError) as error:
        refresh_provider_models("mimo", {
            "base_url": "https://mimo.test/v1", "api_key": "TOP-SECRET"
        }, request_get=lambda *_args, **_kwargs: FakeResponse({"error": "TOP-SECRET"}, 401))
    assert "TOP-SECRET" not in str(error.value)
    assert error.value.kind == "credentials"
```

Add async route tests that call route functions directly, matching the existing `test_voice_api.py` style. Assert catalog fallback, provider-not-found `404`, unsupported live sync `400`, and legacy `fetch_config_models()` behavior.

- [ ] **Step 2: Run the API tests and verify missing modules/routes**

Run `pytest tests/test_llm_provider_api.py -q`.

Expected: import or attribute failures for `provider_models` and the new route functions.

- [ ] **Step 3: Implement live adapters and sanitized errors**

Implement only the declared adapters. For `provider_id="custom"`, choose `openai` or `anthropic` from the submitted `protocol` instead of hard-coding one adapter:

- `openai`: `GET {base}/models`, bearer token when API Key exists.
- `anthropic`: `GET {base}/v1/models` or `{base}/models`, `x-api-key` plus `anthropic-version`.
- `ollama`: `GET {base}/api/tags`, no credential requirement.

Define `ProviderModelSyncError(kind, public_message, status_code)` with public kinds `credentials`, `unsupported`, `rate_limit`, `network`, and `invalid_response`. Never include `response.text`, headers, payload, submitted URL query values, or credential values in the exception string.

Merge live and local models by canonical ID, union their `sources`, retain the local label when present, and preserve deterministic sorting.

- [ ] **Step 4: Add the three new FastAPI endpoints**

Implement:

```python
@router.get("/config/llm-providers")
async def get_llm_providers():
    return {"providers": list_llm_providers()}

@router.get("/config/llm-providers/{provider_id}/models")
async def get_llm_provider_models(provider_id: str):
    if not get_provider(provider_id):
        raise HTTPException(status_code=404, detail="生文服务商不存在")
    return {"provider": provider_id, "models": list_provider_models(provider_id)}

@router.post("/config/llm-providers/{provider_id}/models/refresh")
async def refresh_llm_provider_models(provider_id: str, payload: dict = Body(...)):
    try:
        return refresh_provider_models(provider_id, payload)
    except ProviderModelSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
```

Retain `/config/models`, but delegate its LLM-compatible behavior to the custom provider adapter. Keep image callers working until Task 7 removes the frontend dependency.

- [ ] **Step 5: Run focused backend tests**

Run:

```bash
pytest tests/test_llm_provider_api.py tests/test_llm_provider_catalog.py tests/test_llm_config.py tests/test_text_generator.py -q
```

Expected: all pass and captured logs contain none of the test secrets.

- [ ] **Step 6: Commit provider APIs**

```bash
git add ai-kepu-video-server/src/text/provider_models.py ai-kepu-video-server/src/api/routes.py ai-kepu-video-server/tests/test_llm_provider_api.py
git commit -m "feat: expose LLM provider model APIs"
```

---

### Task 5: Add the Frontend Provider Data Layer

**Files:**
- Create: `ai-kepu-video-web/frontend/src/lib/llmProviderCatalog.js`
- Create: `ai-kepu-video-web/frontend/tests/llmProviderCatalog.test.mjs`
- Modify: `ai-kepu-video-web/frontend/src/api/task.js:90-125`
- Modify: `ai-kepu-video-web/frontend/src/lib/settingsConfig.js:40-125`
- Modify: `ai-kepu-video-web/frontend/tests/settingsConfig.test.mjs`

**Interfaces:**
- Produces: `normalizeProviders(payload) -> Provider[]`
- Produces: `providerGroups(providers, query) -> {key,label,items}[]`
- Produces: `mergeProviderModels(local, account, currentModel) -> Model[]`
- Produces: `applyProviderPreset(currentLlm, provider) -> llm`
- Produces: `switchProviderDraft(drafts, currentLlm, provider) -> {drafts,llm}`
- Produces: `buildProviderRefreshPayload(llm, provider) -> object`
- Produces: `isLlmProviderReady(llm, provider) -> boolean`
- Produces API clients: `getLlmProviders`, `getLlmProviderModels`, `refreshLlmProviderModels`

- [ ] **Step 1: Write failing pure interaction tests**

```javascript
test('groups and searches recommended, project, and complete providers', () => {
  const providers = normalizeProviders({ providers: [
    { id: 'deepseek', name: 'DeepSeek', group: 'recommended' },
    { id: 'mimo', name: '小米 MiMo', group: 'project' },
    { id: 'bedrock', name: 'Amazon Bedrock', group: 'all' },
  ] })
  assert.deepEqual(providerGroups(providers, '').map(group => group.key), ['recommended', 'project', 'all'])
  assert.deepEqual(providerGroups(providers, 'mimo')[0].items.map(item => item.id), ['mimo'])
})

test('merges catalog, account, and current models without losing history', () => {
  const models = mergeProviderModels(
    [{ id: 'deepseek/deepseek-chat', label: 'DeepSeek Chat', sources: ['catalog'] }],
    [{ id: 'deepseek/deepseek-chat', label: 'chat', sources: ['account'] }],
    'deepseek/legacy-model',
  )
  assert.deepEqual(models.map(model => model.id), [
    'deepseek/deepseek-chat', 'deepseek/legacy-model'
  ])
  assert.deepEqual(models[0].sources.sort(), ['account', 'catalog'])
  assert.equal(models[1].historical, true)
})

test('switching providers caches unsaved drafts and applies a first-use preset', () => {
  const current = { provider: 'mimo', api_key: 'mimo-key', model: 'openai/mimo-v2.5-pro' }
  const deepseek = {
    id: 'deepseek', default_base_url: 'https://api.deepseek.com',
    recommended_model: 'deepseek/deepseek-chat', compatibility_protocol: 'openai'
  }
  const result = switchProviderDraft({}, current, deepseek)
  assert.equal(result.drafts.mimo.api_key, 'mimo-key')
  assert.equal(result.llm.provider, 'deepseek')
  assert.equal(result.llm.api_key, '')
  assert.equal(result.llm.model, 'deepseek/deepseek-chat')
})
```

Extend `settingsConfig.test.mjs` to assert `normalizeConfig()` preserves `llm.provider`/`provider_options` and no longer requires Base URL for a native provider whose metadata does not declare it required.

- [ ] **Step 2: Run frontend tests and verify imports fail**

Run `cd ai-kepu-video-web/frontend && npm test`.

Expected: new tests fail because `llmProviderCatalog.js` and its exports do not exist.

- [ ] **Step 3: Implement pure provider/model helpers**

Use immutable objects. Model label precedence is local catalog label, then account label, then the current model ID for a generated historical entry. Sort model groups as recommended/current-account/other/historical and provider groups as recommended/project/all. Match search case-insensitively against ID and display name.

`applyProviderPreset()` must clear credentials on first use of another provider, preserve provider-specific `provider_options` only for a restored draft, and set these fields explicitly:

```javascript
return {
  provider: provider.id,
  protocol: provider.compatibility_protocol || 'openai',
  base_url: provider.default_base_url || '',
  api_key: '',
  model: provider.recommended_model || '',
  provider_options: {},
}
```

`isLlmProviderReady()` validates every `credential_fields` entry against either top-level `api_key`/`base_url` or `provider_options[field.id]`.

- [ ] **Step 4: Add API clients and update config normalization**

Add clients using exact paths:

```javascript
export const getLlmProviders = () => request({
  url: '/ai/native/video/kepu/config/llm-providers', method: 'get'
})
export const getLlmProviderModels = providerId => request({
  url: `/ai/native/video/kepu/config/llm-providers/${providerId}/models`, method: 'get'
})
export const refreshLlmProviderModels = (providerId, data) => request({
  url: `/ai/native/video/kepu/config/llm-providers/${providerId}/models/refresh`,
  method: 'post', data, timeout: 30000
})
```

Normalize `llm.provider` to the backend value or `custom`, preserve `provider_options` as an object, and make `validateConfig(config, llmProvider)` call `isLlmProviderReady()` for known providers while retaining the existing custom validation.

- [ ] **Step 5: Run all frontend unit tests**

Run `npm test`.

Expected: all existing and new Node tests pass.

- [ ] **Step 6: Commit the frontend data layer**

```bash
git add ai-kepu-video-web/frontend/src/api/task.js ai-kepu-video-web/frontend/src/lib/llmProviderCatalog.js ai-kepu-video-web/frontend/src/lib/settingsConfig.js ai-kepu-video-web/frontend/tests/llmProviderCatalog.test.mjs ai-kepu-video-web/frontend/tests/settingsConfig.test.mjs
git commit -m "feat: add LLM provider settings data layer"
```

---

### Task 6: Build Searchable Provider and Model Selection UI

**Files:**
- Create: `ai-kepu-video-web/frontend/src/components/ProviderCombobox.jsx`
- Create: `ai-kepu-video-web/frontend/src/components/ModelCombobox.jsx`
- Create: `ai-kepu-video-web/frontend/src/components/LlmProviderSettings.jsx`
- Modify: `ai-kepu-video-web/frontend/src/pages/SettingsPage.jsx:1-160,336-445,503-505`
- Modify: `ai-kepu-video-web/frontend/src/pages/delivery-pages.css:56-87`
- Modify: `ai-kepu-video-web/frontend/tests/llmProviderCatalog.test.mjs`

**Interfaces:**
- Consumes: provider helpers and API clients from Task 5
- Produces: controlled `<LlmProviderSettings value providers models syncState onChange onProviderChange onSync />`

- [ ] **Step 1: Add failing picker view-model assertions**

Add tests for result grouping and active selection:

```javascript
test('provider group output exposes stable listbox option keys', () => {
  const groups = providerGroups(normalizeProviders({ providers: [
    { id: 'mimo', name: '小米 MiMo', group: 'project', config_status: 'ready' },
    { id: 'bedrock', name: 'Amazon Bedrock', group: 'all', config_status: 'advanced' },
  ] }), '')
  assert.deepEqual(groups.flatMap(group => group.items).map(item => item.optionKey), [
    'provider:mimo', 'provider:bedrock'
  ])
  assert.equal(groups[1].items[0].statusLabel, '需要高级配置')
})

test('model groups put account availability before catalog-only models', () => {
  const grouped = modelGroups([
    { id: 'one', label: 'One', sources: ['catalog'] },
    { id: 'two', label: 'Two', sources: ['catalog', 'account'] },
  ], '')
  assert.deepEqual(grouped.map(group => group.key), ['account', 'catalog'])
})
```

- [ ] **Step 2: Run the new tests and verify missing view-model fields**

Run `npm test -- --test-name-pattern="provider group|model groups"`.

Expected: failures for `optionKey`, `statusLabel`, or `modelGroups`.

- [ ] **Step 3: Complete picker view models and build accessible comboboxes**

Both components must use a real text input with `role="combobox"`, `aria-expanded`, `aria-controls`, and a sibling `role="listbox"`. Options use `role="option"` and `aria-selected`; Escape closes the list, ArrowUp/ArrowDown changes the active option, Enter selects, and blur closes only after pointer selection completes.

`ProviderCombobox` displays provider name, ID and `statusLabel`. `ModelCombobox` accepts only an option click/keyboard selection; it must not convert arbitrary search text into a model value. A historical current model is a valid generated option.

- [ ] **Step 4: Implement the controlled LLM settings section**

`LlmProviderSettings` renders:

- provider combobox;
- Registry-driven credential fields, using `type="password"` for `secret=true`;
- model combobox;
- “验证并同步” only when `supports_live_models` is true;
- sync success/failure status without clearing the picker;
- a `<details>` advanced summary containing provider ID, connection mode, protocol and Base URL;
- editable protocol/Base URL/model only when `provider.id === "custom"`.

All updates call `onChange(nextLlm)`; the component owns search/open UI state only.

- [ ] **Step 5: Integrate provider loading, drafts and model synchronization in SettingsPage**

Load config, voices and clones together. Fetch providers through a caught promise so provider-catalog failure does not reject the whole settings page; the fallback array contains a synthetic entry for the current LLM config plus the custom-compatible entry. Initialize a `useRef({ [currentProvider]: currentLlm })` draft map. On provider selection call `switchProviderDraft()`, then fetch local models. Keep separate `localModels` and `accountModels`; derive display models with `mergeProviderModels()`. When the selected provider has no current model, choose its available `recommended_model`; if that value is absent from the returned models, choose the first local model. Never replace a non-empty saved or draft model.

On sync, send `buildProviderRefreshPayload(form.llm, selectedProvider)`. On failure, keep both model arrays and the selected model unchanged. On save, call `validateConfig(normalized, selectedProvider)`.

Remove the old LLM `ModelField` input/list pair. Keep the image path unchanged until Task 7.

- [ ] **Step 6: Add responsive styles and build**

Add `.provider-combobox`, `.provider-combobox-list`, `.provider-option`, `.model-option`, `.settings-provider-credentials`, `.settings-sync-status`, and `.settings-advanced` styles. Limit list height with scrolling, keep the list above neighboring cards, and collapse credential grids to one column at `max-width: 766px`.

Run:

```bash
npm test
npm run build
```

Expected: all tests pass and Vite produces `dist/` without JSX/import errors.

- [ ] **Step 7: Commit the selectable LLM UI**

```bash
git add ai-kepu-video-web/frontend/src/components/ProviderCombobox.jsx ai-kepu-video-web/frontend/src/components/ModelCombobox.jsx ai-kepu-video-web/frontend/src/components/LlmProviderSettings.jsx ai-kepu-video-web/frontend/src/pages/SettingsPage.jsx ai-kepu-video-web/frontend/src/pages/delivery-pages.css ai-kepu-video-web/frontend/tests/llmProviderCatalog.test.mjs
git commit -m "feat: add searchable provider model picker"
```

---

### Task 7: Move Fixed Image and TTS Technical Fields Into Advanced Settings

**Files:**
- Create: `ai-kepu-video-web/frontend/src/components/AdvancedSettings.jsx`
- Modify: `ai-kepu-video-web/frontend/src/lib/settingsConfig.js:1-35,110-190`
- Modify: `ai-kepu-video-web/frontend/tests/settingsConfig.test.mjs`
- Modify: `ai-kepu-video-web/frontend/src/pages/SettingsPage.jsx:441-476,507-523`
- Modify: `ai-kepu-video-web/frontend/src/pages/delivery-pages.css`

**Interfaces:**
- Produces: `AGNES_PRESET`
- Produces: `restoreAgnesPreset(config) -> config`
- Produces: `restoreMimoTechnicalPreset(config) -> config`
- Produces: `<AdvancedSettings title summary onRestore>{children}</AdvancedSettings>`

- [ ] **Step 1: Write failing fixed-preset tests**

```javascript
test('restores fixed Agnes endpoint and model without changing key or size', () => {
  const config = normalizeConfig({ image: {
    api_url: 'https://custom.test/images', api_key: 'keep-key',
    model: 'custom-image', size: '1024x1024'
  } })
  const restored = restoreAgnesPreset(config)
  assert.equal(restored.image.api_url, AGNES_PRESET.api_url)
  assert.equal(restored.image.model, AGNES_PRESET.model)
  assert.equal(restored.image.api_key, 'keep-key')
  assert.equal(restored.image.size, '1024x1024')
})

test('restores MiMo technical fields without changing credentials or voice', () => {
  const config = normalizeConfig({ tts: { mimo: {
    api_key: 'keep-key', default_voice: 'Mia', base_url: 'bad',
    model: 'bad', clone_model: 'bad-clone', format: 'mp3'
  } } })
  const restored = restoreMimoTechnicalPreset(config)
  assert.equal(restored.tts.mimo.api_key, 'keep-key')
  assert.equal(restored.tts.mimo.default_voice, 'Mia')
  assert.equal(restored.tts.mimo.model, MIMO_PRESET.model)
  assert.equal(restored.tts.mimo.clone_model, MIMO_PRESET.clone_model)
  assert.equal(restored.tts.mimo.format, MIMO_PRESET.format)
})
```

- [ ] **Step 2: Run tests and confirm preset exports are missing**

Run `npm test -- --test-name-pattern="restores fixed|restores MiMo"`.

Expected: import failures for `AGNES_PRESET`, `restoreAgnesPreset`, or `restoreMimoTechnicalPreset`.

- [ ] **Step 3: Implement preset helpers and AdvancedSettings**

Define:

```javascript
export const AGNES_PRESET = {
  api_url: 'https://apihub.agnes-ai.com/v1/images/generations',
  model: 'agnes-image-2.1-flash',
}
```

Restore helpers replace only documented technical fields. `AdvancedSettings` uses native `<details>`/`<summary>`, displays the current summary, and renders an optional “恢复预置” button that calls `event.preventDefault()` before `onRestore()`.

- [ ] **Step 4: Simplify image and TTS sections**

Image ordinary fields: fixed `Agnes / agnes-image-2.1-flash` summary, API Key and image size. Advanced fields: API URL and model plus restore.

Doubao ordinary fields: auth method and its credential inputs. Advanced fields: API URL and Cluster.

MiMo ordinary fields: API Key; the existing voice library, speed and style controls remain where they are. Advanced fields: Base URL, TTS model, clone model and format plus restore.

Do not change voice preview, clone, enable/disable, default voice, or TTS test payloads.

- [ ] **Step 5: Run frontend regressions and build**

Run:

```bash
npm test
npm run build
```

Expected: all tests pass; no old model-fetch state remains for the image section.

- [ ] **Step 6: Commit progressive disclosure changes**

```bash
git add ai-kepu-video-web/frontend/src/components/AdvancedSettings.jsx ai-kepu-video-web/frontend/src/lib/settingsConfig.js ai-kepu-video-web/frontend/tests/settingsConfig.test.mjs ai-kepu-video-web/frontend/src/pages/SettingsPage.jsx ai-kepu-video-web/frontend/src/pages/delivery-pages.css
git commit -m "feat: simplify fixed model settings"
```

---

### Task 8: Document, Regress and Verify the Complete Flow

**Files:**
- Modify: `ai-kepu-video-server/.env.example:5-14`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: all previous tasks
- Produces: documented provider configuration contract and evidence that existing generation settings still work

- [ ] **Step 1: Update environment and repository instructions**

Add `LLM_PROVIDER=` to `.env.example`, with a comment that it is optional and inferred for legacy configuration.

In both `AGENTS.md` and `CLAUDE.md`, replace the old “protocol-first” description with the exact rules implemented:

- `llm.provider` selects the LiteLLM provider or project extension.
- Known models are saved as canonical LiteLLM IDs.
- `protocol/base_url/model` remain editable for custom compatible endpoints.
- Local LiteLLM metadata is the default catalog; live model sync is optional.
- Provider secrets and sync request data must not be logged.
- Existing MiMo, Agnes and TTS architecture notes remain unchanged.

Copy one file to the other through `apply_patch`-equivalent edits and verify equality; do not edit only one.

- [ ] **Step 2: Run the full backend suite**

Run:

```bash
cd ai-kepu-video-server
source venv/bin/activate
pytest tests -q
```

Expected: all existing and new tests pass. If a failure comes from a user-owned test file absent from the isolated worktree, record that distinction and still run every tracked test.

- [ ] **Step 3: Run the full frontend suite and production build**

Run:

```bash
cd ai-kepu-video-web/frontend
npm test
npm run build
```

Expected: all tests pass and Vite finishes with a successful `dist/` build.

- [ ] **Step 4: Verify documentation and secret-safe diffs**

Run:

```bash
cmp -s AGENTS.md CLAUDE.md
git diff --check
git grep -n "TOP-SECRET\|Authorization: Bearer\|api_key.*print" -- ':!docs/superpowers/plans/*'
```

Expected: `cmp` and `git diff --check` exit zero; grep finds no committed secret/logging fixture outside tests.

- [ ] **Step 5: Commit documentation**

```bash
git add AGENTS.md CLAUDE.md ai-kepu-video-server/.env.example
git commit -m "docs: describe selectable LLM providers"
```

- [ ] **Step 6: Start the implementation worktree services and smoke-test APIs**

Stop ports `2001` and `2002`, start backend first on `2002`, then frontend on `2001`. If the isolated worktree lacks local credentials, source the main checkout's existing backend `.env` into the process environment without printing it.

Run:

```bash
curl -fsS http://localhost:2002/health
curl -fsS http://localhost:2002/ai/native/video/kepu/config/llm-providers
curl -fsS http://localhost:2002/ai/native/video/kepu/config/llm-providers/mimo/models
curl -fsS http://localhost:2001/
```

Expected: health is `ok`; provider response contains `mimo`, `deepseek`, and catalog-derived providers; MiMo models contain `openai/mimo-v2.5-pro`; frontend returns HTML.

- [ ] **Step 7: Perform browser acceptance on the settings page**

Open `http://localhost:2001/settings` and verify:

1. Provider search shows common, project and all-provider groups.
2. Selecting MiMo immediately selects `MiMo V2.5 Pro` without manual model input.
3. “验证并同步” either merges account models or shows a sanitized failure while preserving the selected model.
4. Switching to DeepSeek and back restores the unsaved MiMo draft.
5. Custom compatible mode exposes protocol, Base URL and model inputs.
6. Agnes technical fields and MiMo/Doubao technical fields are collapsed under advanced settings.
7. Saving, refreshing and reopening preserves the selected provider and model.
8. Voice preview and clone sections still load and remain interactive.

Do not overwrite the user's active saved provider during acceptance. Capture the original config before the save/reload check and restore it through the API afterward.

- [ ] **Step 8: Final branch audit**

Run `git status --short` and `git log --oneline --decorate -10`.

Expected: only intentional ignored runtime/build artifacts remain; implementation commits are ordered by the eight tasks; the main checkout's user changes remain untouched.

Use `superpowers:verification-before-completion` before claiming completion, then use `superpowers:finishing-a-development-branch` to present merge/PR/keep options.
