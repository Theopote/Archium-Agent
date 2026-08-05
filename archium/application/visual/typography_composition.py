"""Build TypographyComposition for Phase-1 expressive pages (VQ-001).

Deterministic, rule-first — no LLM. Wired by RenderSceneCompiler so PPTX
receives multi-scale TextRuns (hero words, connectors, giant metrics, ghost).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from archium.domain.enums import SlideType
from archium.domain.visual.enums import ContinuityRole, LayoutElementRole, LayoutFamily
from archium.domain.visual.render_scene import TextRun
from archium.domain.visual.visual_language.typography_composition import (
    TypographyArrangement,
    TypographyComposition,
    TypographyPageKind,
    TypographyRunRole,
    TypographyRunSpec,
)

if TYPE_CHECKING:
    from archium.domain.slide import SlideSpec
    from archium.domain.visual.design_system import DesignSystem
    from archium.domain.visual.layout import LayoutPlan
    from archium.domain.visual.visual_intent import VisualIntent

# Small Chinese connectors stay restrained; flanking words become the heroes.
_CONNECTOR = re.compile(
    r"(不是|而是|不止是|不只是|并非|而是|与|及|和|——|—|：|:|/|／)"
)
_METRIC_HEAD = re.compile(
    r"^\s*(?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|％|㎡|m²|km|公顷|万㎡|万人|亿|万吨|万|亿元|年|层|床)?\s*"
    r"(?P<label>.*)$",
    re.DOTALL,
)
_COVER_TITLES = frozenset({"封面", "封面页", "开篇", "项目封面", "title", "cover"})
_CLOSING_TITLES = frozenset({"结尾", "结语", "总结", "致谢", "closing", "thank you", "谢谢"})
_THESIS_HINTS = frozenset(
    {
        "核心理念",
        "设计理念",
        "愿景",
        "主张",
        "概念",
        "总图策略",
        "设计策略",
        "更新不是修补",
        "thesis",
        "concept",
        "vision",
    }
)
_SECTION_HINTS = frozenset(
    {
        "章节",
        "篇章",
        "第一部分",
        "第二部分",
        "第三部分",
        "现状",
        "问题",
        "策略",
        "实施",
        "section",
    }
)


def infer_typography_page_kind(
    *,
    slide: SlideSpec | None,
    layout_plan: LayoutPlan | None = None,
    visual_intent: VisualIntent | None = None,
) -> TypographyPageKind:
    """Map slide / family / pacing into one of the five expressive page kinds."""
    title = ""
    slide_type: SlideType | None = None
    if slide is not None:
        title = (slide.title or "").strip()
        slide_type = slide.slide_type

    family = layout_plan.layout_family if layout_plan is not None else None
    variant = (layout_plan.layout_variant or "").strip().lower() if layout_plan else ""
    continuity = visual_intent.continuity_role if visual_intent is not None else None

    title_l = title.lower()
    if (
        slide_type == SlideType.TITLE
        or continuity == ContinuityRole.OPENING
        or title in _COVER_TITLES
        or title_l in _COVER_TITLES
        or (family == LayoutFamily.HERO and variant in {"", "full_bleed", "overlay"})
    ):
        return TypographyPageKind.COVER

    if (
        slide_type == SlideType.CLOSING
        or continuity == ContinuityRole.CLOSING
        or title in _CLOSING_TITLES
        or title_l in _CLOSING_TITLES
    ):
        return TypographyPageKind.CLOSING

    if family == LayoutFamily.METRIC_DASHBOARD or slide_type == SlideType.DATA:
        return TypographyPageKind.METRIC

    if (
        variant in {"monument", "section_opener"}
        or any(hint in title for hint in _THESIS_HINTS)
        or continuity == ContinuityRole.CLIMAX
    ):
        return TypographyPageKind.THESIS

    if (
        slide_type == SlideType.SECTION
        or continuity == ContinuityRole.SECTION_OPENING
        or any(hint in title for hint in _SECTION_HINTS)
        or variant == "section_opener"
    ):
        return TypographyPageKind.SECTION

    return TypographyPageKind.DEFAULT


def compose_title_typography(
    text: str,
    *,
    page_kind: TypographyPageKind,
    base_size_pt: float,
) -> TypographyComposition:
    """Split a title into multi-scale runs for expressive page kinds."""
    cleaned = (text or "").strip()
    if not cleaned:
        return TypographyComposition(page_kind=page_kind, runs=[])

    if page_kind == TypographyPageKind.DEFAULT:
        return TypographyComposition(
            page_kind=page_kind,
            arrangement=TypographyArrangement.INLINE,
            runs=[
                TypographyRunSpec(
                    text=cleaned,
                    semantic_role=TypographyRunRole.SUPPORT_WORD,
                    size_scale=1.0,
                )
            ],
            base_size_pt=base_size_pt,
        )

    letter_spacing = {
        TypographyPageKind.COVER: 0.06,
        TypographyPageKind.SECTION: 0.08,
        TypographyPageKind.THESIS: 0.04,
        TypographyPageKind.CLOSING: 0.1,
        TypographyPageKind.METRIC: 0.02,
    }.get(page_kind, 0.0)

    runs = _split_title_runs(cleaned, page_kind=page_kind)
    ghost = None
    ghost_scale = 5.0
    ghost_opacity = 0.07
    if page_kind in {
        TypographyPageKind.COVER,
        TypographyPageKind.THESIS,
        TypographyPageKind.CLOSING,
    }:
        ghost = _ghost_fragment(cleaned)
        if page_kind == TypographyPageKind.CLOSING:
            ghost_scale = 6.0
            ghost_opacity = 0.06
        elif page_kind == TypographyPageKind.COVER:
            ghost_scale = 5.5
            ghost_opacity = 0.08

    # Cover / closing prefer slightly larger base.
    size_boost = {
        TypographyPageKind.COVER: 1.35,
        TypographyPageKind.THESIS: 1.25,
        TypographyPageKind.SECTION: 1.15,
        TypographyPageKind.CLOSING: 1.3,
        TypographyPageKind.METRIC: 1.0,
    }.get(page_kind, 1.0)

    return TypographyComposition(
        page_kind=page_kind,
        arrangement=(
            TypographyArrangement.STACKED
            if any(run.break_after for run in runs)
            else TypographyArrangement.INLINE
        ),
        runs=runs,
        letter_spacing_em=letter_spacing,
        base_size_pt=round(base_size_pt * size_boost, 1),
        ghost_text=ghost,
        ghost_size_scale=ghost_scale,
        ghost_opacity=ghost_opacity,
    )


def compose_metric_typography(
    text: str,
    *,
    base_size_pt: float,
) -> TypographyComposition:
    """Make the number the visual protagonist; label stays small."""
    cleaned = (text or "").strip()
    if not cleaned:
        return TypographyComposition(
            page_kind=TypographyPageKind.METRIC,
            arrangement=TypographyArrangement.METRIC_STACK,
            runs=[],
            base_size_pt=base_size_pt,
        )
    match = _METRIC_HEAD.match(cleaned)
    if match is None:
        return TypographyComposition(
            page_kind=TypographyPageKind.METRIC,
            arrangement=TypographyArrangement.METRIC_STACK,
            runs=[
                TypographyRunSpec(
                    text=cleaned,
                    semantic_role=TypographyRunRole.METRIC_VALUE,
                    size_scale=1.8,
                    font_weight=700,
                    color_token="accent",
                )
            ],
            base_size_pt=base_size_pt,
        )
    value = match.group("value") or ""
    unit = match.group("unit") or ""
    label = (match.group("label") or "").strip()
    runs: list[TypographyRunSpec] = [
        TypographyRunSpec(
            text=value,
            semantic_role=TypographyRunRole.METRIC_VALUE,
            size_scale=2.4,
            font_weight=700,
            color_token="accent",
            break_after=bool(unit or label),
        )
    ]
    if unit:
        runs.append(
            TypographyRunSpec(
                text=unit,
                semantic_role=TypographyRunRole.METRIC_UNIT,
                size_scale=0.85,
                font_weight=600,
                color_token="primary_text",
                break_after=bool(label),
            )
        )
    if label:
        runs.append(
            TypographyRunSpec(
                text=label,
                semantic_role=TypographyRunRole.LABEL,
                size_scale=0.55,
                font_weight=400,
                color_token="muted_text",
                tracking_em=0.06,
            )
        )
    return TypographyComposition(
        page_kind=TypographyPageKind.METRIC,
        arrangement=TypographyArrangement.METRIC_STACK,
        runs=runs,
        letter_spacing_em=0.02,
        base_size_pt=base_size_pt,
    )


def composition_to_text_runs(
    composition: TypographyComposition,
    *,
    design_system: DesignSystem,
    fallback_color: str,
    fallback_weight: int,
) -> list[TextRun]:
    """Materialize composition spans as RenderScene TextRuns."""
    if not composition.runs:
        return []
    base = composition.base_size_pt or 20.0
    colors = design_system.colors
    out: list[TextRun] = []
    for run in composition.runs:
        text = run.text.upper() if run.uppercase else run.text
        if run.break_after and not text.endswith("\n"):
            text = f"{text}\n"
        color = fallback_color
        if run.color_token:
            try:
                color = colors.resolve(run.color_token)
            except KeyError:
                color = fallback_color
        weight = run.font_weight if run.font_weight is not None else fallback_weight
        if run.semantic_role in {
            TypographyRunRole.HERO_WORD,
            TypographyRunRole.METRIC_VALUE,
        }:
            weight = max(weight, 700)
        out.append(
            TextRun(
                text=text,
                font_size=round(base * run.size_scale, 1),
                font_weight=weight,
                color=color,
                color_token=run.color_token or "",
            )
        )
    return out


def should_compose_element(
    role: LayoutElementRole,
    page_kind: TypographyPageKind,
) -> bool:
    if role == LayoutElementRole.TITLE and page_kind != TypographyPageKind.DEFAULT:
        return True
    if role == LayoutElementRole.METRIC and page_kind in {
        TypographyPageKind.METRIC,
        TypographyPageKind.COVER,
        TypographyPageKind.THESIS,
        TypographyPageKind.CLOSING,
        TypographyPageKind.DEFAULT,
    }:
        # Always compose metrics — numbers should dominate when present.
        return True
    if role == LayoutElementRole.LEAD_STATEMENT and page_kind in {
        TypographyPageKind.COVER,
        TypographyPageKind.THESIS,
        TypographyPageKind.CLOSING,
    }:
        return True
    return False


def _split_title_runs(
    text: str,
    *,
    page_kind: TypographyPageKind,
) -> list[TypographyRunSpec]:
    # Prefer connector-aware split:「更新」不是「修补」
    parts = _CONNECTOR.split(text)
    if len(parts) >= 3 and any(parts[i] for i in range(1, len(parts), 2)):
        return _runs_from_connector_parts(parts, page_kind=page_kind)

    # Punctuation / newline stack.
    for sep in ("\n", "——", "—", "：", ":", "、", " / ", "/"):
        if sep in text:
            chunks = [chunk.strip() for chunk in text.split(sep) if chunk.strip()]
            if len(chunks) >= 2:
                return _runs_from_chunks(chunks, page_kind=page_kind, sep=sep)

    # Short monumental word — single hero.
    if len(text) <= 6:
        return [
            TypographyRunSpec(
                text=text,
                semantic_role=TypographyRunRole.HERO_WORD,
                size_scale=_hero_scale(page_kind),
                font_weight=700,
                color_token="primary",
            )
        ]

    # Medium title: amplify last 2–4 characters as the punch.
    punch = min(4, max(2, len(text) // 3))
    head, tail = text[:-punch], text[-punch:]
    return [
        TypographyRunSpec(
            text=head,
            semantic_role=TypographyRunRole.SUPPORT_WORD,
            size_scale=0.72 if page_kind != TypographyPageKind.SECTION else 0.85,
            font_weight=500,
            color_token="primary_text",
            break_after=page_kind in {TypographyPageKind.COVER, TypographyPageKind.THESIS},
        ),
        TypographyRunSpec(
            text=tail,
            semantic_role=TypographyRunRole.HERO_WORD,
            size_scale=_hero_scale(page_kind),
            font_weight=700,
            color_token="primary",
        ),
    ]


def _runs_from_connector_parts(
    parts: list[str],
    *,
    page_kind: TypographyPageKind,
) -> list[TypographyRunSpec]:
    runs: list[TypographyRunSpec] = []
    hero = _hero_scale(page_kind)
    for index, part in enumerate(parts):
        if not part:
            continue
        is_connector = bool(_CONNECTOR.fullmatch(part))
        if is_connector:
            runs.append(
                TypographyRunSpec(
                    text=part,
                    semantic_role=TypographyRunRole.CONNECTOR,
                    size_scale=0.55,
                    font_weight=400,
                    color_token="muted_text",
                    break_after=page_kind
                    in {
                        TypographyPageKind.COVER,
                        TypographyPageKind.THESIS,
                        TypographyPageKind.CLOSING,
                    },
                )
            )
            continue
        # Alternate: first and last chunks are heroes.
        is_hero = index == 0 or index == len(parts) - 1 or len(part) <= 4
        runs.append(
            TypographyRunSpec(
                text=part,
                semantic_role=(
                    TypographyRunRole.HERO_WORD if is_hero else TypographyRunRole.SUPPORT_WORD
                ),
                size_scale=hero if is_hero else 0.7,
                font_weight=700 if is_hero else 500,
                color_token="primary" if is_hero else "primary_text",
            )
        )
    return runs or [
        TypographyRunSpec(
            text="".join(parts),
            semantic_role=TypographyRunRole.HERO_WORD,
            size_scale=hero,
            font_weight=700,
        )
    ]


def _runs_from_chunks(
    chunks: list[str],
    *,
    page_kind: TypographyPageKind,
    sep: str,
) -> list[TypographyRunSpec]:
    hero = _hero_scale(page_kind)
    runs: list[TypographyRunSpec] = []
    for index, chunk in enumerate(chunks):
        is_last = index == len(chunks) - 1
        scale = hero if index == 0 or (is_last and len(chunks) == 2) else 0.75
        if index == len(chunks) - 1 and len(chunks) > 2:
            scale = hero
        runs.append(
            TypographyRunSpec(
                text=chunk,
                semantic_role=(
                    TypographyRunRole.HERO_WORD if scale >= hero * 0.95 else TypographyRunRole.SUPPORT_WORD
                ),
                size_scale=scale,
                font_weight=700 if scale >= hero * 0.95 else 500,
                color_token="primary" if scale >= hero * 0.95 else "secondary_text",
                break_after=not is_last,
            )
        )
        # Keep slash-style separators only when not stacking.
        if not is_last and sep.strip() in {"/", "／"} and page_kind == TypographyPageKind.SECTION:
            runs[-1] = runs[-1].model_copy(update={"break_after": False})
            runs.append(
                TypographyRunSpec(
                    text=f" {sep.strip()} ",
                    semantic_role=TypographyRunRole.CONNECTOR,
                    size_scale=0.5,
                    font_weight=400,
                    color_token="muted_text",
                )
            )
    return runs


def _hero_scale(page_kind: TypographyPageKind) -> float:
    return {
        TypographyPageKind.COVER: 1.55,
        TypographyPageKind.THESIS: 1.7,
        TypographyPageKind.SECTION: 1.35,
        TypographyPageKind.CLOSING: 1.6,
        TypographyPageKind.METRIC: 1.2,
    }.get(page_kind, 1.2)


def _ghost_fragment(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 2:
        return None
    # Prefer first 2–4 CJK chars / latin word stem.
    if re.search(r"[\u4e00-\u9fff]", compact):
        return compact[: min(4, len(compact))]
    token = compact.split()[0] if " " in text else compact
    return token[: min(8, len(token))].upper()
