"""
SQLite 数据库客户端
本地持久化任务、分镜和素材数据
"""

import logging
import sqlite3
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "local.db"


class SQLiteClient:
    """SQLite 数据库客户端"""

    TASK_CHECKPOINT_COLUMNS = frozenset({"script_text", "summary", "input_mode"})
    SEGMENT_CHECKPOINT_COLUMNS = frozenset({
        "text", "image_prompt", "image_path", "image_url", "image_status",
        "image_error", "audio_path", "audio_url", "audio_status", "audio_error",
        "duration",
    })
    CLEARABLE_SEGMENT_ERROR_COLUMNS = frozenset({"image_error", "audio_error"})

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
                    completed_at TEXT
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
                    voice_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    description TEXT,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
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

            # 插入默认音色数据（如果表为空）
            cursor.execute("SELECT COUNT(*) FROM tts_voices")
            if cursor.fetchone()[0] == 0:
                voices = [
                    ('zh_female_shuangkuaisisi_moon_bigtts', '爽快思思', 'female', '活泼开朗，适合轻松愉快的内容', 1, 100),
                    ('zh_female_wanwanxiaohe_moon_bigtts', '弯弯小鹤', 'female', '温柔甜美，适合温馨治愈的内容', 1, 90),
                    ('zh_female_tianmeibeibei_moon_bigtts', '甜美贝贝', 'female', '甜美可爱，适合少女风格内容', 1, 80),
                    ('zh_female_qingxinruoxi_moon_bigtts', '清新若溪', 'female', '清新自然，适合文艺清新内容', 1, 70),
                    ('zh_female_wenrouxiaoya_moon_bigtts', '温柔小雅', 'female', '温柔知性，适合知识科普内容', 1, 60),
                    ('zh_female_mizai_uranus_bigtts', '米仔', 'female', '自然真实，适合故事讲述', 1, 50),
                    ('zh_male_wennuanahu_moon_bigtts', '温暖阿虎', 'male', '温暖磁性，适合情感类内容', 1, 40),
                    ('zh_male_qingchexiaoxin_moon_bigtts', '清澈小新', 'male', '清澈明朗，适合青春活力内容', 1, 30),
                    ('zh_male_yangguangxiaolei_moon_bigtts', '阳光小磊', 'male', '阳光开朗，适合励志正能量内容', 1, 20),
                    ('zh_male_chenwendongge_moon_bigtts', '沉稳东哥', 'male', '沉稳大气，适合严肃专业内容', 1, 10),
                ]
                cursor.executemany(
                    "INSERT INTO tts_voices (voice_id, name, gender, description, is_enabled, sort_order) VALUES (?,?,?,?,?,?)",
                    voices
                )

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

    def create_task(self, task_id: str, theme: str, style: str, length: int, name: str = None, ratio: str = "16:9", voice_type: str = None) -> bool:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO tasks (task_id, name, theme, style, length, ratio, voice_type, status, current_step) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, name or theme[:20], theme, style, length, ratio, voice_type, 'pending', 'pending')
            )
            steps = [
                "text_generation",
                "image_prompt_generation",
                "voiceover_generation",
                "image_generation",
                "draft_building",
                "video_synthesis",
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
                             summary: str = None, input_mode: str = None) -> bool:
        values = {
            "script_text": script_text,
            "summary": summary,
            "input_mode": input_mode,
        }
        updates = {key: value for key, value in values.items() if value is not None}
        return self._update_task_fields(task_id, updates)

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

    def get_enabled_voices(self) -> List[Dict]:
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return []
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT voice_id, name, gender, description, sort_order FROM tts_voices WHERE is_enabled=1 ORDER BY sort_order DESC, id ASC")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"获取音色列表失败: {e}")
            return []

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
                    """INSERT INTO task_segments (task_id, segment_index, text, image_prompt, image_path, image_url, image_status, image_error, audio_path, audio_url, audio_status, audio_error, duration)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                       duration=COALESCE(excluded.duration, task_segments.duration),
                       updated_at=datetime('now','localtime')""",
                    (task_id, seg['segment_index'], seg['text'],
                     seg.get('image_prompt'),
                     seg.get('image_path'), seg.get('image_url'),
                     seg.get('image_status'), seg.get('image_error'),
                     seg.get('audio_path'), seg.get('audio_url'),
                     seg.get('audio_status'), seg.get('audio_error'),
                     seg.get('duration'))
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

    def normalize_generated_task_asset(
        self, task_id: str, segment_index: int, asset_type: str,
        path: str = None, url: str = None,
    ) -> bool:
        """Clear stale errors on an existing generated checkpoint without inserting."""
        if not self._initialized:
            self._init_db()
        if not self._initialized:
            return False
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE task_assets
                   SET path=COALESCE(?, path), url=COALESCE(?, url),
                       status='completed', error_message=NULL,
                       updated_at=datetime('now','localtime')
                   WHERE task_id=? AND segment_index=? AND asset_type=?
                     AND source='generated'""",
                (path, url, task_id, segment_index, asset_type),
            )
            updated = cur.rowcount > 0
            conn.commit()
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"规范化任务资产检查点失败: {e}")
            return False

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
