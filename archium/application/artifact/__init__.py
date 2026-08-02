"""Artifact and job management services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ArtifactHistoryService",
    "ArtifactJobService",
    "ArtifactPolicyService",
    "ArtifactSnapshots",
    "ArtifactLineage",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ArtifactHistoryService": ("archium.application.artifact.artifact_history_service", "ArtifactHistoryService"),
    "ArtifactJobService": ("archium.application.artifact.artifact_job_service", "ArtifactJobService"),
    "ArtifactPolicyService": ("archium.application.artifact.artifact_policy_service", "ArtifactPolicyService"),
    "ArtifactSnapshots": ("archium.application.artifact.artifact_snapshots", "ArtifactSnapshots"),
    "ArtifactLineage": ("archium.application.artifact.artifact_lineage", "ArtifactLineage"),
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
