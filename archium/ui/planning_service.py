"""UI-facing helpers for the project mission planning experience."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.fact_ledger_service import FactLedgerService
from archium.application.mission_clarification_service import (
    ClarificationActionResult,
    ClarificationReadiness,
    MissionClarificationService,
)
from archium.application.mission_to_presentation_request import (
    MissionPresentationBridge,
    PresentationOverrides,
)
from archium.application.planning_workflow_service import (
    PlanningWorkflowResult,
    PlanningWorkflowService,
)
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.application.workflow_models import WorkflowRunResult
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.config.settings import Settings
from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import DeliverableType, KnowledgeGapStatus, QuestionStatus
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import Assumption, ClarifyingQuestion, KnowledgeGap
from archium.domain.planning_session import PlanningSession
from archium.domain.project_mission import ProjectMission
from archium.domain.workflow import WorkflowRun
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    FactRepository,
    PlanningSessionRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm.factory import create_llm_provider
from archium.ui.workflow_resources import get_workflow_checkpointer_manager
from archium.ui.workspace_service import _resolve_runtime_settings


@dataclass
class PlanningSnapshot:
    """UI-ready snapshot of the active planning session."""

    planning_session: PlanningSession | None = None
    workflow_run: WorkflowRun | None = None
    mission: ProjectMission | None = None
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    workstreams: list[Workstream] = field(default_factory=list)
    deliverable_plan: DeliverablePlan | None = None
    project_facts: list[ProjectFact] = field(default_factory=list)
    presentation_request: PresentationRequest | None = None
    readiness: ClarificationReadiness | None = None
    review_gate: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def mission_id(self) -> UUID | None:
        return self.mission.id if self.mission is not None else None

    @property
    def open_questions(self) -> list[ClarifyingQuestion]:
        return [q for q in self.clarifying_questions if q.status == QuestionStatus.OPEN]

    @property
    def confirmed_gaps(self) -> list[KnowledgeGap]:
        return [
            g
            for g in self.knowledge_gaps
            if g.status in {KnowledgeGapStatus.ANSWERED, KnowledgeGapStatus.ASSUMED}
        ]

    @property
    def pending_gaps(self) -> list[KnowledgeGap]:
        return [g for g in self.knowledge_gaps if g.status == KnowledgeGapStatus.OPEN]


def _create_planning_service(
    session: Session,
    settings: Settings,
) -> PlanningWorkflowService:
    llm = create_llm_provider(settings)
    return PlanningWorkflowService(
        session,
        llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def _create_presentation_service(
    session: Session,
    settings: Settings,
) -> PresentationWorkflowService:
    llm = create_llm_provider(settings)
    return PresentationWorkflowService(
        session,
        llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def start_planning(
    session: Session,
    project_id: UUID,
    task_description: str,
    *,
    settings: Settings | None = None,
) -> PlanningWorkflowResult:
    runtime = _resolve_runtime_settings(settings)
    service = _create_planning_service(session, runtime)
    return service.run(project_id, task_description)


def continue_after_clarification(
    session: Session,
    workflow_run_id: UUID,
    *,
    settings: Settings | None = None,
) -> PlanningWorkflowResult:
    runtime = _resolve_runtime_settings(settings)
    service = _create_planning_service(session, runtime)
    return service.continue_after_clarification(workflow_run_id)


def continue_after_plan_approval(
    session: Session,
    workflow_run_id: UUID,
    *,
    settings: Settings | None = None,
) -> PlanningWorkflowResult:
    runtime = _resolve_runtime_settings(settings)
    service = _create_planning_service(session, runtime)
    return service.continue_after_plan_approval(workflow_run_id)


def get_planning_snapshot(
    session: Session,
    *,
    planning_session_id: UUID | None = None,
    workflow_run_id: UUID | None = None,
    mission_id: UUID | None = None,
    project_id: UUID | None = None,
    settings: Settings | None = None,
) -> PlanningSnapshot:
    """Load the best available planning snapshot for the UI."""
    runtime = _resolve_runtime_settings(settings)
    runs = WorkflowRunRepository(session)
    sessions = PlanningSessionRepository(session)
    missions = MissionRepository(session)
    llm = create_llm_provider(runtime)
    clarification = MissionClarificationService(session, llm, settings=runtime)

    planning_session: PlanningSession | None = None
    if planning_session_id is not None:
        planning_session = sessions.get_by_id(planning_session_id)
    elif workflow_run_id is not None:
        planning_session = sessions.get_by_workflow_run_id(workflow_run_id)
    elif project_id is not None:
        project_sessions = sessions.list_by_project(project_id)
        planning_session = project_sessions[0] if project_sessions else None

    run: WorkflowRun | None = None
    if workflow_run_id is not None:
        run = runs.get_by_id(workflow_run_id)
    elif planning_session is not None and planning_session.workflow_run_id is not None:
        run = runs.get_by_id(planning_session.workflow_run_id)
    elif project_id is not None:
        planning_runs = runs.list_planning_by_project(project_id)
        run = planning_runs[0] if planning_runs else None
        if planning_session is None and run is not None:
            planning_session = sessions.get_by_workflow_run_id(run.id)

    resolved_mission_id = mission_id
    if resolved_mission_id is None and planning_session is not None:
        resolved_mission_id = planning_session.current_mission_id
    warnings: list[str] = []
    presentation_request = None
    review_gate = None

    if run is not None:
        review_gate = run.state.get("review_gate") if isinstance(run.state.get("review_gate"), str) else None
        if resolved_mission_id is None:
            raw = run.state.get("mission_id")
            if raw:
                resolved_mission_id = UUID(str(raw))
            elif isinstance(run.state.get("mission"), dict) and run.state["mission"].get("id"):
                resolved_mission_id = UUID(str(run.state["mission"]["id"]))
        draft = run.state.get("presentation_request_draft")
        if isinstance(draft, dict) and draft.get("mission_id"):
            from archium.application.mission_to_presentation_request import bridge_from_draft

            try:
                bridge = bridge_from_draft(draft)
                presentation_request = bridge.request
                warnings.extend(bridge.warnings)
            except WorkflowError:
                pass

    if resolved_mission_id is None and project_id is not None:
        project_missions = missions.list_missions_by_project(project_id)
        if project_missions:
            resolved_mission_id = project_missions[0].id

    if resolved_mission_id is None:
        return PlanningSnapshot(
            planning_session=planning_session,
            workflow_run=run,
            review_gate=review_gate,
            warnings=warnings,
        )

    mission = missions.get_mission(resolved_mission_id)
    if mission is None:
        return PlanningSnapshot(
            planning_session=planning_session,
            workflow_run=run,
            review_gate=review_gate,
            warnings=warnings,
        )

    plans = missions.list_deliverable_plans(resolved_mission_id)
    plan = plans[0] if plans else None
    readiness = clarification.get_readiness(resolved_mission_id)
    project_facts = FactRepository(session).list_by_project(mission.project_id)

    return PlanningSnapshot(
        planning_session=planning_session,
        workflow_run=run,
        mission=mission,
        knowledge_gaps=missions.list_knowledge_gaps(resolved_mission_id),
        assumptions=missions.list_assumptions(resolved_mission_id),
        clarifying_questions=missions.list_clarifying_questions(resolved_mission_id),
        workstreams=missions.list_workstreams(resolved_mission_id),
        deliverable_plan=plan,
        project_facts=project_facts,
        presentation_request=presentation_request,
        readiness=readiness,
        review_gate=review_gate if isinstance(review_gate, str) else None,
        warnings=warnings,
    )


def update_mission_fields(
    session: Session,
    mission_id: UUID,
    patch: MissionPatch,
    *,
    settings: Settings | None = None,
) -> ProjectMission:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return ProjectMissionService(session, llm, settings=runtime).update_mission(mission_id, patch)


def answer_clarifying_question(
    session: Session,
    question_id: UUID,
    answer: str,
    *,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).answer_question(
        question_id, answer
    )


def assume_clarifying_question(
    session: Session,
    question_id: UUID,
    *,
    assumption_text: str | None = None,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).assume_question(
        question_id, assumption_text=assumption_text
    )


def defer_clarifying_question(
    session: Session,
    question_id: UUID,
    *,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).defer_question(question_id)


def mark_question_not_applicable(
    session: Session,
    question_id: UUID,
    *,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).mark_question_not_applicable(
        question_id
    )


def answer_knowledge_gap(
    session: Session,
    gap_id: UUID,
    answer: str,
    *,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).answer_gap(gap_id, answer)


def assume_knowledge_gap(
    session: Session,
    gap_id: UUID,
    assumption_text: str,
    *,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).assume_gap(
        gap_id, assumption_text
    )


def defer_knowledge_gap(
    session: Session,
    gap_id: UUID,
    *,
    settings: Settings | None = None,
) -> ClarificationActionResult:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    return MissionClarificationService(session, llm, settings=runtime).defer_gap(gap_id)


def confirm_project_fact(session: Session, fact_id: UUID) -> ProjectFact:
    return FactLedgerService(session).confirm_fact(fact_id)


def reject_project_fact(session: Session, fact_id: UUID) -> ProjectFact:
    return FactLedgerService(session).reject_fact(fact_id)


def set_workstream_selected(
    session: Session,
    workstream_id: UUID,
    selected: bool,
    *,
    settings: Settings | None = None,
) -> Workstream:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    service = WorkstreamPlanningService(session, llm, settings=runtime)
    if selected:
        return service.select_workstream(workstream_id)
    return service.deselect_workstream(workstream_id)


def set_deliverable_selected(
    session: Session,
    plan_id: UUID,
    deliverable_id: str,
    selected: bool,
    *,
    settings: Settings | None = None,
) -> DeliverablePlan:
    runtime = _resolve_runtime_settings(settings)
    llm = create_llm_provider(runtime)
    service = DeliverablePlanningService(session, llm, settings=runtime)
    if selected:
        return service.select_deliverable(plan_id, deliverable_id)
    return service.deselect_deliverable(plan_id, deliverable_id)


def get_presentation_bridge(
    session: Session,
    workflow_run_id: UUID,
    *,
    user_overrides: PresentationOverrides | None = None,
    settings: Settings | None = None,
) -> MissionPresentationBridge:
    runtime = _resolve_runtime_settings(settings)
    service = _create_planning_service(session, runtime)
    return service.get_presentation_bridge(workflow_run_id, user_overrides=user_overrides)


def start_presentation_from_planning(
    session: Session,
    project_id: UUID,
    workflow_run_id: UUID,
    *,
    export_json: bool = True,
    export_marp: bool = True,
    require_brief_review: bool = True,
    require_storyline_review: bool = True,
    settings: Settings | None = None,
) -> WorkflowRunResult:
    """Approve plan gate if needed, then launch the existing presentation pipeline."""
    runtime = _resolve_runtime_settings(settings)
    planning = _create_planning_service(session, runtime)
    run = planning.get_run(workflow_run_id)
    if run is None:
        raise WorkflowError(f"Workflow run {workflow_run_id} not found")

    if run.status.value == "awaiting_review" and run.state.get("review_gate") == "plan_approval":
        planning.continue_after_plan_approval(workflow_run_id)
        run = planning.get_run(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} disappeared after plan approval")

    missions = MissionRepository(session)
    mission_id = None
    raw = run.state.get("mission_id")
    if raw:
        mission_id = UUID(str(raw))
    plan = None
    if mission_id is not None:
        plan = missions.get_approved_deliverable_plan(mission_id)
        if plan is None:
            plans = missions.list_deliverable_plans(mission_id)
            plan = plans[0] if plans else None
    if plan is None:
        plan_data = run.state.get("deliverable_plan")
        if isinstance(plan_data, dict) and plan_data.get("id"):
            plan = missions.get_deliverable_plan(UUID(str(plan_data["id"])))
    if plan is None:
        raise WorkflowError("尚未生成成果规划，无法启动汇报")

    selected_presentations = [
        item
        for item in plan.deliverables
        if item.selected and item.deliverable_type == DeliverableType.PRESENTATION
    ]
    if not selected_presentations:
        raise WorkflowError(
            "当前成果计划未选择「汇报 / Presentation」类成果。"
            "非汇报成果不会自动创建 Presentation；请调整成果选择后再启动。"
        )

    bridge = planning.get_presentation_bridge(workflow_run_id)
    presentation_service = _create_presentation_service(session, runtime)
    result = presentation_service.run(
        project_id,
        bridge.request,
        export_json=export_json,
        export_marp=export_marp,
        require_brief_review=require_brief_review,
        require_storyline_review=require_storyline_review,
    )

    planning_session = planning.get_session_for_run(workflow_run_id)
    if planning_session is not None:
        planning.attach_presentation(planning_session.id, result.presentation.id)
    return result


TASK_EXAMPLE_PROMPTS = [
    "三原县清凉寺历史上多次被毁，现在希望重新建设。目前只有部分地方志和现场照片，面积未知。希望先形成前期策划与概念设计汇报。",
    "大学图书馆需要改造，不停业施工，功能与空间运营都要兼顾，希望形成改造汇报与分期路线图。",
    "园区希望做绿色低碳专项建议，不是完整建筑设计，不要施工图与设备选型。",
]
