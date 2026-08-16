"""
SQLite 数据库客户端
本地持久化任务、分镜和素材数据
"""

import logging
import sqlite3
import os
import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager
from pathlib import Path

from src.draft.voice_catalog import (
    DOUBAO_DEFAULT_ENABLED_IDS,
    DOUBAO_PRESET_VOICES,
    MIMO_DEFAULT_ENABLED_IDS,
    MIMO_PRESET_VOICES,
    build_voice_key,
    parse_voice_key,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "local.db"


class SQLiteClient:
    """SQLite 数据库客户端"""

    TASK_CHECKPOINT_COLUMNS = frozenset({
        "script_text", "summary", "input_mode", "delete_files_on_delete",
        "execution_mode", "workflow_phase", "script_policy", "voice_confirmed",
    })
    SEGMENT_CHECKPOINT_COLUMNS = frozenset({
        "text", "image_prompt", "image_path", "image_url", "image_status",
        "image_error", "audio_path", "audio_url", "audio_status", "audio_error",
        "duration", "audio_voice_type", "audio_tts_options_json",
        "prompt_status", "prompt_error", "prompt_manual", "prompt_needs_review",
    })
    CLEARABLE_SEGMENT_ERROR_COLUMNS = frozenset({"image_error", "audio_error", "prompt_error"})

    def __init__(self):
        self._initialized = False

    def _init_db(self):
        """初始化数据库和表结构"""
        if self._initialized:
            return

        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
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
                    completed_at TEXT,
                    delete_files_on_delete INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS task_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    draft_path TEXT NOT NULL,
                    draft_url TEXT,
                    video_url TEXT,
                    segments_count INTEGER NOT NULL DEFAULT 0,
                    total_duration REAL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS task_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress INTEGER,
                    total INTEGER,
                    duration REAL,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS tts_voices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL DEFAULT 'doubao',
                    voice_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'zh',
                    description TEXT,
                    source TEXT NOT NULL DEFAULT 'builtin',
                    capabilities_json TEXT,
                    preview_url TEXT,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    UNIQUE(provider, voice_id)
                );

                CREATE TABLE IF NOT EXISTS tts_voice_clones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clone_id TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL DEFAULT 'mimo',
                    name TEXT NOT NULL,
                    reference_path TEXT NOT NULL,
                    duration REAL,
                    file_size INTEGER,
                    status TEXT NOT NULL DEFAULT 'draft',
                    preview_path TEXT,
                    error_message TEXT,
                    is_enabled INTEGER NOT NULL DEFAULT 0,
                    consent_confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS task_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    segment_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    image_prompt TEXT,
                    image_path TEXT,
                    image_url TEXT,
                    image_status TEXT DEFAULT 'completed',
                    image_error TEXT,
                    audio_path TEXT,
                    audio_url TEXT,
                    audio_status TEXT DEFAULT 'completed',
                    audio_error TEXT,
                    duration REAL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    UNIQUE(task_id, segment_index)
                );

                CREATE TABLE IF NOT EXISTS task_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    segment_index INTEGER,
                    asset_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    path TEXT,
                    url TEXT,
                    label TEXT,
                    prompt TEXT,
                    text TEXT,
                    voice_type TEXT,
                    metadata_json TEXT,
                    status TEXT DEFAULT 'completed',
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );
            """)

            self._migrate_voice_catalog(cursor)
            self._apply_migration(
                cursor,
                "20260716_replace_ungranted_doubao_voice",
                """
                DELETE FROM tts_voices
                WHERE provider = 'doubao'
                  AND voice_id = 'zh_male_yangguangxiaolei_moon_bigtts'
                  AND source = 'builtin';
                UPDATE tts_voices
                SET is_enabled = 1,
                    updated_at = datetime('now','localtime')
                WHERE provider = 'doubao'
                  AND voice_id = 'zh_male_jieshuoxiaoming_moon_bigtts';
                """,
            )
            self._seed_voice_catalog(cursor)

            # 为已有数据库添加 ratio 字段（兼容旧表结构）
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN ratio TEXT NOT NULL DEFAULT '16:9'")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN voice_type TEXT")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            try:
                cursor.execute("ALTER TABLE task_segments ADD COLUMN image_prompt TEXT")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            try:
                cursor.execute("ALTER TABLE task_segments ADD COLUMN image_status TEXT DEFAULT 'completed'")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE task_segments ADD COLUMN image_error TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE task_segments ADD COLUMN audio_status TEXT DEFAULT 'completed'")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE task_segments ADD COLUMN audio_error TEXT")
            except sqlite3.OperationalError:
                pass

            self._apply_migration(
                cursor,
                "20260623_operational_indexes",
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at
                    ON tasks(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_task_steps_task_step
                    ON task_steps(task_id, step_name);
                CREATE INDEX IF NOT EXISTS idx_task_assets_task_type_segment
                    ON task_assets(task_id, asset_type, segment_index);
                """,
            )
            self._apply_column_migration(
                cursor,
                "20260711_task_recovery_checkpoints",
                "tasks",
                {
                    "script_text": "TEXT",
                    "summary": "TEXT",
                    "input_mode": "TEXT NOT NULL DEFAULT 'script'",
                },
            )
            self._apply_column_migration(
                cursor,
                "20260716_tts_task_options",
                "tasks",
                {"tts_options_json": "TEXT"},
            )
            self._apply_column_migration(
                cursor,
                "20260716_segment_tts_options",
                "task_segments",
                {
                    "audio_voice_type": "TEXT",
                    "audio_tts_options_json": "TEXT",
                },
            )
            self._apply_column_migration(
                cursor,
                "20260712_task_deletion_intent",
                "tasks",
                {"delete_files_on_delete": "INTEGER NOT NULL DEFAULT 0"},
            )
            self._apply_column_migration(
                cursor,
                "20260816_review_first_workspace_tasks",
                "tasks",
                {
                    "execution_mode": "TEXT NOT NULL DEFAULT 'full'",
                    "workflow_phase": "TEXT NOT NULL DEFAULT 'pending'",
                    "plan_version": "INTEGER NOT NULL DEFAULT 0",
                    "script_policy": "TEXT NOT NULL DEFAULT 'rewrite'",
                    "voice_confirmed": "INTEGER NOT NULL DEFAULT 0",
                },
            )
            self._apply_column_migration(
                cursor,
                "20260816_review_first_workspace_segments",
                "task_segments",
                {
                    "prompt_status": "TEXT NOT NULL DEFAULT 'completed'",
                    "prompt_error": "TEXT",
                    "prompt_manual": "INTEGER NOT NULL DEFAULT 0",
                    "prompt_needs_review": "INTEGER NOT NULL DEFAULT 0",
                },
            )

            conn.commit()
            conn.close()
            self._initialized = True
            logger.info(f"SQLite 数据库初始化成功: {DB_PATH}")
        except Exception as e:
            logger.error(f"SQLite 数据库初始化失败: {e}")
            self._initialized = False

    def _apply_migration(self, cursor, version: str, sql: str) -> None:
        cursor.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,))
        if cursor.fetchone():
            return
        cursor.executescript(sql)
        cursor.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        logger.info(f"SQLite 迁移已应用: {version}")

    def _migrate_voice_catalog(self, cursor) -> None:
        cursor.execute("PRAGMA table_info(tts_voices)")
        columns = {row[1] for row in cursor.fetchall()}
        if "provider" in columns and "language" in columns and "source" in columns:
            return
        cursor.executescript(
            """
            ALTER TABLE tts_voices RENAME TO tts_voices_legacy_20260716;
            CREATE TABLE tts_voices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL DEFAULT 'doubao',
                voice_id TEXT NOT NULL,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'zh',
                description TEXT,
                source TEXT NOT NULL DEFAULT 'builtin',
                capabilities_json TEXT,
                preview_url TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE(provider, voice_id)
            );
            INSERT INTO tts_voices
                (id, provider, voice_id, name, gender, language, description, source,
                 is_enabled, sort_order, created_at, updated_at)
            SELECT id, 'doubao', voice_id, name, gender, 'zh', description, 'builtin',
                   CASE WHEN voice_id IN (
                       'zh_female_shuangkuaisisi_moon_bigtts',
                       'zh_male_jieshuoxiaoming_moon_bigtts'
                   ) THEN 1 ELSE 0 END,
                   sort_order, created_at, updated_at
            FROM tts_voices_legacy_20260716;
            DROP TABLE tts_voices_legacy_20260716;
            """
        )

    def _seed_voice_catalog(self, cursor) -> None:
        capabilities = json.dumps(
            {"preview": True, "speed": "numeric", "volume": True},
            ensure_ascii=False,
        )
        for voice_id, name, gender, description, sort_order in DOUBAO_PRESET_VOICES:
            cursor.execute(
                """INSERT OR IGNORE INTO tts_voices
                   (provider, voice_id, name, gender, language, description, source,
                    capabilities_json, is_enabled, sort_order)
                   VALUES ('doubao', ?, ?, ?, 'zh', ?, 'builtin', ?, ?, ?)""",
                (
                    voice_id,
                    name,
                    gender,
                    description,
                    capabilities,
                    1 if voice_id in DOUBAO_DEFAULT_ENABLED_IDS else 0,
                    sort_order,
                ),
            )
        mimo_capabilities = json.dumps(
            {"preview": True, "speed": "style", "style": True},
            ensure_ascii=False,
        )
        for voice in MIMO_PRESET_VOICES:
            cursor.execute(
                """INSERT OR IGNORE INTO tts_voices
                   (provider, voice_id, name, gender, language, description, source,
                    capabilities_json, is_enabled, sort_order)
                   VALUES ('mimo', ?, ?, ?, ?, ?, 'builtin', ?, ?, ?)""",
                (
                    voice["voice_id"],
                    voice["name"],
                    voice["gender"],
                    voice["language"],
                    voice["description"],
                    mimo_capabilities,
                    1 if voice["voice_id"] in MIMO_DEFAULT_ENABLED_IDS else 0,
                    voice["sort_order"],
                ),
            )

    def _apply_column_migration(self, cursor, version: str, table: str,
                                columns: Dict[str, str]) -> None:
        cursor.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,))
        if cursor.fetchone():
            return

        cursor.execute(f"PRAGMA table_info({table})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column_name, column_definition in columns.items():
            if column_name in existing_columns:
                continue
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN {column_name} {column_definition}"
            )

        cursor.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        logger.info(f"SQLite 迁移已应用: {version}")

    def _get_conn(self):
        """获取数据库连接"""
        if not self._initialized:
            self._init_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            logger.warning("SQLite 不可用，跳过数据库操作")
            yield None
            return
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()

    def _row_to_dict(self, row):
        """将 sqlite3.Row 转为 dict"""
        if row is None:
            return None
        return dict(row)

    def _rows_to_dicts(self, rows):
        return [dict(r) for r in rows]

    def create_task(
        self,
        task_id: str,
        theme: str,
        style: str,
        length: int,
        name: str = None,
        ratio: str = "16:9",
        voice_type: str = None,
        tts_options: Dict = None,
        execution_mode: str = "full",
        script_policy: str = "rewrite",
    ) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO tasks
                   (task_id, name, theme, style, length, ratio, voice_type,
                    tts_options_json, status, current_step, execution_mode,
                    workflow_phase, script_policy, voice_confirmed)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task_id, name or theme[:20], theme, style, length, ratio,
                    voice_type,
                    json.dumps(tts_options, ensure_ascii=False) if tts_options else None,
                    'pending', 'pending', execution_mode,
                    'planning' if execution_mode == 'review_first' else 'pending',
                    script_policy, 0,
                )
            )
            steps = [
                "text_generation",
                "image_prompt_generation",
                "voiceover_generation",
                "image_generation",
                "draft_building",
            ]
            for step in steps:
                cur.execute(
                    "INSERT INTO task_steps (task_id, step_name, status) VALUES (?,?,?)",
                    (task_id, step, 'pending')
                )
            conn.commit()
            conn.close()
            logger.info(f"任务记录创建成功: {task_id}")
            return True
        except Exception as e:
            logger.error(f"创建任务记录失败: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM task_segments WHERE task_id=?", (task_id,))
            cur.execute("DELETE FROM task_assets WHERE task_id=?", (task_id,))
            cur.execute("DELETE FROM task_steps WHERE task_id=?", (task_id,))
            cur.execute("DELETE FROM task_results WHERE task_id=?", (task_id,))
            cur.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()
            logger.info(f"任务记录已删除: {task_id}")
            return True
        except Exception as e:
            logger.error(f"删除任务记录失败: {e}")
            return False

    def update_task_status(self, task_id: str, status: str, current_step: str = None, error: str = None) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            if status == "completed":
                cur.execute(
                    "UPDATE tasks SET status=?, current_step=?, error=?, completed_at=datetime('now','localtime'), updated_at=datetime('now','localtime') WHERE task_id=?",
                    (status, current_step, error, task_id)
                )
            else:
                cur.execute(
                    "UPDATE tasks SET status=?, current_step=?, error=?, updated_at=datetime('now','localtime') WHERE task_id=?",
                    (status, current_step, error, task_id)
                )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            return False

    def mark_task_interrupted(
        self, task_id: str, current_step: str = None, error: str = None
    ) -> bool:
        """Mark a task interrupted unless deletion has already claimed it."""
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE tasks
                   SET status='interrupted', current_step=?, error=?,
                       updated_at=datetime('now','localtime')
                   WHERE task_id=? AND status != 'deleting'""",
                (current_step, error, task_id),
            )
            updated = cur.rowcount > 0
            conn.commit()
            conn.close()
            return updated
        except Exception as exc:
            logger.error(f"标记任务中断失败: {exc}")
            return False

    def _update_task_fields(self, task_id: str, updates: Dict) -> bool:
        fields = {
            key: value for key, value in updates.items()
            if key in self.TASK_CHECKPOINT_COLUMNS
        }
        if not fields:
            return False

        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            set_parts = [f"{key}=?" for key in fields]
            values = list(fields.values())
            values.append(task_id)
            cur.execute(
                f"UPDATE tasks SET {', '.join(set_parts)}, "
                "updated_at=datetime('now','localtime') WHERE task_id=?",
                values,
            )
            updated = cur.rowcount > 0
            conn.commit()
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"更新任务检查点失败: {e}")
            return False

    def save_task_checkpoint(self, task_id: str, script_text: str = None,
                             summary: str = None, input_mode: str = None,
                             execution_mode: str = None,
                             workflow_phase: str = None,
                             script_policy: str = None,
                             voice_confirmed: int = None) -> bool:
        values = {
            "script_text": script_text,
            "summary": summary,
            "input_mode": input_mode,
            "execution_mode": execution_mode,
            "workflow_phase": workflow_phase,
            "script_policy": script_policy,
            "voice_confirmed": voice_confirmed,
        }
        updates = {key: value for key, value in values.items() if value is not None}
        return self._update_task_fields(task_id, updates)

    def update_task_workflow(
        self,
        task_id: str,
        workflow_phase: str,
        status: str = None,
        current_step: str = None,
    ) -> bool:
        """Persist a workflow transition without losing the task checkpoint."""
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            fields = ["workflow_phase=?", "updated_at=datetime('now','localtime')"]
            values = [workflow_phase]
            if status is not None:
                fields.append("status=?")
                values.append(status)
            if current_step is not None:
                fields.append("current_step=?")
                values.append(current_step)
            values.append(task_id)
            cur.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE task_id=?",
                values,
            )
            updated = cur.rowcount > 0
            conn.commit()
            conn.close()
            return updated
        except Exception as exc:
            logger.error(f"更新任务工作流失败: {exc}")
            return False

    def update_task_plan_fields(
        self,
        task_id: str,
        updates: Dict,
        expected_plan_version: int = None,
    ) -> Optional[int]:
        """Atomically update task settings and advance the plan version."""
        allowed = {
            "style", "ratio", "voice_type", "tts_options_json", "voice_confirmed",
            "script_text", "summary", "workflow_phase",
        }
        fields = {key: value for key, value in updates.items() if key in allowed}
        if not fields:
            return None
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT plan_version FROM tasks WHERE task_id=?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            current = int(row["plan_version"] or 0)
            if expected_plan_version is not None and current != int(expected_plan_version):
                return -1
            next_version = current + 1
            parts = [f"{key}=?" for key in fields]
            values = list(fields.values())
            parts.extend(["plan_version=?", "updated_at=datetime('now','localtime')"])
            values.extend([next_version, task_id])
            cur.execute(
                f"UPDATE tasks SET {', '.join(parts)} WHERE task_id=?",
                values,
            )
            conn.commit()
            return next_version
        except Exception as exc:
            conn.rollback()
            logger.error(f"更新任务预案字段失败: {exc}")
            return None
        finally:
            conn.close()

    def update_segment_plan(
        self,
        task_id: str,
        segment_index: int,
        updates: Dict,
        expected_plan_version: int = None,
    ) -> Optional[int]:
        """Atomically edit one segment and advance the task plan version."""
        fields = {
            key: value for key, value in updates.items()
            if key in self.SEGMENT_CHECKPOINT_COLUMNS
        }
        if not fields:
            return None
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT plan_version FROM tasks WHERE task_id=?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            current = int(row["plan_version"] or 0)
            if expected_plan_version is not None and current != int(expected_plan_version):
                return -1
            parts = [f"{key}=?" for key in fields]
            values = list(fields.values())
            values.extend([task_id, segment_index])
            cur.execute(
                f"UPDATE task_segments SET {', '.join(parts)}, "
                "updated_at=datetime('now','localtime') WHERE task_id=? AND segment_index=?",
                values,
            )
            if cur.rowcount <= 0:
                return None
            next_version = current + 1
            cur.execute(
                "UPDATE tasks SET plan_version=?, updated_at=datetime('now','localtime') WHERE task_id=?",
                (next_version, task_id),
            )
            conn.commit()
            return next_version
        except Exception as exc:
            conn.rollback()
            logger.error(f"更新分镜预案失败: {exc}")
            return None
        finally:
            conn.close()

    def replace_plan_segments(
        self,
        task_id: str,
        script_text: str,
        segments: List[Dict],
        expected_plan_version: int = None,
    ) -> Optional[int]:
        """Replace the whole plan in one transaction, removing obsolete tail rows."""
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT plan_version FROM tasks WHERE task_id=?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            current = int(row["plan_version"] or 0)
            if expected_plan_version is not None and current != int(expected_plan_version):
                return -1
            cur.execute("DELETE FROM task_segments WHERE task_id=?", (task_id,))
            for segment in segments:
                cur.execute(
                    """INSERT INTO task_segments
                       (task_id, segment_index, text, image_prompt, image_status,
                        audio_status, prompt_status, prompt_manual, prompt_needs_review)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        task_id, segment["segment_index"], segment["text"],
                        segment.get("image_prompt", ""),
                        segment.get("image_status", "pending"),
                        segment.get("audio_status", "pending"),
                        segment.get("prompt_status", "pending"),
                        int(bool(segment.get("prompt_manual"))),
                        int(bool(segment.get("prompt_needs_review"))),
                    ),
                )
            next_version = current + 1
            cur.execute(
                """UPDATE tasks SET script_text=?, plan_version=?, workflow_phase='planning',
                   status='interrupted', current_step='image_prompt_generation', error=NULL,
                   updated_at=datetime('now','localtime') WHERE task_id=?""",
                (script_text, next_version, task_id),
            )
            conn.commit()
            return next_version
        except Exception as exc:
            conn.rollback()
            logger.error(f"替换分镜预案失败: {exc}")
            return None
        finally:
            conn.close()

    def set_task_deletion_intent(self, task_id: str, delete_files: bool) -> bool:
        """Persist file cleanup intent so startup can finish deletion safely."""
        return self._update_task_fields(
            task_id, {"delete_files_on_delete": int(bool(delete_files))}
        )

    def save_task_result(self, task_id: str, draft_path: str, segments_count: int,
                         draft_url: str = None, video_url: str = None, total_duration: float = None) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO task_results (task_id, draft_path, draft_url, video_url, segments_count, total_duration)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(task_id) DO UPDATE SET
                   draft_path=excluded.draft_path, draft_url=excluded.draft_url,
                   video_url=excluded.video_url, segments_count=excluded.segments_count,
                   total_duration=excluded.total_duration""",
                (task_id, draft_path, draft_url, video_url, segments_count, total_duration)
            )
            conn.commit()
            conn.close()
            logger.info(f"任务结果保存成功: {task_id}")
            return True
        except Exception as e:
            logger.error(f"保存任务结果失败: {e}")
            return False

    def update_step(self, task_id: str, step_name: str, status: str,
                    progress: int = None, total: int = None, duration: float = None) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            if status == "processing":
                cur.execute(
                    "UPDATE task_steps SET status=?, started_at=datetime('now','localtime'), updated_at=datetime('now','localtime') WHERE task_id=? AND step_name=?",
                    (status, task_id, step_name)
                )
            elif status == "completed":
                cur.execute(
                    "UPDATE task_steps SET status=?, progress=?, total=?, duration=?, completed_at=datetime('now','localtime'), updated_at=datetime('now','localtime') WHERE task_id=? AND step_name=?",
                    (status, progress, total, duration, task_id, step_name)
                )
            else:
                cur.execute(
                    "UPDATE task_steps SET status=?, progress=?, total=?, updated_at=datetime('now','localtime') WHERE task_id=? AND step_name=?",
                    (status, progress, total, task_id, step_name)
                )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新步骤状态失败: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,))
            task = cur.fetchone()
            if not task:
                conn.close()
                return None
            task = dict(task)

            cur.execute("SELECT * FROM task_results WHERE task_id=?", (task_id,))
            result = cur.fetchone()
            task["result"] = dict(result) if result else None

            cur.execute("SELECT * FROM task_steps WHERE task_id=? ORDER BY id", (task_id,))
            steps = [dict(r) for r in cur.fetchall()]
            task["steps"] = steps

            conn.close()
            return task
        except Exception as e:
            logger.error(f"获取任务信息失败: {e}")
            return None

    def list_tts_voices(self, provider: str = None, include_disabled: bool = False) -> List[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return []
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            sql = "SELECT * FROM tts_voices WHERE 1=1"
            values = []
            if provider:
                sql += " AND provider=?"
                values.append(provider)
            if not include_disabled:
                sql += " AND is_enabled=1"
            sql += " ORDER BY provider ASC, sort_order DESC, id ASC"
            cur.execute(sql, values)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            for row in rows:
                row["id"] = build_voice_key(row["provider"], row["voice_id"])
                row["is_enabled"] = bool(row["is_enabled"])
                try:
                    row["capabilities"] = json.loads(row.get("capabilities_json") or "{}")
                except (TypeError, ValueError):
                    row["capabilities"] = {}
            return rows
        except Exception as e:
            logger.error(f"获取音色列表失败: {e}")
            return []

    def get_enabled_voices(self) -> List[Dict]:
        return self.list_tts_voices(include_disabled=False)

    def find_tts_voice(self, provider: str, voice_id: str) -> Optional[Dict]:
        rows = self.list_tts_voices(provider=provider, include_disabled=True)
        return next((row for row in rows if row["voice_id"] == voice_id), None)

    def set_voice_availability(self, voice_keys: List[str]) -> int:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return 0
        selections = {
            (selection.provider, selection.voice_id)
            for selection in (parse_voice_key(key) for key in voice_keys)
            if selection.kind == "preset"
        }
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT provider, voice_id FROM tts_voices")
            rows = cur.fetchall()
            for row in rows:
                cur.execute(
                    """UPDATE tts_voices SET is_enabled=?,
                       updated_at=datetime('now','localtime')
                       WHERE provider=? AND voice_id=?""",
                    (1 if (row["provider"], row["voice_id"]) in selections else 0,
                     row["provider"], row["voice_id"]),
                )
            conn.commit()
            conn.close()
            return len(rows)
        except Exception as e:
            logger.error(f"更新音色开放状态失败: {e}")
            return 0

    def update_voice_status(self, voice_id: str, is_enabled: bool) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE tts_voices SET is_enabled=? WHERE voice_id=?", (1 if is_enabled else 0, voice_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新音色状态失败: {e}")
            return False

    def create_voice_clone(self, record: Dict) -> Dict:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return {}
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO tts_voice_clones
                   (clone_id, provider, name, reference_path, duration, file_size,
                    status, preview_path, error_message, is_enabled, consent_confirmed)
                   VALUES (?, 'mimo', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["clone_id"], record["name"], record["reference_path"],
                    record.get("duration"), record.get("file_size"),
                    record.get("status", "draft"), record.get("preview_path"),
                    record.get("error_message"), 1 if record.get("is_enabled") else 0,
                    1 if record.get("consent_confirmed") else 0,
                ),
            )
            conn.commit()
            conn.close()
            return self.get_voice_clone(record["clone_id"]) or {}
        except Exception as exc:
            logger.error(f"创建克隆音色失败: {exc}")
            return {}

    def get_voice_clone(self, clone_id: str) -> Optional[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tts_voice_clones WHERE clone_id=?", (clone_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_voice_clones(self, include_hidden: bool = False) -> List[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return []
        conn = self._get_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM tts_voice_clones"
        if not include_hidden:
            sql += " WHERE status != 'hidden'"
        sql += " ORDER BY updated_at DESC, id DESC"
        cur.execute(sql)
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows

    def update_voice_clone(self, clone_id: str, updates: Dict) -> Optional[Dict]:
        allowed = {
            "name", "reference_path", "duration", "file_size", "status",
            "preview_path", "error_message", "is_enabled", "consent_confirmed",
        }
        fields = {key: value for key, value in updates.items() if key in allowed}
        if not fields:
            return self.get_voice_clone(clone_id)
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        conn = self._get_conn()
        cur = conn.cursor()
        parts = [f"{key}=?" for key in fields]
        values = [
            1 if key in {"is_enabled", "consent_confirmed"} and value else
            0 if key in {"is_enabled", "consent_confirmed"} else value
            for key, value in fields.items()
        ]
        values.append(clone_id)
        cur.execute(
            f"UPDATE tts_voice_clones SET {', '.join(parts)}, "
            "updated_at=datetime('now','localtime') WHERE clone_id=?",
            values,
        )
        conn.commit()
        conn.close()
        return self.get_voice_clone(clone_id)

    def delete_voice_clone(self, clone_id: str) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM tts_voice_clones WHERE clone_id=?", (clone_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def is_voice_clone_referenced(self, clone_id: str) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        key = f"mimo-clone:{clone_id}"
        conn = self._get_conn()
        cur = conn.cursor()
        checks = (
            ("SELECT 1 FROM tasks WHERE voice_type=? LIMIT 1", (key,)),
            ("SELECT 1 FROM task_segments WHERE audio_voice_type=? LIMIT 1", (key,)),
            ("SELECT 1 FROM task_assets WHERE voice_type=? LIMIT 1", (key,)),
        )
        referenced = False
        for sql, values in checks:
            cur.execute(sql, values)
            if cur.fetchone():
                referenced = True
                break
        conn.close()
        return referenced

    def update_extract_path(self, task_id: str, extract_path: str) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE tasks SET extract_path=? WHERE task_id=?", (extract_path, task_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新解压路径失败: {e}")
            return False

    def list_tasks(self, status: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return []
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            if status:
                cur.execute(
                    """SELECT t.*, r.draft_url, r.video_url, r.segments_count,
                              (
                                SELECT s.image_url
                                FROM task_segments s
                                WHERE s.task_id = t.task_id
                                  AND s.image_url IS NOT NULL
                                  AND TRIM(s.image_url) != ''
                                ORDER BY s.segment_index ASC
                                LIMIT 1
                              ) AS cover_image_url,
                              (
                                SELECT s.image_path
                                FROM task_segments s
                                WHERE s.task_id = t.task_id
                                  AND s.image_path IS NOT NULL
                                  AND TRIM(s.image_path) != ''
                                ORDER BY s.segment_index ASC
                                LIMIT 1
                              ) AS cover_image_path
                       FROM tasks t LEFT JOIN task_results r ON t.task_id = r.task_id
                       WHERE t.status=? ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
                    (status, limit, offset)
                )
            else:
                cur.execute(
                    """SELECT t.*, r.draft_url, r.video_url, r.segments_count,
                              (
                                SELECT s.image_url
                                FROM task_segments s
                                WHERE s.task_id = t.task_id
                                  AND s.image_url IS NOT NULL
                                  AND TRIM(s.image_url) != ''
                                ORDER BY s.segment_index ASC
                                LIMIT 1
                              ) AS cover_image_url,
                              (
                                SELECT s.image_path
                                FROM task_segments s
                                WHERE s.task_id = t.task_id
                                  AND s.image_path IS NOT NULL
                                  AND TRIM(s.image_path) != ''
                                ORDER BY s.segment_index ASC
                                LIMIT 1
                              ) AS cover_image_path
                       FROM tasks t LEFT JOIN task_results r ON t.task_id = r.task_id
                       WHERE t.status != ?
                       ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
                    ("deleting", limit, offset)
                )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return []

    def save_segments(self, task_id: str, segments: List[Dict]) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            for seg in segments:
                cur.execute(
                    """INSERT INTO task_segments
                       (task_id, segment_index, text, image_prompt, image_path,
                        image_url, image_status, image_error, audio_path, audio_url,
                        audio_status, audio_error, duration, audio_voice_type,
                        audio_tts_options_json, prompt_status, prompt_error,
                        prompt_manual, prompt_needs_review)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(task_id, segment_index) DO UPDATE SET
                       text=excluded.text, image_prompt=excluded.image_prompt,
                       image_path=COALESCE(excluded.image_path, task_segments.image_path),
                       image_url=COALESCE(excluded.image_url, task_segments.image_url),
                       image_status=COALESCE(excluded.image_status, task_segments.image_status),
                       image_error=COALESCE(excluded.image_error, task_segments.image_error),
                       audio_path=COALESCE(excluded.audio_path, task_segments.audio_path),
                       audio_url=COALESCE(excluded.audio_url, task_segments.audio_url),
                       audio_status=COALESCE(excluded.audio_status, task_segments.audio_status),
                       audio_error=COALESCE(excluded.audio_error, task_segments.audio_error),
                       audio_voice_type=COALESCE(excluded.audio_voice_type, task_segments.audio_voice_type),
                       audio_tts_options_json=COALESCE(excluded.audio_tts_options_json, task_segments.audio_tts_options_json),
                       prompt_status=COALESCE(excluded.prompt_status, task_segments.prompt_status),
                       prompt_error=COALESCE(excluded.prompt_error, task_segments.prompt_error),
                       prompt_manual=COALESCE(excluded.prompt_manual, task_segments.prompt_manual),
                       prompt_needs_review=COALESCE(excluded.prompt_needs_review, task_segments.prompt_needs_review),
                       duration=COALESCE(excluded.duration, task_segments.duration),
                       updated_at=datetime('now','localtime')""",
                    (task_id, seg['segment_index'], seg['text'],
                     seg.get('image_prompt'),
                     seg.get('image_path'), seg.get('image_url'),
                     seg.get('image_status'), seg.get('image_error'),
                     seg.get('audio_path'), seg.get('audio_url'),
                     seg.get('audio_status'), seg.get('audio_error'),
                     seg.get('duration'), seg.get('audio_voice_type'),
                     seg.get('audio_tts_options_json'),
                     seg.get('prompt_status') or ('completed' if seg.get('image_prompt') else 'pending'),
                     seg.get('prompt_error'), int(bool(seg.get('prompt_manual'))),
                     int(bool(seg.get('prompt_needs_review'))))
                )
            conn.commit()
            conn.close()
            logger.info(f"任务段落保存成功: {task_id}, 共 {len(segments)} 段")
            return True
        except Exception as e:
            logger.error(f"保存任务段落失败: {e}")
            return False

    def get_segments(self, task_id: str) -> List[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return []
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM task_segments WHERE task_id=? ORDER BY segment_index ASC", (task_id,))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"获取任务段落失败: {e}")
            return []

    def update_segment(self, task_id: str, segment_index: int, updates: Dict) -> bool:
        return self._update_segment_fields(task_id, segment_index, updates)

    def update_segment_checkpoint(self, task_id: str, segment_index: int, **updates) -> bool:
        return self._update_segment_fields(task_id, segment_index, updates)

    def _update_segment_fields(self, task_id: str, segment_index: int, updates: Dict) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            set_parts = []
            values = []
            for key, value in updates.items():
                if value is None and key not in self.CLEARABLE_SEGMENT_ERROR_COLUMNS:
                    continue
                if key in self.SEGMENT_CHECKPOINT_COLUMNS:
                    set_parts.append(f"{key}=?")
                    values.append(value)
            if not set_parts:
                conn.close()
                return False
            values.extend([task_id, segment_index])
            cur.execute(
                f"UPDATE task_segments SET {', '.join(set_parts)}, "
                "updated_at=datetime('now','localtime') WHERE task_id=? AND segment_index=?",
                values
            )
            updated = cur.rowcount > 0
            conn.commit()
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"更新段落失败: {e}")
            return False

    def save_task_asset(self, task_id: str, asset_type: str, source: str, path: str = None,
                        url: str = None, segment_index: int = None, label: str = None,
                        prompt: str = None, text: str = None, voice_type: str = None,
                        metadata_json: str = None, status: str = "completed", error_message: str = None) -> Dict:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return {}
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            if source == "generated" and segment_index is not None:
                cur.execute(
                    """SELECT * FROM task_assets
                       WHERE task_id=? AND asset_type=? AND source=? AND segment_index=?
                       ORDER BY id DESC LIMIT 1""",
                    (task_id, asset_type, source, segment_index)
                )
            elif path:
                cur.execute(
                    """SELECT * FROM task_assets
                       WHERE task_id=? AND asset_type=? AND source=? AND path=?
                       ORDER BY id DESC LIMIT 1""",
                    (task_id, asset_type, source, path)
                )
            else:
                cur.execute(
                    """SELECT * FROM task_assets
                       WHERE task_id=? AND asset_type=? AND source=? AND segment_index=?
                       ORDER BY id DESC LIMIT 1""",
                    (task_id, asset_type, source, segment_index)
                )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE task_assets SET segment_index=?, source=?, path=COALESCE(?, path),
                       url=COALESCE(?, url), label=?,
                       prompt=?, text=?, voice_type=?, metadata_json=?, status=?, error_message=?,
                       updated_at=datetime('now','localtime')
                       WHERE asset_id=?""",
                    (segment_index, source, path, url, label, prompt, text, voice_type, metadata_json, status, error_message, existing["asset_id"])
                )
                conn.commit()
                cur.execute("SELECT * FROM task_assets WHERE asset_id=?", (existing["asset_id"],))
                row = dict(cur.fetchone())
                conn.close()
                return row

            asset_id = uuid.uuid4().hex
            cur.execute(
                """INSERT INTO task_assets
                   (asset_id, task_id, segment_index, asset_type, source, path, url, label, prompt, text, voice_type, metadata_json, status, error_message)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (asset_id, task_id, segment_index, asset_type, source, path, url, label, prompt, text, voice_type, metadata_json, status, error_message)
            )
            conn.commit()
            cur.execute("SELECT * FROM task_assets WHERE asset_id=?", (asset_id,))
            row = dict(cur.fetchone())
            conn.close()
            return row
        except Exception as e:
            logger.error(f"保存任务资产失败: {e}")
            return {}

    def list_task_assets(self, task_id: str, asset_type: str = None, segment_index: int = None) -> List[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return []
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            sql = "SELECT * FROM task_assets WHERE task_id=?"
            values = [task_id]
            if asset_type:
                if asset_type == "upload":
                    sql += " AND source='upload'"
                else:
                    sql += " AND asset_type=?"
                    values.append(asset_type)
            if segment_index is not None:
                sql += " AND segment_index=?"
                values.append(segment_index)
            sql += " ORDER BY created_at DESC, id DESC"
            cur.execute(sql, values)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"获取任务资产失败: {e}")
            return []

    def get_task_asset(self, task_id: str, asset_id: str) -> Optional[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return None
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM task_assets WHERE task_id=? AND asset_id=?", (task_id, asset_id))
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取任务资产失败: {e}")
            return None


# 全局 SQLite 客户端实例
sqlite_client = SQLiteClient()
