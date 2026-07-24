"""LangGraph nodes for project mission planning workflow."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from langgraph.types import interrupt
from sqlalchemy.orm import Session

from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.mission_validation_service import MissionValidationService
from archium.application.project_mission_service import (
    ProjectMissionService,
    is_mission_approval_current,
)
from archium.application.workflow_checkpoint import commit_workflow_checkpoint, finalize_run_state
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.config.settings import Settings
from archium.domain.enums import (
    ApprovalStatus,
    PlanningWorkflowStep,
    PresentationWorkflowStep,
    ProjectOriginMode,
    QuestionStatus,
    WorkflowStatus,
)
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
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": [f"项目 {state['project_id']} 不存在"],
            }
        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_LOAD_CONTEXT.value,
            "project_name": project.name,
            "project_context": project.description or "",
            "origin_mode": project.origin_mode.value,
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def analyze_task(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        origin_mode = ProjectOriginMode(
            state.get("origin_mode", ProjectOriginMode.EXISTING_PROJECT.value)
        )
        try:
            result = self._runtime.mission_service.generate_mission(
                UUID(state["project_id"]),
                state["user_task_description"],
                origin_mode=origin_mode,
            )
        except WorkflowError as exc:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_ANALYZE_TASK.value,
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

    def run_autonomous_research(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        """Concept exploration: web search + synthesis into PUBLIC_RESEARCH knowledge."""
        logger = get_logger(__name__, operation="planning_workflow")
        mission_id = planning_mission_id(state)
        warnings = list(state.get("warnings") or [])
        step = PlanningWorkflowStep.PLANNING_AUTONOMOUS_RESEARCH.value

        if mission_id is None:
            next_state: PlanningWorkflowState = {
                "current_step": step,
                "warnings": warnings,
            }
            self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
            return next_state

        origin_mode = ProjectOriginMode(
            state.get("origin_mode", ProjectOriginMode.EXISTING_PROJECT.value)
        )
        from archium.application.autonomous_research_service import AutonomousResearchService
        from archium.application.web_research_settings_service import (
            WebResearchSettingsService,
            apply_web_research_preferences,
        )
        from archium.infrastructure.research.web_search.service import WebResearchSearchService

        prefs = WebResearchSettingsService(self._runtime.session).get_preferences(
            base_settings=self._runtime.settings,
        )
        if origin_mode != ProjectOriginMode.CONCEPT_EXPLORATION or not prefs.auto_on_concept_planning:
            next_state = {"current_step": step, "warnings": warnings}
            self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
            return next_state

        if not prefs.enabled:
            warnings.append("联网研究已禁用，跳过概念探索自动研究")
            next_state = {"current_step": step, "warnings": warnings}
            self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
            return next_state

        effective_settings = apply_web_research_preferences(self._runtime.settings, prefs)
        try:
            result = AutonomousResearchService(
                self._runtime.session,
                self._runtime.llm,
                settings=effective_settings,
                web_research=WebResearchSearchService(effective_settings),
            ).research_for_mission(mission_id)
            warnings.extend(result.warnings)
            if result.items:
                provider_note = result.search_provider or "无联网"
                warnings.append(
                    "概念探索自动研究：已写入 "
                    f"{len(result.items)} 条公开资料（检索 {result.search_hit_count} 条，{provider_note}）"
                )
                logger.info(
                    "Concept planning auto research wrote %s items for mission %s",
                    len(result.items),
                    mission_id,
                )
            next_state = {
                "current_step": step,
                "warnings": warnings,
                "autonomous_research_item_count": len(result.items),
            }
        except WorkflowError as exc:
            warnings.append(f"概念探索自动研究跳过：{exc}")
            next_state = {"current_step": step, "warnings": warnings}
        except Exception as exc:
            logger.warning("Concept planning auto research failed: %s", exc)
            warnings.append(f"概念探索自动研究失败：{exc}")
            next_state = {"current_step": step, "warnings": warnings}

        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def validate_mission(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        """Initial mission consistency check before clarification."""
        return self._validate_mission_state(
            state,
            current_step=PlanningWorkflowStep.PLANNING_VALIDATE_MISSION,
            refresh_from_db=False,
            phase="initial",
        )

    def validate_revised_mission(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        """Re-validate after clarification revision — does not loop back to clarification."""
        return self._validate_mission_state(
            state,
            current_step=PlanningWorkflowStep.PLANNING_VALIDATE_REVISED_MISSION,
            refresh_from_db=True,
            phase="revised",
        )

    def _validate_mission_state(
        self,
        state: PlanningWorkflowState,
        *,
        current_step: PlanningWorkflowStep | PresentationWorkflowStep,
        refresh_from_db: bool,
        phase: str,
        persist: bool = True,
    ) -> PlanningWorkflowState:
        mission = state.get("mission")
        knowledge_gaps = list(state.get("knowledge_gaps") or [])
        clarifying_questions = list(state.get("clarifying_questions") or [])
        design_questions = list(state.get("design_questions") or [])
        assumptions = list(state.get("assumptions") or [])

        if refresh_from_db:
            mission_id = planning_mission_id(state)
            if mission_id is not None:
                bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
                mission = bundle.mission
                knowledge_gaps = bundle.knowledge_gaps
                clarifying_questions = bundle.clarifying_questions
                design_questions = bundle.design_questions
                assumptions = bundle.assumptions

        if mission is None:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["任务理解缺失，无法校验"],
                "needs_mission_correction": False,
                "mission_validation_phase": phase,
            }

        facts = self._runtime.facts.list_by_project(UUID(state["project_id"]))
        report = self._runtime.mission_validator.validate(
            mission,
            knowledge_gaps=knowledge_gaps,
            clarifying_questions=clarifying_questions,
            facts=facts,
        )

        artifacts: PlanningWorkflowState = {
            "mission_validation": report.to_dict(),
            "mission": mission,
            "knowledge_gaps": knowledge_gaps,
            "clarifying_questions": clarifying_questions,
            "design_questions": design_questions,
            "assumptions": assumptions,
            "mission_validation_phase": phase,
        }

        if report.is_fatal:
            return {
                **artifacts,
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": list(report.fatal_errors),
                "warnings": list(report.warnings)
                + list(report.suggestions)
                + list(report.recoverable_errors),
                "needs_mission_correction": False,
            }

        notice = list(report.warnings)
        if report.suggestions:
            notice.extend(report.suggestions)

        if report.needs_correction:
            notice = list(report.recoverable_errors) + notice
            next_state: PlanningWorkflowState = {
                **artifacts,
                "current_step": current_step.value,
                "warnings": notice,
                "needs_mission_correction": True,
            }
            if persist:
                self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
            return next_state

        next_state = {
            **artifacts,
            "current_step": current_step.value,
            "warnings": notice,
            "needs_mission_correction": False,
        }
        if persist:
            self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    def await_mission_correction(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        """Pause for user to fix recoverable mission validation issues, then revalidate."""
        logger = get_logger(__name__, operation="planning_workflow")
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
                "needs_mission_correction": False,
            }

        phase = str(state.get("mission_validation_phase") or "initial")
        working = cast(PlanningWorkflowState, dict(state))

        while True:
            pause: PlanningWorkflowState = {
                "current_step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_CORRECTION.value,
                "review_gate": "mission_correction",
                "needs_mission_correction": True,
                "mission_validation_phase": phase,
                "mission_validation": working.get("mission_validation"),
                "warnings": list(working.get("warnings") or []),
                "mission": working.get("mission"),
                "knowledge_gaps": list(working.get("knowledge_gaps") or []),
                "clarifying_questions": list(working.get("clarifying_questions") or []),
                "design_questions": list(working.get("design_questions") or []),
                "assumptions": list(working.get("assumptions") or []),
            }
            merged = cast(PlanningWorkflowState, {**working, **pause})
            self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
            logger.info(
                "Planning workflow paused for mission correction on mission %s",
                mission_id,
            )
            interrupt(
                {
                    "gate": "mission_correction",
                    "step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_CORRECTION.value,
                }
            )

            validated = self._validate_mission_state(
                merged,
                current_step=PlanningWorkflowStep.PLANNING_AWAIT_MISSION_CORRECTION,
                refresh_from_db=True,
                phase=phase,
                persist=False,
            )
            if validated.get("errors"):
                self._persist({**merged, **validated}, status=WorkflowStatus.RUNNING)
                return validated

            if not validated.get("needs_mission_correction"):
                next_state: PlanningWorkflowState = {
                    **validated,
                    "review_gate": None,
                    "current_step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_CORRECTION.value,
                    "needs_mission_correction": False,
                }
                self._persist({**merged, **next_state}, status=WorkflowStatus.RUNNING)
                logger.info("Planning mission correction resolved")
                return next_state

            # Still recoverable — refresh working state and pause again.
            working = cast(PlanningWorkflowState, {**merged, **validated})
            logger.info("Planning mission correction still has recoverable errors")

    def await_user_clarification(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        logger = get_logger(__name__, operation="planning_workflow")
        mission_id = planning_mission_id(state)
        if mission_id is None:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }

        origin_mode = ProjectOriginMode(
            state.get("origin_mode", ProjectOriginMode.EXISTING_PROJECT.value)
        )
        if origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION:
            self._runtime.clarification_service.auto_assume_concept_defaults(mission_id)

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
                "current_step": PlanningWorkflowStep.PLANNING_AWAIT_CLARIFICATION.value,
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
            return {"current_step": PlanningWorkflowStep.PLANNING_AWAIT_CLARIFICATION.value}

        # Always pause once so the user can confirm/answer/assume before planning.
        pause: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_AWAIT_CLARIFICATION.value,
            "review_gate": "clarification",
        }
        merged = cast(PlanningWorkflowState, {**state, **pause})
        self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Planning workflow paused for clarification on mission %s", mission_id)
        interrupt({"gate": "clarification", "step": PlanningWorkflowStep.PLANNING_AWAIT_CLARIFICATION.value})

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
                "current_step": PresentationWorkflowStep.FAILED.value,
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
            return {"current_step": PlanningWorkflowStep.PLANNING_REVISE_MISSION.value}

        try:
            result = self._runtime.clarification_service.revise_mission_after_clarification(
                mission_id,
                require_ready=True,
            )
        except WorkflowError as exc:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_REVISE_MISSION.value,
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
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }

        mission = self._runtime.missions.get_mission(mission_id)
        if mission is None:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": [f"Mission {mission_id} 不存在"],
            }

        run = self._runtime.workflow_runs.get_by_id(UUID(state["workflow_run_id"]))
        if (
            run is not None
            and run.state.get("review_gate") == "mission_approval"
            and is_mission_approval_current(mission)
        ):
            bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
            resume_state: PlanningWorkflowState = {
                "current_step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
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
            if not is_mission_approval_current(mission):
                mission = self._runtime.mission_service.approve_mission(mission_id)
            return {
                "current_step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
                "mission": mission,
            }

        pause: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
            "review_gate": "mission_approval",
            "mission": mission,
        }
        merged = cast(PlanningWorkflowState, {**state, **pause})
        self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Planning workflow paused for mission approval")
        interrupt(
            {
                "gate": "mission_approval",
                "step": PlanningWorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value,
            }
        )

        bundle = self._runtime.mission_service.get_mission_bundle(mission_id)
        if not is_mission_approval_current(bundle.mission):
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["任务理解审批已失效或不完整，无法继续下游规划"],
                "mission": bundle.mission,
            }
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
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }
        try:
            result = self._runtime.workstream_service.plan_workstreams(
                mission_id,
                require_ready=True,
            )
        except WorkflowError as exc:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_WORKSTREAMS.value,
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
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["缺少 mission_id"],
            }
        try:
            result = self._runtime.deliverable_service.plan_deliverables(
                mission_id,
                require_ready=True,
            )
        except WorkflowError as exc:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": [str(exc)],
            }
        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_DELIVERABLES.value,
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
                "current_step": PresentationWorkflowStep.FAILED.value,
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
                "current_step": PlanningWorkflowStep.PLANNING_AWAIT_APPROVAL.value,
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
                "current_step": PlanningWorkflowStep.PLANNING_AWAIT_APPROVAL.value,
                "deliverable_plan": plan,
            }

        pause: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_AWAIT_APPROVAL.value,
            "review_gate": "plan_approval",
            "deliverable_plan": plan,
        }
        merged = cast(PlanningWorkflowState, {**state, **pause})
        self._persist(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Planning workflow paused for plan approval")
        interrupt({"gate": "plan_approval", "step": PlanningWorkflowStep.PLANNING_AWAIT_APPROVAL.value})

        plan = self._runtime.missions.get_deliverable_plan(plan.id) if plan is not None else None
        if plan is None or plan.approval_status != ApprovalStatus.APPROVED:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
                "errors": ["成果计划尚未批准，无法继续"],
                "deliverable_plan": plan,
            }
        mission = self._runtime.missions.get_mission(mission_id)
        resume_state = {
            **pause,
            "deliverable_plan": plan,
            "mission": mission,
            "workstreams": self._runtime.missions.list_workstreams(mission_id),
        }
        self._persist({**merged, **resume_state}, status=WorkflowStatus.RUNNING)
        return resume_state

    def prepare_artifact_execution_plans(
        self, state: PlanningWorkflowState
    ) -> PlanningWorkflowState:
        """Build typed execution plans for selected deliverables (not PPT-only)."""
        from archium.application.deliverable_execution import DeliverableExecutionRouter
        from archium.application.mission_to_presentation_request import MissionPresentationBridge
        from archium.domain.enums import DeliverableType

        mission = state.get("mission")
        plan = state.get("deliverable_plan")
        if mission is None:
            return {
                "current_step": PresentationWorkflowStep.FAILED.value,
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
                warnings.append("未选择任何成果；未生成成果执行计划。")

        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_PREPARE_ARTIFACTS.value,
            "presentation_request_draft": draft,
            "artifact_execution_plans": [item.to_dict() for item in execution_plans],
            "warnings": warnings,
        }
        self._persist({**state, **next_state}, status=WorkflowStatus.RUNNING)
        return next_state

    # Backward-compatible alias for older call sites / docs.
    prepare_presentation_request = prepare_artifact_execution_plans

    def finalize(self, state: PlanningWorkflowState) -> PlanningWorkflowState:
        errors = list(state.get("errors", []))
        status = WorkflowStatus.FAILED if errors else WorkflowStatus.COMPLETED
        next_state: PlanningWorkflowState = {
            "current_step": PlanningWorkflowStep.PLANNING_FINALIZE.value
            if not errors
            else PresentationWorkflowStep.FAILED.value,
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
        finalize_run_state(run, snapshot_planning_state(state))
        run.errors = list(state.get("errors", []))
        if status is not None:
            run.status = status
        run.touch()
        self._runtime.workflow_runs.update(run)
        commit_workflow_checkpoint(self._runtime.session, self._runtime.settings)
