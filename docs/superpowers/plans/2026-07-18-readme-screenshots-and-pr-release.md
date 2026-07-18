# InsightCut README, Screenshots, and PR Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the completed provider/model and multi-provider TTS work with an accurate, human-written README, sanitized current screenshots, and a verified Pull Request merged into `master`.

**Architecture:** Keep the existing feature implementation and showcase assets intact. Rewrite only the root README, add or replace repository screenshots captured from the running local product, then use repository tests plus browser checks as the release gate before pushing, opening, and merging the PR.

**Tech Stack:** Markdown, React 19, React Router 7, Vite 4, FastAPI, SQLite, LiteLLM, Agnes Image, Doubao TTS, Xiaomi MiMo TTS, FFmpeg, GitHub CLI.

## Global Constraints

- Preserve the existing generated video showcase, thumbnails, fallback MP4 links, and the product principles around editable assets, recoverable failures, local-first storage, and dual MP4/Jianying draft output.
- Use a natural project-maintainer voice; do not use generic promotional copy, invented metrics, or claim unfinished features.
- Frontend is React 19 + React Router 7 + Vite 4 on port `2001`; backend is FastAPI from `api_server.py` on port `2002`.
- Screenshots must come from the current running product and must not expose API keys, access tokens, complete account identifiers, local paths, or user voice files.
- Do not stage runtime symlinks `ai-kepu-video-server/output` or `ai-kepu-video-server/venv`.
- Do not touch or overwrite unrelated dirty files in the primary checkout.
- `AGENTS.md` and `CLAUDE.md` must remain byte-identical.
- Push `codex/llm-provider-catalog`, create a PR targeting `master`, verify it, and merge it through GitHub.

---

### Task 1: Rewrite the Root README Around the Real Product

**Files:**
- Modify: `README.md`
- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-07-16-multi-provider-voice-library-and-mimo-clone-design.md`
- Read: `docs/superpowers/specs/2026-07-17-llm-provider-catalog-and-model-picker-design.md`

**Interfaces:**
- Consumes: Current implemented behavior documented in `AGENTS.md`, existing showcase files under `docs/showcase/`, and current screenshots under `design-qa-artifacts/`.
- Produces: A single public landing document whose local links resolve from the repository root and whose usage commands match the actual project layout.

- [ ] **Step 1: Record the stale facts and assets that must be preserved**

Run:

```bash
rg -n "Vue 3|React 19|Generated Results|生成效果展示|showcase|Recoverable failures|Local Development|TTS" README.md
find docs/showcase -type f -maxdepth 3 | sort
```

Expected: the old `Vue 3` stack entry is visible, and all four thumbnails plus all four MP4 examples are present before editing.

- [ ] **Step 2: Replace the README information architecture**

Rewrite `README.md` using this heading order and content contract:

```markdown
# InsightCut

> 把文稿真正做成可修改、可恢复、可继续精修的视频项目。

## InsightCut 是什么
## 为什么不是普通的一键成片
## 现在可以做什么
## 产品截图
## 真实生成效果
## 从零开始使用
### 1. 准备环境
### 2. 启动后端
### 3. 启动前端
### 4. 配置模型
### 5. 完成第一次生成
## 生文模型怎么配置
## 配音、试听与声音克隆
### 豆包 TTS
### 小米 MiMo TTS
### MiMo 声音克隆
## 失败以后，已经生成的内容怎么办
## 输出内容
## 技术栈
## 项目结构
## 测试与构建
## 本地数据与安全
## 更多文档
## 当前阶段
## License
```

The finished copy must state these concrete facts:

- The homepage starts with a topic or manuscript, then moves through production setup, storyboard/assets, preview, and export.
- Generated scripts, prompts, images, audio, subtitles, and drafts remain visible when a later stage fails.
- The existing four generated video examples, durations, ratios, online Showcase URLs, thumbnails, and fallback MP4 links remain in the README.
- Normal LLM configuration is provider first, then model; “验证并同步” merges account models into the same picker and excludes image, ASR, TTS, VoiceClone, and VoiceDesign model families.
- Custom OpenAI-compatible and Anthropic-compatible endpoints remain available for advanced use.
- Doubao and MiMo can both be enabled. Preset voices can be selected per provider and previewed; speed is shared, Doubao has volume, and MiMo has a style prompt.
- MiMo cloning requires explicit voice authorization, accepts MP3/WAV or browser recording, converts to 24 kHz mono WAV, and can only be enabled after a successful preview.
- Credentials, local SQLite data, media, logs, generated output, and clone reference audio must not be committed.
- The tech stack table says React 19, React Router 7, Vite 4, FastAPI, SQLite, LiteLLM, Agnes Image, Doubao/MiMo TTS, FFmpeg, and pyJianYingDraft.

- [ ] **Step 3: Check the README against the source of truth**

Run:

```bash
rg -n "Vue 3|localhost:2001|localhost:2002|React 19|VoiceClone|声音克隆|豆包|MiMo|showcase" README.md
rg -n "mimo_default|冰糖|茉莉|苏打|白桦|Mia|Chloe|Milo|Dean|爽快思思|讲解小明" AGENTS.md
```

Expected: no `Vue 3` result; correct ports, React stack, provider/model, TTS, showcase, and cloning sections are present; README facts agree with `AGENTS.md`.

- [ ] **Step 4: Review the copy as a maintainer**

Read the README top to bottom and remove repeated slogans, repeated “支持” list openings, empty adjectives, or statements that cannot be demonstrated by code, screenshots, videos, or the documented workflow. Preserve the original product viewpoint but connect every claim to a visible behavior.

- [ ] **Step 5: Commit the README draft**

```bash
git add README.md
git commit -m "docs: refresh project guide for model and voice workflows"
```

Expected: only `README.md` is included in this commit.

---

### Task 2: Capture Sanitized Current Settings Screenshots

**Files:**
- Replace: `design-qa-artifacts/current-settings.png`
- Create: `design-qa-artifacts/current-settings-tts.png`
- Modify: `README.md`

**Interfaces:**
- Consumes: Running frontend at `http://localhost:2001/settings` and backend at `http://localhost:2002`.
- Produces: A current settings overview and a readable TTS detail image referenced by the README.

- [ ] **Step 1: Verify the services and safe screenshot state**

Use the in-app Browser against `http://localhost:2001/settings`. Confirm the page renders the LLM provider combobox, model combobox, Agnes image section, and the dual-provider TTS section. Do not inspect cookies, local storage, saved passwords, or raw credential values.

Before capture, change any visible account identifier input to an obviously fake example such as `1234567890` without saving. Leave secret inputs masked. Ensure no dropdown shows a credential-bearing URL or error message.

Expected: the page is fully loaded, secrets remain masked, and no complete real account identifier is visible.

- [ ] **Step 2: Capture the model settings overview**

Capture a desktop-width image at approximately 1536 px wide showing:

- the API configuration header and readiness summary;
- LLM provider and model selectors with visible dropdown affordances;
- the “验证并同步” action;
- the Agnes image section;
- the beginning of the TTS provider section.

Save it as `design-qa-artifacts/current-settings.png`. Close temporary menus before capture so controls remain readable.

- [ ] **Step 3: Capture the TTS and voice-clone detail**

Scroll to the TTS section and capture a readable image showing both provider toggles, the default-provider control, voice selection/preview controls, parameter controls, and the MiMo voice-clone entry. Keep all secrets masked and omit real local audio filenames.

Save it as `design-qa-artifacts/current-settings-tts.png`, then reload the page to discard unsaved safe example values.

- [ ] **Step 4: Inspect the resulting files**

Run:

```bash
file design-qa-artifacts/current-settings.png design-qa-artifacts/current-settings-tts.png
sips -g pixelWidth -g pixelHeight design-qa-artifacts/current-settings.png design-qa-artifacts/current-settings-tts.png
ls -lh design-qa-artifacts/current-settings.png design-qa-artifacts/current-settings-tts.png
```

Expected: both are non-empty PNG images, wide enough to remain readable in GitHub, and neither is an empty/loading/error capture.

- [ ] **Step 5: Add the screenshots to the README**

Place the model overview and TTS detail together in the product screenshot section:

```markdown
| 模型配置 | 配音、试听与声音克隆 |
| --- | --- |
| ![InsightCut 模型配置](design-qa-artifacts/current-settings.png) | ![InsightCut 配音与声音克隆](design-qa-artifacts/current-settings-tts.png) |
```

- [ ] **Step 6: Commit the screenshot update**

```bash
git add README.md design-qa-artifacts/current-settings.png design-qa-artifacts/current-settings-tts.png
git commit -m "docs: add current model and voice settings screenshots"
```

Expected: the commit contains the README references and exactly the two settings images.

---

### Task 3: Run the Complete Release Verification

**Files:**
- Verify: `README.md`
- Verify: `AGENTS.md`
- Verify: `CLAUDE.md`
- Verify: `design-qa-artifacts/current-settings.png`
- Verify: `design-qa-artifacts/current-settings-tts.png`

**Interfaces:**
- Consumes: All feature commits plus Tasks 1–2.
- Produces: Fresh evidence that documentation, screenshots, frontend, backend, and the real model picker are ready for the PR.

- [ ] **Step 1: Validate repository-relative README links**

Check every relative Markdown target in `README.md` against the worktree. Confirm all referenced screenshot, thumbnail, MP4, and documentation files exist. Open the README diff and ensure the four original examples are still present.

Run:

```bash
git diff master...HEAD -- README.md
find docs/showcase/thumbs docs/showcase/videos -type f | sort
git diff --check
cmp -s AGENTS.md CLAUDE.md
```

Expected: all eight showcase media files remain; no whitespace errors; `cmp` exits `0`.

- [ ] **Step 2: Check the staged and committed diff for sensitive/runtime files**

Run:

```bash
git status --short
git diff --name-only master...HEAD
git diff master...HEAD -- README.md docs design-qa-artifacts | rg -n "sk-[A-Za-z0-9]|Bearer [A-Za-z0-9]|Access Token.*[^* ]|API Key.*[A-Za-z0-9]{16,}|/Users/"
```

Expected: only the known runtime symlinks remain untracked; the sensitive-pattern scan returns no credential or local-path matches in published materials.

- [ ] **Step 3: Run the backend suite**

Run from `ai-kepu-video-server/`:

```bash
venv/bin/python -m pytest -q
```

Expected: all backend tests pass with zero failures.

- [ ] **Step 4: Run the frontend suite and production build**

Run from `ai-kepu-video-web/frontend/`:

```bash
npm test
npm run build
```

Expected: all Node tests pass and Vite exits `0` after producing the production bundle.

- [ ] **Step 5: Re-run the real browser acceptance check**

On `/settings`, select Xiaomi MiMo, use “验证并同步”, and inspect the visible model list. Confirm the dropdown affordance is visible and the account list contains only text-generation models such as `openai/mimo-v2.5-pro` and `openai/mimo-v2.5`; ASR, TTS, VoiceClone, and VoiceDesign entries must not appear.

Also open the manuscript, assets, production, and preview routes referenced by README screenshots to ensure none renders an error state.

- [ ] **Step 6: Record final release status**

Run:

```bash
git status --short
git log --oneline --decorate -8
git diff --check
```

Expected: documentation and screenshot commits are present; only runtime symlinks are untracked; no source changes remain unstaged.

---

### Task 4: Push, Open the PR, and Merge It

**Files:**
- Verify only: entire branch diff against `master`

**Interfaces:**
- Consumes: Verified branch `codex/llm-provider-catalog`.
- Produces: A merged GitHub Pull Request and a remote `master` that contains the feature branch commits.

- [ ] **Step 1: Inspect the outgoing branch one final time**

Run:

```bash
git diff --stat master...HEAD
git diff --name-status master...HEAD
git log --oneline master..HEAD
```

Expected: the diff contains only the model/TTS implementation, tests, approved design/plan docs, README, and sanitized screenshots; it excludes SQLite, generated media, credentials, and runtime symlinks.

- [ ] **Step 2: Push the feature branch**

```bash
git push -u origin codex/llm-provider-catalog
```

Expected: Git reports the remote tracking branch and provides or updates the PR comparison URL.

- [ ] **Step 3: Create the PR**

Create `/private/tmp/insightcut-llm-provider-pr-body.md` with this maintainer-written body, then use it for a non-draft PR targeting `master`:

```markdown
## 这次改了什么
- 生文服务商与模型改为可搜索选择，支持账号模型同步和自定义兼容接口
- 同步结果只保留生文模型，排除图片、ASR、TTS 与声音克隆模型
- 豆包与 MiMo 配音可同时开放，加入音色试听、参数快照和 MiMo 声音克隆
- 更新 README、使用方法、真实界面截图，并保留原有视频示例和产品设计理念

## 怎么验证
- 后端完整测试
- 前端完整测试
- Vite 生产构建
- 本地浏览器验证 MiMo 同步只返回生文模型

## 数据与兼容
- 旧配置继续兼容
- API 密钥、声音克隆参考音频、数据库和生成媒体仍只保存在本地
```

Run:

```bash
gh pr create --base master --head codex/llm-provider-catalog --title "feat: improve model configuration and voice workflows" --body-file /private/tmp/insightcut-llm-provider-pr-body.md
```

Expected: GitHub returns the new PR URL.

- [ ] **Step 4: Check PR state and mergeability**

Run:

```bash
gh pr view --json number,url,state,isDraft,mergeable,mergeStateStatus,baseRefName,headRefName,statusCheckRollup
gh pr checks
```

Expected: base is `master`, head is `codex/llm-provider-catalog`, the PR is open and non-draft, required checks are successful or no required checks are configured, and GitHub reports it as mergeable.

- [ ] **Step 5: Merge the PR**

```bash
gh pr merge --merge
```

Expected: GitHub reports the PR merged successfully. Preserve the local worktree for post-merge verification and do not alter the dirty primary checkout.

- [ ] **Step 6: Verify the remote default branch contains the work**

Run:

```bash
git fetch origin master
git merge-base --is-ancestor HEAD origin/master
gh pr view --json url,state,mergedAt,mergeCommit
```

Expected: `merge-base --is-ancestor` exits `0`, and the PR state is `MERGED` with a merge timestamp and merge commit.
