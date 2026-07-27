"""WF-004: resume attaches to LangGraph checkpoint — never replays from START."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from archium.exceptions import WorkflowError


def checkpoint_is_resumable(graph: CompiledStateGraph, thread_id: str) -> bool:
    """True when the thread has pending next nodes or interrupt tasks."""
    config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}
    try:
        snap = graph.get_state(config)
    except Exception:  # noqa: BLE001 — missing/corrupt checkpoint ⇒ not resumable
        return False
    if snap is None:
        return False
    if snap.next:
        return True
    tasks = getattr(snap, "tasks", ()) or ()
    for task in tasks:
        interrupts = getattr(task, "interrupts", None)
        if interrupts:
            return True
    return False


def ensure_resumable_checkpoint(
    *,
    workflow_run_id: UUID | str,
    status: str,
    resumable: bool,
) -> None:
    """Raise when resume would otherwise rebuild input and invoke from START."""
    if resumable:
        return
    raise WorkflowError(
        f"Workflow run {workflow_run_id} 无可恢复的 interrupt/checkpoint"
        f"（status={status}）。resume 拒绝从 START 重跑（WF-004）；"
        "请在审批门禁后 continue，或新建工作流。"
    )


def snapshot_looks_resumable(snap: Any) -> bool:
    """Test helper / pure check for a LangGraph StateSnapshot-like object."""
    if snap is None:
        return False
    if getattr(snap, "next", None):
        return True
    tasks = getattr(snap, "tasks", ()) or ()
    return any(getattr(task, "interrupts", None) for task in tasks)
