"""Integration tests for planning workflow interrupt / resume gates."""

from __future__ import annotations

import pytest
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.planning_workflow_service import PlanningWorkflowService
from archium.domain.enums import ApprovalStatus, WorkflowStatus, WorkflowStep
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_deliverable_responses import TEMPLE_DELIVERABLE_PLAN_JSON
from tests.fixtures.mock_mission_responses import (
    TEMPLE_MISSION_JSON,
    TEMPLE_REVISED_AFTER_CLARIFICATION_JSON,
)
from tests.fixtures.mock_workstream_responses import TEMPLE_WORKSTREAM_PLAN_JSON

TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def planning_workflow_mock_selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "DeliverablePlan JSON" in prompt:
        return TEMPLE_DELIVERABLE_PLAN_JSON
    if "WorkstreamPlan JSON" in prompt:
        return TEMPLE_WORKSTREAM_PLAN_JSON
    if "根据澄清结果修订 ProjectMission JSON" in prompt:
        return TEMPLE_REVISED_AFTER_CLARIFICATION_JSON
    if "ProjectMission JSON" in prompt:
        return TEMPLE_MISSION_JSON
    return None


@pytest.fixture
def temple_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="三原县清凉寺"))


@pytest.fixture
def planning_service(db_session: Session, test_settings: object) -> PlanningWorkflowService:
    mock_llm = MockLLMProvider(selector=planning_workflow_mock_selector)
    return PlanningWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]


def test_planning_workflow_pauses_for_clarification(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)

    assert first.awaiting_review
    assert first.review_gate == "clarification"
    assert first.mission is not None
    assert first.clarifying_questions
    assert first.workstreams == []
    assert first.deliverable_plan is None
    assert first.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
    assert (
        first.workflow_run.state["current_step"]
        == WorkflowStep.PLANNING_AWAIT_CLARIFICATION.value
    )


def test_planning_workflow_continues_after_clarification_to_plan_approval(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    assert first.awaiting_review
    assert first.mission is not None

    clarification = MissionClarificationService(
        db_session,
        MockLLMProvider(selector=planning_workflow_mock_selector),
    )
    clarification.answer_question(first.clarifying_questions[0].id, "传统语汇新建")
    db_session.commit()

    second = planning_service.continue_after_clarification(first.workflow_run.id)

    assert second.awaiting_review
    assert second.review_gate == "plan_approval"
    assert second.mission is not None
    assert second.workstreams
    assert second.deliverable_plan is not None
    assert second.deliverable_plan.approval_status == ApprovalStatus.DRAFT
    assert second.presentation_request_draft is None
    assert (
        second.workflow_run.state["current_step"] == WorkflowStep.PLANNING_AWAIT_APPROVAL.value
    )


def test_planning_workflow_completes_after_plan_approval(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    clarification = MissionClarificationService(
        db_session,
        MockLLMProvider(selector=planning_workflow_mock_selector),
    )
    clarification.answer_question(first.clarifying_questions[0].id, "传统语汇新建")
    db_session.commit()

    second = planning_service.continue_after_clarification(first.workflow_run.id)
    assert second.deliverable_plan is not None

    third = planning_service.continue_after_plan_approval(second.workflow_run.id)

    assert not third.awaiting_review
    assert third.workflow_run.status == WorkflowStatus.COMPLETED
    assert third.presentation_request_draft is not None
    assert third.presentation_request_draft.get("mission_id") == str(third.mission.id)
    assert third.deliverable_plan is not None
    assert third.deliverable_plan.approval_status == ApprovalStatus.APPROVED
    assert (
        third.workflow_run.state["current_step"] == WorkflowStep.PLANNING_FINALIZE.value
    )


def test_planning_workflow_can_skip_gates(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
) -> None:
    result = planning_service.run(
        temple_project.id,
        TEMPLE_TASK,
        require_clarification=False,
        require_plan_approval=False,
    )

    assert not result.awaiting_review
    assert result.workflow_run.status == WorkflowStatus.COMPLETED
    assert result.mission is not None
    assert result.workstreams
    assert result.deliverable_plan is not None
    assert result.deliverable_plan.approval_status == ApprovalStatus.APPROVED
    assert result.presentation_request_draft is not None
