import threading
import time

import pytest

from src.api import task_executor as task_executor_module
from src.api.task_executor import TaskExecutor
from src.api.task_runtime import TaskCancelled, TaskRuntimeRegistry


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


def test_finish_does_not_remove_a_newer_token():
    registry = TaskRuntimeRegistry()
    old_token = registry.begin("task-1")
    registry.finish("task-1", old_token)
    new_token = registry.begin("task-1")

    registry.finish("task-1", old_token)

    assert registry.is_running("task-1")
    assert not new_token.is_cancelled()


def test_request_cancel_returns_false_for_unknown_task():
    registry = TaskRuntimeRegistry()

    assert not registry.request_cancel("missing-task")


def test_wait_until_stopped_observes_finish():
    registry = TaskRuntimeRegistry()
    token = registry.begin("task-1")
    release = threading.Event()

    def finish_task():
        release.wait()
        registry.finish("task-1", token)

    thread = threading.Thread(target=finish_task)
    thread.start()
    try:
        assert not registry.wait_until_stopped("task-1", timeout=0.01)
        release.set()
        assert registry.wait_until_stopped("task-1", timeout=1)
    finally:
        release.set()
        thread.join()


def test_wait_until_stopped_returns_immediately_for_unknown_task():
    registry = TaskRuntimeRegistry()

    assert registry.wait_until_stopped("missing-task", timeout=0)


def test_execute_task_registers_once_and_starts_daemon_thread(monkeypatch):
    registry = TaskRuntimeRegistry()
    created_threads = []

    class DeferredThread:
        def __init__(self, target, args):
            self.target = target
            self.args = args
            self.daemon = False
            self.started = False
            created_threads.append(self)

        def start(self):
            self.started = True

    monkeypatch.setattr(task_executor_module, "task_runtime", registry, raising=False)
    monkeypatch.setattr(task_executor_module, "Thread", DeferredThread)
    executor = TaskExecutor()

    assert executor.execute_task("task-1", "theme", "style", 100)
    assert not executor.execute_task("task-1", "theme", "style", 100)
    assert len(created_threads) == 1
    assert created_threads[0].daemon
    assert created_threads[0].started


def test_registered_worker_always_finishes_after_error(monkeypatch):
    registry = TaskRuntimeRegistry()

    class InlineThread:
        def __init__(self, target, args):
            self.target = target
            self.args = args
            self.daemon = False

        def start(self):
            try:
                self.target(*self.args)
            except RuntimeError:
                pass

    def fail_task(*args, cancellation, **kwargs):
        assert cancellation is not None
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(task_executor_module, "task_runtime", registry, raising=False)
    monkeypatch.setattr(task_executor_module, "Thread", InlineThread)
    executor = TaskExecutor()
    monkeypatch.setattr(executor, "_run_task", fail_task)

    assert executor.execute_task("task-1", "theme", "style", 100)
    assert not registry.is_running("task-1")


def test_cancel_task_requests_cancel_and_waits_for_finish(monkeypatch):
    registry = TaskRuntimeRegistry()
    token = registry.begin("task-1")
    monkeypatch.setattr(task_executor_module, "task_runtime", registry, raising=False)

    def stop_after_cancel():
        while not token.is_cancelled():
            time.sleep(0.001)
        registry.finish("task-1", token)

    worker = threading.Thread(target=stop_after_cancel)
    worker.start()
    try:
        assert TaskExecutor().cancel_task("task-1", timeout=1)
    finally:
        token.cancel()
        worker.join()


def test_cancel_task_is_successful_when_task_is_already_stopped(monkeypatch):
    registry = TaskRuntimeRegistry()
    monkeypatch.setattr(task_executor_module, "task_runtime", registry, raising=False)

    assert TaskExecutor().cancel_task("missing-task", timeout=0)


def test_cancel_task_returns_false_when_worker_does_not_stop(monkeypatch):
    registry = TaskRuntimeRegistry()
    token = registry.begin("task-1")
    monkeypatch.setattr(task_executor_module, "task_runtime", registry, raising=False)
    try:
        assert not TaskExecutor().cancel_task("task-1", timeout=0.01)
    finally:
        registry.finish("task-1", token)
