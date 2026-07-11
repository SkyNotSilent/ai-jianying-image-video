import sqlite3

import pytest

from src.api import task_manager as task_manager_module
from src.api.models import TaskStatus
from src.api.task_manager import Task, TaskManager
from src.database import sqlite_client as sqlite_client_module
from src.database.sqlite_client import SQLiteClient


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", tmp_path / "local.db")
    return SQLiteClient()


@pytest.fixture
def task_manager(temp_db, monkeypatch):
    monkeypatch.setattr(task_manager_module, "db_client", temp_db)
    return TaskManager()


def test_checkpoint_round_trip(temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)

    assert temp_db.save_task_checkpoint(
        "task-1", script_text="完整脚本", summary="摘要", input_mode="theme"
    )

    row = temp_db.get_task("task-1")
    assert row["script_text"] == "完整脚本"
    assert row["summary"] == "摘要"
    assert row["input_mode"] == "theme"


def test_checkpoint_migration_preserves_existing_task(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            name TEXT,
            theme TEXT NOT NULL,
            style TEXT NOT NULL DEFAULT '温暖感人',
            length INTEGER NOT NULL DEFAULT 300,
            ratio TEXT NOT NULL DEFAULT '16:9',
            voice_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT DEFAULT 'pending',
            error TEXT,
            extract_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            completed_at TEXT
        );
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO tasks (task_id, theme, style, length)
        VALUES ('legacy-task', '已有任务', '知识科普|电影质感', 100);
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(sqlite_client_module, "DB_PATH", db_path)

    row = SQLiteClient().get_task("legacy-task")

    assert row["theme"] == "已有任务"
    assert row["script_text"] is None
    assert row["summary"] is None
    assert row["input_mode"] == "script"


def test_segment_checkpoint_updates_only_allowed_fields(temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)
    temp_db.save_segments(
        "task-1",
        [{"segment_index": 0, "text": "第一段", "image_status": "pending"}],
    )

    assert temp_db.update_segment_checkpoint(
        "task-1",
        0,
        image_prompt="画面提示词",
        image_status="completed",
        unsupported="ignored",
    )

    row = temp_db.get_segments("task-1")[0]
    assert row["image_prompt"] == "画面提示词"
    assert row["image_status"] == "completed"


def test_orphaned_processing_task_becomes_interrupted(task_manager, temp_db):
    temp_db.create_task("task-1", "主题", "知识科普|电影质感", 100)
    temp_db.update_task_status("task-1", "processing", "image_generation")
    temp_db.save_segments(
        "task-1",
        [{"segment_index": 0, "text": "已保存分镜", "image_status": "completed"}],
    )
    asset = temp_db.save_task_asset(
        "task-1", "image", "generated", segment_index=0, path="saved.png"
    )

    assert task_manager.mark_orphaned_tasks_interrupted() == 1

    row = temp_db.get_task("task-1")
    assert row["status"] == "interrupted"
    assert row["current_step"] == "image_generation"
    assert row["error"] == "服务重启导致任务中断，可继续生成"
    assert temp_db.get_segments("task-1")[0]["text"] == "已保存分镜"
    assert temp_db.list_task_assets("task-1")[0]["asset_id"] == asset["asset_id"]


def test_interrupted_status_keeps_progress_in_task_response():
    task = Task("task-1", "主题", "知识科普|电影质感", 100)
    task.status = TaskStatus.INTERRUPTED

    assert TaskStatus.DELETING.value == "deleting"
    assert task.to_response().progress is not None
