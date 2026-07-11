"""Thread-safe runtime lifecycle tracking for background tasks."""

import threading
from typing import Dict, Optional


class TaskCancelled(RuntimeError):
    """Raised when a task reaches a checkpoint after cancellation."""


class TaskCancellation:
    """Cancellation token owned by one registered task execution."""

    def __init__(self):
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise TaskCancelled("Task execution was cancelled")


class TaskRuntimeRegistry:
    """Tracks at most one active execution token per task ID."""

    def __init__(self):
        self._condition = threading.Condition()
        self._tokens: Dict[str, TaskCancellation] = {}

    def begin(self, task_id: str) -> Optional[TaskCancellation]:
        with self._condition:
            if task_id in self._tokens:
                return None
            token = TaskCancellation()
            self._tokens[task_id] = token
            return token

    def finish(self, task_id: str, token: TaskCancellation) -> None:
        with self._condition:
            if self._tokens.get(task_id) is not token:
                return
            del self._tokens[task_id]
            self._condition.notify_all()

    def request_cancel(self, task_id: str) -> bool:
        with self._condition:
            token = self._tokens.get(task_id)
            if token is None:
                return False
            token.cancel()
            return True

    def wait_until_stopped(self, task_id: str, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: task_id not in self._tokens,
                timeout=timeout,
            )

    def is_running(self, task_id: str) -> bool:
        with self._condition:
            return task_id in self._tokens


task_runtime = TaskRuntimeRegistry()
