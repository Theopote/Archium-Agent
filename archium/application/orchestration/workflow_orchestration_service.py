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
    HumanGate,
    OrchestrationPlan,
    OrchestrationPlanSource,
    OrchestrationStage,
    OrchestrationStageStatus,
    ProcessTimelineEvent,
    append_process_timeline_event,
    build_orchestration_plan,
    human_gate_for_stage,
    label_for_stage,
    replan_from_context,
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
    human_gate: HumanGate | None = None
    replan_decision: dict[str, object] | None = None

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

    def replan(
        self,
        workflow_run_id: UUID,
        context: ProjectContext | None = None,
        *,
        drive: bool = False,
    ) -> OrchestrationResult:
        """Decision Router: refresh PENDING tail from ProjectContext."""
        run = self._require_run(workflow_run_id)
        plan = self._plan_from_run(run)
        ctx = context or self._load_project_context(run.project_id)
        plan, decision = replan_from_context(plan, context=ctx)
        run.state = {
            **run.state,
            "orchestration_plan": plan.model_dump(mode="json"),
            "decision_router": decision.as_dict(),
        }
        if decision.changed:
            run.state = append_process_timeline_event(
                run.state,
                ProcessTimelineEvent(
                    kind="replan",
                    stage=(plan.active_stage().stage.value if plan.active_stage() else ""),
                    status="replanned",
                    label="按上下文重规划",
                    summary=decision.reason,
                    decision_router=decision.as_dict(),
                ),
            )
        if ctx is not None:
            reflection = self._reflection_payload(ctx)
            if reflection is not None:
                run.state["last_reflection"] = reflection
                run.state = append_process_timeline_event(
                    run.state,
                    ProcessTimelineEvent(
                        kind="reflection",
                        label="设计反思",
                        summary=str(reflection.get("why") or "")[:160],
                        intent_evolution_kind="reflection",
                    ),
                )
        run = self._workflow_runs.update(run)
        if drive:
            task = str(run.state.get("user_task_description") or "")
            result = self._drive(run, plan, user_task_description=task)
            result.replan_decision = decision.as_dict()
            return result
        gate = self._gate_from_plan(plan)
        return OrchestrationResult(
            workflow_run=run,
            plan=plan,
            page_key=gate.page_key if gate else None,
            human_gate=gate,
            replan_decision=decision.as_dict(),
            warnings=[decision.reason] if decision.reason else [],
        )

    def advance(
        self,
        workflow_run_id: UUID,
        *,
        context: ProjectContext | None = None,
        replan: bool = True,
    ) -> OrchestrationResult:
        """Mark active awaiting stage complete, optionally replan from Context, continue."""
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

        replan_payload: dict[str, object] | None = None
        if replan:
            ctx = context or self._load_project_context(run.project_id)
            plan, decision = replan_from_context(plan, context=ctx)
            replan_payload = decision.as_dict()
            run.state = {
                **run.state,
                "decision_router": replan_payload,
            }
            if decision.changed:
                run.state = append_process_timeline_event(
                    run.state,
                    ProcessTimelineEvent(
                        kind="replan",
                        stage=stage.stage.value,
                        status="replanned",
                        label="推进时重规划",
                        summary=decision.reason,
                        decision_router=replan_payload,
                    ),
                )
            if ctx is not None:
                reflection = self._reflection_payload(ctx)
                if reflection is not None:
                    run.state["last_reflection"] = reflection
                    self._best_effort_append_reflection(run.project_id, reflection)
                    run.state = append_process_timeline_event(
                        run.state,
                        ProcessTimelineEvent(
                            kind="reflection",
                            stage=stage.stage.value,
                            label="设计反思",
                            summary=str(reflection.get("why") or "")[:160],
                            intent_evolution_kind="reflection",
                        ),
                    )

        run.state = append_process_timeline_event(
            run.state,
            ProcessTimelineEvent(
                kind="stage",
                stage=stage.stage.value,
                status=OrchestrationStageStatus.COMPLETED.value,
                label=f"完成 {label_for_stage(stage.stage)}",
                summary="建筑师确认后推进",
            ),
        )

        from archium.domain.orchestration.decision_router import first_open_stage_index

        open_idx = first_open_stage_index(plan.stages)
        if open_idx is None:
            run.status = WorkflowStatus.COMPLETED
            run.state = {
                **run.state,
                "orchestration_plan": plan.model_dump(mode="json"),
                "human_gate": None,
                "active_stage": None,
            }
            run = self._workflow_runs.update(run)
            return OrchestrationResult(
                workflow_run=run,
                plan=plan,
                page_key=None,
                replan_decision=replan_payload,
            )
        plan.active_index = open_idx
        # If cursor still on the stage we just completed, step forward.
        current = plan.active_stage()
        if current is not None and current.status in {
            OrchestrationStageStatus.COMPLETED,
            OrchestrationStageStatus.SKIPPED,
            OrchestrationStageStatus.FAILED,
        }:
            if plan.advance_index() is None:
                run.status = WorkflowStatus.COMPLETED
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "human_gate": None,
                    "active_stage": None,
                }
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=None,
                    replan_decision=replan_payload,
                )

        task = str(run.state.get("user_task_description") or "")
        result = self._drive(run, plan, user_task_description=task)
        result.replan_decision = replan_payload
        return result

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
            if result.get("reflection"):
                run.state = {**run.state, "last_reflection": result["reflection"]}
            page_key = stage.page_key
            gate = human_gate_for_stage(
                stage.stage,
                page_key=page_key,
                awaiting_review=status == OrchestrationStageStatus.AWAITING_REVIEW,
            )

            if status == OrchestrationStageStatus.AWAITING_USER:
                run.status = WorkflowStatus.AWAITING_REVIEW
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "active_stage": stage.stage.value,
                    "review_gate": gate.review_gate,
                    "human_gate": gate.as_dict(),
                }
                run.state = append_process_timeline_event(
                    run.state,
                    ProcessTimelineEvent(
                        kind="gate",
                        stage=stage.stage.value,
                        status=status.value,
                        label=gate.label,
                        summary=gate.prompt,
                        human_gate=gate.as_dict(),
                    ),
                )
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=page_key,
                    warnings=warnings,
                    human_gate=gate,
                )
            if status == OrchestrationStageStatus.AWAITING_REVIEW:
                run.status = WorkflowStatus.AWAITING_REVIEW
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "active_stage": stage.stage.value,
                    "review_gate": gate.review_gate,
                    "human_gate": gate.as_dict(),
                    "child_workflow_run_id": str(stage.workflow_run_id)
                    if stage.workflow_run_id
                    else None,
                }
                run.state = append_process_timeline_event(
                    run.state,
                    ProcessTimelineEvent(
                        kind="gate",
                        stage=stage.stage.value,
                        status=status.value,
                        label=gate.label,
                        summary=gate.prompt,
                        human_gate=gate.as_dict(),
                        child_workflow_run_id=(
                            str(stage.workflow_run_id) if stage.workflow_run_id else None
                        ),
                        artifact_refs=(
                            [str(stage.workflow_run_id)] if stage.workflow_run_id else []
                        ),
                    ),
                )
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=page_key,
                    warnings=warnings,
                    human_gate=gate,
                )
            if status == OrchestrationStageStatus.FAILED:
                run.status = WorkflowStatus.FAILED
                run.errors = list(result.get("errors") or [])
                run.state = {
                    **run.state,
                    "orchestration_plan": plan.model_dump(mode="json"),
                    "active_stage": stage.stage.value,
                    "human_gate": None,
                }
                run.state = append_process_timeline_event(
                    run.state,
                    ProcessTimelineEvent(
                        kind="failed",
                        stage=stage.stage.value,
                        status=status.value,
                        label=f"失败 {label_for_stage(stage.stage)}",
                        summary="; ".join(str(e) for e in run.errors[:3]),
                    ),
                )
                run = self._workflow_runs.update(run)
                return OrchestrationResult(
                    workflow_run=run,
                    plan=plan,
                    page_key=page_key,
                    warnings=warnings,
                )
            # completed / skipped → next
            run.state = append_process_timeline_event(
                run.state,
                ProcessTimelineEvent(
                    kind="stage",
                    stage=stage.stage.value,
                    status=status.value,
                    label=f"{'跳过' if status == OrchestrationStageStatus.SKIPPED else '完成'} {label_for_stage(stage.stage)}",
                    summary=str(result.get("skip_reason") or "")[:160],
                    child_workflow_run_id=(
                        str(stage.workflow_run_id) if stage.workflow_run_id else None
                    ),
                ),
            )
            if plan.advance_index() is None:
                run.status = WorkflowStatus.COMPLETED
                break

        run.state = {
            **run.state,
            "orchestration_plan": plan.model_dump(mode="json"),
            "active_stage": None,
            "human_gate": None,
        }
        run.state = append_process_timeline_event(
            run.state,
            ProcessTimelineEvent(
                kind="complete",
                label="编排完成",
                summary="全部阶段已完成或跳过",
                status=WorkflowStatus.COMPLETED.value,
            ),
        )
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
            return self._run_presentation_stage(plan.project_id)
        if stage == OrchestrationStage.VISUAL:
            return self._run_visual_stage(plan.project_id)
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
            payload: dict[str, Any] = {
                "status": OrchestrationStageStatus.COMPLETED,
                "warnings": warnings or ["自主研究阶段已执行"],
            }
            ctx = self._load_project_context(project_id)
            reflection = self._reflection_payload(ctx, source="research")
            if reflection is not None:
                payload["reflection"] = reflection
                self._best_effort_append_reflection(project_id, reflection)
            return payload
        except Exception as exc:  # noqa: BLE001
            logger.warning("orchestration research stage failed: %s", exc)
            return {
                "status": OrchestrationStageStatus.SKIPPED,
                "skip_reason": str(exc),
                "warnings": [f"研究阶段跳过：{exc}"],
            }

    def _load_project_context(self, project_id: UUID) -> ProjectContext | None:
        try:
            from archium.application.context.project_context_builder import (
                build_project_context,
            )

            return build_project_context(self._session, project_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("load ProjectContext for router failed: %s", exc)
            return None

    @staticmethod
    def _reflection_payload(
        context: ProjectContext | None,
        *,
        source: str = "context",
    ) -> dict[str, object] | None:
        if context is None:
            return None
        from archium.application.design_reflection import reflection_from_context

        reflection = reflection_from_context(context)
        if reflection.is_empty():
            return None
        if source != reflection.source:
            reflection = reflection.model_copy(update={"source": source})
        return reflection.as_dict()

    def _best_effort_append_reflection(
        self,
        project_id: UUID,
        reflection: dict[str, object],
    ) -> None:
        try:
            from archium.domain.intent.intent_evolution import (
                IntentEvolution,
                IntentEvolutionKind,
            )
            from archium.infrastructure.database.repositories import ProjectRepository

            repo = ProjectRepository(self._session)
            project = repo.get_by_id(project_id)
            if project is None:
                return
            why = str(reflection.get("why") or "").strip() or "设计反思"
            evo = project.intent_evolution or IntentEvolution()
            project.intent_evolution = evo.append(
                IntentEvolutionKind.REFLECTION,
                why[:200],
                trigger="orchestration_reflection",
                reason=why[:400],
                evidence_refs=[
                    str(item)
                    for item in (reflection.get("top_risks") or [])[:3]
                    if str(item).strip()
                ],
                design_intent_snapshot={"reflection": reflection},
            )
            repo.update(project)
        except Exception as exc:  # noqa: BLE001
            logger.debug("append reflection evolution skipped: %s", exc)

    @staticmethod
    def _gate_from_plan(plan: OrchestrationPlan) -> HumanGate | None:
        stage = plan.active_stage()
        if stage is None:
            return None
        if stage.status not in {
            OrchestrationStageStatus.AWAITING_USER,
            OrchestrationStageStatus.AWAITING_REVIEW,
            OrchestrationStageStatus.PENDING,
            OrchestrationStageStatus.RUNNING,
        }:
            return None
        return human_gate_for_stage(
            stage.stage,
            page_key=stage.page_key,
            awaiting_review=stage.status == OrchestrationStageStatus.AWAITING_REVIEW,
        )

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
        from archium.domain.enums import WorkstreamStatus

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
        if all(
            ws.status in {WorkstreamStatus.COMPLETED, WorkstreamStatus.SKIPPED}
            for ws in selected
        ):
            return {
                "status": OrchestrationStageStatus.COMPLETED,
                "skip_reason": "工作路径已在计划批准后执行",
                "warnings": ["工作路径此前已执行，编排阶段不再重复运行"],
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

    def _run_presentation_stage(self, project_id: UUID) -> dict[str, Any]:
        """Thin adapter: reuse or prepare PresentationWorkflowService (no auto execute)."""
        runs = self._workflow_runs.list_by_project(project_id)
        presentation_runs = [r for r in runs if self._is_presentation_pipeline_run(r)]

        completed = [
            r for r in presentation_runs if r.status == WorkflowStatus.COMPLETED
        ]
        if completed:
            latest = max(completed, key=lambda r: r.updated_at or r.created_at)
            return {
                "status": OrchestrationStageStatus.COMPLETED,
                "workflow_run_id": latest.id,
                "warnings": ["汇报主链已完成"],
            }

        awaiting = [
            r for r in presentation_runs if r.status == WorkflowStatus.AWAITING_REVIEW
        ]
        if awaiting:
            latest = max(awaiting, key=lambda r: r.updated_at or r.created_at)
            return {
                "status": OrchestrationStageStatus.AWAITING_REVIEW,
                "workflow_run_id": latest.id,
                "warnings": ["汇报主链等待审阅，请在生成页继续"],
            }

        running = [r for r in presentation_runs if r.status == WorkflowStatus.RUNNING]
        if running:
            latest = max(running, key=lambda r: r.updated_at or r.created_at)
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "workflow_run_id": latest.id,
                "warnings": ["汇报运行已准备或进行中，请在生成页继续主链"],
            }

        planning_ready = [
            run
            for run in runs
            if run.state.get("workflow_kind") == "planning"
            and run.status == WorkflowStatus.COMPLETED
            and isinstance(run.state.get("presentation_request_draft"), dict)
        ]
        if not planning_ready:
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": ["尚无就绪的汇报请求，请先完成任务规划与计划批准"],
            }

        latest_planning = max(
            planning_ready, key=lambda r: r.updated_at or r.created_at
        )
        return self._prepare_presentation_from_planning(project_id, latest_planning)

    def _prepare_presentation_from_planning(
        self,
        project_id: UUID,
        planning_run: WorkflowRun,
    ) -> dict[str, Any]:
        from archium.application.planning_workflow_service import PlanningWorkflowService
        from archium.application.presentation_workflow_service import (
            PresentationWorkflowService,
        )
        from archium.domain.enums import DeliverableType

        planning = PlanningWorkflowService(
            self._session, self._llm, settings=self._settings
        )
        presentation = PresentationWorkflowService(
            self._session, self._llm, settings=self._settings
        )
        try:
            bridge = planning.get_presentation_bridge(planning_run.id)
            mission_id = None
            raw = planning_run.state.get("mission_id")
            if raw:
                mission_id = UUID(str(raw))
            if mission_id is not None:
                plan = self._missions.get_approved_deliverable_plan(mission_id)
                if plan is None:
                    plans = self._missions.list_deliverable_plans(mission_id)
                    plan = plans[0] if plans else None
                if plan is not None:
                    selected_presentations = [
                        item
                        for item in plan.deliverables
                        if item.selected
                        and item.deliverable_type == DeliverableType.PRESENTATION
                    ]
                    if not selected_presentations:
                        return {
                            "status": OrchestrationStageStatus.SKIPPED,
                            "skip_reason": "成果计划未选择汇报类交付",
                            "warnings": [
                                "当前成果未选择 Presentation，编排跳过汇报阶段"
                            ],
                            "workflow_run_id": planning_run.id,
                        }

            child = presentation.prepare_run(
                project_id,
                bridge.request,
                export_json=True,
                export_marp=False,
                require_brief_review=False,
                require_storyline_review=False,
                require_outline_review=True,
            )
            planning_session = planning.get_session_for_run(planning_run.id)
            if planning_session is not None and child.presentation_id is not None:
                with suppress(Exception):
                    planning.attach_presentation(
                        planning_session.id, child.presentation_id
                    )
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "workflow_run_id": child.id,
                "warnings": [
                    "已通过 PresentationWorkflowService.prepare_run 创建汇报运行；"
                    "请在生成页执行主链（大纲审阅闸门仍生效）"
                ],
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Presentation prepare for orchestration failed: %s", exc)
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "workflow_run_id": planning_run.id,
                "warnings": [
                    f"汇报准备未自动创建：{exc}；请在任务页手动启动 PresentationWorkflowService"
                ],
            }
        finally:
            with suppress(Exception):
                presentation.close()
            with suppress(Exception):
                planning.close()

    def _run_visual_stage(self, project_id: UUID) -> dict[str, Any]:
        """Thin adapter: hand off to VisualWorkflowService when a presentation is ready."""
        from archium.infrastructure.database.repositories import PresentationRepository

        runs = self._workflow_runs.list_by_project(project_id)
        visual_runs = [
            r for r in runs if r.state.get("workflow_kind") == "visual_composition"
        ]

        completed = [r for r in visual_runs if r.status == WorkflowStatus.COMPLETED]
        if completed:
            latest = max(completed, key=lambda r: r.updated_at or r.created_at)
            return {
                "status": OrchestrationStageStatus.COMPLETED,
                "workflow_run_id": latest.id,
                "warnings": ["视觉编排已完成"],
            }

        awaiting = [
            r for r in visual_runs if r.status == WorkflowStatus.AWAITING_REVIEW
        ]
        if awaiting:
            latest = max(awaiting, key=lambda r: r.updated_at or r.created_at)
            return {
                "status": OrchestrationStageStatus.AWAITING_REVIEW,
                "workflow_run_id": latest.id,
                "warnings": ["视觉编排等待审阅，请在工作室继续"],
            }

        running = [r for r in visual_runs if r.status == WorkflowStatus.RUNNING]
        if running:
            latest = max(running, key=lambda r: r.updated_at or r.created_at)
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "workflow_run_id": latest.id,
                "warnings": ["视觉编排进行中，请在工作室继续 VisualWorkflowService"],
            }

        presentations = PresentationRepository(self._session).list_by_project(project_id)
        with_outline = [p for p in presentations if p.current_outline_id]
        if with_outline:
            latest_pres = max(
                with_outline, key=lambda p: p.updated_at or p.created_at
            )
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": [
                    f"汇报已有大纲（presentation `{str(latest_pres.id)[:8]}…`）；"
                    "请在工作室启动 VisualWorkflowService（编排层不自动开跑视觉子图）"
                ],
            }

        presentation_done = [
            r
            for r in runs
            if self._is_presentation_pipeline_run(r)
            and r.status == WorkflowStatus.COMPLETED
        ]
        if presentations or presentation_done:
            return {
                "status": OrchestrationStageStatus.AWAITING_USER,
                "warnings": [
                    "汇报尚无大纲，请先完成汇报主链后再进入工作室启动 VisualWorkflowService"
                ],
            }

        return {
            "status": OrchestrationStageStatus.SKIPPED,
            "skip_reason": "尚无汇报成果，跳过视觉阶段",
            "warnings": ["尚无汇报成果，视觉阶段已跳过"],
        }

    @staticmethod
    def _is_presentation_pipeline_run(run: WorkflowRun) -> bool:
        kind = run.state.get("workflow_kind")
        if kind in {
            ORCHESTRATION_KIND,
            "planning",
            "workstream_execution",
            "visual_composition",
        }:
            return False
        if run.presentation_id is None:
            return False
        return isinstance(run.state.get("request"), dict) or "current_step" in run.state

    def link_child_run(
        self,
        project_id: UUID,
        *,
        stage: OrchestrationStage,
        child_workflow_run_id: UUID,
        status: OrchestrationStageStatus = OrchestrationStageStatus.AWAITING_REVIEW,
    ) -> WorkflowRun | None:
        """Attach a child subgraph run to the active orchestration stage, if matching."""
        active = self.get_active_run(project_id)
        if active is None:
            return None
        plan = self._plan_from_run(active)
        current = plan.active_stage()
        if current is None or current.stage != stage:
            return None
        current.workflow_run_id = child_workflow_run_id
        if current.status in {
            OrchestrationStageStatus.PENDING,
            OrchestrationStageStatus.RUNNING,
            OrchestrationStageStatus.AWAITING_USER,
        }:
            current.status = status
        active.status = WorkflowStatus.AWAITING_REVIEW
        gate = human_gate_for_stage(
            current.stage,
            page_key=current.page_key,
            awaiting_review=True,
        )
        active.state = {
            **active.state,
            "orchestration_plan": plan.model_dump(mode="json"),
            "active_stage": current.stage.value,
            "child_workflow_run_id": str(child_workflow_run_id),
            "review_gate": gate.review_gate,
            "human_gate": gate.as_dict(),
        }
        return self._workflow_runs.update(active)

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
