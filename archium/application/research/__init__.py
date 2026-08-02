"""Research and analysis services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "AutonomousResearchService",
    "ResearchQuestionService",
    "ResearchTopics",
    "RetrievalCredibility",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "AutonomousResearchService": ("archium.application.research.autonomous_research_service", "AutonomousResearchService"),
    "ResearchQuestionService": ("archium.application.research.research_question_service", "ResearchQuestionService"),
    "ResearchTopics": ("archium.application.research.research_topics", "ResearchTopics"),
    "RetrievalCredibility": ("archium.application.research.retrieval_credibility", "RetrievalCredibility"),
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
