"""Tests for workstream planning service and parser."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.project_mission_service import ProjectMissionService
from tests.fixtures.mission_approval import approve_generated_mission
from archium.application.workstream_parser import parse_workstream_plan_draft
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.domain.enums import WorkstreamStatus, WorkstreamType
from archium.domain.project import Project
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from archium.infrastructure.llm.workstream_schemas import WorkstreamPlanDraft
from sqlalchemy.orm import Session

from tests.fixtures.mock_mission_responses import TEMPLE_MISSION_JSON
from tests.fixtures.mock_workstream_responses import (
    CYCLIC_WORKSTREAM_PLAN_JSON,
    GREEN_CAMPUS_WORKSTREAM_PLAN_JSON,
    TEMPLE_WORKSTREAM_PLAN_JSON,
)


def workstream_mock_selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "WorkstreamPlan JSON" in prompt:
        if "绿色低碳" in prompt or "园区" in prompt:
            return GREEN_CAMPUS_WORKSTREAM_PLAN_JSON
        if "CYCLIC_TEST" in prompt:
            return CYCLIC_WORKSTREAM_PLAN_JSON
        return TEMPLE_WORKSTREAM_PLAN_JSON
    if "ProjectMission JSON" in prompt:
        return TEMPLE_MISSION_JSON
    return None


@pytest.fixture
def llm() -> MockLLMProvider:
    return MockLLMProvider(selector=workstream_mock_selector)


@pytest.fixture
def mission_service(db_session: Session, llm: MockLLMProvider) -> ProjectMissionService:
    return ProjectMissionService(db_session, llm)


@pytest.fixture
def workstream_service(
    db_session: Session,
    llm: MockLLMProvider,
) -> WorkstreamPlanningService:
    return WorkstreamPlanningService(db_session, llm)


@pytest.fixture
def temple_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="三原县清凉寺"))


TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def test_plan_workstreams_for_temple_mission(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    result = workstream_service.plan_workstreams(generated.mission.id)
    types = {item.workstream_type for item in result.workstreams}
    assert WorkstreamType.HISTORICAL_RESEARCH in types
    assert WorkstreamType.CASE_STUDY in types
    assert WorkstreamType.PRESENTATION in types
    assert all(item.selected for item in result.workstreams if item.recommended)
    assert result.mission.recommended_workstream_ids


def test_case_study_has_dependencies(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    result = workstream_service.plan_workstreams(generated.mission.id)
    case_study = next(
        item for item in result.workstreams if item.workstream_type == WorkstreamType.CASE_STUDY
    )
    historical = next(
        item
        for item in result.workstreams
        if item.workstream_type == WorkstreamType.HISTORICAL_RESEARCH
    )
    assert historical.id in case_study.dependencies


def test_select_and_deselect_workstream(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    result = workstream_service.plan_workstreams(generated.mission.id)
    target = result.workstreams[0]
    deselected = workstream_service.deselect_workstream(target.id)
    assert deselected.selected is False
    assert deselected.status == WorkstreamStatus.PROPOSED
    selected = workstream_service.select_workstream(target.id)
    assert selected.selected is True
    assert selected.status == WorkstreamStatus.SELECTED


def test_set_workstream_selection(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    result = workstream_service.plan_workstreams(generated.mission.id)
    keep = result.workstreams[0].id
    updated = workstream_service.set_workstream_selection(generated.mission.id, [keep])
    assert sum(1 for item in updated if item.selected) == 1
    assert next(item for item in updated if item.id == keep).selected is True


def test_replace_existing_workstreams(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    first = workstream_service.plan_workstreams(generated.mission.id)
    second = workstream_service.plan_workstreams(generated.mission.id, replace_existing=True)
    assert len(second.workstreams) == len(first.workstreams)
    first_ids = {item.id for item in first.workstreams}
    second_ids = {item.id for item in second.workstreams}
    assert first_ids.isdisjoint(second_ids)


def test_add_custom_workstream(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    workstream_service.plan_workstreams(generated.mission.id)
    custom = Workstream(
        project_id=temple_project.id,
        mission_id=generated.mission.id,
        title="资料可信度评估",
        workstream_type=WorkstreamType.DOCUMENT_REVIEW,
        objective="评估地方志与照片的可用性",
        recommended=False,
    )
    saved = workstream_service.add_workstream(custom)
    listed = workstream_service.list_workstreams(generated.mission.id)
    assert any(item.id == saved.id for item in listed)


def test_green_campus_avoids_full_design_pipeline(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="园区绿色低碳专项"))
    # Force green campus selector via task text in mission generation path:
    # workstream planner reads mission JSON; inject via regenerate after temple draft.
    generated = mission_service.generate_mission(
        project.id,
        "园区绿色低碳专项建议，不是完整建筑设计，只要目标体系、技术筛选和实施路线。",
    )
    # Patch mission fields so workstream prompt contains 园区/绿色低碳
    from archium.application.project_mission_service import MissionPatch

    mission_service.update_mission(
        generated.mission.id,
        MissionPatch(
            title="园区绿色低碳专项建议",
            task_statement="园区绿色低碳专项建议，明确 out of scope：施工图、设备选型、正式碳认证",
        ),
    )
    approve_generated_mission(mission_service, mission_service.get_mission_bundle(generated.mission.id).mission)
    result = workstream_service.plan_workstreams(generated.mission.id)
    types = {item.workstream_type for item in result.workstreams}
    assert WorkstreamType.SUSTAINABILITY in types or WorkstreamType.TECHNICAL_STUDY in types
    assert WorkstreamType.PRESENTATION not in types or len(result.workstreams) <= 4
    titles = " ".join(item.title for item in result.workstreams)
    assert "施工图" not in titles


def test_cyclic_dependencies_are_cleared_with_warning() -> None:
    draft = WorkstreamPlanDraft.model_validate_json(CYCLIC_WORKSTREAM_PLAN_JSON)
    parsed = parse_workstream_plan_draft(
        draft,
        project_id=uuid4(),
        mission_id=uuid4(),
        knowledge_gaps=[],
    )
    assert all(not item.dependencies for item in parsed.workstreams)
    assert any("依赖环" in warning for warning in parsed.warnings)


def test_empty_plan_rejected(
    mission_service: ProjectMissionService,
    temple_project: Project,
    db_session: Session,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)

    def empty_selector(request: LLMRequest) -> str | None:
        if "WorkstreamPlan JSON" in request.user_prompt:
            return '{"workstreams": [], "planning_notes": ""}'
        return TEMPLE_MISSION_JSON

    service = WorkstreamPlanningService(
        db_session, MockLLMProvider(selector=empty_selector)
    )
    with pytest.raises(WorkflowError, match="不能为空"):
        service.plan_workstreams(generated.mission.id)


def test_blocking_gap_indices_resolved(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    result = workstream_service.plan_workstreams(generated.mission.id)
    historical = next(
        item
        for item in result.workstreams
        if item.workstream_type == WorkstreamType.HISTORICAL_RESEARCH
    )
    if len(generated.knowledge_gaps) > 1:
        assert generated.knowledge_gaps[1].id in historical.blocking_gaps
