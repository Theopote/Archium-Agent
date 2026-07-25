"""Shared types for the project context intelligence layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction


@dataclass
class ContextAssessment:
    knowledge_state: KnowledgeState
    actions: list[NextBestAction] = field(default_factory=list)
    suggested_origin_mode: ProjectOriginMode = ProjectOriginMode.CONCEPT_EXPLORATION
    understanding_summary: str = ""
    warnings: list[str] = field(default_factory=list)
    project_context: ProjectContext | None = None


@dataclass(frozen=True)
class ActionDispatch:
    """Where the UI should send the user for a NextBestAction."""

    page_key: str
    mission_step: int | None = None
    label: str = ""
    focus: str | None = None
    orchestration_action: str = "none"  # start | resume | none
    stage_hint: str | None = None


@dataclass(frozen=True)
class WorkflowEntryDispatch:
    """Planning / product entry derived from ProjectContext (workflow + NBA)."""

    page_key: str
    mission_step: int | None = None
    label: str = ""
    focus: str | None = None
    workflow: RecommendedWorkflow | None = None
    action_reason: str = ""
