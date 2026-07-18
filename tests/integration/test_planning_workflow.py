"""Integration tests for planning workflow interrupt / resume gates."""

from __future__ import annotations

import pytest
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.planning_workflow_service import PlanningWorkflowService
from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.domain.enums import ApprovalStatus, PlanningSessionStatus, WorkflowStatus, WorkflowStep
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_deliverable_responses import TEMPLE_DELIVERABLE_PLAN_JSON
from tests.fixtures.mock_mission_responses import (
    TEMPLE_MISSION_JSON,
    TEMPLE_MISSION_SCOPE_CONFLICT_JSON,
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


def _answer_first_question(
    planning_service: PlanningWorkflowService,
    db_session: Session,
    first,
) -> None:
    clarification = MissionClarificationService(
        db_session,
        MockLLMProvider(selector=planning_workflow_mock_selector),
    )
    clarification.answer_question(first.clarifying_questions[0].id, "传统语汇新建")
    db_session.commit()


def test_planning_run_does_not_create_presentation(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    before = len(PresentationRepository(db_session).list_by_project(temple_project.id))
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    after = len(PresentationRepository(db_session).list_by_project(temple_project.id))

    assert after == before
    assert first.presentation is None
    assert first.workflow_run.presentation_id is None
    assert first.planning_session.workflow_run_id == first.workflow_run.id
    assert first.planning_session.status == PlanningSessionStatus.CLARIFYING


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


def test_planning_workflow_pauses_for_mission_approval_after_clarification(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    _answer_first_question(planning_service, db_session, first)

    second = planning_service.continue_after_clarification(first.workflow_run.id)

    assert second.awaiting_review
    assert second.review_gate == "mission_approval"
    assert second.mission is not None
    assert second.mission.approval_status == ApprovalStatus.DRAFT
    assert second.workstreams == []
    assert second.deliverable_plan is None
    assert second.planning_session.status == PlanningSessionStatus.AWAITING_MISSION_APPROVAL
    assert (
        second.workflow_run.state["current_step"]
        == WorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value
    )


def test_resume_after_mission_approval_requires_prior_approve(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    _answer_first_question(planning_service, db_session, first)
    second = planning_service.continue_after_clarification(first.workflow_run.id)

    with pytest.raises(WorkflowError, match="尚未批准"):
        planning_service.resume_after_mission_approval(second.workflow_run.id)


def test_planning_workflow_continues_after_mission_approval_to_plan_approval(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    _answer_first_question(planning_service, db_session, first)
    second = planning_service.continue_after_clarification(first.workflow_run.id)

    third = planning_service.approve_mission_and_continue(second.workflow_run.id)

    assert third.awaiting_review
    assert third.review_gate == "plan_approval"
    assert third.mission is not None
    assert third.mission.approval_status == ApprovalStatus.APPROVED
    assert third.workstreams
    assert third.deliverable_plan is not None
    assert third.deliverable_plan.approval_status == ApprovalStatus.DRAFT
    assert third.presentation_request_draft is None
    assert third.presentation is None
    assert third.planning_session.status == PlanningSessionStatus.AWAITING_APPROVAL
    assert (
        third.workflow_run.state["current_step"] == WorkflowStep.PLANNING_AWAIT_APPROVAL.value
    )


def test_resume_after_plan_approval_requires_prior_approve(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    _answer_first_question(planning_service, db_session, first)
    second = planning_service.continue_after_clarification(first.workflow_run.id)
    third = planning_service.approve_mission_and_continue(second.workflow_run.id)

    with pytest.raises(WorkflowError, match="尚未批准"):
        planning_service.resume_after_plan_approval(third.workflow_run.id)


def test_planning_workflow_completes_after_plan_approval(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    before = len(PresentationRepository(db_session).list_by_project(temple_project.id))
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    _answer_first_question(planning_service, db_session, first)
    second = planning_service.continue_after_clarification(first.workflow_run.id)
    third = planning_service.approve_mission_and_continue(second.workflow_run.id)
    assert third.deliverable_plan is not None

    # Domain approve + resume are separable; facade combines them for UI.
    planning_service.approve_deliverable_plan(third.deliverable_plan.id)
    fourth = planning_service.resume_after_plan_approval(third.workflow_run.id)

    assert not fourth.awaiting_review
    assert fourth.workflow_run.status == WorkflowStatus.COMPLETED
    assert fourth.presentation is None
    assert fourth.workflow_run.presentation_id is None
    assert fourth.planning_session.status == PlanningSessionStatus.READY
    assert fourth.presentation_request_draft is not None
    assert fourth.presentation_request is not None
    assert fourth.presentation_request.purpose == fourth.mission.task_statement
    assert fourth.presentation_request.title == "概念设计汇报"
    assert "施工图" in " ".join(fourth.presentation_request.excluded_topics)
    assert fourth.presentation_request_draft.get("mission_id") == str(fourth.mission.id)
    assert fourth.deliverable_plan is not None
    assert fourth.deliverable_plan.approval_status == ApprovalStatus.APPROVED
    assert (
        fourth.workflow_run.state["current_step"] == WorkflowStep.PLANNING_FINALIZE.value
    )
    assert len(PresentationRepository(db_session).list_by_project(temple_project.id)) == before

    bridge = planning_service.get_presentation_bridge(fourth.workflow_run.id)
    assert bridge.request.title == fourth.presentation_request.title
    assert bridge.deliverable_id == "del-concept-ppt"


def test_approve_and_continue_facade(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
    db_session: Session,
) -> None:
    first = planning_service.run(temple_project.id, TEMPLE_TASK)
    _answer_first_question(planning_service, db_session, first)
    second = planning_service.continue_after_clarification(first.workflow_run.id)
    third = planning_service.approve_mission_and_continue(second.workflow_run.id)

    fourth = planning_service.approve_and_continue(third.workflow_run.id)
    assert not fourth.awaiting_review
    assert fourth.workflow_run.status == WorkflowStatus.COMPLETED
    assert fourth.deliverable_plan is not None
    assert fourth.deliverable_plan.approval_status == ApprovalStatus.APPROVED


def test_planning_workflow_can_skip_gates(
    planning_service: PlanningWorkflowService,
    temple_project: Project,
) -> None:
    result = planning_service.run(
        temple_project.id,
        TEMPLE_TASK,
        require_clarification=False,
        require_mission_approval=False,
        require_plan_approval=False,
    )

    assert not result.awaiting_review
    assert result.workflow_run.status == WorkflowStatus.COMPLETED
    assert result.mission is not None
    assert result.mission.approval_status == ApprovalStatus.APPROVED
    assert result.workstreams
    assert result.deliverable_plan is not None
    assert result.deliverable_plan.approval_status == ApprovalStatus.APPROVED
    assert result.presentation_request_draft is not None
    assert result.presentation_request is not None
    assert result.presentation is None
    assert result.presentation_request.purpose
    assert result.planning_session.status == PlanningSessionStatus.READY


def test_recoverable_validation_pauses_for_mission_correction(
    temple_project: Project,
    db_session: Session,
    test_settings: object,
) -> None:
    """Professional issues must not FAILED the session — pause for correction."""

    def selector(request: LLMRequest) -> str | None:
        prompt = request.user_prompt
        if "DeliverablePlan JSON" in prompt:
            return TEMPLE_DELIVERABLE_PLAN_JSON
        if "WorkstreamPlan JSON" in prompt:
            return TEMPLE_WORKSTREAM_PLAN_JSON
        if "根据澄清结果修订 ProjectMission JSON" in prompt:
            return TEMPLE_REVISED_AFTER_CLARIFICATION_JSON
        if "ProjectMission JSON" in prompt:
            return TEMPLE_MISSION_SCOPE_CONFLICT_JSON
        return None

    mock_llm = MockLLMProvider(selector=selector)
    service = PlanningWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]

    first = service.run(temple_project.id, TEMPLE_TASK)

    assert first.awaiting_review
    assert first.review_gate == "mission_correction"
    assert first.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
    assert first.planning_session.status == PlanningSessionStatus.AWAITING_MISSION_CORRECTION
    assert first.planning_session.status != PlanningSessionStatus.FAILED
    assert first.mission is not None
    validation = first.workflow_run.state.get("mission_validation") or {}
    assert validation.get("needs_correction") is True
    assert not validation.get("is_fatal")

    # User fixes scope conflict then resumes.
    ProjectMissionService(
        db_session,
        mock_llm,
        settings=test_settings,  # type: ignore[arg-type]
    ).update_mission(
        first.mission.id,
        MissionPatch(out_of_scope=["施工招标"]),
    )
    db_session.commit()

    second = service.continue_after_mission_correction(first.workflow_run.id)

    assert second.awaiting_review
    assert second.review_gate == "clarification"
    assert second.planning_session.status == PlanningSessionStatus.CLARIFYING
    assert second.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
