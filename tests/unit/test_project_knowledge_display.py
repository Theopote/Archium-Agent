"""Unit tests for knowledge-first display copy."""

from __future__ import annotations

from archium.application.project_knowledge_display import (
    KnowledgeSituation,
    build_project_knowledge_display,
    classify_knowledge_situation,
)
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def test_classify_partial_context_for_hospital_scenario() -> None:
    state = KnowledgeState(
        completeness_score=0.34,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.22,
        assumption_ratio=0.72,
        known={"location": "西安", "type": "医院改造"},
        unknown=["功能分区", "规模"],
    )
    assert classify_knowledge_situation(state) == KnowledgeSituation.PARTIAL_CONTEXT


def test_build_display_uses_partial_not_mode_language() -> None:
    state = KnowledgeState(
        completeness_score=0.34,
        maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
        evidence_ratio=0.22,
        assumption_ratio=0.72,
        known={"location": "西安"},
        unknown=["功能分区"],
    )
    ctx = ProjectContext.compose(
        knowledge_state=state,
        next_actions=[
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="甲方尚未说清功能分区",
                question="优先改造哪些科室？",
                priority=0,
            )
        ],
        understanding_summary="部分资料：有地点与旧楼背景。",
    )
    display = build_project_knowledge_display(ctx)
    assert display.situation_label == "部分资料"
    assert "部分资料" in display.headline
    assert "概念探索" not in display.headline
    assert "已有项目" not in display.headline
    assert display.focus == "澄清关键问题"
    assert display.stage_label == "研究"


def test_sparse_idea_classification() -> None:
    state = KnowledgeState(
        completeness_score=0.12,
        evidence_ratio=0.05,
        assumption_ratio=0.9,
    )
    assert classify_knowledge_situation(state) == KnowledgeSituation.SPARSE_IDEA


def test_evidence_rich_classification() -> None:
    state = KnowledgeState(
        completeness_score=0.62,
        evidence_ratio=0.4,
        assumption_ratio=0.2,
    )
    assert classify_knowledge_situation(state) == KnowledgeSituation.EVIDENCE_RICH


def test_build_display_includes_stale_and_claim_counts() -> None:
    from archium.domain.intent.knowledge_claim import (
        KnowledgeClaimKind,
        KnowledgeClaimRef,
        KnowledgeUnknownRef,
    )

    state = KnowledgeState(
        completeness_score=0.4,
        evidence_ratio=0.25,
        cognition_stale=True,
        knowledge_item_count=2,
        claims=[
            KnowledgeClaimRef(
                key="location",
                summary="西安",
                kind=KnowledgeClaimKind.FACT,
                confirmed=True,
            )
        ],
        open_unknowns=[
            KnowledgeUnknownRef(
                description="缺少建筑面积",
                category="missing_fact",
                blocking=True,
            )
        ],
    )
    ctx = ProjectContext.compose(
        knowledge_state=state,
        next_actions=[],
        understanding_summary="stale index",
    )
    display = build_project_knowledge_display(ctx)
    assert display.cognition_stale is True
    assert display.claim_count == 1
    assert display.blocking_unknown_count == 1
    assert display.knowledge_item_count == 2
