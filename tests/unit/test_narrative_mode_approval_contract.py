from uuid import uuid4

from archium.application.project_mission_service import (
    is_mission_approval_current,
    mission_approval_hash,
    suggest_narrative_mode,
)
from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.enums import ApprovalStatus
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.art_direction import ArtDirection


def _mission(**updates: object) -> ProjectMission:
    values: dict[str, object] = {
        "project_id": uuid4(),
        "title": "老院区更新",
        "task_statement": "梳理老院区现状并形成更新决策汇报",
        "primary_problems": ["交通与功能冲突"],
    }
    values.update(updates)
    return ProjectMission(**values)  # type: ignore[arg-type]


def test_system_suggests_narrative_mode_with_an_explanation() -> None:
    suggestion = suggest_narrative_mode(_mission())
    assert suggestion.mode == ArchitecturalNarrativeMode.PROBLEM_SOLUTION
    assert suggestion.reason


def test_narrative_mode_is_part_of_mission_approval_hash() -> None:
    mission = _mission(narrative_mode=ArchitecturalNarrativeMode.TECHNICAL_BRIEFING)
    technical_hash = mission_approval_hash(mission)
    mission.narrative_mode = ArchitecturalNarrativeMode.DECISION_FIRST
    assert mission_approval_hash(mission) != technical_hash


def test_mission_change_invalidates_approval_and_hash() -> None:
    mission = _mission(narrative_mode=ArchitecturalNarrativeMode.DECISION_FIRST)
    mission.approve()
    mission.approval_hash = mission_approval_hash(mission)
    mission.invalidate_approval()
    assert mission.approval_status == ApprovalStatus.DRAFT
    assert mission.approval_hash is None


def test_workflow_gate_rejects_stale_approval_hash() -> None:
    mission = _mission(narrative_mode=ArchitecturalNarrativeMode.TECHNICAL_BRIEFING)
    mission.approve()
    mission.approval_hash = mission_approval_hash(mission)
    assert is_mission_approval_current(mission)
    mission.narrative_mode = ArchitecturalNarrativeMode.DECISION_FIRST
    assert not is_mission_approval_current(mission)


def test_ensure_mission_approval_current_rejects_unapproved() -> None:
    import pytest
    from archium.application.project_mission_service import ensure_mission_approval_current
    from archium.exceptions import WorkflowError

    mission = _mission()
    with pytest.raises(WorkflowError, match="尚未批准"):
        ensure_mission_approval_current(mission)


def test_narrative_mode_and_art_direction_are_independent_axes() -> None:
    assert "narrative_mode" not in ArtDirection.model_fields
    assert "art_direction" not in ProjectMission.model_fields
