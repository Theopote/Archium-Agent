"""Asset management and matching services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "AssetBoardService",
    "AssetMatchingService",
    "AssetMetadataService",
    "AssetPresentationReadinessService",
    "AssetVisionRAGService",
    "EvidenceItemBindingService",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "AssetBoardService": ("archium.application.asset.asset_board_service", "AssetBoardService"),
    "AssetMatchingService": ("archium.application.asset.asset_matching_service", "AssetMatchingService"),
    "AssetMetadataService": ("archium.application.asset.asset_metadata_service", "AssetMetadataService"),
    "AssetPresentationReadinessService": ("archium.application.asset.asset_presentation_readiness_service", "AssetPresentationReadinessService"),
    "AssetVisionRAGService": ("archium.application.asset.asset_vision_rag_service", "AssetVisionRAGService"),
    "EvidenceItemBindingService": ("archium.application.asset.evidence_item_binding_service", "EvidenceItemBindingService"),
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
