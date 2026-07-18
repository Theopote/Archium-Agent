"""LangGraph-based project mission planning workflow service."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.mission_to_presentation_request import (
    MissionPresentationBridge,
    PresentationOverrides,
    bridge_from_draft,
    build_presentation_bridge,
)
from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings, get_settings
from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import ApprovalStatus, PlanningSessionStatus, WorkflowStatus, WorkflowStep
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.planning_session import PlanningSession
from archium.domain.presentation import Presentation
from archium.domain.project_mission import ProjectMission
from archium.domain.workflow import WorkflowRun
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    PlanningSessionRepository,
    PresentationRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger
from archium.workflow.checkpointer import WorkflowCheckpointerManager
from archium.workflow.planning_graph import PlanningWorkflowGraph
from archium.workflow.planning_nodes import PlanningWorkflowRuntime
from archium.workflow.planning_serialization import (
    restore_planning_artifacts,
    snapshot_planning_state,
)
from archium.workflow.planning_state import PlanningWorkflowState, initial_planning_state

logger = get_logger(__name__, operation="planning_workflow")


@dataclass
class PlanningWorkflowResult:
    """Outcome of a mission planning workflow execution."""

    planning_session: PlanningSession
    workflow_run: WorkflowRun
    presentation: Presentation | None = None
    mission: ProjectMission | None = None
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    design_questions: list[DesignQuestion] = field(default_factory=list)
    workstreams: list[Workstream] = field(default_factory=list)
    deliverable_plan: DeliverablePlan | None = None
    presentation_request: PresentationRequest | None = None
    presentation_request_draft: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.errors

    @property
    def awaiting_review(self) -> bool:
        return self.workflow_run.status == WorkflowStatus.AWAITING_REVIEW

    @property
    def review_gate(self) -> str | None:
        gate = self.workflow_run.state.get("review_gate")
        return gate if isinstance(gate, str) else None


class PlanningWorkflowService:
    """Run mission-first planning as a persisted LangGraph workflow with interrupts."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        checkpointer_manager: WorkflowCheckpointerManager | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runtime = PlanningWorkflowRuntime(session, llm, settings=self._settings)
        self._workflow_runs = WorkflowRunRepository(session)
        self._planning_sessions = PlanningSessionRepository(session)
        self._presentations = PresentationRepository(session)
        self._clarification = MissionClarificationService(
            session, llm, settings=self._settings
        )
        self._deliverables = DeliverablePlanningService(
            session, llm, settings=self._settings
        )
        self._owns_checkpointer = checkpointer_manager is None
        self._checkpointer_manager = checkpointer_manager or WorkflowCheckpointerManager(
            self._settings.workflow_checkpoint_path
        )
        self._graph = PlanningWorkflowGraph(
            self._runtime,
            checkpointer=self._checkpointer_manager.saver,
        )

    def close(self) -> None:
        self._checkpointer_manager.close()

    def __del__(self) -> None:
        if getattr(self, "_owns_checkpointer", False):
            with suppress(Exception):
                self.close()

    def run(
        self,
        project_id: UUID,
        user_task_description: str,
        *,
        require_clarification: bool = True,
        require_mission_approval: bool = True,
        require_plan_approval: bool = True,
    ) -> PlanningWorkflowResult:
        if not user_task_description.strip():
            raise WorkflowError("任务描述不能为空")

        planning_session = self._planning_sessions.create(
            PlanningSession(
                project_id=project_id,
                status=PlanningSessionStatus.DRAFT,
                user_task_description=user_task_description.strip(),
            )
        )
        workflow_run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                presentation_id=None,
                status=WorkflowStatus.RUNNING,
                state={
                    "workflow_kind": "planning",
                    "planning_session_id": str(planning_session.id),
                    "current_step": WorkflowStep.INIT.value,
                    "user_task_description": user_task_description,
                    "require_clarification": require_clarification,
                    "require_mission_approval": require_mission_approval,
                    "require_plan_approval": require_plan_approval,
                },
            )
        )
        planning_session.workflow_run_id = workflow_run.id
        planning_session.status = PlanningSessionStatus.PLANNING
        planning_session.touch()
        planning_session = self._planning_sessions.update(planning_session)

        initial_state = initial_planning_state(
            project_id=str(project_id),
            workflow_run_id=str(workflow_run.id),
            planning_session_id=str(planning_session.id),
            user_task_description=user_task_description,
            presentation_id=None,
            require_clarification=require_clarification,
            require_mission_approval=require_mission_approval,
            require_plan_approval=require_plan_approval,
        )

        try:
            final_state = self._graph.invoke(initial_state, thread_id=str(workflow_run.id))
        except Exception as exc:
            logger.exception("Planning workflow graph execution failed: %s", exc)
            workflow_run.errors = [str(exc)]
            workflow_run.status = WorkflowStatus.FAILED
            workflow_run.state = snapshot_planning_state(initial_state)
            workflow_run.touch()
            self._workflow_runs.update(workflow_run)
            self._mark_session_failed(planning_session.id)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(workflow_run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {workflow_run.id} disappeared after execution")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def continue_after_clarification(self, workflow_run_id: UUID) -> PlanningWorkflowResult:
        """Resume after the clarification interrupt once blocking items are resolved."""
        run = self._require_planning_run(workflow_run_id)
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(f"Workflow run {workflow_run_id} is not awaiting clarification")
        if run.state.get("review_gate") != "clarification":
            raise WorkflowError(
                f"Workflow run {workflow_run_id} is not paused at clarification gate"
            )

        mission_id = self._mission_id_from_run(run)
        self._clarification.ensure_can_continue(mission_id)
        return self._resume_interrupted_run(
            run,
            session_status=PlanningSessionStatus.PLANNING,
            mission_id=mission_id,
            log_label="clarification",
        )

    def approve_mission(
        self,
        mission_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> ProjectMission:
        """Approve mission understanding (domain action only)."""
        return self._runtime.mission_service.approve_mission(
            mission_id, user_id=user_id, note=note
        )

    def resume_after_mission_approval(
        self,
        workflow_run_id: UUID,
    ) -> PlanningWorkflowResult:
        """Resume after the mission-approval interrupt; mission must already be approved."""
        run = self._require_planning_run(workflow_run_id)
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(f"Workflow run {workflow_run_id} is not awaiting mission approval")
        if run.state.get("review_gate") != "mission_approval":
            raise WorkflowError(
                f"Workflow run {workflow_run_id} is not paused at mission approval gate"
            )

        mission_id = self._mission_id_from_run(run)
        mission = self._runtime.missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        if mission.approval_status != ApprovalStatus.APPROVED:
            raise WorkflowError("任务理解尚未批准，无法继续。请先调用 approve_mission。")

        return self._resume_interrupted_run(
            run,
            session_status=PlanningSessionStatus.PLANNING,
            mission_id=mission_id,
            log_label="mission-approval",
        )

    def approve_mission_and_continue(
        self,
        workflow_run_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> PlanningWorkflowResult:
        """UI facade: approve mission then resume past the mission-approval gate."""
        run = self._require_planning_run(workflow_run_id)
        mission_id = self._mission_id_from_run(run)
        self.approve_mission(mission_id, user_id=user_id, note=note)
        return self.resume_after_mission_approval(workflow_run_id)

    def approve_deliverable_plan(
        self,
        plan_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> DeliverablePlan:
        """Approve deliverable plan (domain action only)."""
        return self._deliverables.approve_deliverable_plan(
            plan_id, user_id=user_id, note=note
        )

    def resume_after_plan_approval(
        self,
        workflow_run_id: UUID,
    ) -> PlanningWorkflowResult:
        """Resume after the plan-approval interrupt; plan must already be approved."""
        run = self._require_planning_run(workflow_run_id)
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(f"Workflow run {workflow_run_id} is not awaiting plan approval")
        if run.state.get("review_gate") != "plan_approval":
            raise WorkflowError(
                f"Workflow run {workflow_run_id} is not paused at plan approval gate"
            )

        plan_data = run.state.get("deliverable_plan")
        if not isinstance(plan_data, dict) or "id" not in plan_data:
            raise WorkflowError(f"Workflow run {workflow_run_id} is missing deliverable_plan")
        plan = self._runtime.missions.get_deliverable_plan(UUID(str(plan_data["id"])))
        if plan is None:
            raise WorkflowError(f"DeliverablePlan {plan_data['id']} not found")
        if plan.approval_status != ApprovalStatus.APPROVED:
            raise WorkflowError(
                "交付成果计划尚未批准，无法继续。请先调用 approve_deliverable_plan。"
            )

        return self._resume_interrupted_run(
            run,
            session_status=PlanningSessionStatus.PLANNING,
            log_label="plan-approval",
        )

    def approve_and_continue(
        self,
        workflow_run_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> PlanningWorkflowResult:
        """UI facade: approve deliverable plan then resume past the plan-approval gate."""
        run = self._require_planning_run(workflow_run_id)
        plan_data = run.state.get("deliverable_plan")
        if not isinstance(plan_data, dict) or "id" not in plan_data:
            raise WorkflowError(f"Workflow run {workflow_run_id} is missing deliverable_plan")
        self.approve_deliverable_plan(
            UUID(str(plan_data["id"])),
            user_id=user_id,
            note=note,
        )
        return self.resume_after_plan_approval(workflow_run_id)

    def continue_after_plan_approval(self, workflow_run_id: UUID) -> PlanningWorkflowResult:
        """Deprecated alias for :meth:`approve_and_continue`."""
        return self.approve_and_continue(workflow_run_id)

    def _resume_interrupted_run(
        self,
        run: WorkflowRun,
        *,
        session_status: PlanningSessionStatus,
        mission_id: UUID | None = None,
        log_label: str,
    ) -> PlanningWorkflowResult:
        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)
        self._set_session_status(run, session_status, mission_id=mission_id)

        try:
            final_state = self._graph.invoke(None, thread_id=str(run.id), resume=True)
        except Exception as exc:
            logger.exception("Planning continue-after-%s failed: %s", log_label, exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            self._mark_session_failed_for_run(run.id)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after continuation")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def resume(self, workflow_run_id: UUID) -> PlanningWorkflowResult:
        """Continue a planning run from its current gate or checkpoint."""
        run = self._require_planning_run(workflow_run_id)
        if run.status == WorkflowStatus.COMPLETED:
            return self._to_result(run, run.state)
        if run.status == WorkflowStatus.AWAITING_REVIEW:
            gate = run.state.get("review_gate")
            if gate == "clarification":
                return self.continue_after_clarification(workflow_run_id)
            if gate == "mission_approval":
                return self.resume_after_mission_approval(workflow_run_id)
            if gate == "plan_approval":
                return self.resume_after_plan_approval(workflow_run_id)
            raise WorkflowError(f"Unknown planning review gate: {gate}")

        restored = restore_planning_artifacts(run.state)
        user_task = restored.get("user_task_description") or run.state.get("user_task_description")
        if not user_task:
            raise WorkflowError(f"Workflow run {workflow_run_id} is missing resumable state")

        planning_session = self._require_session_for_run(run)
        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        initial_state = initial_planning_state(
            project_id=str(run.project_id),
            workflow_run_id=str(run.id),
            planning_session_id=str(planning_session.id),
            user_task_description=str(user_task),
            presentation_id=str(run.presentation_id) if run.presentation_id else None,
            require_clarification=bool(run.state.get("require_clarification", True)),
            require_mission_approval=bool(run.state.get("require_mission_approval", True)),
            require_plan_approval=bool(run.state.get("require_plan_approval", True)),
        )
        initial_state = cast(
            PlanningWorkflowState,
            {**initial_state, **restored, "errors": [], "warnings": []},
        )

        try:
            final_state = self._graph.invoke(initial_state, thread_id=str(run.id))
        except Exception as exc:
            logger.exception("Planning workflow resume failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            self._mark_session_failed(planning_session.id)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after resume")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def get_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return self._workflow_runs.get_by_id(workflow_run_id)

    def get_session(self, planning_session_id: UUID) -> PlanningSession | None:
        return self._planning_sessions.get_by_id(planning_session_id)

    def get_session_for_run(self, workflow_run_id: UUID) -> PlanningSession | None:
        return self._planning_sessions.get_by_workflow_run_id(workflow_run_id)

    def attach_presentation(
        self,
        planning_session_id: UUID,
        presentation_id: UUID,
    ) -> PlanningSession:
        """Record the Presentation created after launching a PRESENTATION deliverable."""
        session = self._planning_sessions.get_by_id(planning_session_id)
        if session is None:
            raise WorkflowError(f"Planning session {planning_session_id} not found")
        session.presentation_id = presentation_id
        session.status = PlanningSessionStatus.COMPLETED
        session.touch()
        return self._planning_sessions.update(session)

    def get_presentation_bridge(
        self,
        workflow_run_id: UUID,
        *,
        user_overrides: PresentationOverrides | None = None,
    ) -> MissionPresentationBridge:
        """Return PresentationRequest mapped from a completed planning run."""
        run = self._require_planning_run(workflow_run_id)
        draft = run.state.get("presentation_request_draft")
        if isinstance(draft, dict) and draft.get("mission_id") and user_overrides is None:
            return bridge_from_draft(draft)

        mission_id = self._mission_id_from_run(run)
        missions = MissionRepository(self._session)
        mission = missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        plan = None
        plan_data = run.state.get("deliverable_plan")
        if isinstance(plan_data, dict) and plan_data.get("id"):
            plan = missions.get_deliverable_plan(UUID(str(plan_data["id"])))
        workstreams = missions.list_workstreams(mission_id)
        return build_presentation_bridge(
            mission,
            plan=plan,
            workstreams=workstreams,
            user_overrides=user_overrides,
        )

    def build_presentation_request_for_mission(
        self,
        mission_id: UUID,
        *,
        deliverable_id: str | None = None,
        user_overrides: PresentationOverrides | None = None,
    ) -> MissionPresentationBridge:
        """Map an approved mission (+ plan) to PresentationRequest without a workflow run."""
        missions = MissionRepository(self._session)
        mission = missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        plan = missions.get_approved_deliverable_plan(mission_id)
        if plan is None:
            plans = missions.list_deliverable_plans(mission_id)
            plan = plans[0] if plans else None
        workstreams = missions.list_workstreams(mission_id)
        return build_presentation_bridge(
            mission,
            plan=plan,
            deliverable_id=deliverable_id,
            workstreams=workstreams,
            user_overrides=user_overrides,
        )

    def _require_planning_run(self, workflow_run_id: UUID) -> WorkflowRun:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.state.get("workflow_kind") != "planning":
            raise WorkflowError(f"Workflow run {workflow_run_id} is not a planning workflow")
        return run

    def _require_session_for_run(self, run: WorkflowRun) -> PlanningSession:
        session = self._planning_sessions.get_by_workflow_run_id(run.id)
        if session is not None:
            return session
        raw = run.state.get("planning_session_id")
        if raw:
            session = self._planning_sessions.get_by_id(UUID(str(raw)))
            if session is not None:
                return session
        raise WorkflowError(f"Planning session for workflow run {run.id} not found")

    @staticmethod
    def _mission_id_from_run(run: WorkflowRun) -> UUID:
        raw = run.state.get("mission_id")
        if raw:
            return UUID(str(raw))
        mission = run.state.get("mission")
        if isinstance(mission, dict) and mission.get("id"):
            return UUID(str(mission["id"]))
        raise WorkflowError(f"Workflow run {run.id} is missing mission_id")

    def _to_result(
        self,
        workflow_run: WorkflowRun,
        final_state: PlanningWorkflowState | dict[str, Any],
    ) -> PlanningWorkflowResult:
        restored = restore_planning_artifacts(workflow_run.state)
        if isinstance(final_state, dict):
            restored.update(restore_planning_artifacts(cast(dict[str, Any], final_state)))

        presentation = None
        if workflow_run.presentation_id is not None:
            presentation = self._presentations.get_presentation(workflow_run.presentation_id)

        draft = restored.get("presentation_request_draft")
        if draft is None and isinstance(final_state, dict):
            draft = final_state.get("presentation_request_draft")

        warnings = list(restored.get("warnings") or [])
        if isinstance(final_state, dict):
            warnings.extend(list(final_state.get("warnings") or []))

        presentation_request = None
        if isinstance(draft, dict) and draft.get("mission_id"):
            try:
                presentation_request = bridge_from_draft(draft).request
            except WorkflowError:
                presentation_request = None

        mission = restored.get("mission")
        mission_id = mission.id if mission is not None else None
        if mission_id is None and restored.get("mission_id"):
            mission_id = UUID(str(restored["mission_id"]))

        planning_session = self._sync_session_from_run(
            workflow_run,
            mission_id=mission_id,
        )

        return PlanningWorkflowResult(
            planning_session=planning_session,
            workflow_run=workflow_run,
            presentation=presentation,
            mission=mission,
            knowledge_gaps=list(restored.get("knowledge_gaps", [])),
            assumptions=list(restored.get("assumptions", [])),
            clarifying_questions=list(restored.get("clarifying_questions", [])),
            design_questions=list(restored.get("design_questions", [])),
            workstreams=list(restored.get("workstreams", [])),
            deliverable_plan=restored.get("deliverable_plan"),
            presentation_request=presentation_request,
            presentation_request_draft=draft if isinstance(draft, dict) else None,
            errors=list(workflow_run.errors),
            warnings=warnings,
        )

    def _sync_session_from_run(
        self,
        workflow_run: WorkflowRun,
        *,
        mission_id: UUID | None,
    ) -> PlanningSession:
        session = self._require_session_for_run(workflow_run)
        status = self._derive_session_status(workflow_run, session)
        changed = False
        if session.workflow_run_id != workflow_run.id:
            session.workflow_run_id = workflow_run.id
            changed = True
        if mission_id is not None and session.current_mission_id != mission_id:
            session.current_mission_id = mission_id
            changed = True
        if session.status != status:
            session.status = status
            changed = True
        if changed:
            session.touch()
            return self._planning_sessions.update(session)
        return session

    @staticmethod
    def _derive_session_status(
        workflow_run: WorkflowRun,
        session: PlanningSession,
    ) -> PlanningSessionStatus:
        if session.presentation_id is not None:
            return PlanningSessionStatus.COMPLETED
        if workflow_run.status == WorkflowStatus.FAILED:
            return PlanningSessionStatus.FAILED
        if workflow_run.status == WorkflowStatus.COMPLETED:
            return PlanningSessionStatus.READY
        if workflow_run.status == WorkflowStatus.AWAITING_REVIEW:
            gate = workflow_run.state.get("review_gate")
            if gate == "clarification":
                return PlanningSessionStatus.CLARIFYING
            if gate == "mission_approval":
                return PlanningSessionStatus.AWAITING_MISSION_APPROVAL
            if gate == "plan_approval":
                return PlanningSessionStatus.AWAITING_APPROVAL
        if workflow_run.status == WorkflowStatus.RUNNING:
            return PlanningSessionStatus.PLANNING
        return session.status

    def _set_session_status(
        self,
        run: WorkflowRun,
        status: PlanningSessionStatus,
        *,
        mission_id: UUID | None = None,
    ) -> None:
        session = self._planning_sessions.get_by_workflow_run_id(run.id)
        if session is None:
            return
        session.status = status
        if mission_id is not None:
            session.current_mission_id = mission_id
        session.touch()
        self._planning_sessions.update(session)

    def _mark_session_failed(self, planning_session_id: UUID) -> None:
        session = self._planning_sessions.get_by_id(planning_session_id)
        if session is None:
            return
        session.status = PlanningSessionStatus.FAILED
        session.touch()
        self._planning_sessions.update(session)

    def _mark_session_failed_for_run(self, workflow_run_id: UUID) -> None:
        session = self._planning_sessions.get_by_workflow_run_id(workflow_run_id)
        if session is None:
            return
        self._mark_session_failed(session.id)

    @staticmethod
    def _ensure_success(result: PlanningWorkflowResult) -> PlanningWorkflowResult:
        if result.errors and not result.awaiting_review:
            message = "; ".join(result.errors)
            raise WorkflowError(f"Planning workflow failed: {message}")
        return result
