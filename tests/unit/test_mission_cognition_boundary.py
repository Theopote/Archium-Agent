"""Unit tests for Mission vs KnowledgeState cognition boundary."""

from __future__ import annotations

from uuid import uuid4

from archium.application.context.mission_cognition import (
    cognition_confidence,
    cognition_unknown_texts,
)
from archium.application.project_mission_service import mission_approval_hash
from archium.domain.context.project_context import ProjectContext
from archium.domain.intent.knowledge_claim import KnowledgeUnknownRef
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_mission import ProjectMission


def test_cognition_unknowns_prefer_knowledge_state() -> None:
    state = KnowledgeState(
        open_unknowns=[
            KnowledgeUnknownRef(description="缺少用户画像", blocking=True),
        ],
        unknown=["legacy"],
    )
    mission = ProjectMission(
        project_id=uuid4(),
        title="养老社区",
        task_statement="探索未来养老社区模式",
        key_unknowns=["旧的 Mission 未知项"],
    )
    texts = cognition_unknown_texts(knowledge_state=state, mission=mission)
    assert texts == ["缺少用户画像"]


def test_cognition_unknowns_fallback_to_mission_snapshot() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="养老社区",
        task_statement="探索未来养老社区模式",
        key_unknowns=["缺少用户画像"],
    )
    assert cognition_unknown_texts(mission=mission) == ["缺少用户画像"]


def test_cognition_confidence_prefers_project_context() -> None:
    state = KnowledgeState(evidence_ratio=0.8, assumption_ratio=0.2)
    ctx = ProjectContext.compose(
        knowledge_state=state,
        next_actions=[],
        understanding_summary="test",
    )
    mission = ProjectMission(
        project_id=uuid4(),
        title="t",
        task_statement="探索未来养老社区模式",
        confidence=0.2,
    )
    assert cognition_confidence(project_context=ctx, mission=mission) == ctx.confidence
    assert cognition_confidence(project_context=ctx, mission=mission) != 0.2


def test_approval_hash_ignores_cognition_snapshots() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="养老社区",
        task_statement="探索未来养老社区模式",
        key_unknowns=["A"],
        confidence=0.4,
    )
    base = mission_approval_hash(mission)
    changed = mission.model_copy(
        update={"key_unknowns": ["B", "C"], "confidence": 0.95}
    )
    assert mission_approval_hash(changed) == base
    task_changed = mission.model_copy(update={"task_statement": "不同任务定义"})
    assert mission_approval_hash(task_changed) != base


def test_mission_patch_ignores_cognition_snapshots() -> None:
    from archium.application.context.mission_cognition import (
        strip_cognition_snapshot_fields,
    )

    cleaned = strip_cognition_snapshot_fields(
        {
            "task_statement": "探索未来养老社区模式",
            "key_unknowns": ["应被忽略"],
            "confidence": 0.99,
            "research_questions": ["用户画像是什么"],
        }
    )
    assert "key_unknowns" not in cleaned
    assert "confidence" not in cleaned
    assert cleaned["task_statement"] == "探索未来养老社区模式"
    assert cleaned["research_questions"] == ["用户画像是什么"]


def test_mission_holds_stable_task_not_live_unknown() -> None:
    """Product boundary example: Mission = task definition; Context = live unknown."""
    mission = ProjectMission(
        project_id=uuid4(),
        title="养老社区",
        task_statement="探索未来养老社区模式",
        key_unknowns=["过时的未知"],
        confidence=0.9,
    )
    state = KnowledgeState(
        open_unknowns=[
            KnowledgeUnknownRef(description="缺少用户画像", blocking=True),
        ],
        evidence_ratio=0.25,
    )
    assert "探索未来养老社区模式" in mission.task_statement
    assert cognition_unknown_texts(knowledge_state=state, mission=mission) == [
        "缺少用户画像"
    ]
    assert cognition_confidence(knowledge_state=state, mission=mission) == 0.25
