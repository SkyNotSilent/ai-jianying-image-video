import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException, Response

from src.api import routes
from src.api import task_manager as task_manager_module
from src.api import task_executor as task_executor_module
from src.api.models import TaskStatus
from src.api.task_cleanup import DeletionReport, collect_task_paths, delete_task_files
from src.api.task_executor import TaskExecutor
from src.api.task_manager import TaskManager
from src.api.task_runtime import TaskRuntimeRegistry
from src.database import sqlite_client as sqlite_client_module
from src.database.sqlite_client import SQLiteClient


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", tmp_path / "local.db")
    return SQLiteClient()


@pytest.fixture
def isolated_manager(tmp_path, temp_db, monkeypatch):
    monkeypatch.setattr(task_manager_module, "db_client", temp_db)
    monkeypatch.setattr(task_manager_module.Config, "BASE_DIR", tmp_path)
    registry = TaskRuntimeRegistry()
    monkeypatch.setattr(task_manager_module, "task_runtime", registry, raising=False)
    return TaskManager(), registry


def create_task(db, task_id, status="completed"):
    db.create_task(task_id, "主题", "知识科普|电影质感", 100, name="旧项目")
    db.update_task_status(task_id, status, "image_generation")


def test_runtime_delete_claim_blocks_new_execution_registration():
    registry = TaskRuntimeRegistry()

    assert registry.claim_delete("task-1")
    assert registry.begin("task-1") is None
    assert registry.is_deleting("task-1")

    registry.finish_delete("task-1")

    assert not registry.is_deleting("task-1")
    assert registry.begin("task-1") is not None


def test_runtime_delete_claim_can_cancel_an_existing_execution():
    registry = TaskRuntimeRegistry()
    token = registry.begin("task-1")

    assert registry.claim_delete("task-1")
    assert registry.request_cancel("task-1")
    assert token.is_cancelled()


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
    assert str(outside.resolve()) in report.skipped_paths
    assert report.deleted_files == 1
    assert report.failed_paths == []


def test_delete_task_files_resolves_symlinks_before_allowed_root_check(tmp_path):
    output = tmp_path / "output"
    outside = tmp_path / "outside.txt"
    link = output / "task-1" / "linked.txt"
    link.parent.mkdir(parents=True)
    outside.write_text("keep")
    link.symlink_to(outside)

    report = delete_task_files([link], allowed_roots=[output])

    assert outside.read_text() == "keep"
    assert link.is_symlink()
    assert str(outside.resolve()) in report.skipped_paths


def test_delete_task_files_never_removes_allowed_storage_root(tmp_path):
    output = tmp_path / "output"
    output.mkdir()

    report = delete_task_files([output], allowed_roots=[output])

    assert output.is_dir()
    assert str(output.resolve()) in report.skipped_paths


def test_collect_and_delete_recursively_removes_task_id_owned_directories(
    tmp_path, monkeypatch
):
    task_id = "a" * 32
    monkeypatch.setattr(task_manager_module.Config, "BASE_DIR", tmp_path)
    from src.api import task_cleanup

    monkeypatch.setattr(task_cleanup.Config, "BASE_DIR", tmp_path)
    task_root = tmp_path / "output" / task_id
    recorded = task_root / "project" / "images" / "recorded.png"
    unrecorded = task_root / "project" / "draft_content.json"
    recorded.parent.mkdir(parents=True)
    recorded.write_bytes(b"png")
    unrecorded.write_text("draft")
    task_row = {
        "task_id": task_id,
        "result": {"draft_path": str(task_root / "project")},
    }

    paths = collect_task_paths(
        task_row,
        [{"image_path": str(recorded)}],
        [],
    )
    report = delete_task_files(
        paths,
        allowed_roots=[tmp_path / "output", tmp_path / "data" / "media"],
    )

    assert not task_root.exists()
    assert report.deleted_files == 2
    assert report.deleted_directories >= 3


def test_legacy_directory_deletes_only_attributed_files(tmp_path, monkeypatch):
    from src.api import task_cleanup

    monkeypatch.setattr(task_cleanup.Config, "BASE_DIR", tmp_path)
    legacy_root = tmp_path / "output" / "旧项目"
    attributed = legacy_root / "images" / "segment.png"
    retained = legacy_root / "keep.txt"
    attributed.parent.mkdir(parents=True)
    attributed.write_bytes(b"png")
    retained.write_text("keep")
    task_row = {
        "task_id": "legacy-task",
        "result": {"draft_path": str(legacy_root)},
    }

    paths = collect_task_paths(
        task_row,
        [{"image_path": str(attributed)}],
        [],
    )
    report = delete_task_files(paths, allowed_roots=[tmp_path / "output"])

    assert not attributed.exists()
    assert retained.read_text() == "keep"
    assert legacy_root.exists()
    assert report.failed_paths == []


def test_collect_task_paths_maps_local_media_urls_and_ignores_remote_urls(
    tmp_path, monkeypatch
):
    from src.api import task_cleanup

    monkeypatch.setattr(task_cleanup.Config, "BASE_DIR", tmp_path)
    paths = collect_task_paths(
        {
            "task_id": "task-1",
            "result": {
                "draft_path": "output/旧项目",
                "video_url": "http://localhost:2002/media/task-1/video.mp4",
                "draft_url": "https://cdn.example.com/archive.zip",
            },
        },
        [{"image_url": "/media/task-1/image.png"}],
        [{"path": "data/media/task-1/audio.wav"}],
    )

    assert (tmp_path / "output" / "旧项目").resolve() in paths
    assert (tmp_path / "data" / "media" / "task-1" / "video.mp4").resolve() in paths
    assert (tmp_path / "data" / "media" / "task-1" / "image.png").resolve() in paths
    assert (tmp_path / "data" / "media" / "task-1" / "audio.wav").resolve() in paths
    assert not any("cdn.example.com" in str(path) for path in paths)


def test_collect_task_paths_does_not_map_remote_media_url_to_local_file(
    tmp_path, monkeypatch
):
    from src.api import task_cleanup

    monkeypatch.setattr(task_cleanup.Config, "BASE_DIR", tmp_path)
    local_candidate = tmp_path / "data" / "media" / "task-1" / "video.mp4"

    paths = collect_task_paths(
        {
            "task_id": "legacy-task",
            "result": {
                "video_url": "https://cdn.example.com/media/task-1/video.mp4",
            },
        },
        [],
        [],
    )

    assert local_candidate.resolve() not in paths


def test_idle_task_deletes_rows_and_files_immediately(
    tmp_path, temp_db, isolated_manager
):
    manager, _ = isolated_manager
    task_id = "b" * 32
    create_task(temp_db, task_id)
    owned = tmp_path / "output" / task_id / "project" / "video.mp4"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"video")
    temp_db.save_task_result(task_id, str(owned.parent), 1)
    temp_db.save_segments(task_id, [{"segment_index": 0, "text": "分镜", "image_path": str(owned)}])

    assert manager.request_delete(task_id, delete_files=True) == "deleted"

    assert temp_db.get_task(task_id) is None
    assert not (tmp_path / "output" / task_id).exists()
    assert manager.request_delete(task_id, delete_files=True) == "deleted"


def test_delete_running_task_is_accepted_once_and_finishes_after_stop(
    tmp_path, temp_db, isolated_manager, monkeypatch
):
    manager, registry = isolated_manager
    task_id = "c" * 32
    create_task(temp_db, task_id, status="processing")
    owned = tmp_path / "output" / task_id / "project" / "image.png"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"png")
    temp_db.save_segments(task_id, [{"segment_index": 0, "text": "分镜", "image_path": str(owned)}])
    token = registry.begin(task_id)
    created_threads = []

    class DeferredThread:
        def __init__(self, target, args=()):
            self.target = target
            self.args = args
            self.daemon = False
            self.started = False
            created_threads.append(self)

        def start(self):
            self.started = True

    monkeypatch.setattr(task_manager_module, "Thread", DeferredThread)

    assert manager.request_delete(task_id, delete_files=True) == "deleting"
    assert manager.request_delete(task_id, delete_files=True) == "deleting"
    assert temp_db.get_task(task_id)["status"] == "deleting"
    assert token.is_cancelled()
    assert len(created_threads) == 1
    assert created_threads[0].daemon
    assert created_threads[0].started

    registry.finish(task_id, token)
    created_threads[0].target(*created_threads[0].args)

    assert temp_db.get_task(task_id) is None
    assert not (tmp_path / "output" / task_id).exists()


@pytest.mark.parametrize("delete_files", [False, True])
def test_startup_preserves_persisted_file_deletion_intent(
    tmp_path, temp_db, isolated_manager, monkeypatch, delete_files
):
    manager, _ = isolated_manager
    task_id = "intent-task"
    create_task(temp_db, task_id, status="deleting")
    owned = tmp_path / "output" / task_id / "project" / "video.mp4"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"video")
    temp_db.save_task_result(task_id, str(owned.parent), 1)
    assert temp_db.set_task_deletion_intent(task_id, delete_files)

    assert manager.complete_deleting_tasks() == 1

    assert temp_db.get_task(task_id) is None
    assert owned.exists() is (not delete_files)


def test_stale_check_does_not_interrupt_a_registered_runtime(
    temp_db, isolated_manager
):
    manager, registry = isolated_manager
    task_id = "active-task"
    create_task(temp_db, task_id, status="processing")
    token = registry.begin(task_id)
    stale = temp_db.get_task(task_id)
    stale["updated_at"] = (datetime.now() - timedelta(hours=2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    assert manager.fail_stale_task_data(stale) is False
    assert temp_db.get_task(task_id)["status"] == "processing"

    registry.finish(task_id, token)


def test_stale_orphan_becomes_recoverable_interruption(
    temp_db, isolated_manager
):
    manager, _ = isolated_manager
    task_id = "orphan-task"
    create_task(temp_db, task_id, status="processing")
    stale = temp_db.get_task(task_id)
    stale["updated_at"] = (datetime.now() - timedelta(hours=2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    assert manager.fail_stale_task_data(stale) is True
    saved = temp_db.get_task(task_id)
    assert saved["status"] == "interrupted"
    assert "可继续生成" in saved["error"]


def test_stale_in_memory_task_lookup_does_not_deadlock(
    temp_db, isolated_manager
):
    manager, _ = isolated_manager
    task_id = manager.create_task("主题", "知识科普|电影质感", 100)
    temp_db.update_task_status(task_id, "processing", "image_generation")
    with temp_db.get_connection() as connection:
        connection.execute(
            "UPDATE tasks SET updated_at=? WHERE task_id=?",
            (
                (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                task_id,
            ),
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        task = executor.submit(manager.get_task, task_id).result(timeout=1)

    assert task.status == TaskStatus.INTERRUPTED


def test_task_detail_reports_script_only_resume_capability(
    temp_db, isolated_manager
):
    manager, _ = isolated_manager
    task_id = "script-checkpoint"
    create_task(temp_db, task_id, status="failed")
    temp_db.save_task_checkpoint(task_id, script_text="已保存脚本")

    response = manager.get_task(task_id).to_response()

    assert response.can_resume is True


def test_task_detail_reports_theme_only_resume_capability(
    temp_db, isolated_manager
):
    manager, _ = isolated_manager
    task_id = "theme-checkpoint"
    create_task(temp_db, task_id, status="interrupted")

    response = manager.get_task(task_id).to_response()

    assert response.can_resume is True


def test_file_cleanup_failure_does_not_restore_deleted_rows(
    temp_db, isolated_manager, monkeypatch, caplog
):
    manager, _ = isolated_manager
    task_id = "d" * 32
    create_task(temp_db, task_id)

    from src.api.task_cleanup import DeletionReport

    monkeypatch.setattr(
        task_manager_module,
        "delete_task_files",
        lambda paths, allowed_roots: DeletionReport(0, 0, [], ["locked.mp4"]),
        raising=False,
    )

    with caplog.at_level(logging.ERROR):
        assert manager.request_delete(task_id, delete_files=True) == "deleted"

    assert temp_db.get_task(task_id) is None
    assert "locked.mp4" in caplog.text


def test_file_cleanup_exception_is_logged_after_rows_stay_deleted(
    temp_db, isolated_manager, monkeypatch, caplog
):
    manager, _ = isolated_manager
    task_id = "e" * 32
    create_task(temp_db, task_id)

    def fail_cleanup(paths, allowed_roots):
        raise OSError("cleanup crashed")

    monkeypatch.setattr(task_manager_module, "delete_task_files", fail_cleanup)

    with caplog.at_level(logging.ERROR):
        outcome = manager.request_delete(task_id, delete_files=True)

    assert outcome == "deleted"
    assert temp_db.get_task(task_id) is None
    assert "cleanup crashed" in caplog.text


@pytest.mark.parametrize(
    ("outcome", "expected_code", "expected_status"),
    [
        ("started", 202, "processing"),
        ("already_running", 200, "processing"),
        ("already_completed", 200, "completed"),
        ("not_recoverable", 409, "interrupted"),
    ],
)
def test_resume_route_maps_executor_outcomes(
    monkeypatch, outcome, expected_code, expected_status
):
    task = type("Task", (), {"status": TaskStatus.INTERRUPTED})()
    monkeypatch.setattr(routes.task_manager, "get_task", lambda task_id: task)
    monkeypatch.setattr(routes.task_executor, "resume_task", lambda task_id: outcome)
    response = Response()

    result = asyncio.run(routes.resume_task("task-1", response))

    assert response.status_code == expected_code
    assert result == {
        "task_id": "task-1",
        "status": expected_status,
        "outcome": outcome,
    }


def test_resume_route_returns_404_for_missing_task(monkeypatch):
    monkeypatch.setattr(routes.task_manager, "get_task", lambda task_id: None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes.resume_task("missing", Response()))

    assert exc_info.value.status_code == 404


def test_resume_during_delete_claim_is_not_reported_as_already_running(monkeypatch):
    registry = TaskRuntimeRegistry()
    registry.claim_delete("task-1")

    class CheckpointDB:
        @staticmethod
        def get_task(task_id):
            return {
                "task_id": task_id,
                "status": "interrupted",
                "script_text": "已保存脚本",
                "theme": "主题",
                "style": "知识科普|电影质感",
                "length": 100,
                "ratio": "16:9",
                "input_mode": "script",
            }

        @staticmethod
        def get_segments(task_id):
            return []

    monkeypatch.setattr(task_executor_module, "task_runtime", registry)
    monkeypatch.setattr(task_executor_module, "db_client", CheckpointDB())

    assert TaskExecutor().resume_task("task-1") == "not_recoverable"


@pytest.mark.parametrize(
    ("outcome", "expected_code", "expected_status"),
    [("deleted", 200, "deleted"), ("deleting", 202, "deleting")],
)
def test_delete_route_maps_manager_outcomes(
    monkeypatch, outcome, expected_code, expected_status
):
    monkeypatch.setattr(
        routes.task_manager,
        "request_delete",
        lambda task_id, delete_files: outcome,
        raising=False,
    )
    response = Response()

    result = asyncio.run(
        routes.delete_task("task-1", response, delete_files=True)
    )

    assert response.status_code == expected_code
    assert result == {
        "task_id": "task-1",
        "status": expected_status,
        "outcome": outcome,
        "message": "任务已删除" if outcome == "deleted" else "任务正在停止并删除",
    }


def test_synchronous_delete_route_returns_file_cleanup_report(monkeypatch):
    report = DeletionReport(
        deleted_files=3,
        deleted_directories=2,
        skipped_paths=["/outside/keep.mp4"],
        failed_paths=["/output/task/locked.mp4"],
    )
    monkeypatch.setattr(
        routes.task_manager,
        "request_delete",
        lambda task_id, delete_files: "deleted",
    )
    monkeypatch.setattr(
        routes.task_manager,
        "get_deletion_report",
        lambda task_id: report,
        raising=False,
    )

    result = asyncio.run(routes.delete_task("task-1", Response(), delete_files=True))

    assert result["deletion_report"] == {
        "deleted_files": 3,
        "deleted_directories": 2,
        "skipped_paths": ["/outside/keep.mp4"],
        "failed_paths": ["/output/task/locked.mp4"],
    }


def test_startup_finishes_deleting_before_interrupting_orphans(monkeypatch):
    import api_server

    calls = []
    monkeypatch.setattr(
        api_server.task_manager,
        "complete_deleting_tasks",
        lambda: calls.append("delete") or 2,
        raising=False,
    )
    monkeypatch.setattr(
        api_server.task_manager,
        "mark_orphaned_tasks_interrupted",
        lambda: calls.append("interrupt") or 3,
    )

    asyncio.run(api_server.startup_event())

    assert calls == ["delete", "interrupt"]
