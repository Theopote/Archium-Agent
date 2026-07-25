"""Unit tests for KnowledgeStateHistory (Intelligence Closure P1)."""

from __future__ import annotations

from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.knowledge_state_history import (
    KnowledgeStateChangeReason,
    KnowledgeStateHistory,
    normalize_knowledge_change_reason,
)


def test_normalize_reason_aliases() -> None:
    assert (
        normalize_knowledge_change_reason("mission_approved")
        == KnowledgeStateChangeReason.MISSION_APPROVED
    )
    assert normalize_knowledge_change_reason("nope") == KnowledgeStateChangeReason.OTHER


def test_history_versions_and_deltas() -> None:
    history = KnowledgeStateHistory()
    s1 = KnowledgeState(
        completeness_score=0.2,
        known={"地点": "西安"},
        unknown=["文化背景", "用户需求"],
    )
    history = history.append_from_state(s1, reason="initial_assess")
    assert history.latest() is not None
    assert history.latest().version_label == "v0.1"
    assert history.latest().added_known_keys == ["地点"]

    s2 = KnowledgeState(
        completeness_score=0.45,
        known={"地点": "西安", "文化背景": "医院老院区"},
        unknown=["用户需求"],
    )
    history = history.append_from_state(s2, reason="clarification_continued")
    latest = history.latest()
    assert latest is not None
    assert latest.version_label == "v0.2"
    assert "文化背景" in latest.added_known_keys
    assert "文化背景" in latest.resolved_unknown

    s3 = KnowledgeState(
        completeness_score=0.88,
        known={
            "地点": "西安",
            "文化背景": "医院老院区",
            "用户需求": "改造不中断运营",
        },
        unknown=[],
    )
    history = history.append_from_state(s3, reason="mission_approved")
    assert history.latest() is not None
    assert history.latest().version_label == "v1.0"
    assert history.latest().milestone == "设计条件较完整"


def test_history_skips_identical_snapshot() -> None:
    history = KnowledgeStateHistory()
    state = KnowledgeState(completeness_score=0.3, known={"a": "1"}, unknown=["b"])
    history = history.append_from_state(state, reason="refresh")
    history = history.append_from_state(state, reason="refresh")
    assert len(history.snapshots) == 1


def test_project_mapper_roundtrip_history() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from archium.domain.project import Project
    from archium.infrastructure.database.mappers import project_to_domain, project_to_orm
    from archium.infrastructure.database.models import ProjectORM

    history = KnowledgeStateHistory().append_from_state(
        KnowledgeState(completeness_score=0.25, known={"地点": "西安"}),
        reason="initial_assess",
    )
    project = Project(name="测试", knowledge_state_history=history)
    orm = project_to_orm(project)
    assert isinstance(orm.knowledge_state_history_json, dict)
    restored = project_to_domain(orm)
    assert len(restored.knowledge_state_history.snapshots) == 1
    assert restored.knowledge_state_history.latest().version_label == "v0.1"

    # Empty column stays valid
    now = datetime.now(UTC)
    bare = ProjectORM(
        id=uuid4(),
        name="bare",
        project_type="other",
        stage="concept",
        status="active",
        origin_mode="existing_project",
        created_at=now,
        updated_at=now,
    )
    bare.knowledge_state_history_json = None
    domain = project_to_domain(bare)
    assert domain.knowledge_state_history.snapshots == []
