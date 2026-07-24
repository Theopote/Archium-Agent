"""Unified project context — knowledge snapshot + evidence + recommended stage."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


class ProjectContext(DomainModel):
    """Aggregate view: how much we know, what we assume, and what to do next."""

    knowledge_state: KnowledgeState
    input_sources: list[str] = Field(default_factory=list)
    extracted_facts: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    lifecycle_stage: ProjectLifecycleStage = ProjectLifecycleStage.CONCEPT
    recommended_workflow: RecommendedWorkflow = RecommendedWorkflow.EXPLORE
    next_actions: list[NextBestAction] = Field(default_factory=list)
    understanding_summary: str = ""
    suggested_origin_mode: ProjectOriginMode = ProjectOriginMode.CONCEPT_EXPLORATION
    primary_page_key: str = ""

    def summary_line(self) -> str:
        return self.knowledge_state.summary_line()

    @classmethod
    def compose(
        cls,
        *,
        knowledge_state: KnowledgeState,
        next_actions: list[NextBestAction],
        understanding_summary: str = "",
        suggested_origin_mode: ProjectOriginMode = ProjectOriginMode.CONCEPT_EXPLORATION,
        input_sources: list[str] | None = None,
        primary_page_key: str = "",
    ) -> ProjectContext:
        """Build a ProjectContext from assessment outputs (no LLM)."""
        sources = list(input_sources or [])
        facts = dict(knowledge_state.known)
        assumptions = _assumptions_from_state(knowledge_state)
        confidence = max(
            0.0,
            min(
                1.0,
                knowledge_state.evidence_ratio * 0.6
                + (1.0 - knowledge_state.assumption_ratio) * 0.4,
            ),
        )
        lifecycle = infer_lifecycle_stage(knowledge_state)
        workflow = infer_recommended_workflow(
            knowledge_state,
            next_actions,
            lifecycle_stage=lifecycle,
        )
        page = primary_page_key or primary_page_for_workflow(workflow, next_actions)
        return cls(
            knowledge_state=knowledge_state,
            input_sources=sources,
            extracted_facts=facts,
            assumptions=assumptions,
            confidence=confidence,
            lifecycle_stage=lifecycle,
            recommended_workflow=workflow,
            next_actions=list(next_actions),
            understanding_summary=understanding_summary.strip(),
            suggested_origin_mode=suggested_origin_mode,
            primary_page_key=page,
        )


def infer_lifecycle_stage(state: KnowledgeState) -> ProjectLifecycleStage:
    """Map knowledge maturity + completeness to a design-process stage."""
    if state.maturity_stage == KnowledgeMaturityStage.TECHNICAL_PRESENTATION:
        return ProjectLifecycleStage.DOCUMENTATION
    if state.maturity_stage == KnowledgeMaturityStage.DESIGN_ANALYSIS:
        if state.completeness_score >= 0.55 and state.evidence_ratio >= 0.35:
            return ProjectLifecycleStage.DESIGN
        return ProjectLifecycleStage.RESEARCH
    if state.completeness_score < 0.22 and state.evidence_ratio < 0.12:
        return ProjectLifecycleStage.IDEA
    return ProjectLifecycleStage.CONCEPT


def infer_recommended_workflow(
    state: KnowledgeState,
    actions: list[NextBestAction],
    *,
    lifecycle_stage: ProjectLifecycleStage | None = None,
) -> RecommendedWorkflow:
    """Pick the primary workflow from top next action, with stage-aware fallback."""
    lifecycle = lifecycle_stage or infer_lifecycle_stage(state)
    if actions:
        mapped = _workflow_for_action(actions[0].action)
        if mapped is not None:
            return mapped
    if lifecycle == ProjectLifecycleStage.DOCUMENTATION:
        return RecommendedWorkflow.DELIVER
    if lifecycle == ProjectLifecycleStage.DESIGN:
        return RecommendedWorkflow.DESIGN
    if lifecycle == ProjectLifecycleStage.RESEARCH:
        if state.evidence_ratio >= 0.2:
            return RecommendedWorkflow.MISSION
        return RecommendedWorkflow.RESEARCH
    if state.evidence_ratio >= 0.25 and state.completeness_score >= 0.4:
        return RecommendedWorkflow.MATERIALS
    return RecommendedWorkflow.EXPLORE


def primary_page_for_workflow(
    workflow: RecommendedWorkflow,
    actions: list[NextBestAction],
) -> str:
    """Resolve default navigation page for a workflow emphasis."""
    if actions:
        page = _page_for_action(actions[0].action)
        if page:
            return page
    return {
        RecommendedWorkflow.EXPLORE: "concept-exploration",
        RecommendedWorkflow.RESEARCH: "project-mission",
        RecommendedWorkflow.MATERIALS: "materials",
        RecommendedWorkflow.MISSION: "project-mission",
        RecommendedWorkflow.DESIGN: "concept-exploration",
        RecommendedWorkflow.DELIVER: "materials",
    }[workflow]


def _assumptions_from_state(state: KnowledgeState) -> list[str]:
    if state.assumption_ratio <= 0.35:
        return []
    items = list(state.unknown or state.missing_information)
    if not items and state.assumption_ratio > 0.5:
        return ["关键条件尚未证实，当前判断基于描述与有限证据"]
    return [f"待证实：{item}" for item in items[:6]]


def _workflow_for_action(action: NextBestActionType) -> RecommendedWorkflow | None:
    return {
        NextBestActionType.EXPLORE_DIRECTIONS: RecommendedWorkflow.EXPLORE,
        NextBestActionType.RESEARCH: RecommendedWorkflow.RESEARCH,
        NextBestActionType.UPLOAD_MATERIALS: RecommendedWorkflow.MATERIALS,
        NextBestActionType.GENERATE_MISSION: RecommendedWorkflow.MISSION,
        NextBestActionType.OPEN_MISSION: RecommendedWorkflow.MISSION,
        NextBestActionType.ASK: RecommendedWorkflow.MISSION,
    }.get(action)


def _page_for_action(action: NextBestActionType) -> str | None:
    return {
        NextBestActionType.EXPLORE_DIRECTIONS: "concept-exploration",
        NextBestActionType.UPLOAD_MATERIALS: "materials",
        NextBestActionType.RESEARCH: "project-mission",
        NextBestActionType.GENERATE_MISSION: "project-mission",
        NextBestActionType.OPEN_MISSION: "project-mission",
        NextBestActionType.ASK: "project-mission",
    }.get(action)
