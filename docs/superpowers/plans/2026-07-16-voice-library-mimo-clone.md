# Voice Library and MiMo Clone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-aware TTS catalog with cached previews, configurable defaults and overrides, plus a reusable local MiMo voice-clone library.

**Architecture:** Keep provider credentials in the existing runtime JSON, migrate SQLite voice metadata to provider-aware records, and resolve every task voice through a canonical voice key. A focused clone service stores normalized local reference WAV files and only constructs MiMo DataURLs in memory at request time; a shared React voice picker drives Settings, Production, and Preview behavior.

**Tech Stack:** Python 3.9, FastAPI, SQLite, requests, FFmpeg/ffprobe, React 19, Vite 4, Node test runner.

## Global Constraints

- Frontend remains on port `2001`; backend remains on port `2002`.
- Backend entrypoint remains `api_server.py` and uses the existing virtual environment.
- Local SQLite and local media storage remain the only persistence systems.
- Failed or interrupted work must retain generated text, images, audio, reference files, previews, and asset records.
- `AGENTS.md` and `CLAUDE.md` must remain identical.
- Existing bare `voice_type` values and query-param segment revoice calls remain compatible.
- Do not persist or log API keys, reference-audio Base64, or DataURLs outside existing runtime configuration behavior.

---

### Task 1: Provider-aware catalog and configuration

**Files:**
- Create: `ai-kepu-video-server/src/draft/voice_catalog.py`
- Modify: `ai-kepu-video-server/src/config.py`
- Modify: `ai-kepu-video-server/src/database/sqlite_client.py`
- Test: `ai-kepu-video-server/tests/test_voice_catalog.py`

**Interfaces:**
- Produces `parse_voice_key(value) -> VoiceSelection`, `build_voice_key(provider, voice_id) -> str`, `normalize_tts_options(options, provider_config) -> dict`, and `speed_instruction(level) -> str`.
- Produces SQLite methods `list_tts_voices(provider=None, include_disabled=False)`, `set_voice_availability(keys, defaults)`, and `find_tts_voice(provider, voice_id)`.
- Extends runtime config with `enabled_providers`, `preview_text`, Doubao `speed_level/volume_ratio`, and MiMo `speed_level/clone_model`.

- [ ] Write failing tests proving canonical key parsing, bare-ID compatibility, five-level speed normalization, config migration, 19 seeded preset rows, and six initially enabled rows.
- [ ] Run `venv/bin/python -m pytest tests/test_voice_catalog.py -q` and confirm failures are caused by missing catalog interfaces.
- [ ] Implement immutable catalog constants, provider/key resolution, option normalization, and provider-specific speed mapping.
- [ ] Add transactional schema migration for provider/language/source/capabilities/preview metadata with `UNIQUE(provider, voice_id)`; preserve existing ten Doubao records and seed nine MiMo records.
- [ ] Add availability/default persistence and config validation without requiring disabled-provider credentials.
- [ ] Run the targeted test, then the complete backend test suite; expect zero failures.
- [ ] Commit catalog/config/database changes with `feat: add provider-aware voice catalog`.

### Task 2: Local MiMo clone storage and validation

**Files:**
- Create: `ai-kepu-video-server/src/draft/voice_clone.py`
- Modify: `ai-kepu-video-server/src/database/sqlite_client.py`
- Test: `ai-kepu-video-server/tests/test_voice_clone.py`

**Interfaces:**
- Produces `VoiceCloneStore.create(name, upload_path, consent_confirmed)`, `replace_reference(clone_id, upload_path)`, `get(clone_id)`, `list(include_hidden=False)`, `update(clone_id, patch)`, and `delete_or_hide(clone_id)`.
- Produces `reference_data_url(clone_id) -> str` and a clone record with states `draft`, `ready`, `failed`, `hidden`.
- Stores canonical references at `data/media/_voice_clones/<clone_id>/reference.wav` and previews at `preview.wav`.

- [ ] Write failing tests for MP3/WAV/WebM normalization, missing audio tracks, the 10 MB post-Base64 limit, required consent, state transitions, replacement invalidation, and referenced-clone soft deletion.
- [ ] Run the targeted tests and confirm missing store/validation failures.
- [ ] Add `tts_voice_clones`, task option snapshot, and segment audio option snapshot schema migrations and database methods.
- [ ] Implement FFmpeg normalization to mono WAV, ffprobe validation, atomic file replacement, local path guards, and in-memory DataURL construction.
- [ ] Run targeted and full backend tests; expect zero failures and no writes outside temporary test directories.
- [ ] Commit with `feat: add local MiMo voice clone storage`.

### Task 3: Provider routing, preview cache, and clone synthesis

**Files:**
- Modify: `ai-kepu-video-server/src/draft/voiceover.py`
- Create: `ai-kepu-video-server/src/draft/voice_preview.py`
- Test: `ai-kepu-video-server/tests/test_voiceover.py`

**Interfaces:**
- Extends `VoiceOverGenerator.generate(text, filename=None, voice_type=None, speed_level=None, volume_ratio=None, style_prompt=None)`.
- Produces per-call provider dispatch for `mimo:*`, `doubao:*`, and `mimo-clone:*`.
- Produces `VoicePreviewService.generate(voice_type, text, tts_options, config_override=None) -> {url, path, cached}`.

- [ ] Write failing request-shape tests proving Doubao numeric speed/volume, MiMo style-speed concatenation, MiMo clone model selection, local reference DataURL inclusion, and no Base64 in logs.
- [ ] Write failing cache tests proving identical inputs reuse a WAV while changed voice/text/model/options create a new entry.
- [ ] Run targeted tests and confirm failures reflect missing dispatch/cache behavior.
- [ ] Refactor `VoiceOverGenerator` so provider is resolved per call, preserving existing retries and response parsing.
- [ ] Implement clone synthesis through `mimo-v2.5-tts-voiceclone` and cache previews below `data/media/_voice_previews/`.
- [ ] Run targeted and full backend tests; expect zero failures.
- [ ] Commit with `feat: route TTS by voice and cache previews`.

### Task 4: APIs and task option snapshots

**Files:**
- Modify: `ai-kepu-video-server/src/api/models.py`
- Modify: `ai-kepu-video-server/src/api/routes.py`
- Modify: `ai-kepu-video-server/src/api/task_manager.py`
- Modify: `ai-kepu-video-server/src/api/task_executor.py`
- Test: `ai-kepu-video-server/tests/test_voice_api.py`

**Interfaces:**
- Adds `TTSOptions` with `speed_level`, `volume_ratio`, and `style_prompt` to task creation and task responses.
- Adds catalog endpoints `/voices`, `/voices/availability`, `/voices/preview` and clone endpoints `/voice-clones` plus item preview/update/reference/delete operations.
- Segment revoice accepts a JSON body and retains the old query-param `voice_type` fallback.

- [ ] Write failing API tests for catalog filtering, bulk availability, unsaved-config preview, clone multipart lifecycle, task snapshots, segment snapshots, and old query compatibility.
- [ ] Run targeted tests and confirm missing route/schema failures.
- [ ] Implement request/response models, API validation, safe multipart staging, catalog merging, and clone lifecycle routes.
- [ ] Resolve and snapshot effective voice/options at task creation; propagate snapshots through resume, generation, asset persistence, task responses, and segment revoice.
- [ ] Confirm disabled voices are rejected for new tasks but old task snapshots remain usable.
- [ ] Run targeted and full backend tests; expect zero failures.
- [ ] Commit with `feat: expose voice catalog and clone APIs`.

### Task 5: Frontend catalog utilities and shared picker

**Files:**
- Create: `ai-kepu-video-web/frontend/src/lib/voiceCatalog.js`
- Create: `ai-kepu-video-web/frontend/src/components/VoicePicker.jsx`
- Create: `ai-kepu-video-web/frontend/src/components/voice-picker.css`
- Modify: `ai-kepu-video-web/frontend/src/api/task.js`
- Test: `ai-kepu-video-web/frontend/tests/voiceCatalog.test.mjs`

**Interfaces:**
- Produces `normalizeVoiceCatalog`, `groupVisibleVoices`, `mergeTtsOptions`, and `buildVoiceTaskPayload`.
- `VoicePicker` accepts `voices`, `value`, `ttsOptions`, `onChange`, `onOptionsChange`, `onPreview`, `playingVoice`, and `showAdvanced`.
- Adds API clients for voice catalog, availability, preview, and clone CRUD/preview/reference calls.

- [ ] Write failing Node tests for provider grouping, visibility/status boundaries, canonical IDs, inherited option payloads, and one-active-preview state transitions.
- [ ] Run `npm test -- tests/voiceCatalog.test.mjs` and confirm missing-module failures.
- [ ] Implement pure catalog utilities and API methods.
- [ ] Implement an accessible card picker with provider sections, playback controls, loading/error states, and provider-specific advanced fields.
- [ ] Run frontend tests and build; expect zero failures.
- [ ] Commit with `feat: add shared voice picker`.

### Task 6: Settings catalog and MiMo clone management

**Files:**
- Modify: `ai-kepu-video-web/frontend/src/lib/settingsConfig.js`
- Modify: `ai-kepu-video-web/frontend/src/pages/SettingsPage.jsx`
- Modify: `ai-kepu-video-web/frontend/src/pages/delivery-pages.css`
- Test: `ai-kepu-video-web/frontend/tests/settingsConfig.test.mjs`

**Interfaces:**
- Settings retains both provider configurations simultaneously and saves provider defaults separately from voice availability.
- MiMo clone creation supports MP3/WAV upload and browser MediaRecorder blobs, consent confirmation, preview validation, rename, enable/hide, replace, and delete.

- [ ] Extend failing settings tests for enabled providers, per-provider defaults, clone model, preview text, and validation of only enabled providers.
- [ ] Run targeted tests and confirm expected normalization/validation failures.
- [ ] Replace the provider two-way switch with Doubao/MiMo tabs and readiness indicators.
- [ ] Add filters, select-all/select-none, default controls, preset preview cards, and the MiMo clone library panel.
- [ ] Implement microphone permission, start/stop/re-record, local source playback, upload replacement, consent gating, retry, and persisted clone states.
- [ ] Run all frontend tests and build; expect zero failures.
- [ ] Commit with `feat: manage TTS voices and MiMo clones`.

### Task 7: Production and Preview integration

**Files:**
- Modify: `ai-kepu-video-web/frontend/src/pages/ProductionSetupPage.jsx`
- Modify: `ai-kepu-video-web/frontend/src/pages/PreviewPage.jsx`
- Modify: `ai-kepu-video-web/frontend/src/pages/creation-flow.css`
- Modify: `ai-kepu-video-web/frontend/src/pages/preview-page.css`
- Modify: `ai-kepu-video-web/frontend/src/utils/projectDrafts.js`
- Test: `ai-kepu-video-web/frontend/tests/voiceCatalog.test.mjs`

**Interfaces:**
- Drafts store canonical `voice_type`, display name, and optional task `tts_options`.
- Preview shows effective segment/task voice and sends JSON snapshot overrides when regenerating audio.

- [ ] Add failing tests for draft option inheritance, task payload overrides, clone voice grouping, and segment revoice payloads.
- [ ] Run targeted tests and confirm expected payload failures.
- [ ] Replace Production's select with `VoicePicker`, inherit provider defaults, and submit canonical voice/options.
- [ ] Integrate the same picker into Preview without removing existing saved-asset/recovery behavior; display actual segment override and preserve existing user changes when merging.
- [ ] Run all frontend tests and build; expect zero failures.
- [ ] Commit with `feat: select TTS voices per task and segment`.

### Task 8: Documentation, full verification, and live acceptance

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Test: complete backend/frontend suites and live services.

- [ ] Update both agent documents identically with canonical voice keys, enabled-provider semantics, MiMo clone model/DataURL behavior, 10 MB limit, local paths, and asset-preservation rules.
- [ ] Run `cmp AGENTS.md CLAUDE.md`; expect exit code 0.
- [ ] Run backend `python -m pytest tests -q`; expect zero failures.
- [ ] Run frontend `npm test` and `npm run build`; expect zero failures.
- [ ] Start isolated backend/frontend on non-conflicting verification ports, then probe health, full/admin catalog counts, and clone/catalog routes.
- [ ] Generate one MiMo preset preview, one Doubao preview, and one clone preview from a non-personal local WAV; validate each with `ffprobe`.
- [ ] Create a short clone-voice task and revoice one segment with Doubao; verify SQLite snapshots, asset records, media URLs, and restart persistence.
- [ ] Re-read the design spec requirement by requirement and record any missing evidence before declaring completion.
- [ ] Commit docs and final fixes with `docs: document voice catalog and cloning`.
