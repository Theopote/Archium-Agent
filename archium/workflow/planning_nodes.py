"""LangGraph nodes for project mission planning workflow."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from langgraph.types import interrupt
from sqlalchemy.orm import Session

from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.mission_validation_service import MissionValidationService
from archium.application.project_mission_service import ProjectMissionService
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus, QuestionStatus, WorkflowStatus, WorkflowStep
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    FactRepository,
    PresentationRepository,
    ProjectRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger
from archium.workflow.planning_serialization import (
    planning_mission_id,
    snapshot_planning_state,
)
from archium.workflow.planning_state import PlanningWorkflowState


class PlanningWorkflowRuntime:
    """Dependencies for planning workflow nodes."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings,
    ) -> None:
        self.session = session
        self.llm = llm
        self.settings = settings
        self.projects = ProjectRepository(session)
        self.presentations = PresentationRepository(session)
        self.workflow_runs = WorkflowRunRepository(session)
        self.missions = MissionRepository(session)
        self.facts = FactRepository(session)
        self.mission_service = ProjectMissionService(session, llm, settings=settings)
        self.mission_validator = MissionValidationService()
        self.clarification_service = MissionClarificationService(
            session, llm, settings=settings, mission_service=self.mission_service
        )
        self.workstream_service = WorkstreamPlanningService(
            session, llm, settings=settings, clarification_service=self.clarification_service
        )
        self.deliverable_service = DeliverablePlanningService(
            session, llm, settings=settings, clarification_service=self.clarification_service
        )


class PlanningWorkflowNodes:
    """Node implementations for the planning graph."""

    def __init__(self, runtime: PlanningWorkflowRuntime) -> None:
        self._runtime = runtime

    def load_project_context(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        project = self._runtime.projects.get_by_id(UUID(state["project_id"]))
        if project is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": [f"项目 {state['project_id']} 不存在"],
            }
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_LOAD_CONTEXT.value,
            "project_name": project.name,
            "project_context": project.description or "",
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def analyze_task(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        try:
            result = self._runtime.mission_service.generate_mission(
                UUID(state["project_id"]),
                state["user_task_description"],
            )
        except WorkflowError as exc:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_ANALYZE_TASK.value,
            "mission_id": str(result.mission.id),
            "mission": result.mission,
            "knowledge_gaps": result.knowledge_gaps,
            "assumptions": result.assumptions,
            "clarifying_questions": result.clarifying_questions,
            "design_questions": result.design_questions,
            "warnings": list(result.warnings),
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def validate_mission(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        mission = state.get("mission")
        if mission is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["任务理解缺失，无法校验"],
            }

        facts = self._runtime.facts.list_by_project(UUID(state["project_id"]))
        report = self._runtime.mission_validator.validate(
            mission,
            knowledge_gaps=list(state.get("knowledge_gaps") or []),
            clarifying_questions=list(state.get("clarifying_questions") or []),
            facts=facts,
        )
        if not report.ok:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": list(report.errors),
                "warnings": list(report.warnings) + list(report.suggestions),
                "mission_validation": report.to_dict(),
            }

        notice = list(report.warnings)
        if report.suggestions:
            notice.extend(report.suggestions)
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_VALIDATE_MISSION.value,
            "warnings": notice,
            "mission_validation": report.to_dict(),
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def await_user_clarification(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        logger = get_logger(__name__, operation="planning_workflow")
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }

        # Resume path: clarification already handled and readiness allows continue.
        readiness = self._runtime.clarification_service.get_readiness(mission_id)
        run = self._runtime.workflow_runs.get_by_id(UUID(state["workflow_run_id"]))
        if (
            run is not None
            and run.state.get("review_gate") == "clarification"
            and readiness.can_continue
        ):
            bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
            resume_state: PlanningWorkflowState = {
                "current_step": WorkflowStep.PLANNING_AWAIT_CLARIFICATION.value,
                "review_gate": "clarification",
                "mission": bundle.mission,
                "knowledge_gaps": bundle.knowledge_gaps,
                "assumptions": bundle.assumptions,
                "clarifying_questions": bundle.clarifying_questions,
                "design_questions": bundle.design_questions,
            }
            self._persist({**state, **resume_state}, status=WorkflowStatus.RUNNING)
            logger.info("Planning workflow resumed after clarification")
            return resume_state

        if not state.get("require_clarification", True):
            return {"current_step": WorkflowStep.PLANNING_AWAIT_CLARIFICATION.value}

        # Always pause once so the user can confirm/answer/assume before planning.
        pause: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_AWAIT_CLARIFICATION.value,
            "review_gate": "clarification",
        }
        merged = cast(PlanningWorkflowState, {**state, **pause})
        self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Planning workflow paused for clarification on mission %s", mission_id)
        interrupt({"gate": "clarification", "step": WorkflowStep.PLANNING_AWAIT_CLARIFICATION.value})

        bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
        resume_state = {
            **pause,
            "mission": bundle.mission,
            "knowledge_gaps": bundle.knowledge_gaps,
            "assumptions": bundle.assumptions,
            "clarifying_questions": bundle.clarifying_questions,
            "design_questions": bundle.design_questions,
        }
        self._persist({**merged, **resume_state}, status=WorkflowStatus.RUNNING)
        return resume_state

    def revise_mission(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }
        questions = self._runtime.missions.list_clarifying_questions(mission_id)
        answered = [
            q
            for q in questions
            if q.status
            in {
                QuestionStatus.ANSWERED,
                QuestionStatus.ASSUMED,
                QuestionStatus.DEFERRED,
                QuestionStatus.NOT_APPLICABLE,
            }
        ]
        if not answered:
            # Nothing to revise; keep current mission.
            return {"current_step": WorkflowStep.PLANNING_REVISE_MISSION.value}

        try:
            result = self._runtime.clarification_service.revise_mission_after_clarification(
                mission_id,
                require_ready=True,
            )
        except WorkflowError as exc:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_REVISE_MISSION.value,
            "mission": result.mission,
            "knowledge_gaps": result.knowledge_gaps,
            "assumptions": result.assumptions,
            "clarifying_questions": result.clarifying_questions,
            "design_questions": result.design_questions,
            "warnings": list(result.warnings),
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def await_mission_approval(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        """Explicit gate: mission must be approved before workstream planning."""
        logger = get_logger(__name__, operation="planning_workflow")
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }

        mission = self._runtime.missions.get_mission(mission_id)
        if mission is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": [f"Mission {mission_id} 不存在"],
            }

        run = self._runtime.workflow_runs.get_by_id(UUID(state["workflow_run_id"]))
        if (
            run is not None
            and run.state.get("review_gate") == "mission_approval"
            and mission.approval_status == ApprovalStatus.APPROVED
        ):
            bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
            resume_state: PlanningWorkflowState = {
                "current_step": WorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
                "review_gate": "mission_approval",
                "mission": bundle.mission,
                "knowledge_gaps": bundle.knowledge_gaps,
                "assumptions": bundle.assumptions,
                "clarifying_questions": bundle.clarifying_questions,
                "design_questions": bundle.design_questions,
            }
            self._persist({**state, **resume_state}, status=WorkflowStatus.RUNNING)
            logger.info("Planning workflow resumed after mission approval")
            return resume_state

        if not state.get("require_mission_approval", True):
            if mission.approval_status != ApprovalStatus.APPROVED:
                mission = self._runtime.mission_service.approve_mission(mission_id)
            return {
                "current_step": WorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
                "mission": mission,
            }

        pause: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
            "review_gate": "mission_approval",
            "mission": mission,
        }
        merged = cast(PlanningWorkflowState, {**state, **pause})
        self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Planning workflow paused for mission approval")
        interrupt(
            {
                "gate": "mission_approval",
                "step": WorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
            }
        )

        bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
        resume_state = {
            **pause,
            "mission": bundle.mission,
            "knowledge_gaps": bundle.knowledge_gaps,
            "assumptions": bundle.assumptions,
            "clarifying_questions": bundle.clarifying_questions,
            "design_questions": bundle.design_questions,
        }
        self._persist({**merged, **resume_state}, status=WorkflowStatus.RUNNING)
        return resume_state

    def plan_workstreams(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }
        try:
            result = self._runtime.workstream_service.plan_workstreams(
                mission_id,
                require_ready=True,
            )
        except WorkflowError as exc:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_WORKSTREAMS.value,
            "mission": result.mission,
            "workstreams": result.workstreams,
            "warnings": list(result.warnings),
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def plan_deliverables(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }
        try:
            result = self._runtime.deliverable_service.plan_deliverables(
                mission_id,
                require_ready=True,
            )
        except WorkflowError as exc:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_DELIVERABLES.value,
            "mission": result.mission,
            "deliverable_plan": result.plan,
            "workstreams": result.workstreams,
            "warnings": list(result.warnings),
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def await_plan_approval(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        logger = get_logger(__name__, operation="planning_workflow")
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }

        plan = state.get("deliverable_plan")
        if plan is not None:
            refreshed = self._runtime.missions.get_deliverable_plan(plan.id)
            if refreshed is not None:
                plan = refreshed

        run = self._runtime.workflow_runs.get_by_id(UUID(state["workflow_run_id"]))
        if (
            run is not None
            and run.state.get("review_gate") == "plan_approval"
            and plan is not None
            and plan.approval_status == ApprovalStatus.APPROVED
        ):
            mission = self._runtime.missions.get_mission(mission_id)
            resume_state: PlanningWorkflowState = {
                "current_step": WorkflowStep.PLANNING_AWAIT_APPROVAL.value,
                "review_gate": "plan_approval",
                "deliverable_plan": plan,
                "mission": mission,
                "workstreams": self._runtime.missions.list_workstreams(mission_id),
            }
            self._persist({**state, **resume_state}, status=WorkflowStatus.RUNNING)
            logger.info("Planning workflow resumed after plan approval")
            return resume_state

        if not state.get("require_plan_approval", True):
            if plan is not None and plan.approval_status != ApprovalStatus.APPROVED:
                plan.approve()
                plan = self._runtime.missions.save_deliverable_plan(plan)
            return {
                "current_step": WorkflowStep.PLANNING_AWAIT_APPROVAL.value,
                "deliverable_plan": plan,
            }

        pause: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_AWAIT_APPROVAL.value,
            "review_gate": "plan_approval",
            "deliverable_plan": plan,
        }
        merged = cast(PlanningWorkflowState, {**state, **pause})
        self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Planning workflow paused for plan approval")
        interrupt({"gate": "plan_approval", "step": WorkflowStep.PLANNING_AWAIT_APPROVAL.value})

        plan = self._runtime.missions.get_deliverable_plan(plan.id) if plan is not None else None
        mission = self._runtime.missions.get_mission(mission_id)
        resume_state = {
            **pause,
            "deliverable_plan": plan,
            "mission": mission,
            "workstreams": self._runtime.missions.list_workstreams(mission_id),
        }
        self._persist({**merged, **resume_state}, status=WorkflowStatus.RUNNING)
        return resume_state

    def prepare_presentation_request(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        from archium.application.deliverable_execution import DeliverableExecutionRouter
        from archium.application.mission_to_presentation_request import MissionPresentationBridge
        from archium.domain.enums import DeliverableType

        mission = state.get("mission")
        plan = state.get("deliverable_plan")
        if mission is None:
            return {
                "current_step": WorkflowStep.FAILED.value,
                "errors": ["缺少任务理解，无法准备成果执行计划"],
            }

        workstreams = list(state.get("workstreams") or [])
        router = DeliverableExecutionRouter()
        execution_plans = (
            router.route_plan(mission, plan, workstreams=workstreams)
            if plan is not None
            else []
        )
        warnings: list[str] = []
        draft = None
        presentation_plans = [
            item
            for item in execution_plans
            if item.supported and item.deliverable_type == DeliverableType.PRESENTATION
        ]
        if presentation_plans:
            chosen = presentation_plans[0]
            assert chosen.presentation_request is not None
            bridge = MissionPresentationBridge(
                request=chosen.presentation_request,
                mission_id=mission.id,
                deliverable_id=chosen.deliverable_id,
                warnings=list(chosen.warnings),
            )
            draft = bridge.to_draft()
            warnings.extend(bridge.warnings)
        else:
            for item in execution_plans:
                if not item.supported:
                    warnings.append(f"「{item.deliverable_title}」：{item.message}")
            if not execution_plans:
                warnings.append("未选择任何成果；未生成 PresentationRequest。")

        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_PREPARE_PRESENTATION.value,
            "presentation_request_draft": draft,
            "artifact_execution_plans": [item.to_dict() for item in execution_plans],
            "warnings": warnings,
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def finalize(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        errors = list(state.get("errors", []))
        status = WorkflowStatus.FAILED if errors else WorkflowStatus.COMPLETED
        next_state: PlanningWorkflowState = {
            "current_step": WorkflowStep.PLANNING_FINALIZE.value
            if not errors
            else WorkflowStep.FAILED.value,
        }
        self._persist({**state, **next_state}, status=status)
        return next_state

    def _persist(
        self,
        state: PlanningWorkflowState,
        *,
        status: WorkflowStatus | None = None,
    ) -> None:
        run_id = state.get("workflow_run_id")
        if run_id is None:
            return
        run = self._runtime.workflow_runs.get_by_id(UUID(run_id))
        if run is None:
            return
        run.state = snapshot_planning_state(state)
        run.errors = list(state.get("errors", []))
        if status is not None:
            run.status = status
        run.touch()
        self._runtime.workflow_runs.update(run)
