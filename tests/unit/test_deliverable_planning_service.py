"""Tests for deliverable planning service and parser."""

from __future__ import annotations

import pytest
from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.domain.enums import ApprovalStatus, DeliverableType
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mission_approval import approve_generated_mission
from tests.fixtures.mock_deliverable_responses import (
    GREEN_CAMPUS_DELIVERABLE_PLAN_JSON,
    TEMPLE_DELIVERABLE_PLAN_JSON,
)
from tests.fixtures.mock_mission_responses import TEMPLE_MISSION_JSON
from tests.fixtures.mock_workstream_responses import (
    GREEN_CAMPUS_WORKSTREAM_PLAN_JSON,
    TEMPLE_WORKSTREAM_PLAN_JSON,
)


def planning_mock_selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "DeliverablePlan JSON" in prompt:
        if "绿色低碳" in prompt or "园区" in prompt:
            return GREEN_CAMPUS_DELIVERABLE_PLAN_JSON
        return TEMPLE_DELIVERABLE_PLAN_JSON
    if "WorkstreamPlan JSON" in prompt:
        if "绿色低碳" in prompt or "园区" in prompt:
            return GREEN_CAMPUS_WORKSTREAM_PLAN_JSON
        return TEMPLE_WORKSTREAM_PLAN_JSON
    if "ProjectMission JSON" in prompt:
        return TEMPLE_MISSION_JSON
    return None


@pytest.fixture
def llm() -> MockLLMProvider:
    return MockLLMProvider(selector=planning_mock_selector)


@pytest.fixture
def mission_service(db_session: Session, llm: MockLLMProvider) -> ProjectMissionService:
    return ProjectMissionService(db_session, llm)


@pytest.fixture
def workstream_service(db_session: Session, llm: MockLLMProvider) -> WorkstreamPlanningService:
    return WorkstreamPlanningService(db_session, llm)


@pytest.fixture
def deliverable_service(db_session: Session, llm: MockLLMProvider) -> DeliverablePlanningService:
    return DeliverablePlanningService(db_session, llm)


@pytest.fixture
def temple_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="三原县清凉寺"))


TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def _prepare_temple_mission(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    project: Project,
):
    generated = mission_service.generate_mission(project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    workstream_service.plan_workstreams(generated.mission.id)
    return generated.mission


def test_plan_deliverables_for_temple(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)
    result = deliverable_service.plan_deliverables(mission.id)
    types = {item.deliverable_type for item in result.plan.deliverables}
    assert DeliverableType.PRESENTATION in types
    assert DeliverableType.CASE_STUDY in types
    assert DeliverableType.QUESTION_LIST in types
    assert any(item.required and item.selected for item in result.plan.deliverables)
    not_recommended = [
        item for item in result.plan.deliverables if "不建议" in (item.notes or "")
    ]
    assert not_recommended
    assert all(not item.selected for item in not_recommended)


def test_presentation_links_to_workstreams(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)
    result = deliverable_service.plan_deliverables(mission.id)
    ppt = next(
        item
        for item in result.plan.deliverables
        if item.deliverable_type == DeliverableType.PRESENTATION
    )
    assert ppt.source_workstream_ids
    workstream_ids = {item.id for item in result.workstreams}
    assert set(ppt.source_workstream_ids).issubset(workstream_ids)


def test_select_deselect_and_approve(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)
    result = deliverable_service.plan_deliverables(mission.id)
    optional = next(
        (item for item in result.plan.deliverables if not item.required and item.selected),
        None,
    )
    if optional is not None:
        updated = deliverable_service.deselect_deliverable(result.plan.id, optional.id)
        assert all(item.id != optional.id or not item.selected for item in updated.deliverables)

    required = next(item for item in result.plan.deliverables if item.required)
    with pytest.raises(WorkflowError, match="必要成果"):
        deliverable_service.deselect_deliverable(result.plan.id, required.id)

    approved = deliverable_service.approve_plan(result.plan.id)
    assert approved.approval_status == ApprovalStatus.APPROVED


def test_selection_edit_invalidates_approved_plan(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)
    result = deliverable_service.plan_deliverables(mission.id)
    approved = deliverable_service.approve_plan(result.plan.id)
    assert approved.approval_status == ApprovalStatus.APPROVED

    optional = next(
        (item for item in approved.deliverables if not item.required),
        None,
    )
    assert optional is not None

    if optional.selected:
        updated = deliverable_service.deselect_deliverable(approved.id, optional.id)
    else:
        updated = deliverable_service.select_deliverable(approved.id, optional.id)

    assert updated.approval_status == ApprovalStatus.DRAFT

    # Idempotent re-apply must not keep a stale approved status after prior invalidation.
    again = deliverable_service.set_deliverable_selection(
        updated.id,
        [item.id for item in updated.deliverables if item.selected],
    )
    assert again.approval_status == ApprovalStatus.DRAFT


def test_requires_workstreams_first(
    mission_service: ProjectMissionService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    with pytest.raises(WorkflowError, match="工作路径"):
        deliverable_service.plan_deliverables(generated.mission.id)


def test_green_campus_prefers_report_not_scheme_ppt(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="园区绿色低碳专项"))
    generated = mission_service.generate_mission(
        project.id,
        "园区绿色低碳专项建议，不要完整建筑设计方案汇报。",
    )
    mission_service.update_mission(
        generated.mission.id,
        MissionPatch(
            title="园区绿色低碳专项建议",
            task_statement="园区绿色低碳专项建议，out of scope：施工图、设备选型、正式碳认证、完整方案PPT",
            out_of_scope=["施工图", "设备选型", "正式碳认证", "完整建筑设计方案汇报"],
        ),
    )
    approve_generated_mission(
        mission_service,
        mission_service.get_mission_bundle(generated.mission.id).mission,
    )
    workstream_service.plan_workstreams(generated.mission.id)
    result = deliverable_service.plan_deliverables(generated.mission.id)

    selected_types = {item.deliverable_type for item in result.selected_deliverables}
    assert DeliverableType.REPORT in selected_types or DeliverableType.TECHNICAL_PROPOSAL in selected_types
    presentation_selected = [
        item
        for item in result.plan.deliverables
        if item.deliverable_type == DeliverableType.PRESENTATION and item.selected
    ]
    assert presentation_selected == []
    assert result.presentation_deliverables == []


def test_version_increments_on_replan(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)
    first = deliverable_service.plan_deliverables(mission.id)
    second = deliverable_service.plan_deliverables(mission.id)
    assert second.plan.version == first.plan.version + 1
    assert second.plan.lineage_id == first.plan.lineage_id


def test_empty_plan_rejected(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    temple_project: Project,
    db_session: Session,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)

    def empty_selector(request: LLMRequest) -> str | None:
        if "DeliverablePlan JSON" in request.user_prompt:
            return '{"deliverables": [], "planning_notes": ""}'
        return planning_mock_selector(request)

    service = DeliverablePlanningService(db_session, MockLLMProvider(selector=empty_selector))
    with pytest.raises(WorkflowError, match="不能为空"):
        service.plan_deliverables(mission.id)


def test_approve_requires_selection(
    mission_service: ProjectMissionService,
    workstream_service: WorkstreamPlanningService,
    deliverable_service: DeliverablePlanningService,
    temple_project: Project,
) -> None:
    mission = _prepare_temple_mission(mission_service, workstream_service, temple_project)
    result = deliverable_service.plan_deliverables(mission.id)
    # Deselect everything that is allowed, then force-clear selection via set API
    # including required items to simulate empty approval attempt.
    cleared = deliverable_service.set_deliverable_selection(result.plan.id, [])
    assert cleared.selected_deliverables() == []
    with pytest.raises(WorkflowError, match="至少选择"):
        deliverable_service.approve_plan(result.plan.id)
