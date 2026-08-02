"""Design and concept services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ConceptDirectionService",
    "DesignReviseService",
    "DesignArtifactCatalog",
    "DesignKnowledgeMapping",
    "SpatialDesignLayer",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ConceptDirectionService": ("archium.application.design.concept_direction_service", "ConceptDirectionService"),
    "DesignReviseService": ("archium.application.design.design_revise_service", "DesignReviseService"),
    "DesignArtifactCatalog": ("archium.application.design.design_artifact_catalog", "DesignArtifactCatalog"),
    "DesignKnowledgeMapping": ("archium.application.design.design_knowledge_mapping", "DesignKnowledgeMapping"),
    "SpatialDesignLayer": ("archium.application.design.spatial_design_layer", "SpatialDesignLayer"),
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
