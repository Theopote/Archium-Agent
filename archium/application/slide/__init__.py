"""Slide-specific operation services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "SlideRecoveryService",
    "SlideRepairService",
    "SlideSemanticQAService",
    "SlideSplitPlanner",
    "SlideHistoryService",
    "SlideAssetBindingService",
    "SlideEvidenceEditService",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "SlideRecoveryService": ("archium.application.slide.slide_recovery_service", "SlideRecoveryService"),
    "SlideRepairService": ("archium.application.slide.slide_repair_service", "SlideRepairService"),
    "SlideSemanticQAService": ("archium.application.slide.slide_semantic_qa_service", "SlideSemanticQAService"),
    "SlideSplitPlanner": ("archium.application.slide.slide_split_planner", "SlideSplitPlanner"),
    "SlideHistoryService": ("archium.application.slide.slide_history_service", "SlideHistoryService"),
    "SlideAssetBindingService": ("archium.application.slide.slide_asset_binding_service", "SlideAssetBindingService"),
    "SlideEvidenceEditService": ("archium.application.slide.slide_evidence_edit_service", "SlideEvidenceEditService"),
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
