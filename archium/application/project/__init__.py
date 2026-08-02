"""Project management and access services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ProjectManagementService",
    "ProjectAccessService",
    "ProjectMissionService",
    "ProjectKnowledgeService",
    "ProjectEventService",
    "ProjectInviteService",
    "ProjectDeletionService",
    "OrganizationService",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ProjectManagementService": ("archium.application.project.project_management_service", "ProjectManagementService"),
    "ProjectAccessService": ("archium.application.project.project_access_service", "ProjectAccessService"),
    "ProjectMissionService": ("archium.application.project.project_mission_service", "ProjectMissionService"),
    "ProjectKnowledgeService": ("archium.application.project.project_knowledge_service", "ProjectKnowledgeService"),
    "ProjectEventService": ("archium.application.project.project_event_service", "ProjectEventService"),
    "ProjectInviteService": ("archium.application.project.project_invite_service", "ProjectInviteService"),
    "ProjectDeletionService": ("archium.application.project.project_deletion_service", "ProjectDeletionService"),
    "OrganizationService": ("archium.application.project.organization_service", "OrganizationService"),
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
