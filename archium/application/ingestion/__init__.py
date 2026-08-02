"""Document ingestion and parsing services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "IngestionService",
    "ChunkService",
    "MultimodalRetrieval",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "IngestionService": ("archium.application.ingestion.ingestion_service", "IngestionService"),
    "ChunkService": ("archium.application.ingestion.chunk_service", "ChunkService"),
    "MultimodalRetrieval": ("archium.application.ingestion.multimodal_retrieval", "MultimodalRetrieval"),
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
