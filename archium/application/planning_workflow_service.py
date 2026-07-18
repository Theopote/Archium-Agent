"""LangGraph-based project mission planning workflow service."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.mission_clarification_service import MissionClarificationService
from archium.config.settings import Settings, get_settings
from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import WorkflowStatus, WorkflowStep
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.presentation import Presentation
from archium.domain.project_mission import ProjectMission
from archium.domain.workflow import WorkflowRun
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
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

    workflow_run: WorkflowRun
    presentation: Presentation
    mission: ProjectMission | None = None
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    design_questions: list[DesignQuestion] = field(default_factory=list)
    workstreams: list[Workstream] = field(default_factory=list)
    deliverable_plan: DeliverablePlan | None = None
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
        require_plan_approval: bool = True,
    ) -> PlanningWorkflowResult:
        if not user_task_description.strip():
            raise WorkflowError("任务描述不能为空")

        presentation = self._presentations.create_presentation(
            Presentation(
                project_id=project_id,
                title="规划草稿（待任务理解完成）",
                description="Planning workflow carrier presentation",
            )
        )
        workflow_run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                presentation_id=presentation.id,
                status=WorkflowStatus.RUNNING,
                state={
                    "workflow_kind": "planning",
                    "current_step": WorkflowStep.INIT.value,
                    "user_task_description": user_task_description,
                    "require_clarification": require_clarification,
                    "require_plan_approval": require_plan_approval,
                },
            )
        )

        initial_state = initial_planning_state(
            project_id=str(project_id),
            presentation_id=str(presentation.id),
            workflow_run_id=str(workflow_run.id),
            user_task_description=user_task_description,
            require_clarification=require_clarification,
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

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        try:
            final_state = self._graph.invoke(None, thread_id=str(run.id), resume=True)
        except Exception as exc:
            logger.exception("Planning continue-after-clarification failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after continuation")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def continue_after_plan_approval(self, workflow_run_id: UUID) -> PlanningWorkflowResult:
        """Resume after the deliverable-plan approval interrupt."""
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
        plan = self._deliverables.approve_plan(UUID(str(plan_data["id"])))
        if plan.approval_status.value != "approved":
            raise WorkflowError("交付成果计划尚未批准，无法继续")

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        try:
            final_state = self._graph.invoke(None, thread_id=str(run.id), resume=True)
        except Exception as exc:
            logger.exception("Planning continue-after-plan-approval failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
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
            if gate == "plan_approval":
                return self.continue_after_plan_approval(workflow_run_id)
            raise WorkflowError(f"Unknown planning review gate: {gate}")

        restored = restore_planning_artifacts(run.state)
        user_task = restored.get("user_task_description") or run.state.get("user_task_description")
        if not user_task:
            raise WorkflowError(f"Workflow run {workflow_run_id} is missing resumable state")

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        initial_state = initial_planning_state(
            project_id=str(run.project_id),
            presentation_id=str(run.presentation_id),
            workflow_run_id=str(run.id),
            user_task_description=str(user_task),
            require_clarification=bool(run.state.get("require_clarification", True)),
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
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after resume")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def get_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return self._workflow_runs.get_by_id(workflow_run_id)

    def _require_planning_run(self, workflow_run_id: UUID) -> WorkflowRun:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.state.get("workflow_kind") != "planning":
            raise WorkflowError(f"Workflow run {workflow_run_id} is not a planning workflow")
        return run

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

        presentation = self._presentations.get_presentation(workflow_run.presentation_id)
        if presentation is None:
            raise WorkflowError(
                f"Workflow run {workflow_run.id} is missing presentation {workflow_run.presentation_id}"
            )

        draft = restored.get("presentation_request_draft")
        if draft is None and isinstance(final_state, dict):
            draft = final_state.get("presentation_request_draft")

        warnings = list(restored.get("warnings") or [])
        if isinstance(final_state, dict):
            warnings.extend(list(final_state.get("warnings") or []))

        return PlanningWorkflowResult(
            workflow_run=workflow_run,
            presentation=presentation,
            mission=restored.get("mission"),
            knowledge_gaps=list(restored.get("knowledge_gaps", [])),
            assumptions=list(restored.get("assumptions", [])),
            clarifying_questions=list(restored.get("clarifying_questions", [])),
            design_questions=list(restored.get("design_questions", [])),
            workstreams=list(restored.get("workstreams", [])),
            deliverable_plan=restored.get("deliverable_plan"),
            presentation_request_draft=draft if isinstance(draft, dict) else None,
            errors=list(workflow_run.errors),
            warnings=warnings,
        )

    @staticmethod
    def _ensure_success(result: PlanningWorkflowResult) -> PlanningWorkflowResult:
        if result.errors and not result.awaiting_review:
            message = "; ".join(result.errors)
            raise WorkflowError(f"Planning workflow failed: {message}")
        return result
