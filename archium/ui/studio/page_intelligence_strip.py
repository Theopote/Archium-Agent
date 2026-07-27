"""Page Intelligence Strip — architect-facing slide semantics above the canvas."""

from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from archium.domain.visual.enums import LayoutFamily
from archium.ui.label_map import slide_role_label
from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.visual_service import SlideVisualSnapshot


@dataclass(frozen=True)
class PageIntelligence:
    """Read-only summary of what AI understands about the current page."""

    page_label: str
    role: str
    expression: str
    visual_language: str
    layout_family: str
    score: int | None
    score_tone: str


def build_page_intelligence(
    slide_snapshot: SlideVisualSnapshot | None,
    *,
    advanced: bool = False,
) -> PageIntelligence | None:
    if slide_snapshot is None:
        return None

    slide = slide_snapshot.slide
    page_label = f"P{slide.order + 1} · {(slide.title or '未命名').strip()}"

    role = slide_role_label(getattr(slide, "slide_role", None), advanced=advanced)

    expression = (slide.message or "").strip()
    intent = slide_snapshot.visual_intent
    if intent is not None:
        takeaway = (intent.audience_takeaway or "").strip()
        goal = (intent.communication_goal or "").strip()
        if takeaway:
            expression = takeaway
        elif goal and not expression:
            expression = goal

    strategy = getattr(slide, "visual_strategy", None)
    visual_language = ""
    if strategy is not None and not strategy.is_empty():
        visual_language = (strategy.graphic_language or strategy.recommended_diagram or "").strip()
    if not visual_language and intent is not None:
        visual_language = (intent.composition_strategy or intent.emotional_tone or "").strip()

    layout_family = ""
    plan = slide_snapshot.layout_plan
    if plan is not None:
        try:
            family = LayoutFamily(plan.layout_family)
            layout_family = format_layout_family_label(family)
        except ValueError:
            layout_family = str(plan.layout_family)

    score, tone = _resolve_score(slide_snapshot)
    return PageIntelligence(
        page_label=page_label,
        role=role,
        expression=expression[:120] if expression else "（待补充页意图）",
        visual_language=visual_language[:80] if visual_language else "（待生成视觉语言）",
        layout_family=layout_family or "（待生成版式）",
        score=score,
        score_tone=tone,
    )


def _resolve_score(slide_snapshot: SlideVisualSnapshot) -> tuple[int | None, str]:
    scores: list[float] = []
    if slide_snapshot.validation is not None:
        scores.append(float(slide_snapshot.validation.score) * 100)
    critic = slide_snapshot.visual_critic
    if isinstance(critic, dict):
        total = critic.get("total_score")
        if isinstance(total, (int, float)):
            scores.append(float(total) * 100 if total <= 1.0 else float(total))
    if not scores:
        return None, "neutral"
    avg = sum(scores) / len(scores)
    score_int = max(0, min(100, int(round(avg))))
    if score_int >= 85:
        return score_int, "ok"
    if score_int >= 70:
        return score_int, "info"
    if score_int >= 55:
        return score_int, "warn"
    return score_int, "error"


def _chip(label: str, value: str, *, accent: str = "#667085") -> str:
    return (
        f'<span class="page-intel-chip" style="border-color:{accent};">'
        f'<span class="page-intel-chip-label">{html.escape(label)}</span>'
        f'<span class="page-intel-chip-value">{html.escape(value)}</span>'
        f"</span>"
    )


def render_page_intelligence_strip(
    slide_snapshot: SlideVisualSnapshot | None,
    *,
    advanced: bool = False,
) -> None:
    """Render the page semantics bar above the canvas."""
    intel = build_page_intelligence(slide_snapshot, advanced=advanced)
    if intel is None:
        return

    score_html = ""
    if intel.score is not None:
        score_colors = {
            "ok": "#12b76a",
            "info": "#175cd3",
            "warn": "#b54708",
            "error": "#d92d20",
            "neutral": "#667085",
        }
        color = score_colors.get(intel.score_tone, "#667085")
        score_html = _chip("评分", f"{intel.score}", accent=color)

    chips = [
        _chip("页角色", intel.role, accent="#7a5af8"),
        _chip("表达", intel.expression, accent="#175cd3"),
        _chip("视觉语言", intel.visual_language, accent="#12b76a"),
        _chip("版式", intel.layout_family, accent="#f79009"),
    ]
    if score_html:
        chips.append(score_html)

    st.markdown(
        f'<div class="page-intelligence-strip">'
        f'<div class="page-intelligence-title">{html.escape(intel.page_label)}</div>'
        f'<div class="page-intelligence-chips">{"".join(chips)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
