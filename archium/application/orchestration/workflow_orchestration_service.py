"""Product-stage orchestrator — starts/resumes durable subgraphs from ProjectContext."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.orchestration.workstream_execution_service import (
    WorkstreamExecutionService,
)
from archium.config.settings import Settings, get_settings
from archium.domain.context.project_context import ProjectContext
from archium.domain.enums import WorkflowStatus
from archium.domain.orchestration import (
    OrchestrationPlan,
    OrchestrationPlanSource,
    OrchestrationStage,
    OrchestrationStageStatus,
    build_orchestration_plan,
    label_for_stage,
    stage_hint_for_action,
)
from archium.domain.intent.next_best_action import NextBestActionType
from archium.domain.workflow import WorkflowRun
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger

logger = get_logger(__name__, operation="workflow_orchestration")

ORCHESTRATION_KIND = "orchestration"


@dataclass
class OrchestrationResult:
    workflow_run: WorkflowRun
    plan: OrchestrationPlan
    page_key: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def awaiting_user(self) -> bool:
        stage = self.plan.active_stage()
        return stage is not None and stage.status == OrchestrationStageStatus.AWAITING_USER

    @property
    def active_stage(self) -> OrchestrationStage | None:
        stage = self.plan.active_stage()
        return stage.stage if stage else None


class WorkflowOrchestrationService:
    """A: map ProjectContext → OrchestrationPlan and advance durable stages."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._workflow_runs = WorkflowRunRepository(session)
        self._missions = MissionRepository(session)

    def build_plan(
        self,
        project_id: UUID,
        context: ProjectContext | None = None,
        *,
        action: NextBestActionType | None = None,
        source: OrchestrationPlanSource | None = None,
    ) -> OrchestrationPlan:
        from archium.domain.orchestration import workflow_for_nba_action

        hint = stage_hint_for_action(action) if action is not None else None
        workflow = None
        if context is None and action is not None:
            workflow = workflow_for_nba_action(action)
            source = source or OrchestrationPlanSource.NBA
        return build_orchestration_plan(
            project_id,
            workflow=workflow,
            context=context,
            source=source,
            stage_hint=hint,
        )

    def get_active_run(self, project_id: UUID) -> WorkflowRun | None:
        for run in self._workflow_runs.list_by_project(project_id):
            if run.state.get("workflow_kind") != ORCHESTRATION_KIND:
                continue
            if run.status in {WorkflowStatus.RUNNING, WorkflowStatus.AWAITING_REVIEW}:
                return run
        return None

    def get_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None or run.state.get("workflow_kind") != ORCHESTRATION_KIND:
            return None
        return run

    def start(
        self,
        project_id: UUID,
        context: ProjectContext | None = None,
        *,
        action: NextBestActionType | None = None,
        user_task_description: str = "",
    ) -> OrchestrationResult:
        existing = self.get_active_run(project_id)
        if existing is not None:
            return self.resume(existing.id)

        plan = self.build_plan(project_id, context, action=action)
        run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                status=WorkflowStatus.RUNNING,
                state={
                    "workflow_kind": ORCHESTRATION_KIND,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "user_task_description": user_task_description.strip(),
                },
            )
        )
        return self._drive(run, plan, user_task_description=user_task_description)

    def resume(self, workflow_run_id: UUID) -> OrchestrationResult:
        run = self._require_run(workflow_run_id)
        plan = self._plan_from_run(run)
        task = str(run.state.get("user_task_description") or "")
        return self._drive(run, plan, user_task_description=task)

    def advance(self, workflow_run_id: UUID) -> OrchestrationResult:
        """Mark active awaiting_user stage complete and continue."""
        run = self._require_run(workflow_run_id)
        plan = self._plan_from_run(run)
        stage = plan.active_stage()
        if stage is None:
            raise WorkflowError("编排计划没有活动阶段")
        if stage.status not in {
            OrchestrationStageStatus.AWAITING_USER,
            OrchestrationStageStatus.AWAITING_REVIEW,
            OrchestrationStageStatus.COMPLETED,
            OrchestrationStageStatus.SKIPPED,
        }:
            raise WorkflowError(f"阶段 {stage.stage.value} 尚未可推进（{stage.status.value}）")
        if stage.status in {
            OrchestrationStageStatus.AWAITING_USER,
            OrchestrationStageStatus.AWAITING_REVIEW,
        }:
            stage.status = OrchestrationStageStatus.COMPLETED
        nxt = plan.advance_index()
        if nxt is None:
            run.status = WorkflowStatus.COMPLETED
            run.state = {**run.state, "orchestration_plan": plan.model_dump(mode="json")}
            run = self._workflow_runs.update(run)
            return OrchestrationResult(workflow_run=run, plan=plan, page_key=None)
        task = str(run.state.get("user_task_description") or "")
        return self._drive(run, plan, user_task_description=task)

    def _drive(
        self,
        run: WorkflowRun,
        plan: OrchestrationPlan,
        *,
        user_task_description: str = "",
    ) -> OrchestrationResult:
        warnings: list[str] = []
        # Auto-skip empty workstream execution / complete terminal navigation loops.
        safety = 0
        while safety < 12:
            safety += 1
            stage = plan.active_stage()
            if stage is None:
                run.status = WorkflowStatus.COMPLETED
                break
            if stage.status in {
                OrchestrationStageStatus.COMPLETED,
                OrchestrationStageStatus.SKIPPED,
            }:
                if plan.advance_index() is None:
                    run.status = WorkflowStatus.COMPLETED
                    break
                continue

            result = self._execute_stage(
                plan,
                stage.stage,
                run=run,
                user_task_description=user_task_description,
            )
            warnings.extend(result.get("warnings") or [])
            status = result["status"]
            stage.status = status
            if result.get("workflow_run_id"):
                stage.workflow_run_id = UUID(str(result["workflow_run_id"]))
            if result.get("skip_reason"):
                stage.skip_reason = str(result["skip_reason"])
            page_key = stage.page_key

            if status == OrchestrationStageStatus.AWAITING_USER:
                run.status = WorkflowStatus.AWAITING_REVIEW
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "active_stage": stage.stage.value,
                    "review_gate": f"orchestration:{stage.stage.value}",
                }
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=page_key,
                    warnings=warnings,
                )
            if status == OrchestrationStageStatus.AWAITING_REVIEW:
                run.status = WorkflowStatus.AWAITING_REVIEW
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "active_stage": stage.stage.value,
                    "review_gate": f"orchestration:{stage.stage.value}",
                    "child_workflow_run_id": str(stage.workflow_run_id)
                    if stage.workflow_run_id
                    else None,
                }
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=page_key,
                    warnings=warnings,
                )
            if status == OrchestrationStageStatus.FAILED:
                run.status = WorkflowStatus.FAILED
                run.errors = list(result.get("errors") or [])
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "active_stage": stage.stage.value,
                }
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=page_key,
                    warnings=warnings,
                )
            # completed / skipped → next
            if plan.advance_index() is None:
                run.status = WorkflowStatus.COMPLETED
                break

        run.state = {
            **run.state,
            "orchestration_plan": plan.model_dump(mode="json"),
            "active_stage": None,
        }
        run = self._workflow_runs.update(run)
        return OrchestrationResult(
            workflow_run=run,
            plan=plan,
            page_key=None,
            warnings=warnings,
        )

    def _execute_stage(
        self,
        plan: OrchestrationPlan,
        stage: OrchestrationStage,
        *,
        run: WorkflowRun,
        user_task_description: str,
    ) -> dict[str, Any]:
        if stage in {
            OrchestrationStage.EXPLORE,
            OrchestrationStage.MATERIALS,
            OrchestrationStage.DELIVER,
        }:
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": [f"请在界面完成「{label_for_stage(stage)}」后继续编排"],
            }
        if stage == OrchestrationStage.RESEARCH:
            return self._run_research_stage(plan.project_id)
        if stage == OrchestrationStage.MISSION_PLANNING:
            return self._run_mission_planning_stage(
                plan.project_id,
                user_task_description=user_task_description,
            )
        if stage == OrchestrationStage.WORKSTREAM_EXECUTION:
            return self._run_workstream_stage(plan.project_id)
        if stage == OrchestrationStage.PRESENTATION:
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": ["请在生成页启动或继续汇报主链"],
            }
        if stage == OrchestrationStage.VISUAL:
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": ["请在工作室继续视觉与版式"],
            }
        return {
            "status": OrchestrationStageStatus.SKIPPED,
            "skip_reason": f"未实现的阶段：{stage.value}",
        }

    def _run_research_stage(self, project_id: UUID) -> dict[str, Any]:
        try:
            from archium.application.context.context_analyzer import ContextAnalyzer

            analyzer = ContextAnalyzer(self._session, self._llm, settings=self._settings)
            result = analyzer.try_execute_research(project_id)
            warnings = []
            if hasattr(result, "warnings"):
                warnings = list(getattr(result, "warnings") or [])
            return {
                "status": OrchestrationStageStatus.COMPLETED,
                "warnings": warnings or ["自主研究阶段已执行"],
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("orchestration research stage failed: %s", exc)
            return {
                "status": OrchestrationStageStatus.SKIPPED,
                "skip_reason": str(exc),
                "warnings": [f"研究阶段跳过：{exc}"],
            }

    def _run_mission_planning_stage(
        self,
        project_id: UUID,
        *,
        user_task_description: str,
    ) -> dict[str, Any]:
        from archium.application.planning_workflow_service import PlanningWorkflowService

        task = user_task_description.strip()
        if not task:
            missions = self._missions.list_missions_by_project(project_id)
            if missions:
                task = missions[0].task_statement or missions[0].title
        if not task:
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": ["缺少任务描述，请在项目任务页填写后继续"],
            }
        service = PlanningWorkflowService(
            self._session, self._llm, settings=self._settings
        )
        try:
            result = service.run(project_id, task)
            child_id = result.workflow_run.id
            if result.awaiting_review:
                return {
                    "status": OrchestrationStageStatus.AWAITING_REVIEW,
                    "workflow_run_id": child_id,
                    "warnings": list(result.warnings),
                }
            if result.workflow_run.status == WorkflowStatus.FAILED or result.errors:
                return {
                    "status": OrchestrationStageStatus.FAILED,
                    "workflow_run_id": child_id,
                    "errors": list(result.errors) or result.workflow_run.errors,
                    "warnings": list(result.warnings),
                }
            return {
                "status": OrchestrationStageStatus.COMPLETED,
                "workflow_run_id": child_id,
                "warnings": list(result.warnings),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": [f"任务规划未自动启动：{exc}"],
            }
        finally:
            with suppress(Exception):
                service.close()

    def _run_workstream_stage(self, project_id: UUID) -> dict[str, Any]:
        missions = self._missions.list_missions_by_project(project_id)
        if not missions:
            return {
                "status": OrchestrationStageStatus.SKIPPED,
                "skip_reason": "尚无 Mission，跳过工作路径执行",
            }
        mission = missions[0]
        workstreams = self._missions.list_workstreams(mission.id)
        selected = [ws for ws in workstreams if ws.selected]
        if not selected:
            return {
                "status": OrchestrationStageStatus.SKIPPED,
                "skip_reason": "未选择工作路径，自动跳过",
                "warnings": ["未选择工作路径，工作路径执行阶段已跳过"],
            }
        service = WorkstreamExecutionService(
            self._session, self._llm, settings=self._settings
        )
        try:
            result = service.run_for_mission(mission.id, workstreams)
            for ws in workstreams:
                if ws.selected:
                    self._missions.save_workstream(ws)
            return {
                "status": OrchestrationStageStatus.COMPLETED
                if result.succeeded or result.completed or result.skipped
                else OrchestrationStageStatus.FAILED,
                "workflow_run_id": result.workflow_run.id,
                "warnings": list(result.warnings),
                "errors": list(result.workflow_run.errors),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": OrchestrationStageStatus.SKIPPED,
                "skip_reason": str(exc),
                "warnings": [f"工作路径执行跳过：{exc}"],
            }
        finally:
            with suppress(Exception):
                service.close()

    def _require_run(self, workflow_run_id: UUID) -> WorkflowRun:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"编排运行 {workflow_run_id} 不存在")
        if run.state.get("workflow_kind") != ORCHESTRATION_KIND:
            raise WorkflowError(f"运行 {workflow_run_id} 不是编排工作流")
        return run

    def _plan_from_run(self, run: WorkflowRun) -> OrchestrationPlan:
        raw = run.state.get("orchestration_plan")
        if not isinstance(raw, dict):
            raise WorkflowError("编排运行缺少 orchestration_plan")
        return OrchestrationPlan.model_validate(raw)
