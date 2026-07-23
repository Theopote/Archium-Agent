"""WF-002: shared Sqlite checkpoint serialization for concurrent continue."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
from archium.exceptions import WorkflowError
from archium.workflow.checkpointer import WorkflowCheckpointerManager


def test_serialized_execution_rejects_concurrent_same_run(tmp_path: Path) -> None:
    manager = WorkflowCheckpointerManager(tmp_path / "wf.db")
    thread_id = str(uuid4())
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def holder() -> None:
        try:
            with manager.serialized_execution(thread_id):
                entered.set()
                release.wait(timeout=5)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=holder)
    t.start()
    assert entered.wait(timeout=5)

    with pytest.raises(WorkflowError, match="WF-002|正在执行"):
        with manager.serialized_execution(thread_id):
            pass

    release.set()
    t.join(timeout=5)
    assert not errors
    assert not manager.is_run_busy(thread_id)

    # After release, same run can enter again.
    with manager.serialized_execution(thread_id):
        assert manager.saver is not None
    manager.close()


def test_serialized_execution_serializes_different_runs_on_shared_db(
    tmp_path: Path,
) -> None:
    """Global DB lock: two runs never touch SqliteSaver concurrently."""
    manager = WorkflowCheckpointerManager(tmp_path / "wf.db")
    active = 0
    max_active = 0
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def worker(run_id: str) -> None:
        nonlocal active, max_active
        barrier.wait(timeout=5)
        with manager.serialized_execution(run_id):
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1

    threads = [
        threading.Thread(target=worker, args=(str(uuid4()),)),
        threading.Thread(target=worker, args=(str(uuid4()),)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert max_active == 1
    manager.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    manager = WorkflowCheckpointerManager(tmp_path / "wf.db")
    _ = manager.saver
    manager.close()
    manager.close()


def test_presentation_service_does_not_close_shared_checkpointer(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from archium.application.presentation_workflow_service import (
        PresentationWorkflowService,
    )
    from archium.config.settings import Settings

    settings = Settings(workflow_checkpoint_path=tmp_path / "shared.db")
    manager = WorkflowCheckpointerManager(settings.workflow_checkpoint_path)
    _ = manager.saver
    service = PresentationWorkflowService(
        MagicMock(),
        MagicMock(),
        settings=settings,
        checkpointer_manager=manager,
    )
    service.close()
    # Shared manager must remain usable.
    assert manager.saver is not None
    manager.close()
