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
    INTENT_LED = "intent_led"
    PARTIAL_CONTEXT = "partial_context"
    EVIDENCE_RICH = "evidence_rich"


_SITUATION_LABELS = {
    KnowledgeSituation.SPARSE_IDEA: "起步想法",
    KnowledgeSituation.INTENT_LED: "意图清晰·资料尚少",
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
    cognition_stale: bool = False
    claim_count: int = 0
    linked_claim_count: int = 0
    blocking_unknown_count: int = 0
    knowledge_item_count: int = 0
    dimension_bits: tuple[str, ...] = ()
    intent_pct: int = 0
    information_pct: int = 0
    research_need_pct: int = 0
    design_readiness_pct: int = 0
    vector_bars: tuple[tuple[str, int], ...] = ()
    known_highlights: tuple[str, ...] = ()
    missing_highlights: tuple[str, ...] = ()
    partner_headline: str = ""


def classify_knowledge_situation(state: KnowledgeState) -> KnowledgeSituation:
    """Map multi-axis KnowledgeState to a user-facing situation (not origin_mode)."""
    dims = state.effective_dimensions()
    if dims.information_completeness >= 0.55 and dims.evidence_confidence >= 0.35:
        return KnowledgeSituation.EVIDENCE_RICH
    if dims.design_intent_clarity >= 0.55 and dims.information_completeness < 0.4:
        return KnowledgeSituation.INTENT_LED
    if (
        dims.information_completeness < 0.18
        and dims.evidence_confidence < 0.12
        and dims.design_intent_clarity < 0.4
    ):
        return KnowledgeSituation.SPARSE_IDEA
    return KnowledgeSituation.PARTIAL_CONTEXT


def build_project_knowledge_display(
    context: ProjectContext,
    *,
    suggested_actions: tuple[str, ...] | None = None,
) -> ProjectKnowledgeDisplay:
    """Build demodeified copy from ProjectContext."""
    state = context.knowledge_state
    dims = state.effective_dimensions()
    situation = classify_knowledge_situation(state)
    situation_label = _SITUATION_LABELS[situation]
    completeness_pct = int(round(dims.display_score() * 100))
    intent_pct = int(round(dims.design_intent_clarity * 100))
    information_pct = int(round(dims.information_completeness * 100))
    research_need_pct = int(round(dims.research_need * 100))
    design_readiness_pct = int(round(float(dims.design_readiness) * 100))
    stage_label = _STAGE_LABELS.get(
        context.lifecycle_stage,
        context.lifecycle_stage.value,
    )
    workflow_label = _WORKFLOW_LABELS.get(
        context.recommended_workflow,
        context.recommended_workflow.value,
    )
    confidence_pct = int(round(context.confidence * 100))
    dim_bits = tuple(dims.summary_bits(limit=4))
    vector_bars = tuple(
        (label, int(round(score * 100))) for label, score in dims.vector_bars()
    )

    actions = suggested_actions or _suggested_actions_from_context(context)
    focus = _focus_for_situation(situation, workflow_label, context.next_actions)
    known_highlights = _known_highlights(state)
    missing_highlights = _missing_highlights(state)
    # Partner-facing: design language, not dashboard percentages.
    partner_headline = (
        f"AI 当前理解：**{situation_label}** · 阶段 **{stage_label}**"
        f" · 建议优先 **{workflow_label}**"
    )
    headline = partner_headline
    caption = _caption_for_situation(
        situation,
        state=state,
        workflow_label=workflow_label,
        understanding=context.understanding_summary,
    )
    linked = sum(
        1
        for claim in state.claims
        if claim.fact_id is not None or claim.knowledge_item_id is not None
    )
    blocking = sum(1 for gap in state.open_unknowns if gap.blocking)
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
        cognition_stale=bool(state.cognition_stale),
        claim_count=len(state.claims),
        linked_claim_count=linked,
        blocking_unknown_count=blocking,
        knowledge_item_count=int(state.knowledge_item_count or 0),
        dimension_bits=dim_bits,
        intent_pct=intent_pct,
        information_pct=information_pct,
        research_need_pct=research_need_pct,
        design_readiness_pct=design_readiness_pct,
        vector_bars=vector_bars,
        known_highlights=known_highlights,
        missing_highlights=missing_highlights,
        partner_headline=partner_headline,
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
    if situation == KnowledgeSituation.INTENT_LED:
        return "在清晰意图上推演方向 / 写任务理解"
    if situation == KnowledgeSituation.SPARSE_IDEA:
        return "从想法澄清与方向推演开始"
    return workflow_label


_KNOWN_KEY_LABELS = {
    "name": "项目名称",
    "project_name": "项目名称",
    "location": "项目位置",
    "client": "甲方",
    "main_function": "主要功能",
    "project_stage": "项目阶段",
    "site_area": "用地面积",
    "building_area": "建筑面积",
}


def _partner_key_label(key: str) -> str:
    text = (key or "").strip()
    if not text:
        return "主张"
    from archium.domain.fact_ledger import STANDARD_FACT_KEY_MAP

    if text in STANDARD_FACT_KEY_MAP:
        return STANDARD_FACT_KEY_MAP[text].label
    return _KNOWN_KEY_LABELS.get(text, text)


def _partner_gap_text(description: str, *, blocking: bool = False) -> str:
    """Rewrite internal gap jargon for partner-facing panels."""
    text = (description or "").strip()
    text = text.replace("缺少标准事实：", "待补充：")
    text = text.replace("待确认关键事实：", "待确认：")
    text = text.replace("事实冲突：", "信息冲突：")
    text = text.replace("外部信息缺少引用：", "外部信息缺来源：")
    if text.startswith("缺少标准事实"):
        text = text.replace("缺少标准事实", "待补充信息", 1)
    prefix = "需先确认：" if blocking else ""
    return f"{prefix}{text}" if prefix else text


def _known_highlights(state: KnowledgeState, *, limit: int = 6) -> tuple[str, ...]:
    rows: list[str] = []
    if state.claims:
        for claim in state.claims[:limit]:
            label = _partner_key_label(claim.key)
            summary = (claim.summary or "").strip()
            mark = "✓" if claim.confirmed else "·"
            rows.append(f"{mark} {label}" + (f"：{summary[:40]}" if summary else ""))
        return tuple(rows)
    for key, value in list((state.known or {}).items())[:limit]:
        rows.append(f"✓ {_partner_key_label(str(key))}：{value}")
    return tuple(rows)


def _missing_highlights(state: KnowledgeState, *, limit: int = 6) -> tuple[str, ...]:
    rows: list[str] = []
    if state.open_unknowns:
        for gap in state.open_unknowns[:limit]:
            rows.append(_partner_gap_text(gap.description, blocking=gap.blocking))
        return tuple(rows)
    for item in (state.unknown or state.missing_information or [])[:limit]:
        text = str(item).strip()
        if text:
            rows.append(_partner_gap_text(text))
    return tuple(rows)


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
    elif situation == KnowledgeSituation.INTENT_LED:
        base = (
            "设计意图已经较清楚，资料仍可后续补齐 — "
            "不必因资料少而停在「未成熟」。"
        )
    elif situation == KnowledgeSituation.PARTIAL_CONTEXT:
        base = (
            "这是大多数真实项目的状态：有一点地址、照片或介绍，"
            "仍有功能/规模等待澄清 — 不必在「纯想法」与「完备资料」之间二选一。"
        )
    else:
        base = "资料较充实，可整理事实并推进汇报结构；正式交付仍建议核对证据。"
    missing = _missing_highlights(state, limit=3)
    missing_line = "、".join(
        item.removeprefix("需先确认：") for item in missing
    )
    if summary:
        if missing_line:
            return f"{base} {summary} 仍缺：{missing_line}。建议下一步：{workflow_label}。"
        return f"{base} {summary} 建议下一步：{workflow_label}。"
    if missing_line and situation in {
        KnowledgeSituation.PARTIAL_CONTEXT,
        KnowledgeSituation.INTENT_LED,
        KnowledgeSituation.SPARSE_IDEA,
    }:
        return f"{base} 仍缺：{missing_line}。建议下一步：{workflow_label}。"
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
        return ("上传或整理现有资料", "核对关键项目信息")
    if workflow == RecommendedWorkflow.MISSION:
        return ("澄清任务与未知项", "完善项目任务理解")
    return ("描述项目并刷新知识状态",)
