"""Select next-best actions and map them to product navigation targets."""

from __future__ import annotations

from archium.application.context.types import ActionDispatch, WorkflowEntryDispatch
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def resolve_action_target(
    action: NextBestActionType,
    *,
    pending_fact_count: int = 0,
    conflict_fact_count: int = 0,
) -> ActionDispatch:
    """Map NBA to an existing product page (no new pipeline)."""
    if action == NextBestActionType.EXPLORE_DIRECTIONS:
        return ActionDispatch(
            page_key="concept-exploration",
            label="推演概念方向",
        )
    if action == NextBestActionType.UPLOAD_MATERIALS:
        return ActionDispatch(page_key="materials", label="上传 / 整理资料")
    if action == NextBestActionType.RESEARCH:
        return ActionDispatch(
            page_key="project-mission",
            mission_step=2,
            label="启动研究补充背景",
        )
    if action == NextBestActionType.ASK:
        if pending_fact_count > 0 or conflict_fact_count > 0:
            count = pending_fact_count + conflict_fact_count
            return ActionDispatch(
                page_key="materials",
                label=f"确认待核实事实（{count}）",
                focus="pending_facts",
            )
        return ActionDispatch(
            page_key="project-mission",
            mission_step=3,
            label="先澄清关键问题",
        )
    if action in {
        NextBestActionType.GENERATE_MISSION,
        NextBestActionType.OPEN_MISSION,
    }:
        return ActionDispatch(
            page_key="project-mission",
            mission_step=1,
            label="打开项目任务",
        )
    return ActionDispatch(page_key="project-mission", mission_step=1, label=action.value)


def default_actions_for_stage(
    stage: str,
    *,
    has_materials: bool = False,
    blocking_gaps: bool = False,
) -> list[NextBestAction]:
    if blocking_gaps:
        return [
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="存在待确认或冲突的关键事实，先澄清再推进",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.UPLOAD_MATERIALS,
                reason="补充可核验资料以消解缺口",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="在约束内仍可并行推演概念方向",
                priority=2,
            ),
        ]
    if stage == KnowledgeMaturityStage.TECHNICAL_PRESENTATION.value:
        return [
            NextBestAction(
                action=NextBestActionType.UPLOAD_MATERIALS,
                reason="资料较充分时可继续补全证据并进入汇报结构",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.OPEN_MISSION,
                reason="整理任务理解与汇报目标",
                priority=1,
            ),
        ]
    if stage == KnowledgeMaturityStage.DESIGN_ANALYSIS.value or has_materials:
        return [
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="基于已有资料澄清仍缺的关键条件",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="资料已有部分证据，可形成任务理解",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="在已证实约束内推演概念方向",
                priority=2,
            ),
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="补公开背景与案例参照",
                priority=3,
            ),
        ]
    return [
        NextBestAction(
            action=NextBestActionType.EXPLORE_DIRECTIONS,
            reason="信息较少时可先推演概念方向",
            priority=0,
        ),
        NextBestAction(
            action=NextBestActionType.RESEARCH,
            reason="补充公开背景与类型参照",
            priority=1,
        ),
        NextBestAction(
            action=NextBestActionType.ASK,
            reason="澄清目标用户与核心问题",
            priority=2,
        ),
    ]


def resolve_workflow_entry(
    context: ProjectContext,
    *,
    pending_fact_count: int = 0,
    conflict_fact_count: int = 0,
) -> WorkflowEntryDispatch:
    """Derive navigation from recommended_workflow, falling back to top NBA."""
    if context.next_actions:
        action = context.next_actions[0]
        target = resolve_action_target(
            action.action,
            pending_fact_count=pending_fact_count,
            conflict_fact_count=conflict_fact_count,
        )
        return WorkflowEntryDispatch(
            page_key=target.page_key,
            mission_step=target.mission_step,
            label=target.label or action.reason,
            focus=target.focus,
            workflow=context.recommended_workflow,
            action_reason=action.reason,
        )
    return _workflow_fallback(context)


def _workflow_fallback(context: ProjectContext) -> WorkflowEntryDispatch:
    workflow = context.recommended_workflow
    page = (context.primary_page_key or "").strip()
    mapping: dict[RecommendedWorkflow, tuple[str, int | None, str]] = {
        RecommendedWorkflow.EXPLORE: ("concept-exploration", None, "推演概念方向"),
        RecommendedWorkflow.RESEARCH: ("project-mission", 2, "补充背景研究"),
        RecommendedWorkflow.MATERIALS: ("materials", None, "整理项目资料"),
        RecommendedWorkflow.MISSION: ("project-mission", 1, "理解项目任务"),
        RecommendedWorkflow.DESIGN: ("project-mission", 1, "方案比较与迭代"),
        RecommendedWorkflow.DELIVER: (
            "outline" if context.knowledge_state.completeness_score >= 0.45 else "materials",
            None,
            "推进正式交付准备",
        ),
    }
    page_key, step, label = mapping.get(
        workflow,
        ("project-mission", 1, "打开项目任务"),
    )
    if page:
        page_key = page
    return WorkflowEntryDispatch(
        page_key=page_key,
        mission_step=step,
        label=label,
        workflow=workflow,
    )
