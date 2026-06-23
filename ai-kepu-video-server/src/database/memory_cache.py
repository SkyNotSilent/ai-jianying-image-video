"""
内存缓存客户端
缓存任务和进度数据
"""

import json
import logging
import time
from typing import Optional, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存"""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}  # key -> {"data": ..., "expire_at": ...}
        self._lock = Lock()
        self._initialized = True
        logger.info("内存缓存初始化成功")

    def _task_key(self, task_id: str) -> str:
        return f"task:{task_id}"

    def _progress_key(self, task_id: str) -> str:
        return f"task:progress:{task_id}"

    def _set(self, key: str, value: Any, ttl: int = 86400):
        with self._lock:
            self._store[key] = {
                "data": value,
                "expire_at": time.time() + ttl
            }

    def _get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry["expire_at"]:
                del self._store[key]
                return None
            return entry["data"]

    def _delete(self, *keys):
        with self._lock:
            for key in keys:
                self._store.pop(key, None)

    def _expire(self, key: str, ttl: int):
        with self._lock:
            entry = self._store.get(key)
            if entry:
                entry["expire_at"] = time.time() + ttl

    def cache_task(self, task_id: str, task_data: Dict[str, Any], ttl: int = 86400) -> bool:
        try:
            key = self._task_key(task_id)
            self._set(key, json.dumps(task_data, ensure_ascii=False), ttl)
            return True
        except Exception as e:
            logger.error(f"缓存任务数据失败: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._task_key(task_id)
            data = self._get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取缓存任务数据失败: {e}")
            return None

    def delete_task(self, task_id: str) -> bool:
        try:
            key = self._task_key(task_id)
            progress_key = self._progress_key(task_id)
            self._delete(key, progress_key)
            return True
        except Exception as e:
            logger.error(f"删除任务缓存失败: {e}")
            return False

    def update_progress(self, task_id: str, current_step: str, steps: Dict[str, Dict[str, Any]], ttl: int = 86400) -> bool:
        try:
            key = self._progress_key(task_id)
            progress_data = {
                "current_step": current_step,
                "steps": steps,
            }
            self._set(key, json.dumps(progress_data, ensure_ascii=False), ttl)
            return True
        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
            return False

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._progress_key(task_id)
            data = self._get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取任务进度失败: {e}")
            return None

    def set_step_progress(self, task_id: str, step_name: str, status: str,
                          progress: int = None, total: int = None, duration: float = None) -> bool:
        try:
            progress_data = self.get_progress(task_id)
            if not progress_data:
                progress_data = {"current_step": step_name, "steps": {}}

            if step_name not in progress_data["steps"]:
                progress_data["steps"][step_name] = {}

            progress_data["steps"][step_name]["status"] = status
            if progress is not None:
                progress_data["steps"][step_name]["progress"] = progress
            if total is not None:
                progress_data["steps"][step_name]["total"] = total
            if duration is not None:
                progress_data["steps"][step_name]["duration"] = duration

            key = self._progress_key(task_id)
            self._set(key, json.dumps(progress_data, ensure_ascii=False), 86400)
            return True
        except Exception as e:
            logger.error(f"更新步骤进度失败: {e}")
            return False

    def extend_ttl(self, task_id: str, ttl: int = 86400) -> bool:
        try:
            key = self._task_key(task_id)
            progress_key = self._progress_key(task_id)
            self._expire(key, ttl)
            self._expire(progress_key, ttl)
            return True
        except Exception as e:
            logger.error(f"延长缓存过期时间失败: {e}")
            return False


# 全局内存缓存实例
memory_cache = MemoryCache()
