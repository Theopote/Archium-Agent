"""Select next-best actions and map them to product navigation targets."""

from __future__ import annotations

from archium.application.context.types import ActionDispatch, WorkflowEntryDispatch
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def resolve_action_target(
    action: NextBestActionType,
    *,
    pending_fact_count: int = 0,
    conflict_fact_count: int = 0,
) -> ActionDispatch:
    """Map NBA to an existing product page (+ optional orchestration kickoff)."""
    from archium.application.context.nba_action_executor import nba_execute_label
    from archium.domain.orchestration import stage_hint_for_action

    hint = stage_hint_for_action(action)
    hint_value = hint.value if hint is not None else None
    has_pending = pending_fact_count > 0 or conflict_fact_count > 0

    if action == NextBestActionType.EXPLORE_DIRECTIONS:
        return ActionDispatch(
            page_key="concept-exploration",
            label=nba_execute_label(action),
            orchestration_action="start",
            stage_hint=hint_value,
        )
    if action == NextBestActionType.UPLOAD_MATERIALS:
        return ActionDispatch(
            page_key="materials",
            label=nba_execute_label(action),
            orchestration_action="start",
            stage_hint=hint_value,
        )
    if action == NextBestActionType.RESEARCH:
        return ActionDispatch(
            page_key="project-mission",
            mission_step=2,
            label=nba_execute_label(action),
            orchestration_action="start",
            stage_hint=hint_value,
        )
    if action == NextBestActionType.ASK:
        if has_pending:
            count = pending_fact_count + conflict_fact_count
            return ActionDispatch(
                page_key="materials",
                label=f"确认待核实事实（{count}）",
                focus="pending_facts",
            )
        return ActionDispatch(
            page_key="project-mission",
            mission_step=3,
            label=nba_execute_label(action, has_pending_facts=False),
            orchestration_action="start",
            stage_hint=hint_value,
        )
    if action in {
        NextBestActionType.GENERATE_MISSION,
        NextBestActionType.OPEN_MISSION,
    }:
        return ActionDispatch(
            page_key="project-mission",
            mission_step=1,
            label=nba_execute_label(action),
            orchestration_action="start",
            stage_hint=hint_value,
        )
    return ActionDispatch(
        page_key="project-mission",
        mission_step=1,
        label=action.value,
    )


def default_actions_for_dimensions(
    dimensions: KnowledgeDimensions,
    *,
    stage: str = "",
    has_materials: bool = False,
    blocking_gaps: bool = False,
) -> list[NextBestAction]:
    """NBA from multi-axis cognition — temple-case: high intent + low info → explore."""
    if blocking_gaps:
        return default_actions_for_stage(
            stage or KnowledgeMaturityStage.DESIGN_ANALYSIS.value,
            has_materials=has_materials,
            blocking_gaps=True,
        )

    info = dimensions.information_completeness
    intent = dimensions.design_intent_clarity
    research = dimensions.research_need

    # Clear concept, sparse materials — do not force upload first
    if intent >= 0.6 and info < 0.4:
        actions = [
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="设计意图较清晰、资料仍少，可先推演概念方向",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="意图清楚时可先固化任务理解，不必等齐资料",
                priority=1,
            ),
        ]
        if research >= 0.55:
            actions.append(
                NextBestAction(
                    action=NextBestActionType.RESEARCH,
                    reason="背景/类型研究需求高，并行补充公开参照",
                    priority=2,
                )
            )
        actions.append(
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="澄清仍缺的关键约束与使用者条件",
                priority=3,
            )
        )
        return actions

    # Rich materials, fuzzy intent — clarify first
    if info >= 0.55 and intent < 0.45:
        return [
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="资料较充足但设计目标仍模糊，先澄清意图",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="用任务理解把目标与成果边界说清",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="意图澄清后可并行比较方向",
                priority=2,
            ),
        ]

    if research >= 0.7 and info < 0.55 and intent >= 0.5:
        return [
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="意图已有雏形且研究需求高，优先补充类型与背景证据",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="研究同时仍可推演方向",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="对齐关键未知项",
                priority=2,
            ),
        ]

    return default_actions_for_stage(
        stage or KnowledgeMaturityStage.CONCEPT_FORMATION.value,
        has_materials=has_materials or info >= 0.35,
        blocking_gaps=False,
    )


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
