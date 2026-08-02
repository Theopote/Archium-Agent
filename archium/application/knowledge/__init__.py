"""Knowledge and fact management services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "FactExtractionService",
    "FactLedgerService",
    "FactValidationService",
    "KnowledgeGraphService",
    "KnowledgeVectorIndex",
    "RetrievalService",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "FactExtractionService": ("archium.application.knowledge.fact_extraction_service", "FactExtractionService"),
    "FactLedgerService": ("archium.application.knowledge.fact_ledger_service", "FactLedgerService"),
    "FactValidationService": ("archium.application.knowledge.fact_validation_service", "FactValidationService"),
    "KnowledgeGraphService": ("archium.application.knowledge.knowledge_graph_service", "KnowledgeGraphService"),
    "KnowledgeVectorIndex": ("archium.application.knowledge.knowledge_vector_index", "KnowledgeVectorIndex"),
    "RetrievalService": ("archium.application.knowledge.retrieval_service", "RetrievalService"),
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
