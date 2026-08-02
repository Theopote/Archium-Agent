"""Mission planning and clarification services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "MissionClarificationService",
    "MissionHistoryService", 
    "MissionResearchEnrichmentService",
    "MissionValidationService",
    "MissionToPresentationRequest",
    "DeliverablePlanningService",
    "WorkstreamPlanningService",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "MissionClarificationService": ("archium.application.mission.mission_clarification_service", "MissionClarificationService"),
    "MissionHistoryService": ("archium.application.mission.mission_history_service", "MissionHistoryService"),
    "MissionResearchEnrichmentService": ("archium.application.mission.mission_research_enrichment_service", "MissionResearchEnrichmentService"),
    "MissionValidationService": ("archium.application.mission.mission_validation_service", "MissionValidationService"),
    "MissionToPresentationRequest": ("archium.application.mission.mission_to_presentation_request", "MissionToPresentationRequest"),
    "DeliverablePlanningService": ("archium.application.mission.deliverable_planning_service", "DeliverablePlanningService"),
    "WorkstreamPlanningService": ("archium.application.mission.workstream_planning_service", "WorkstreamPlanningService"),
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
