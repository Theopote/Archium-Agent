"""Unit tests for PlanningSession persistence and late Presentation attach."""

from __future__ import annotations

import pytest
from archium.application.planning_workflow_service import PlanningWorkflowService
from archium.domain.enums import PlanningSessionStatus
from archium.domain.planning_session import PlanningSession
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PlanningSessionRepository,
    ProjectRepository,
)
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from archium.ui.planning_service import start_presentation_from_planning
from sqlalchemy.orm import Session

from tests.fixtures.mock_deliverable_responses import TEMPLE_DELIVERABLE_PLAN_JSON
from tests.fixtures.mock_mission_responses import TEMPLE_MISSION_JSON
from tests.fixtures.mock_workstream_responses import TEMPLE_WORKSTREAM_PLAN_JSON


def _selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "DeliverablePlan JSON" in prompt:
        return TEMPLE_DELIVERABLE_PLAN_JSON
    if "WorkstreamPlan JSON" in prompt:
        return TEMPLE_WORKSTREAM_PLAN_JSON
    if "ProjectMission JSON" in prompt:
        return TEMPLE_MISSION_JSON
    return None


def test_planning_session_repository_crud(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="会话仓库测试"))
    repo = PlanningSessionRepository(db_session)
    created = repo.create(
        PlanningSession(
            project_id=project.id,
            status=PlanningSessionStatus.DRAFT,
            user_task_description="测试任务",
        )
    )
    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.user_task_description == "测试任务"
    listed = repo.list_by_project(project.id)
    assert len(listed) == 1


def test_attach_presentation_marks_session_completed(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="附着汇报测试"))
    from archium.domain.presentation import Presentation
    from archium.infrastructure.database.repositories import PresentationRepository

    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="真实汇报")
    )
    repo = PlanningSessionRepository(db_session)
    session = repo.create(
        PlanningSession(
            project_id=project.id,
            status=PlanningSessionStatus.READY,
            user_task_description="完成规划",
        )
    )
    service = PlanningWorkflowService(db_session, MockLLMProvider(selector=_selector))
    updated = service.attach_presentation(session.id, presentation.id)
    assert updated.presentation_id == presentation.id
    assert updated.status == PlanningSessionStatus.COMPLETED


def test_start_presentation_requires_presentation_deliverable(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="无汇报成果"))
    service = PlanningWorkflowService(
        db_session,
        MockLLMProvider(selector=_selector),
        settings=test_settings,  # type: ignore[arg-type]
    )
    result = service.run(
        project.id,
        "园区希望做绿色低碳专项建议，不是完整建筑设计。",
        require_clarification=False,
        require_plan_approval=False,
    )
    # Force-clear selected presentation deliverables to simulate non-presentation plan
    assert result.deliverable_plan is not None
    for item in result.deliverable_plan.deliverables:
        if item.deliverable_type.value == "presentation":
            item.selected = False
            item.required = False
    from archium.infrastructure.database.mission_repositories import MissionRepository

    MissionRepository(db_session).save_deliverable_plan(result.deliverable_plan)
    run_state = dict(result.workflow_run.state)
    run_state["deliverable_plan"] = result.deliverable_plan.model_dump(mode="json")
    result.workflow_run.state = run_state
    from archium.infrastructure.database.repositories import WorkflowRunRepository

    WorkflowRunRepository(db_session).update(result.workflow_run)

    with pytest.raises(WorkflowError, match="未选择「汇报"):
        start_presentation_from_planning(
            db_session,
            project.id,
            result.workflow_run.id,
            settings=test_settings,  # type: ignore[arg-type]
        )
