"""Workflow orchestration services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "PlanningWorkflowService",
    "WorkflowRouteService",
    "WorkflowProgress",
    "WorkflowCheckpoint",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "PlanningWorkflowService": ("archium.application.workflow.planning_workflow_service", "PlanningWorkflowService"),
    "WorkflowRouteService": ("archium.application.workflow.workflow_route_service", "WorkflowRouteService"),
    "WorkflowProgress": ("archium.application.workflow.workflow_progress", "WorkflowProgress"),
    "WorkflowCheckpoint": ("archium.application.workflow.workflow_checkpoint", "WorkflowCheckpoint"),
}

def __getattr__(name: str) -> Any:
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module
    
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value
