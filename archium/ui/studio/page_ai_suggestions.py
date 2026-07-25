"""Page-level AI suggestions for Studio / Outline (partner language, not scores)."""

from __future__ import annotations

import streamlit as st

from archium.domain.slide import SlideSpec
from archium.domain.slide_intent import SlideIntent
from archium.domain.slide_role import SlideRole


def page_partner_suggestions(slide: SlideSpec) -> list[str]:
    """Deterministic, architect-facing suggestions for the current page."""
    suggestions: list[str] = []
    message = (slide.message or "").strip()
    points = list(slide.key_points or [])
    title = (slide.title or "").strip() or "本页"

    if len(points) >= 5 or len(message) > 120:
        suggestions.append(f"「{title}」信息过多 — 建议减少文字，保留单一核心结论")
    if len(points) == 0 and len(message) < 20:
        suggestions.append(f"「{title}」叙事偏空 — 补一句页意图或关键论据")

    role = slide.slide_role
    strategy = slide.visual_strategy
    analysis_roles = {
        SlideRole.PROBLEM_ANALYSIS,
        SlideRole.SITE_ANALYSIS,
        SlideRole.STRATEGY,
        SlideRole.SPATIAL_LOGIC,
    }
    if role in analysis_roles:
        diagram = ""
        if strategy is not None:
            diagram = (strategy.recommended_diagram or "").strip()
        if not diagram:
            suggestions.append(
                f"「{title}」是分析/策略页 — 建议增加剖面、流线或关系图，而非装饰图"
            )
        else:
            suggestions.append(f"「{title}」推荐图解：{diagram}")

    if role in {SlideRole.EXPERIENCE, SlideRole.VISION, SlideRole.CONCEPT}:
        suggestions.append(f"「{title}」体验/概念页 — 可用氛围示意，避免堆砌数据表格")

    if strategy is not None and not strategy.is_empty():
        if (strategy.image_requirement or "").strip():
            suggestions.append(f"图像需求：{strategy.image_requirement.strip()}")
        if (strategy.graphic_language or "").strip():
            suggestions.append(f"图面语言：{strategy.graphic_language.strip()}")
    elif role is None or role == SlideRole.OTHER:
        suggestions.append(f"「{title}」尚未标注页角色 — 补 SlideRole 有助版式与图解选择")

    return _dedupe(suggestions)[:5]


def outline_partner_suggestions(intent: SlideIntent) -> list[str]:
    """Suggestions while authoring outline page intents (pre-generate)."""
    suggestions: list[str] = []
    title = (intent.page_task or "").strip() or f"第 {intent.order + 1} 页"
    conclusion = (intent.central_conclusion or "").strip()
    evidence = list(intent.required_evidence or [])
    notes = (intent.notes or "").strip()

    if not conclusion:
        suggestions.append(f"「{title}」缺少中心结论 — 先写清本页一句话主张")
    elif len(conclusion) > 160:
        suggestions.append(f"「{title}」结论偏长 — 压缩为可上屏的一句")

    if len(evidence) == 0 and intent.slide_role not in {
        SlideRole.OPENING,
        SlideRole.CONCLUSION,
        SlideRole.SUMMARY,
        None,
    }:
        suggestions.append(f"「{title}」未指定证据 — 标出现场照片、图纸或数据来源")

    if len(evidence) > 4:
        suggestions.append(f"「{title}」证据过多 — 每页保留 1–2 个关键证据更清晰")

    role = intent.slide_role
    strategy = intent.visual_strategy
    if role in {
        SlideRole.PROBLEM_ANALYSIS,
        SlideRole.SITE_ANALYSIS,
        SlideRole.STRATEGY,
        SlideRole.SPATIAL_LOGIC,
    }:
        diagram = ""
        if strategy is not None:
            diagram = (strategy.recommended_diagram or "").strip()
        if not diagram and not (intent.expected_layout or "").strip():
            suggestions.append(
                f"「{title}」分析页 — 预设剖面 / 流线 / 关系图版式，避免纯文字"
            )

    if role in {SlideRole.EXPERIENCE, SlideRole.VISION, SlideRole.CONCEPT}:
        suggestions.append(f"「{title}」概念体验页 — 生成后可用 Visual Thinking 绑示意")

    if role is None or role == SlideRole.OTHER:
        suggestions.append(f"「{title}」建议标注 SlideRole，方便后续版式与图解")

    if notes and len(notes) > 300:
        suggestions.append("备注过长 — 把禁止事项写入「禁止内容」，备注留短句")

    return _dedupe(suggestions)[:5]


def render_page_ai_suggestions_rail(
    slide: SlideSpec | None,
    *,
    title: str = "本页 AI 建议",
) -> None:
    """Always-visible partner rail for Studio right column."""
    st.markdown(f"**{title}**")
    if slide is None:
        st.caption("选择一页后显示叙事与图解建议。")
        return
    tips = page_partner_suggestions(slide)
    if not tips:
        st.caption("本页结构尚可 — 暂无强制建议。")
        return
    for tip in tips:
        st.markdown(f"- {tip}")


def render_outline_ai_suggestions_rail(intent: SlideIntent | None) -> None:
    """Right-rail tips while editing outline page intents."""
    st.markdown("**本页 AI 建议**")
    if intent is None:
        st.caption("在中间选择一页后，这里给出叙事与证据建议。")
        return
    tips = outline_partner_suggestions(intent)
    if not tips:
        st.caption("本页意图较完整。")
        return
    for tip in tips:
        st.markdown(f"- {tip}")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
