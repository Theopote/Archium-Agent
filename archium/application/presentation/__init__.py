"""Presentation generation and workflow services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "PresentationService",
    "PresentationWorkflowService",
    "PresentationManuscriptService",
    "PresentationIntentLayer",
    "PresentationCritic",
    "OutlineService",
    "SlideDesignBriefService",
    "SlideGenerationContextService",
    "RegenerationService",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "PresentationService": ("archium.application.presentation.presentation_service", "PresentationService"),
    "PresentationWorkflowService": ("archium.application.presentation.presentation_workflow_service", "PresentationWorkflowService"),
    "PresentationManuscriptService": ("archium.application.presentation.presentation_manuscript_service", "PresentationManuscriptService"),
    "PresentationIntentLayer": ("archium.application.presentation.presentation_intent_layer", "PresentationIntentLayer"),
    "PresentationCritic": ("archium.application.presentation.presentation_critic", "PresentationCritic"),
    "OutlineService": ("archium.application.presentation.outline_service", "OutlineService"),
    "SlideDesignBriefService": ("archium.application.presentation.slide_design_brief_service", "SlideDesignBriefService"),
    "SlideGenerationContextService": ("archium.application.presentation.slide_generation_context_service", "SlideGenerationContextService"),
    "RegenerationService": ("archium.application.presentation.regeneration_service", "RegenerationService"),
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
