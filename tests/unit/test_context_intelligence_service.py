"""Unit tests for ContextIntelligenceService / KnowledgeState assessment."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.context_intelligence_service import ContextIntelligenceService
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage
from archium.domain.intent.next_best_action import NextBestActionType
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.context_intelligence_schemas import (
    ContextAssessmentDraft,
    NextBestActionDraft,
)


def test_assess_text_from_llm_draft() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = ContextAssessmentDraft(
        completeness_score=0.32,
        maturity_stage="concept_formation",
        evidence_ratio=0.1,
        assumption_ratio=0.8,
        known={"location": "西安", "type": "文化建筑"},
        unknown=["规模", "目标用户"],
        missing_information=["规模", "目标用户"],
        suggested_origin_mode="concept_exploration",
        understanding_summary="已有地点与类型，仍处概念形成阶段。",
        actions=[
            NextBestActionDraft(
                action="explore_directions",
                reason="可先推演方向",
                priority=0,
            ),
            NextBestActionDraft(
                action="ask",
                reason="澄清人群",
                question="主要服务什么人群？",
                priority=1,
            ),
        ],
    )
    service = ContextIntelligenceService(MagicMock(), llm)
    result = service.assess_text("我想在西安做一个青年文化中心")

    assert result.knowledge_state.maturity_stage == KnowledgeMaturityStage.CONCEPT_FORMATION
    assert result.knowledge_state.known["location"] == "西安"
    assert result.suggested_origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION
    assert result.actions[0].action == NextBestActionType.EXPLORE_DIRECTIONS
    assert "概念" in result.understanding_summary


def test_assess_rule_fallback_when_llm_fails() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("down")
    service = ContextIntelligenceService(MagicMock(), llm)
    result = service.assess_text("秦岭山里的博物馆想法", project_name="秦岭馆")

    assert result.warnings
    assert result.knowledge_state.maturity_stage == KnowledgeMaturityStage.CONCEPT_FORMATION
    assert result.suggested_origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION
    assert result.actions
    assert result.knowledge_state.known.get("name") == "秦岭馆"


def test_assess_rule_fallback_existing_docs() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("down")
    service = ContextIntelligenceService(MagicMock(), llm)
    result = service.assess_text(
        "医院改扩建，手头有旧总平 PDF",
        document_count=3,
    )
    assert result.suggested_origin_mode == ProjectOriginMode.EXISTING_PROJECT
    assert result.knowledge_state.maturity_stage == KnowledgeMaturityStage.DESIGN_ANALYSIS
    assert result.knowledge_state.completeness_score >= 0.5


def test_assess_and_persist_writes_knowledge_and_evolution(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="青年文化中心", description="想法")
    )
    db_session.commit()

    llm = MagicMock()
    llm.generate_structured.return_value = ContextAssessmentDraft(
        completeness_score=0.3,
        maturity_stage="concept_formation",
        evidence_ratio=0.05,
        assumption_ratio=0.9,
        known={"type": "文化中心"},
        unknown=["场地"],
        missing_information=["场地"],
        suggested_origin_mode="concept_exploration",
        understanding_summary="概念形成阶段。",
        actions=[
            NextBestActionDraft(action="explore_directions", reason="推演", priority=0)
        ],
    )
    service = ContextIntelligenceService(db_session, llm)
    result = service.assess_and_persist(project.id, "我想在西安做青年文化中心")

    refreshed = ProjectRepository(db_session).get_by_id(project.id)
    assert refreshed is not None
    assert refreshed.knowledge_state is not None
    assert refreshed.knowledge_state.completeness_score == pytest.approx(0.3)
    assert refreshed.origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION
    assert len(refreshed.intent_evolution.events) >= 2
    assert refreshed.intent_evolution.events[0].kind.value == "seed"
    assert result.understanding_summary


def test_assess_empty_raises() -> None:
    with pytest.raises(WorkflowError, match="描述"):
        ContextIntelligenceService(MagicMock(), MagicMock()).assess_text("  ")
