"""Context intelligence — assess KnowledgeState and suggest next actions.

Backward-compatible facade; implementation lives in ``archium.application.context``.
"""

from __future__ import annotations

from archium.application.context.context_analyzer import ContextAnalyzer
from archium.application.context.next_action_selector import (
    default_actions_for_stage,
    resolve_action_target,
)
from archium.application.context.project_context_composer import (
    compose_project_context,
    finalize_assessment_context,
)
from archium.application.context.types import ActionDispatch, ContextAssessment


class ContextIntelligenceService(ContextAnalyzer):
    """Deprecated name — prefer ``ContextAnalyzer`` from ``application.context``."""

    resolve_action_target = staticmethod(resolve_action_target)
    _default_actions_for_stage = staticmethod(default_actions_for_stage)
    _compose_project_context = staticmethod(compose_project_context)
    _finalize_assessment_context = staticmethod(finalize_assessment_context)


__all__ = [
    "ActionDispatch",
    "ContextAssessment",
    "ContextIntelligenceService",
]
