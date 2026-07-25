"""Map RecommendedWorkflow / NBA hints onto an OrchestrationPlan."""

from __future__ import annotations

from uuid import UUID

from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.next_best_action import NextBestActionType
from archium.domain.orchestration.models import (
    OrchestrationPlan,
    OrchestrationPlanSource,
    OrchestrationStage,
    OrchestrationStageSpec,
    OrchestrationStageStatus,
)

_STAGE_PAGE: dict[OrchestrationStage, str] = {
    OrchestrationStage.EXPLORE: "concept-exploration",
    OrchestrationStage.RESEARCH: "project-mission",
    OrchestrationStage.MATERIALS: "materials",
    OrchestrationStage.MISSION_PLANNING: "project-mission",
    OrchestrationStage.WORKSTREAM_EXECUTION: "project-mission",
    OrchestrationStage.PRESENTATION: "generate",
    OrchestrationStage.VISUAL: "edit",
    OrchestrationStage.DELIVER: "deliver",
}

_STAGE_LABEL: dict[OrchestrationStage, str] = {
    OrchestrationStage.EXPLORE: "概念探索",
    OrchestrationStage.RESEARCH: "自主研究",
    OrchestrationStage.MATERIALS: "资料整理",
    OrchestrationStage.MISSION_PLANNING: "任务规划",
    OrchestrationStage.WORKSTREAM_EXECUTION: "工作路径执行",
    OrchestrationStage.PRESENTATION: "汇报生成",
    OrchestrationStage.VISUAL: "视觉与版式",
    OrchestrationStage.DELIVER: "交付导出",
}

_WORKFLOW_STAGES: dict[RecommendedWorkflow, tuple[OrchestrationStage, ...]] = {
    RecommendedWorkflow.EXPLORE: (
        OrchestrationStage.EXPLORE,
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
        OrchestrationStage.PRESENTATION,
    ),
    RecommendedWorkflow.RESEARCH: (
        OrchestrationStage.RESEARCH,
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
        OrchestrationStage.PRESENTATION,
    ),
    RecommendedWorkflow.MATERIALS: (
        OrchestrationStage.MATERIALS,
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
        OrchestrationStage.PRESENTATION,
    ),
    RecommendedWorkflow.MISSION: (
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
        OrchestrationStage.PRESENTATION,
    ),
    RecommendedWorkflow.DESIGN: (
        OrchestrationStage.EXPLORE,
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
        OrchestrationStage.PRESENTATION,
        OrchestrationStage.VISUAL,
    ),
    RecommendedWorkflow.DELIVER: (
        OrchestrationStage.PRESENTATION,
        OrchestrationStage.VISUAL,
        OrchestrationStage.DELIVER,
    ),
}


def stages_for_recommended_workflow(
    workflow: RecommendedWorkflow,
) -> tuple[OrchestrationStage, ...]:
    return _WORKFLOW_STAGES.get(
        workflow,
        _WORKFLOW_STAGES[RecommendedWorkflow.MISSION],
    )


def page_key_for_stage(stage: OrchestrationStage) -> str:
    return _STAGE_PAGE[stage]


def label_for_stage(stage: OrchestrationStage) -> str:
    return _STAGE_LABEL[stage]


def build_orchestration_plan(
    project_id: UUID,
    *,
    workflow: RecommendedWorkflow | None = None,
    context: ProjectContext | None = None,
    source: OrchestrationPlanSource | None = None,
    stage_hint: OrchestrationStage | None = None,
) -> OrchestrationPlan:
    """Pure mapping: RecommendedWorkflow (+ optional NBA hint) → OrchestrationPlan."""
    resolved_workflow = workflow
    resolved_source = source or OrchestrationPlanSource.RECOMMENDED_WORKFLOW
    if context is not None:
        resolved_workflow = resolved_workflow or context.recommended_workflow
        if source is None and context.next_actions:
            resolved_source = OrchestrationPlanSource.NBA
    if resolved_workflow is None:
        resolved_workflow = RecommendedWorkflow.MISSION

    stages = list(stages_for_recommended_workflow(resolved_workflow))
    if stage_hint is not None and stage_hint in stages:
        # Start at the hinted stage; keep the remainder of the path.
        idx = stages.index(stage_hint)
        stages = stages[idx:]

    specs = [
        OrchestrationStageSpec(
            stage=stage,
            status=OrchestrationStageStatus.PENDING,
            page_key=page_key_for_stage(stage),
            label=label_for_stage(stage),
        )
        for stage in stages
    ]
    return OrchestrationPlan(
        project_id=project_id,
        source=resolved_source,
        stages=specs,
        active_index=0,
    )


def stage_hint_for_action(action: NextBestActionType) -> OrchestrationStage | None:
    return {
        NextBestActionType.EXPLORE_DIRECTIONS: OrchestrationStage.EXPLORE,
        NextBestActionType.RESEARCH: OrchestrationStage.RESEARCH,
        NextBestActionType.UPLOAD_MATERIALS: OrchestrationStage.MATERIALS,
        NextBestActionType.GENERATE_MISSION: OrchestrationStage.MISSION_PLANNING,
        NextBestActionType.OPEN_MISSION: OrchestrationStage.MISSION_PLANNING,
        NextBestActionType.ASK: OrchestrationStage.MISSION_PLANNING,
    }.get(action)


def workflow_for_nba_action(action: NextBestActionType) -> RecommendedWorkflow:
    return {
        NextBestActionType.EXPLORE_DIRECTIONS: RecommendedWorkflow.EXPLORE,
        NextBestActionType.RESEARCH: RecommendedWorkflow.RESEARCH,
        NextBestActionType.UPLOAD_MATERIALS: RecommendedWorkflow.MATERIALS,
        NextBestActionType.GENERATE_MISSION: RecommendedWorkflow.MISSION,
        NextBestActionType.OPEN_MISSION: RecommendedWorkflow.MISSION,
        NextBestActionType.ASK: RecommendedWorkflow.MISSION,
    }.get(action, RecommendedWorkflow.MISSION)
