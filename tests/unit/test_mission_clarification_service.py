"""Tests for MissionClarificationService."""

from __future__ import annotations

import pytest
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.project_mission_service import ProjectMissionService
from archium.domain.enums import (
    AssumptionStatus,
    KnowledgeGapStatus,
    QuestionStatus,
)
from archium.domain.knowledge_gap import ClarifyingQuestion
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_mission_responses import (
    TEMPLE_MISSION_JSON,
    TEMPLE_REVISED_AFTER_CLARIFICATION_JSON,
)


def clarification_mock_selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "根据澄清结果修订 ProjectMission JSON" in prompt:
        return TEMPLE_REVISED_AFTER_CLARIFICATION_JSON
    if "ProjectMission JSON" in prompt:
        return TEMPLE_MISSION_JSON
    return None


@pytest.fixture
def llm() -> MockLLMProvider:
    return MockLLMProvider(selector=clarification_mock_selector)


@pytest.fixture
def mission_service(db_session: Session, llm: MockLLMProvider) -> ProjectMissionService:
    return ProjectMissionService(db_session, llm)


@pytest.fixture
def clarification_service(
    db_session: Session,
    llm: MockLLMProvider,
    mission_service: ProjectMissionService,
) -> MissionClarificationService:
    return MissionClarificationService(db_session, llm, mission_service=mission_service)


@pytest.fixture
def temple_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="三原县清凉寺"))


TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def test_answer_question_updates_status_and_mission(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    question = generated.clarifying_questions[0]
    result = clarification_service.answer_question(question.id, "传统语汇新建")
    assert result.question is not None
    assert result.question.status == QuestionStatus.ANSWERED
    assert result.question.answer == "传统语汇新建"
    assert any("传统语汇新建" in item for item in result.mission.decisions_required)


def test_assume_question_creates_assumption(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    question = next(q for q in generated.clarifying_questions if q.can_assume and q.suggested_assumption)
    result = clarification_service.assume_question(question.id)
    assert result.question is not None
    assert result.question.status == QuestionStatus.ASSUMED
    assert result.assumption is not None
    assert result.assumption.status == AssumptionStatus.ACCEPTED
    assert any(
        item.source.value == "assumption" for item in result.mission.known_constraints
    )


def test_defer_non_blocking_question(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    question = next(q for q in generated.clarifying_questions if not q.blocking)
    result = clarification_service.defer_question(question.id)
    assert result.question is not None
    assert result.question.status == QuestionStatus.DEFERRED
    assert result.readiness is not None
    assert result.readiness.can_continue is True


def test_defer_blocking_question_rejected(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
    db_session: Session,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    repo = MissionRepository(db_session)
    blocking = ClarifyingQuestion(
        project_id=temple_project.id,
        mission_id=generated.mission.id,
        question="是否已有明确用地红线？",
        why_asked="没有边界无法推进总图",
        blocking=True,
        can_assume=False,
    )
    saved = repo.save_clarifying_question(blocking)
    with pytest.raises(WorkflowError, match="阻塞性问题"):
        clarification_service.defer_question(saved.id)


def test_unanswered_non_blocking_does_not_block_continue(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    readiness = clarification_service.get_readiness(generated.mission.id)
    assert readiness.open_questions
    assert readiness.can_continue is True
    clarification_service.ensure_can_continue(generated.mission.id)


def test_blocking_question_blocks_continue(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
    db_session: Session,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    repo = MissionRepository(db_session)
    repo.save_clarifying_question(
        ClarifyingQuestion(
            project_id=temple_project.id,
            mission_id=generated.mission.id,
            question="阻塞问题",
            why_asked="必须回答",
            blocking=True,
        )
    )
    readiness = clarification_service.get_readiness(generated.mission.id)
    assert readiness.can_continue is False
    with pytest.raises(WorkflowError, match="阻塞性"):
        clarification_service.ensure_can_continue(generated.mission.id)


def test_answer_gap_and_assume_gap(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    assert len(generated.knowledge_gaps) >= 2
    answered = clarification_service.answer_gap(
        generated.knowledge_gaps[0].id,
        "建设规模暂未确定，本轮不做定量方案",
    )
    assert answered.gap is not None
    assert answered.gap.status == KnowledgeGapStatus.ANSWERED

    assumed = clarification_service.assume_gap(
        generated.knowledge_gaps[1].id,
        "历史形制以地方志可核验部分为准",
    )
    assert assumed.gap is not None
    assert assumed.gap.status == KnowledgeGapStatus.ASSUMED
    assert assumed.assumption is not None
    assert assumed.assumption.status == AssumptionStatus.ACCEPTED


def test_mark_not_applicable(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    question = generated.clarifying_questions[0]
    result = clarification_service.mark_question_not_applicable(question.id)
    assert result.question is not None
    assert result.question.status == QuestionStatus.NOT_APPLICABLE


def test_revise_mission_after_clarification_keeps_mission_id(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    question = next(q for q in generated.clarifying_questions if q.suggested_assumption)
    clarification_service.assume_question(question.id)
    for q in generated.clarifying_questions:
        if q.id == question.id:
            continue
        if q.status == QuestionStatus.OPEN and not q.blocking:
            clarification_service.defer_question(q.id)

    revised = clarification_service.revise_mission_after_clarification(generated.mission.id)
    assert revised.mission.id == generated.mission.id
    assert revised.mission.version == generated.mission.version + 1
    assert "传统语汇" in revised.mission.task_statement or any(
        "传统语汇" in c.value for c in revised.mission.known_constraints
    )
    # Existing clarification records remain attached to the same mission.
    assert any(q.status == QuestionStatus.ASSUMED for q in revised.clarifying_questions)
    assert revised.mission.approval_status.value == "draft"
    assert revised.mission.approval_hash is None


def test_clarification_answer_invalidates_approved_mission(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    from archium.domain.enums import ApprovalStatus
    from tests.fixtures.mission_approval import approve_generated_mission

    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    approve_generated_mission(mission_service, generated.mission)
    approved = mission_service.get_mission_bundle(generated.mission.id).mission
    assert approved.approval_status == ApprovalStatus.APPROVED
    assert approved.approval_hash is not None

    question = next(q for q in generated.clarifying_questions if q.status == QuestionStatus.OPEN)
    result = clarification_service.answer_question(question.id, "补充澄清答案")
    assert result.mission.approval_status == ApprovalStatus.DRAFT
    assert result.mission.approval_hash is None


def test_empty_answer_rejected(
    mission_service: ProjectMissionService,
    clarification_service: MissionClarificationService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    with pytest.raises(WorkflowError, match="回答内容不能为空"):
        clarification_service.answer_question(generated.clarifying_questions[0].id, "  ")
