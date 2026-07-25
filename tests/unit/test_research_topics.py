"""Unit tests for ranked research topics + presentation-entry NBA policy."""

from __future__ import annotations

from archium.application.context.knowledge_vector_policy import (
    actions_for_presentation_entry,
)
from archium.application.context.presentation_readiness import (
    presentation_readiness_from_context,
)
from archium.application.research_topics import (
    collect_mission_research_topics,
    collect_project_research_topic_candidates,
    collect_project_research_topics,
)
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ApprovalStatus
from archium.domain.intent.context_assessment_reason import (
    AssessmentReasonAxis,
    AssessmentReasonPolarity,
    ContextAssessmentReason,
)
from archium.domain.intent.knowledge_claim import KnowledgeUnknownRef
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.next_best_action import NextBestActionType
from archium.domain.project_mission import DesignIntent, ProjectMission


def test_temple_case_derives_cultural_topics() -> None:
    state = KnowledgeState(
        known={"location": "秦岭", "type": "寺庙"},
        unknown=["场地条件"],
    )
    topics = collect_project_research_topics(
        project_name="秦岭寺庙",
        project_description="秦岭深处一座寺庙改扩建，强调礼佛轴线与禅意氛围",
        knowledge_state=state,
    )
    blob = " ".join(topics)
    assert topics
    assert "文化" in blob or "礼仪" in blob or "秦岭" in blob


def test_design_impact_ranks_blocking_constraint_above_generic() -> None:
    state = KnowledgeState(
        completeness_score=0.3,
        dimensions=KnowledgeDimensions(
            information_completeness=0.35,
            design_intent_clarity=0.6,
            evidence_confidence=0.3,
            constraint_understanding=0.2,
            user_alignment=0.5,
            research_need=0.7,
        ),
        unknown=["业主偏好色调"],
        open_unknowns=[
            KnowledgeUnknownRef(
                description="消防疏散与红线退距未确认",
                category="constraint",
                blocking=True,
            ),
        ],
        assessment_reasons=[
            ContextAssessmentReason(
                factor="缺少类型先例参照",
                evidence="尚无同类寺院改扩建案例摘要",
                impact="概念论证偏弱",
                polarity=AssessmentReasonPolarity.BLOCK,
                related_axis=AssessmentReasonAxis.RESEARCH_NEED,
                confidence=0.8,
            ),
        ],
        known={"location": "秦岭", "type": "寺庙"},
    )
    ranked = collect_project_research_topic_candidates(
        project_name="秦岭寺庙",
        knowledge_state=state,
        max_topics=5,
    )
    assert ranked
    # Blocking fire/setback gap should outrank soft owner-color unknown
    texts = [c.text for c in ranked]
    assert any("消防" in t or "红线" in t for t in texts[:3])
    assert ranked[0].score >= ranked[-1].score
    assert any(
        c.axis == AssessmentReasonAxis.CONSTRAINTS
        or (c.question is not None and "消防" in c.text)
        for c in ranked[:3]
    )


def test_mission_topics_prefer_design_intent_research_needed() -> None:
    mission = ProjectMission(
        project_id=__import__("uuid").uuid4(),
        title="改扩建",
        task_statement="寺庙改扩建概念汇报",
        approval_status=ApprovalStatus.DRAFT,
        research_questions=["周边交通流量"],
        design_intent=DesignIntent(
            theme="强化礼佛轴线",
            research_needed=["地方礼佛仪轨与空间序列先例"],
        ),
    )
    topics = collect_mission_research_topics(mission)
    assert topics
    blob = " ".join(topics)
    assert "礼佛" in blob or "仪轨" in blob
    # Problem framing may rewrite exact strings; research_needed should still rank first.
    assert any("礼佛" in t or "仪轨" in t or "空间序列" in t for t in topics[:2])
    assert any("交通" in t for t in topics)


def test_presentation_entry_sparse_prefers_research() -> None:
    dims = KnowledgeDimensions(
        information_completeness=0.2,
        design_intent_clarity=0.55,
        evidence_confidence=0.2,
        constraint_understanding=0.25,
        user_alignment=0.4,
        research_need=0.8,
    )
    actions = actions_for_presentation_entry(
        dims,
        completeness_pct=18,
        unknown_count=1,
        recommended_workflow=RecommendedWorkflow.RESEARCH,
    )
    assert actions
    assert actions[0].action == NextBestActionType.RESEARCH


def test_presentation_entry_explore_workflow() -> None:
    actions = actions_for_presentation_entry(
        completeness_pct=40,
        recommended_workflow=RecommendedWorkflow.EXPLORE,
    )
    assert actions[0].action == NextBestActionType.EXPLORE_DIRECTIONS


def test_presentation_entry_many_unknowns_asks_first() -> None:
    actions = actions_for_presentation_entry(
        completeness_pct=30,
        unknown_count=4,
        blocking_gaps=False,
    )
    assert actions[0].action == NextBestActionType.ASK


def test_readiness_uses_presentation_entry_policy() -> None:
    state = KnowledgeState(
        completeness_score=0.18,
        dimensions=KnowledgeDimensions(
            information_completeness=0.18,
            design_intent_clarity=0.5,
            evidence_confidence=0.2,
            constraint_understanding=0.2,
            user_alignment=0.4,
            research_need=0.75,
        ),
        unknown=["用地面积"],
    )
    ctx = ProjectContext(
        knowledge_state=state,
        lifecycle_stage=ProjectLifecycleStage.CONCEPT,
        recommended_workflow=RecommendedWorkflow.RESEARCH,
        confidence=0.2,
    )
    ready = presentation_readiness_from_context(ctx)
    assert ready.suggested_action == NextBestActionType.RESEARCH
    assert ready.suggested_action_reason
