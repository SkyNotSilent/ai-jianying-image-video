# InsightCut Task Recovery And Project Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-segment generation checkpoints, user-triggered task resume after interruption, and confirmed deletion of a project plus all safely attributable local files.

**Architecture:** Persist generated script metadata and every segment checkpoint in SQLite, then rebuild the existing pipeline from those checkpoints when `POST /tasks/{task_id}/resume` is called. A small thread-safe runtime registry owns execution, idempotent resume, and cancellation; a separate cleanup module validates all paths before deleting files. React consumes the new status and endpoints without changing routes or local draft storage.

**Tech Stack:** Python 3.9, FastAPI, SQLite, `threading`, `unittest`/`pytest`, React 19, React Router 7, Axios, Node test runner, Vite 4.

## Global Constraints

- Keep FastAPI endpoint base paths, SQLite storage, `/media/{file_path}`, frontend port `2001`, and backend port `2002` compatible.
- Do not introduce Celery, a Redis service, a remote task queue, or automatic model calls after backend startup.
- Preserve every completed script, prompt, image, audio, draft, and video checkpoint when a task becomes interrupted or failed.
- Resume uses the original task ID and only regenerates missing, failed, or locally absent units.
- A confirmed project deletion removes database records and safely attributable local files; it must never delete paths outside `output/` and `data/media/`.
- Keep `insightcut:project-drafts` localStorage compatibility and all existing frontend routes.
- Use `apply_patch` for manual file edits and write a failing automated test before each production behavior change.

---

## File Map

- Create `ai-kepu-video-server/src/api/task_runtime.py`: thread-safe running-task registry, cancellation tokens, and lifecycle exceptions.
- Create `ai-kepu-video-server/src/api/task_cleanup.py`: allowed-root validation, task-owned path collection, and deletion reports.
- Create `ai-kepu-video-server/tests/test_task_recovery.py`: status, checkpoint selection, stale-task conversion, and resume behavior tests.
- Create `ai-kepu-video-server/tests/test_task_runtime.py`: idempotent execution and cancellation tests.
- Create `ai-kepu-video-server/tests/test_task_cleanup.py`: safe-path deletion and record cleanup tests.
- Create `ai-kepu-video-web/frontend/src/pages/projectActions.js`: pure project action and confirmation-copy helpers.
- Create `ai-kepu-video-web/frontend/tests/projectActions.test.mjs`: interrupted action and deletion-copy tests.
- Modify `ai-kepu-video-server/src/api/models.py`: add `interrupted` task status and expose progress for recoverable tasks.
- Modify `ai-kepu-video-server/src/database/sqlite_client.py`: add checkpoint columns and checkpoint update methods.
- Modify `ai-kepu-video-server/src/api/task_manager.py`: preserve interrupted state and convert stale running tasks to interrupted.
- Modify `ai-kepu-video-server/src/api/task_executor.py`: persist checkpoints, skip completed work, resume, cancel, and use task-owned output directories.
- Modify `ai-kepu-video-server/src/api/routes.py`: resume endpoint and full deletion orchestration.
- Modify `ai-kepu-video-server/api_server.py`: convert orphaned running tasks to interrupted at startup.
- Modify `ai-kepu-video-web/frontend/src/api/task.js`: add resume and full-delete requests.
- Modify `ai-kepu-video-web/frontend/src/utils/taskState.js`: derive interrupted state and action.
- Modify `ai-kepu-video-web/frontend/src/pages/ProjectAssetsPage.jsx`: menu, continue action, confirmed deletion, and busy states.
- Modify `ai-kepu-video-web/frontend/src/pages/ProcessPage.jsx`: interrupted recovery panel and resume button.
- Modify `ai-kepu-video-web/frontend/src/components/Modal.jsx`: support disabled confirmation while an async destructive action is running.
- Modify `ai-kepu-video-web/frontend/src/pages/delivery-pages.css` and `creation-flow.css`: responsive menu and recovery controls.

---

### Task 1: Persist Recoverable Task State And Checkpoints

**Files:**
- Modify: `ai-kepu-video-server/src/api/models.py`
- Modify: `ai-kepu-video-server/src/database/sqlite_client.py`
- Modify: `ai-kepu-video-server/src/api/task_manager.py`
- Test: `ai-kepu-video-server/tests/test_task_recovery.py`

**Interfaces:**
- Produces: `TaskStatus.INTERRUPTED`, `SQLiteClient.save_task_checkpoint(task_id, script_text=None, summary=None, input_mode=None) -> bool`, `SQLiteClient.update_segment_checkpoint(task_id, segment_index, **updates) -> bool`, and `TaskManager.mark_orphaned_tasks_interrupted(limit=200) -> int`.
- Consumes: existing `tasks`, `task_steps`, and `task_segments` tables.

- [ ] **Step 1: Write failing status and checkpoint tests**

```python
def test_checkpoint_round_trip(temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)
    assert temp_db.save_task_checkpoint(
        "task-1", script_text="完整脚本", summary="摘要", input_mode="theme"
    )
    row = temp_db.get_task("task-1")
    assert row["script_text"] == "完整脚本"
    assert row["summary"] == "摘要"
    assert row["input_mode"] == "theme"

def test_orphaned_processing_task_becomes_interrupted(task_manager, temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)
    temp_db.update_task_status("task-1", "processing", "image_generation")
    assert task_manager.mark_orphaned_tasks_interrupted() == 1
    assert temp_db.get_task("task-1")["status"] == "interrupted"
```

- [ ] **Step 2: Run tests and verify the missing interfaces fail**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_recovery.py -v`

Expected: FAIL because checkpoint columns, `TaskStatus.INTERRUPTED`, and `mark_orphaned_tasks_interrupted` do not exist.

- [ ] **Step 3: Add schema migration and checkpoint methods**

Add nullable `script_text` and `summary` columns plus `input_mode TEXT NOT NULL DEFAULT 'script'` through `_apply_migration`. Implement updates using explicit allowed columns and `updated_at=datetime('now','localtime')`:

```python
def save_task_checkpoint(self, task_id, script_text=None, summary=None, input_mode=None):
    values = {"script_text": script_text, "summary": summary, "input_mode": input_mode}
    updates = {key: value for key, value in values.items() if value is not None}
    return self._update_task_fields(task_id, updates)
```

Add `INTERRUPTED = "interrupted"` and include interrupted progress in `Task.to_response()`.

- [ ] **Step 4: Replace stale failure conversion with orphan interruption**

Implement `mark_orphaned_tasks_interrupted()` to convert all persisted `pending` and `processing` rows found at process startup to `interrupted`, retain the current step, retain segments/assets, clear no files, and set a user-facing interruption reason. Keep timeout detection available during a live process, but convert recoverable stale tasks to `interrupted` instead of `failed`.

- [ ] **Step 5: Run focused and existing backend tests**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_recovery.py tests/test_ffmpeg_exporter.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add ai-kepu-video-server/src/api/models.py ai-kepu-video-server/src/database/sqlite_client.py ai-kepu-video-server/src/api/task_manager.py ai-kepu-video-server/tests/test_task_recovery.py
git commit -m "feat: persist recoverable task checkpoints"
```

### Task 2: Add Idempotent Runtime Registration And Cancellation

**Files:**
- Create: `ai-kepu-video-server/src/api/task_runtime.py`
- Create: `ai-kepu-video-server/tests/test_task_runtime.py`
- Modify: `ai-kepu-video-server/src/api/task_executor.py`

**Interfaces:**
- Produces: `TaskRuntimeRegistry.begin(task_id) -> TaskCancellation | None`, `finish(task_id, token)`, `request_cancel(task_id) -> bool`, `wait_until_stopped(task_id, timeout) -> bool`, `is_running(task_id) -> bool`, `TaskCancelled`, and global `task_runtime`.
- Consumes: task IDs from `TaskExecutor` and delete/resume routes.

- [ ] **Step 1: Write failing registry tests**

```python
def test_begin_is_idempotent_until_finish():
    registry = TaskRuntimeRegistry()
    token = registry.begin("task-1")
    assert token is not None
    assert registry.begin("task-1") is None
    registry.finish("task-1", token)
    assert registry.begin("task-1") is not None

def test_cancel_token_raises_at_checkpoint():
    registry = TaskRuntimeRegistry()
    token = registry.begin("task-1")
    assert registry.request_cancel("task-1")
    with pytest.raises(TaskCancelled):
        token.raise_if_cancelled()
```

- [ ] **Step 2: Run tests and verify they fail for the missing module**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_runtime.py -v`

Expected: FAIL with `ModuleNotFoundError: src.api.task_runtime`.

- [ ] **Step 3: Implement the minimal registry**

Use a `threading.Condition` around `{task_id: TaskCancellation}`. `begin` must atomically reject a duplicate; `finish` must only remove the exact token; `request_cancel` sets a `threading.Event`; `wait_until_stopped` waits on the condition until the task is absent or timeout expires.

- [ ] **Step 4: Integrate the registry into task execution**

`TaskExecutor.execute_task(task_id, theme, style, length, voice_type=None, ratio="16:9", input_mode="script") -> bool` calls `task_runtime.begin()` before creating a daemon thread. The thread receives the token, checks it between stages, and always calls `finish()` in `finally`. Add `TaskExecutor.cancel_task(task_id, timeout=30) -> bool` without changing pipeline behavior yet.

- [ ] **Step 5: Run registry and recovery tests**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_runtime.py tests/test_task_recovery.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add ai-kepu-video-server/src/api/task_runtime.py ai-kepu-video-server/src/api/task_executor.py ai-kepu-video-server/tests/test_task_runtime.py
git commit -m "feat: control task execution lifecycle"
```

### Task 3: Resume The Pipeline From Per-Segment Checkpoints

**Files:**
- Modify: `ai-kepu-video-server/src/api/task_executor.py`
- Modify: `ai-kepu-video-server/src/database/sqlite_client.py`
- Modify: `ai-kepu-video-server/src/api/task_manager.py`
- Test: `ai-kepu-video-server/tests/test_task_recovery.py`

**Interfaces:**
- Produces: `TaskExecutor.resume_task(task_id) -> str`, where the result is `started`, `already_running`, `already_completed`, or `not_recoverable`; `TaskExecutor.__init__(pipeline_factory=VideoEditorPipeline)` supports deterministic executor tests.
- Consumes: Task 1 checkpoint methods and Task 2 cancellation token.

- [ ] **Step 1: Write failing resume-selection tests**

```python
def test_resume_selection_skips_valid_completed_assets(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"png")
    segments = [
        {"segment_index": 0, "image_prompt": "已有提示词", "image_path": str(image), "image_status": "completed"},
        {"segment_index": 1, "image_prompt": "", "image_path": None, "image_status": "pending"},
    ]
    work = build_resume_work(segments)
    assert work.prompt_indexes == [1]
    assert work.image_indexes == [1]

def test_each_prompt_is_persisted_before_the_next_model_call(temp_db, monkeypatch):
    pipeline = FakePipeline(prompt_failure_call=2)
    executor = TaskExecutor(pipeline_factory=lambda **kwargs: pipeline)
    monkeypatch.setattr(task_executor_module, "db_client", temp_db)
    executor.run_inline("task-1", cancellation=TaskCancellation("task-1"))
    assert temp_db.get_segments("task-1")[0]["image_prompt"] == "prompt-0"
```

Define `FakePipeline` in the test with a script rewriter returning a two-segment script, a text segmenter returning `['第一段', '第二段']`, and an image prompt agent that returns `prompt-0` on its first call and raises `RuntimeError('prompt failed')` on its second call. Add `TaskExecutor.run_inline(task_id, cancellation) -> None` as a testable synchronous wrapper over the same implementation used by the background thread.

- [ ] **Step 2: Run the focused tests and verify checkpoint behavior fails**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_recovery.py -k 'resume_selection or each_prompt' -v`

Expected: FAIL because resume work selection and per-prompt persistence are missing.

- [ ] **Step 3: Persist script and initial segments before prompt generation**

After rewrite, call `save_task_checkpoint`. After splitting, immediately upsert all segment rows with pending asset states. During prompt generation, skip non-empty prompts and call `update_segment(task_id, index, {"image_prompt": prompt})` after each successful model response and before starting the next segment.

- [ ] **Step 4: Rebuild pipeline state on resume**

Load the task row and ordered segments. Use `script_text`/`summary` when present; use existing segment text instead of splitting again; map valid completed image/audio paths into `pipeline.media_paths` and `pipeline.voiceover_files`. Submit futures only for missing, failed, or absent-on-disk items.

- [ ] **Step 5: Stop at recoverable failures and cancellation**

Add `RecoverableTaskError`. When prompt generation raises, or image/audio futures report failures, save item errors and set the task to `interrupted` before draft building. Catch `TaskCancelled` separately and set `interrupted` unless deletion has claimed the task. Do not clear any segment or asset rows.

- [ ] **Step 6: Use task-owned output paths**

New tasks write working files below `output/{task_id}/{safe_project_name}/`. Keep `/media/{file_path}` serving behavior and task-ID media upload paths compatible. Existing tasks continue using persisted paths during resume.

- [ ] **Step 7: Run backend recovery tests**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_recovery.py tests/test_task_runtime.py -v`

Expected: PASS, including a test proving completed indexes are not submitted again.

- [ ] **Step 8: Commit Task 3**

```bash
git add ai-kepu-video-server/src/api/task_executor.py ai-kepu-video-server/src/database/sqlite_client.py ai-kepu-video-server/src/api/task_manager.py ai-kepu-video-server/tests/test_task_recovery.py
git commit -m "feat: resume generation from segment checkpoints"
```

### Task 4: Expose Resume And Safe Full Deletion APIs

**Files:**
- Create: `ai-kepu-video-server/src/api/task_cleanup.py`
- Create: `ai-kepu-video-server/tests/test_task_cleanup.py`
- Modify: `ai-kepu-video-server/src/api/routes.py`
- Modify: `ai-kepu-video-server/api_server.py`
- Modify: `ai-kepu-video-server/src/api/task_manager.py`

**Interfaces:**
- Produces: `collect_task_paths(task_row: dict, segments: list[dict], assets: list[dict]) -> set[Path]`, `delete_task_files(paths: Iterable[Path], allowed_roots: Iterable[Path]) -> DeletionReport`, `POST /tasks/{task_id}/resume`, and enhanced `DELETE /tasks/{task_id}?delete_files=true`.
- Consumes: Task 2 cancellation and Task 3 resume interfaces.

- [ ] **Step 1: Write failing cleanup safety tests**

```python
def test_delete_task_files_removes_only_allowed_owned_paths(tmp_path):
    output = tmp_path / "output"
    media = tmp_path / "media"
    owned = output / "task-1" / "video.mp4"
    outside = tmp_path / "keep.txt"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"video")
    outside.write_text("keep")
    report = delete_task_files([owned, outside], allowed_roots=[output, media])
    assert not owned.exists()
    assert outside.exists()
    assert str(outside) in report.skipped_paths

def test_delete_refuses_to_remove_database_row_while_task_is_running(monkeypatch):
    monkeypatch.setattr(routes.task_manager, "get_task", lambda task_id: object())
    monkeypatch.setattr(routes.task_executor, "cancel_task", lambda task_id, timeout=30: False)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.delete_task("task-1", delete_files=True))
    assert error.value.status_code == 409
```

- [ ] **Step 2: Run cleanup tests and verify they fail**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_cleanup.py -v`

Expected: FAIL because `task_cleanup` does not exist.

- [ ] **Step 3: Implement validated file collection and deletion**

Resolve every path before comparing it to allowed roots. Accept task-ID-owned directories directly. For legacy name-based directories, delete only exact files recorded by task segments, task assets, or task results; remove a directory only when empty. Return:

```python
@dataclass
class DeletionReport:
    deleted_files: int
    deleted_directories: int
    skipped_paths: list[str]
    failed_paths: list[str]
```

- [ ] **Step 4: Add resume route**

Map executor outcomes to HTTP behavior: `started` -> 202, `already_running` -> 200, `already_completed` -> 200, `not_recoverable` -> 409, missing task -> 404. Return `{task_id, status, outcome}`.

- [ ] **Step 5: Enhance delete route**

Set an executor deletion claim, request cancellation, and wait up to 30 seconds. If still running, return 409 without deleting. Otherwise snapshot task rows and paths, delete database records, then delete files. Return the `DeletionReport`; repeat deletion returns 404.

- [ ] **Step 6: Change startup recovery**

Replace `mark_stale_tasks_failed()` in `startup_event()` with `mark_orphaned_tasks_interrupted()` and log the number of tasks made resumable.

- [ ] **Step 7: Run API and cleanup tests**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_cleanup.py tests/test_task_recovery.py tests/test_task_runtime.py -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add ai-kepu-video-server/src/api/task_cleanup.py ai-kepu-video-server/src/api/routes.py ai-kepu-video-server/api_server.py ai-kepu-video-server/src/api/task_manager.py ai-kepu-video-server/tests/test_task_cleanup.py
git commit -m "feat: expose task resume and full deletion"
```

### Task 5: Add Resume And Delete Project Controls In React

**Files:**
- Create: `ai-kepu-video-web/frontend/src/pages/projectActions.js`
- Create: `ai-kepu-video-web/frontend/tests/projectActions.test.mjs`
- Modify: `ai-kepu-video-web/frontend/src/api/task.js`
- Modify: `ai-kepu-video-web/frontend/src/utils/taskState.js`
- Modify: `ai-kepu-video-web/frontend/src/pages/ProjectAssetsPage.jsx`
- Modify: `ai-kepu-video-web/frontend/src/pages/ProcessPage.jsx`
- Modify: `ai-kepu-video-web/frontend/src/components/Modal.jsx`
- Modify: `ai-kepu-video-web/frontend/src/pages/delivery-pages.css`
- Modify: `ai-kepu-video-web/frontend/src/pages/creation-flow.css`

**Interfaces:**
- Produces: `resumeTask(taskId)`, `deleteTask(taskId, {deleteFiles: true})`, `getProjectPrimaryAction(project)`, and `getDeleteConfirmation(project)`.
- Consumes: Task 4 API responses and existing toast/router components.

- [ ] **Step 1: Write failing pure frontend tests**

```javascript
test('interrupted task exposes continue generation', () => {
  const state = deriveTaskState({ task: { status: 'interrupted' }, segments: [{ text: 'saved' }] })
  assert.equal(state.key, 'interrupted')
  assert.equal(state.actionLabel, '继续生成')
})

test('generated project deletion warns that every local artifact is permanent', () => {
  const confirmation = getDeleteConfirmation({ type: 'task', name: '测试项目' })
  assert.match(confirmation.message, /图片、配音、视频和剪映草稿/u)
  assert.equal(confirmation.confirmLabel, '永久删除')
})
```

- [ ] **Step 2: Run frontend tests and verify they fail**

Run: `cd ai-kepu-video-web/frontend && npm test`

Expected: FAIL because interrupted state and `projectActions.js` are missing.

- [ ] **Step 3: Add API and pure action helpers**

`resumeTask` posts to `/tasks/${taskId}/resume`. `deleteTask` sends `params: { delete_files: true }`. `getProjectPrimaryAction` maps interrupted tasks to resume and processing tasks to progress. Keep local draft deletion copy separate.

- [ ] **Step 4: Add project-card menu and async confirmation**

Show the icon menu for every project. Selecting delete opens `ConfirmDialog`; generated-project confirmation explicitly names permanent artifacts. While deleting, set `confirmDisabled` and label the button `正在删除...`. On success remove the task from `remoteTasks`, `taskSegments`, and cover maps without waiting for a full reload. On partial file failures, show a warning toast with the count.

- [ ] **Step 5: Add resume actions**

On an interrupted project card, call `resumeTask`, then navigate to `/process/{taskId}`. In `ProcessPage`, do not treat interrupted as a terminal failure modal; show “继续生成” and “查看已保存素材”. Disable resume while the request is pending.

- [ ] **Step 6: Keep menus and dialogs responsive**

Use stable icon-button dimensions, avoid nesting a button inside the card-open button, and ensure the destructive confirmation footer stacks at 390px without horizontal overflow.

- [ ] **Step 7: Run frontend tests and build**

Run: `cd ai-kepu-video-web/frontend && npm test && npm run build`

Expected: all Node tests PASS and Vite build succeeds.

- [ ] **Step 8: Commit Task 5**

```bash
git add ai-kepu-video-web/frontend/src ai-kepu-video-web/frontend/tests/projectActions.test.mjs
git commit -m "feat: manage interrupted and deleted projects"
```

### Task 6: End-To-End Recovery, Deletion, And Visual Verification

**Files:**
- Modify only files required by defects found during verification.
- Test: all backend and frontend test files above.

**Interfaces:**
- Consumes: all previous task interfaces.
- Produces: verified local workflow on ports `2001` and `2002`.

- [ ] **Step 1: Run the complete automated suites**

Run: `cd ai-kepu-video-server && source venv/bin/activate && pytest tests/test_task_recovery.py tests/test_task_runtime.py tests/test_task_cleanup.py tests/test_ffmpeg_exporter.py -v`

Run: `cd ai-kepu-video-web/frontend && npm test && npm run build`

Expected: PASS with no test warnings or build errors.

- [ ] **Step 2: Restart both services using repository commands**

Stop ports `2001` and `2002`, start FastAPI from `ai-kepu-video-server` with `api_server:app`, then start Vite from `ai-kepu-video-web/frontend`. Verify `GET http://localhost:2002/health` returns `{"status":"ok"}` and `http://localhost:2001` returns HTTP 200.

- [ ] **Step 3: Verify a real interrupted task**

Create a short theme-mode task, stop the backend after at least one prompt or asset checkpoint exists, restart the backend, verify the task is `interrupted`, click “继续生成”, and confirm completed checkpoint rows are unchanged while missing rows finish.

- [ ] **Step 4: Verify full deletion**

Delete the test task from Project Assets. Confirm the task API returns 404, all five SQLite record groups are absent, `data/media/{task_id}` is absent, and its task-owned `output/{task_id}` directory is absent.

- [ ] **Step 5: Capture responsive screenshots**

Check Project Assets and Process pages at 1440x900, 1180x900, 766x1024, and 390x844. Confirm menus, status labels, confirm dialog, and resume/delete buttons do not overlap or introduce horizontal scrolling.

- [ ] **Step 6: Run maintenance dry-run and inspect Git scope**

Run: `cd ai-kepu-video-server && source venv/bin/activate && python scripts/maintenance_report.py --dry-run`

Run: `git status --short && git diff --check`

Expected: no accidental file deletion, no whitespace errors, and only intended source/test changes.

- [ ] **Step 7: Commit verification fixes if needed**

If verification changes backend recovery code, explicitly stage the changed files under `ai-kepu-video-server/src/api/` and their matching tests under `ai-kepu-video-server/tests/`. If it changes frontend behavior, explicitly stage the changed files under `ai-kepu-video-web/frontend/src/` and their matching test under `ai-kepu-video-web/frontend/tests/`. Verify `git diff --cached --name-only`, then commit with `git commit -m "fix: harden task recovery verification"`. Do not create an empty commit when verification requires no changes.
