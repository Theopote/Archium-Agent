"""Tests for KnowledgeState routing snapshot persistence."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.application.context_intelligence_service import ContextIntelligenceService
from archium.application.project_context_builder import build_project_context, overlay_persisted_routing
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.context.project_context import ProjectContext
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.context_intelligence_schemas import (
    ContextAssessmentDraft,
    NextBestActionDraft,
)


def test_assess_persists_routing_on_knowledge_state(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="医院改造", description="部分资料")
    )
    db_session.commit()

    llm = MagicMock()
    llm.generate_structured.return_value = ContextAssessmentDraft(
        completeness_score=0.34,
        maturity_stage="design_analysis",
        evidence_ratio=0.2,
        assumption_ratio=0.75,
        known={"location": "西安"},
        unknown=["功能分区"],
        missing_information=["功能分区"],
        suggested_origin_mode="existing_project",
        understanding_summary="部分资料。",
        actions=[
            NextBestActionDraft(action="ask", reason="澄清", priority=0),
        ],
    )
    result = ContextIntelligenceService(db_session, llm).assess_and_persist(
        project.id,
        "西安医院老院区改造，资料很少",
    )

    assert result.knowledge_state.recommended_workflow
    assert result.knowledge_state.lifecycle_stage
    assert result.knowledge_state.primary_page_key

    refreshed = ProjectRepository(db_session).get_by_id(project.id)
    assert refreshed is not None
    assert refreshed.knowledge_state is not None
    assert refreshed.knowledge_state.recommended_workflow == result.knowledge_state.recommended_workflow
    assert refreshed.origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION


def test_overlay_persisted_routing_prefers_snapshot() -> None:
    ks = KnowledgeState(
        completeness_score=0.34,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        lifecycle_stage=ProjectLifecycleStage.RESEARCH.value,
        recommended_workflow=RecommendedWorkflow.MISSION.value,
        primary_page_key="project-mission",
    )
    ctx = ProjectContext.compose(
        knowledge_state=ks,
        next_actions=[],
        primary_page_key="concept-exploration",
    ).model_copy(
        update={"recommended_workflow": RecommendedWorkflow.EXPLORE},
    )
    overlaid = overlay_persisted_routing(ctx, ks)
    assert overlaid.recommended_workflow == RecommendedWorkflow.MISSION
    assert overlaid.primary_page_key == "project-mission"
    assert overlaid.lifecycle_stage == ProjectLifecycleStage.RESEARCH


def test_build_project_context_uses_persisted_routing(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(
            name="改造",
            description="部分资料",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
            knowledge_state=KnowledgeState(
                completeness_score=0.32,
                maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
                lifecycle_stage=ProjectLifecycleStage.RESEARCH.value,
                recommended_workflow=RecommendedWorkflow.MISSION.value,
                primary_page_key="project-mission",
            ),
        )
    )
    db_session.commit()
    ctx = build_project_context(db_session, project.id)
    assert ctx is not None
    assert ctx.recommended_workflow == RecommendedWorkflow.MISSION
    assert ctx.primary_page_key == "project-mission"
