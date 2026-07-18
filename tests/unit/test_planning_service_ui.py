"""Unit tests for planning UI facade helpers."""

from __future__ import annotations

import pytest
from archium.application.planning_workflow_service import PlanningWorkflowService
from archium.application.project_mission_service import MissionPatch
from archium.domain.enums import WorkflowStatus
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository, WorkflowRunRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from archium.ui.planning_service import (
    get_planning_snapshot,
    update_mission_fields,
)
from sqlalchemy.orm import Session

from tests.fixtures.mock_deliverable_responses import TEMPLE_DELIVERABLE_PLAN_JSON
from tests.fixtures.mock_mission_responses import TEMPLE_MISSION_JSON
from tests.fixtures.mock_workstream_responses import TEMPLE_WORKSTREAM_PLAN_JSON

TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def planning_ui_mock_selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "DeliverablePlan JSON" in prompt:
        return TEMPLE_DELIVERABLE_PLAN_JSON
    if "WorkstreamPlan JSON" in prompt:
        return TEMPLE_WORKSTREAM_PLAN_JSON
    if "ProjectMission JSON" in prompt:
        return TEMPLE_MISSION_JSON
    return None


@pytest.fixture
def temple_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="三原县清凉寺"))


def test_get_planning_snapshot_from_run(
    db_session: Session,
    temple_project: Project,
    test_settings: object,
) -> None:
    llm = MockLLMProvider(selector=planning_ui_mock_selector)
    service = PlanningWorkflowService(db_session, llm, settings=test_settings)  # type: ignore[arg-type]
    result = service.run(temple_project.id, TEMPLE_TASK)
    assert result.awaiting_review

    snapshot = get_planning_snapshot(
        db_session,
        workflow_run_id=result.workflow_run.id,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert snapshot.mission is not None
    assert snapshot.mission.title
    assert snapshot.clarifying_questions
    assert snapshot.review_gate == "clarification"
    assert snapshot.readiness is not None
    assert snapshot.readiness.can_continue


def test_get_planning_snapshot_by_project(
    db_session: Session,
    temple_project: Project,
    test_settings: object,
) -> None:
    llm = MockLLMProvider(selector=planning_ui_mock_selector)
    service = PlanningWorkflowService(db_session, llm, settings=test_settings)  # type: ignore[arg-type]
    service.run(temple_project.id, TEMPLE_TASK)

    snapshot = get_planning_snapshot(
        db_session,
        project_id=temple_project.id,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert snapshot.workflow_run is not None
    assert snapshot.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
    assert snapshot.mission is not None


def test_list_planning_runs_and_update_mission(
    db_session: Session,
    temple_project: Project,
    test_settings: object,
) -> None:
    llm = MockLLMProvider(selector=planning_ui_mock_selector)
    service = PlanningWorkflowService(db_session, llm, settings=test_settings)  # type: ignore[arg-type]
    result = service.run(temple_project.id, TEMPLE_TASK)
    assert result.mission is not None

    runs = WorkflowRunRepository(db_session).list_planning_by_project(temple_project.id)
    assert len(runs) == 1
    assert runs[0].id == result.workflow_run.id

    updated = update_mission_fields(
        db_session,
        result.mission.id,
        MissionPatch(title="清凉寺重建（已编辑）"),
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert updated.title == "清凉寺重建（已编辑）"


def test_refresh_resume_snapshot_keeps_mission_and_facts(
    db_session: Session,
    temple_project: Project,
    test_settings: object,
) -> None:
    """Simulates UI refresh: recover planning state by project_id only."""
    from archium.domain.enums import VerificationStatus
    from archium.domain.fact import ProjectFact
    from archium.infrastructure.database.repositories import FactRepository

    FactRepository(db_session).create(
        ProjectFact(
            project_id=temple_project.id,
            key="site_area",
            label="用地面积",
            value=12000,
            unit="㎡",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    )
    llm = MockLLMProvider(selector=planning_ui_mock_selector)
    PlanningWorkflowService(db_session, llm, settings=test_settings).run(  # type: ignore[arg-type]
        temple_project.id, TEMPLE_TASK
    )

    # Fresh load without workflow_run_id (browser refresh)
    snapshot = get_planning_snapshot(
        db_session,
        project_id=temple_project.id,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert snapshot.workflow_run is not None
    assert snapshot.mission is not None
    assert any(f.key == "site_area" and f.is_confirmed for f in snapshot.project_facts)
    assert snapshot.knowledge_gaps or snapshot.clarifying_questions
