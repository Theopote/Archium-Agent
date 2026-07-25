"""Knowledge-first display copy — partial context as default narrative, not workspace mode names."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


class KnowledgeSituation(StrEnum):
    """Coarse knowledge posture — not a user-selected project mode."""

    SPARSE_IDEA = "sparse_idea"
    PARTIAL_CONTEXT = "partial_context"
    EVIDENCE_RICH = "evidence_rich"


_SITUATION_LABELS = {
    KnowledgeSituation.SPARSE_IDEA: "起步想法",
    KnowledgeSituation.PARTIAL_CONTEXT: "部分资料",
    KnowledgeSituation.EVIDENCE_RICH: "资料较充实",
}

_STAGE_LABELS = {
    ProjectLifecycleStage.IDEA: "想法",
    ProjectLifecycleStage.CONCEPT: "概念",
    ProjectLifecycleStage.RESEARCH: "研究",
    ProjectLifecycleStage.DESIGN: "设计",
    ProjectLifecycleStage.DOCUMENTATION: "文档化",
}

_WORKFLOW_LABELS = {
    RecommendedWorkflow.EXPLORE: "推演概念方向",
    RecommendedWorkflow.RESEARCH: "补充背景研究",
    RecommendedWorkflow.MATERIALS: "整理项目资料",
    RecommendedWorkflow.MISSION: "澄清任务与使命",
    RecommendedWorkflow.DESIGN: "方案比较与迭代",
    RecommendedWorkflow.DELIVER: "正式交付准备",
}

_NBA_LABELS = {
    NextBestActionType.ASK: "澄清关键问题",
    NextBestActionType.EXPLORE_DIRECTIONS: "推演概念方向",
    NextBestActionType.GENERATE_MISSION: "理解项目任务",
    NextBestActionType.UPLOAD_MATERIALS: "补充项目资料",
    NextBestActionType.RESEARCH: "公开背景研究",
}


@dataclass(frozen=True)
class ProjectKnowledgeDisplay:
    """UI-facing knowledge profile — replaces mode-first chrome for most users."""

    situation: KnowledgeSituation
    situation_label: str
    completeness_pct: int
    stage_label: str
    workflow_label: str
    confidence_pct: int
    headline: str
    caption: str
    focus: str
    suggested_actions: tuple[str, ...]


def classify_knowledge_situation(state: KnowledgeState) -> KnowledgeSituation:
    """Map continuous KnowledgeState to a user-facing situation (not origin_mode)."""
    if state.completeness_score >= 0.55 and state.evidence_ratio >= 0.35:
        return KnowledgeSituation.EVIDENCE_RICH
    if state.completeness_score < 0.18 and state.evidence_ratio < 0.12:
        return KnowledgeSituation.SPARSE_IDEA
    return KnowledgeSituation.PARTIAL_CONTEXT


def build_project_knowledge_display(
    context: ProjectContext,
    *,
    suggested_actions: tuple[str, ...] | None = None,
) -> ProjectKnowledgeDisplay:
    """Build demodeified copy from ProjectContext."""
    state = context.knowledge_state
    situation = classify_knowledge_situation(state)
    situation_label = _SITUATION_LABELS[situation]
    completeness_pct = int(round(state.completeness_score * 100))
    stage_label = _STAGE_LABELS.get(
        context.lifecycle_stage,
        context.lifecycle_stage.value,
    )
    workflow_label = _WORKFLOW_LABELS.get(
        context.recommended_workflow,
        context.recommended_workflow.value,
    )
    confidence_pct = int(round(context.confidence * 100))

    actions = suggested_actions or _suggested_actions_from_context(context)
    focus = _focus_for_situation(situation, workflow_label, context.next_actions)
    headline = (
        f"项目认知：**{situation_label}**（完整度约 {completeness_pct}%）"
        f" · 阶段 {stage_label} · 建议优先 **{workflow_label}**"
    )
    caption = _caption_for_situation(
        situation,
        state=state,
        workflow_label=workflow_label,
        understanding=context.understanding_summary,
    )
    return ProjectKnowledgeDisplay(
        situation=situation,
        situation_label=situation_label,
        completeness_pct=completeness_pct,
        stage_label=stage_label,
        workflow_label=workflow_label,
        confidence_pct=confidence_pct,
        headline=headline,
        caption=caption,
        focus=focus,
        suggested_actions=actions,
    )


def _focus_for_situation(
    situation: KnowledgeSituation,
    workflow_label: str,
    actions: list[NextBestAction],
) -> str:
    if actions:
        label = _NBA_LABELS.get(actions[0].action)
        if label:
            return label
    if situation == KnowledgeSituation.EVIDENCE_RICH:
        return "事实账本与汇报结构"
    if situation == KnowledgeSituation.SPARSE_IDEA:
        return "从想法澄清与方向推演开始"
    return workflow_label


def _caption_for_situation(
    situation: KnowledgeSituation,
    *,
    state: KnowledgeState,
    workflow_label: str,
    understanding: str,
) -> str:
    summary = (understanding or "").strip()
    if situation == KnowledgeSituation.SPARSE_IDEA:
        base = "目前主要是想法与片段描述，不必先备齐资料。"
    elif situation == KnowledgeSituation.PARTIAL_CONTEXT:
        base = (
            "这是大多数真实项目的状态：有一点地址、照片或介绍，"
            "仍有功能/规模等待澄清 — 不必在「纯想法」与「完备资料」之间二选一。"
        )
    else:
        base = "资料较充实，可整理事实并推进汇报结构；正式交付仍建议核对证据。"
    if summary:
        return f"{base} {summary}"
    unknowns = state.unknown or state.missing_information
    if unknowns and situation == KnowledgeSituation.PARTIAL_CONTEXT:
        sample = "、".join(unknowns[:3])
        return f"{base} 仍缺：{sample}。建议下一步：{workflow_label}。"
    return f"{base} 建议下一步：{workflow_label}。"


def _suggested_actions_from_context(context: ProjectContext) -> tuple[str, ...]:
    actions: list[str] = []
    for nba in context.next_actions[:3]:
        label = _NBA_LABELS.get(nba.action)
        if label:
            detail = (nba.reason or nba.question or "").strip()
            actions.append(f"{label}：{detail}" if detail else label)
    if actions:
        return tuple(actions)
    workflow = context.recommended_workflow
    if workflow == RecommendedWorkflow.EXPLORE:
        return ("推演 2–3 个概念方向", "选定方向后生成项目任务")
    if workflow == RecommendedWorkflow.MATERIALS:
        return ("上传或整理现有资料", "确认事实账本")
    if workflow == RecommendedWorkflow.MISSION:
        return ("澄清任务与未知项", "生成或完善 Mission")
    return ("描述项目并刷新知识状态",)
