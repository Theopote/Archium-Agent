"""Application services.

Imports are lazy so infrastructure modules can depend on
``archium.application.visual.*`` without circular package init.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ImportItemResult",
    "IngestionService",
    "PipelineResult",
    "PresentationRequest",
    "PresentationService",
    "PresentationReviewService",
    "PresentationWorkflowService",
    "RegenerationService",
    "RetrievalService",
    "create_retrieval_service",
    "WorkflowRunResult",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ImportItemResult": ("archium.application.ingestion_service", "ImportItemResult"),
    "IngestionService": ("archium.application.ingestion_service", "IngestionService"),
    "PipelineResult": ("archium.application.presentation_models", "PipelineResult"),
    "PresentationRequest": ("archium.application.presentation_models", "PresentationRequest"),
    "PresentationService": ("archium.application.presentation_service", "PresentationService"),
    "PresentationReviewService": (
        "archium.application.review_service",
        "PresentationReviewService",
    ),
    "PresentationWorkflowService": (
        "archium.application.presentation_workflow_service",
        "PresentationWorkflowService",
    ),
    "RegenerationService": ("archium.application.regeneration_service", "RegenerationService"),
    "RetrievalService": ("archium.application.retrieval_service", "RetrievalService"),
    "create_retrieval_service": (
        "archium.application.retrieval_service",
        "create_retrieval_service",
    ),
    "WorkflowRunResult": ("archium.application.workflow_models", "WorkflowRunResult"),
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
