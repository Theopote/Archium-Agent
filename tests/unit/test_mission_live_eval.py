"""Unit tests for live mission auto-observation heuristics (no real LLM)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.project_mission_service import MissionGenerationResult
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    DeliverableType,
    ProjectType,
    ServiceDepth,
    TaskNature,
    WorkstreamType,
)
from archium.domain.project_mission import MissionConstraint, ProjectMission
from archium.domain.workstream import Workstream
from tests.golden.live.mission_eval import collect_auto_observations
from tests.golden.live.mission_rubric import MISSION_LIVE_RUBRIC, TOTAL_MAX_SCORE
from tests.golden.mission.loader import MissionGoldenCase


def test_rubric_totals_100() -> None:
    assert TOTAL_MAX_SCORE == 100
    assert sum(item.max_score for item in MISSION_LIVE_RUBRIC) == 100
    assert [item.label for item in MISSION_LIVE_RUBRIC] == [
        "任务性质判断",
        "尺度与服务深度",
        "事实忠实度",
        "关键未知识别",
        "澄清问题价值",
        "Workstream 合理性",
        "Deliverable 合理性",
    ]


def _case(**overrides: object) -> MissionGoldenCase:
    raw = {
        "id": "case_m1_temple",
        "name": "清凉寺重建",
        "expectations": {
            "forbidden_fabricated_substrings": ["12000"],
            "max_clarifying_questions": 5,
        },
    }
    raw.update(overrides)
    return MissionGoldenCase(
        id=str(raw["id"]),
        name=str(raw["name"]),
        project_name="p",
        project_type=ProjectType.CULTURE,
        project_description="",
        task_description="面积未知的重建任务",
        expectations=dict(raw.get("expectations") or {}),
        raw=raw,
    )


def test_flags_fabricated_substring() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="t",
        task_statement="重建",
        known_constraints=[
            MissionConstraint(name="建筑面积", value="约12000㎡"),
        ],
        key_unknowns=["建筑面积"],
    )
    generation = MissionGenerationResult(mission=mission)
    flags, notes = collect_auto_observations(
        case=_case(),
        generation=generation,
        workstreams=[],
        plan=DeliverablePlan(project_id=mission.project_id, mission_id=mission.id),
        validation={"errors": [], "warnings": []},
    )
    assert "fabricated_metrics" in flags
    assert notes


def test_flags_consulting_as_full_design() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="低碳专项",
        task_statement="专项建议",
        task_natures=[TaskNature.CONSULTING, TaskNature.NEW_BUILD],
        requested_service_depths=[ServiceDepth.CONCEPT_DESIGN],
    )
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="d1",
                title="完整建筑设计方案汇报",
                deliverable_type=DeliverableType.PRESENTATION,
                purpose="方案",
                selected=True,
            )
        ],
    )
    case = _case(
        id="case_m6_green_campus",
        name="园区绿色低碳",
        expectations={},
    )
    # Override task description via object replace
    case = MissionGoldenCase(
        id=case.id,
        name=case.name,
        project_name=case.project_name,
        project_type=case.project_type,
        project_description=case.project_description,
        task_description="园区希望做绿色低碳专项建议",
        expectations={},
        raw=case.raw,
    )
    flags, _ = collect_auto_observations(
        case=case,
        generation=MissionGenerationResult(mission=mission),
        workstreams=[],
        plan=plan,
        validation={"errors": [], "warnings": []},
    )
    assert "consulting_as_full_design" in flags


def test_flags_missing_stakeholders() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="村庄",
        task_statement="更新",
        decisions_required=["是否搬迁"],
        stakeholders=[],
    )
    case = _case(
        expectations={"stakeholder_min_count": 3},
    )
    flags, _ = collect_auto_observations(
        case=case,
        generation=MissionGenerationResult(mission=mission),
        workstreams=[
            Workstream(
                project_id=mission.project_id,
                mission_id=mission.id,
                title="资源盘点",
                workstream_type=WorkstreamType.OTHER,
                objective="盘点",
            )
        ],
        plan=DeliverablePlan(project_id=mission.project_id, mission_id=mission.id),
        validation={"errors": [], "warnings": []},
    )
    assert "missing_stakeholders" in flags
