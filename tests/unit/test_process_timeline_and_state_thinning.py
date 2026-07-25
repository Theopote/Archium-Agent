"""Tests for process timeline + planning state thinning (Phase K P1)."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.orchestration import (
    ProcessTimelineEvent,
    append_process_timeline_event,
    list_process_timeline,
)
from archium.domain.project_mission import ProjectMission
from archium.workflow.planning_serialization import snapshot_planning_state
from archium.workflow.planning_state import PlanningWorkflowState


def test_append_and_list_process_timeline() -> None:
    state: dict = {}
    state = append_process_timeline_event(
        state,
        ProcessTimelineEvent(
            kind="gate",
            stage="explore",
            status="awaiting_user",
            label="选定概念方向",
            summary="请选择方向",
            intent_evolution_kind=None,
        ),
    )
    state = append_process_timeline_event(
        state,
        ProcessTimelineEvent(
            kind="replan",
            stage="explore",
            status="replanned",
            label="按上下文重规划",
            summary="插入 research",
            decision_router={"changed": True, "workflow": "research"},
        ),
    )
    # duplicate consecutive ignored
    state = append_process_timeline_event(
        state,
        ProcessTimelineEvent(
            kind="replan",
            stage="explore",
            status="replanned",
            label="按上下文重规划",
            summary="插入 research",
            decision_router={"changed": True, "workflow": "research"},
        ),
    )
    events = list_process_timeline(state)
    assert len(events) == 2
    assert events[0].kind == "gate"
    assert events[1].kind == "replan"
    assert "重规划" in events[1].display_line()


def test_snapshot_planning_thins_mission_when_id_present() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="山地艺术中心",
        task_statement="弱化体量嵌入台地",
    )
    state: PlanningWorkflowState = {
        "workflow_kind": "planning",
        "project_id": str(mission.project_id),
        "mission_id": str(mission.id),
        "mission": mission,
        "knowledge_gaps": [],
        "assumptions": [],
        "clarifying_questions": [],
        "design_questions": [],
        "workstreams": [],
        "user_task_description": "艺术中心",
        "errors": [],
        "warnings": [],
    }
    snap = snapshot_planning_state(state)
    assert snap["mission_id"] == str(mission.id)
    assert snap["mission"] is None
    assert snap["workstreams"] == []
    assert snap["state_thinning"] == "mission_id"
    assert snap["user_task_description"] == "艺术中心"


def test_snapshot_planning_keeps_mission_id_from_embed() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="临时",
        task_statement="x",
    )
    state: PlanningWorkflowState = {
        "mission": mission,
        "errors": [],
        "warnings": [],
    }
    snap = snapshot_planning_state(state)
    assert snap["mission_id"] == str(mission.id)
    assert snap["mission"] is None
