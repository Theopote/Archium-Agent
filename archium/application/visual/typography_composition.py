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
    section_index: int | None = None,
) -> TypographyComposition:
    """Split a title into multi-scale runs for expressive page kinds (v1.1)."""
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

    arrangement = select_title_arrangement(cleaned, page_kind=page_kind)
    letter_spacing = {
        TypographyPageKind.COVER: 0.06,
        TypographyPageKind.SECTION: 0.08,
        TypographyPageKind.THESIS: 0.04,
        TypographyPageKind.CLOSING: 0.1,
        TypographyPageKind.METRIC: 0.02,
    }.get(page_kind, 0.0)

    size_boost = {
        TypographyPageKind.COVER: 1.35,
        TypographyPageKind.THESIS: 1.25,
        TypographyPageKind.SECTION: 1.15,
        TypographyPageKind.CLOSING: 1.3,
        TypographyPageKind.METRIC: 1.0,
    }.get(page_kind, 1.0)
    boosted = round(base_size_pt * size_boost, 1)

    if arrangement == TypographyArrangement.INDEX_TITLE:
        return _compose_index_title(
            cleaned,
            page_kind=page_kind,
            base_size_pt=boosted,
            letter_spacing=letter_spacing,
            section_index=section_index,
        )
    if arrangement == TypographyArrangement.OUTLINE_STATEMENT:
        return _compose_outline_statement(
            cleaned,
            page_kind=page_kind,
            base_size_pt=boosted,
            letter_spacing=letter_spacing,
        )
    if arrangement == TypographyArrangement.VERTICAL_EDGE:
        return _compose_vertical_edge(
            cleaned,
            page_kind=page_kind,
            base_size_pt=boosted,
            letter_spacing=letter_spacing,
        )
    if arrangement == TypographyArrangement.SPLIT_KEYWORD:
        return _compose_split_keyword(
            cleaned,
            page_kind=page_kind,
            base_size_pt=boosted,
            letter_spacing=letter_spacing,
        )
    if arrangement == TypographyArrangement.GIANT_BACKGROUND:
        return _compose_giant_background(
            cleaned,
            page_kind=page_kind,
            base_size_pt=boosted,
            letter_spacing=letter_spacing,
        )

    # Legacy stacked / inline path (connector-aware).
    runs = _split_title_runs(cleaned, page_kind=page_kind)
    ghost = None
    ghost_scale = 5.0
    ghost_opacity = 0.07
    if page_kind == TypographyPageKind.CLOSING:
        ghost = _ghost_fragment(cleaned)
        ghost_scale = 6.0
        ghost_opacity = 0.06
    elif page_kind == TypographyPageKind.THESIS:
        ghost = _ghost_fragment(cleaned)
        ghost_scale = 5.0
        ghost_opacity = 0.07
    elif page_kind == TypographyPageKind.COVER and len(cleaned) < 16:
        ghost = _ghost_fragment(cleaned)
        ghost_scale = 3.2
        ghost_opacity = 0.045

    return TypographyComposition(
        page_kind=page_kind,
        arrangement=(
            TypographyArrangement.STACKED
            if any(run.break_after for run in runs)
            else TypographyArrangement.INLINE
        ),
        runs=runs,
        letter_spacing_em=letter_spacing,
        base_size_pt=boosted,
        ghost_text=ghost,
        ghost_size_scale=ghost_scale,
        ghost_opacity=ghost_opacity,
        title_band_height_ratio=_band_ratio(page_kind),
    )


def select_title_arrangement(
    text: str,
    *,
    page_kind: TypographyPageKind,
) -> TypographyArrangement:
    """Pick one of the six v1.1 recipes from page kind + title shape."""
    cleaned = (text or "").strip()
    if page_kind == TypographyPageKind.SECTION:
        return TypographyArrangement.INDEX_TITLE
    if page_kind == TypographyPageKind.METRIC:
        return TypographyArrangement.METRIC_MONUMENT
    if page_kind == TypographyPageKind.COVER:
        if len(cleaned) <= 4:
            return TypographyArrangement.OUTLINE_STATEMENT
        if len(cleaned) <= 10:
            return TypographyArrangement.GIANT_BACKGROUND
        return TypographyArrangement.SPLIT_KEYWORD
    if page_kind == TypographyPageKind.THESIS:
        # Connector titles keep split_keyword so hero/support/connector roles survive.
        if not _CONNECTOR.search(cleaned) and len(cleaned) <= 6:
            return TypographyArrangement.OUTLINE_STATEMENT
        return TypographyArrangement.SPLIT_KEYWORD
    if page_kind == TypographyPageKind.CLOSING:
        if len(cleaned) <= 6:
            return TypographyArrangement.VERTICAL_EDGE
        return TypographyArrangement.GIANT_BACKGROUND
    return TypographyArrangement.STACKED


def compose_metric_typography(
    text: str,
    *,
    base_size_pt: float,
) -> TypographyComposition:
    """Make the number the visual protagonist; label stays small (metric_monument)."""
    cleaned = (text or "").strip()
    if not cleaned:
        return TypographyComposition(
            page_kind=TypographyPageKind.METRIC,
            arrangement=TypographyArrangement.METRIC_MONUMENT,
            runs=[],
            base_size_pt=base_size_pt,
            title_band_height_ratio=0.42,
        )
    match = _METRIC_HEAD.match(cleaned)
    if match is None:
        return TypographyComposition(
            page_kind=TypographyPageKind.METRIC,
            arrangement=TypographyArrangement.METRIC_MONUMENT,
            runs=[
                TypographyRunSpec(
                    text=cleaned,
                    semantic_role=TypographyRunRole.METRIC_VALUE,
                    size_scale=2.2,
                    font_weight=700,
                    color_token="accent",
                    tracking_em=0.02,
                )
            ],
            base_size_pt=base_size_pt,
            title_band_height_ratio=0.42,
        )
    value = match.group("value") or ""
    unit = match.group("unit") or ""
    label = (match.group("label") or "").strip()
    runs: list[TypographyRunSpec] = [
        TypographyRunSpec(
            text=value,
            semantic_role=TypographyRunRole.METRIC_VALUE,
            size_scale=2.8,
            font_weight=700,
            color_token="accent",
            tracking_em=-0.02,
            break_after=bool(unit or label),
        )
    ]
    if unit:
        runs.append(
            TypographyRunSpec(
                text=unit,
                semantic_role=TypographyRunRole.METRIC_UNIT,
                size_scale=0.9,
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
                size_scale=0.5,
                font_weight=400,
                color_token="muted_text",
                tracking_em=0.08,
                uppercase=False,
            )
        )
    return TypographyComposition(
        page_kind=TypographyPageKind.METRIC,
        arrangement=TypographyArrangement.METRIC_MONUMENT,
        runs=runs,
        letter_spacing_em=0.02,
        base_size_pt=base_size_pt,
        title_band_height_ratio=0.42,
    )


def composition_to_text_runs(
    composition: TypographyComposition,
    *,
    design_system: DesignSystem,
    fallback_color: str,
    fallback_weight: int,
) -> list[TextRun]:
    """Materialize composition spans as RenderScene TextRuns (v1.1 fields)."""
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
        tracking = run.tracking_em
        if tracking is None and composition.letter_spacing_em:
            tracking = composition.letter_spacing_em
        out.append(
            TextRun(
                text=text,
                font_size=round(base * run.size_scale, 1),
                font_weight=weight,
                font_style="italic" if run.italic else "normal",
                color=color,
                color_token=run.color_token or "",
                letter_spacing=tracking,
                opacity=run.opacity,
                outline=run.outline,
                outline_width_pt=run.outline_width_pt,
                outline_color=color if run.outline else "",
                fill_enabled=run.fill_enabled,
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
        return True
    if role == LayoutElementRole.LEAD_STATEMENT and page_kind in {
        TypographyPageKind.COVER,
        TypographyPageKind.THESIS,
        TypographyPageKind.CLOSING,
    }:
        return True
    return False


def _compose_split_keyword(
    text: str,
    *,
    page_kind: TypographyPageKind,
    base_size_pt: float,
    letter_spacing: float,
) -> TypographyComposition:
    """Amplify the last keyword / punch phrase 2–3× with accent color."""
    runs = _split_title_runs(text, page_kind=page_kind)
    # Force last hero punch larger + accent.
    for index in range(len(runs) - 1, -1, -1):
        if runs[index].semantic_role == TypographyRunRole.HERO_WORD:
            runs[index] = runs[index].model_copy(
                update={
                    "size_scale": max(runs[index].size_scale, 2.2),
                    "color_token": "accent",
                    "font_weight": 700,
                    "tracking_em": 0.02,
                }
            )
            break
    if len(runs) >= 2:
        for index, run in enumerate(runs[:-1]):
            if run.semantic_role != TypographyRunRole.CONNECTOR:
                runs[index] = run.model_copy(
                    update={
                        "size_scale": min(run.size_scale, 0.85),
                        "break_after": True,
                        "opacity": 0.9,
                    }
                )
    ghost = None
    ghost_scale = 5.0
    ghost_opacity = 0.07
    if page_kind in {TypographyPageKind.THESIS, TypographyPageKind.CLOSING}:
        ghost = _ghost_fragment(text)
        ghost_scale = 5.5 if page_kind == TypographyPageKind.THESIS else 6.0
        ghost_opacity = 0.06
    elif page_kind == TypographyPageKind.COVER and len(text) < 16:
        ghost = _ghost_fragment(text)
        ghost_scale = 3.2
        ghost_opacity = 0.045
    return TypographyComposition(
        page_kind=page_kind,
        arrangement=TypographyArrangement.SPLIT_KEYWORD,
        runs=runs,
        letter_spacing_em=letter_spacing,
        base_size_pt=base_size_pt,
        ghost_text=ghost,
        ghost_size_scale=ghost_scale,
        ghost_opacity=ghost_opacity,
        title_band_height_ratio=_band_ratio(page_kind, tall=True),
    )


def _compose_giant_background(
    text: str,
    *,
    page_kind: TypographyPageKind,
    base_size_pt: float,
    letter_spacing: float,
) -> TypographyComposition:
    ghost = _ghost_fragment(text) or (text[:4] if text else None)
    runs = _split_title_runs(text, page_kind=page_kind)
    return TypographyComposition(
        page_kind=page_kind,
        arrangement=TypographyArrangement.GIANT_BACKGROUND,
        runs=runs,
        letter_spacing_em=letter_spacing,
        base_size_pt=base_size_pt,
        ghost_text=ghost,
        ghost_size_scale=6.5 if page_kind == TypographyPageKind.CLOSING else 5.5,
        ghost_opacity=0.055,
        title_band_height_ratio=_band_ratio(page_kind, tall=True),
    )


def _compose_index_title(
    text: str,
    *,
    page_kind: TypographyPageKind,
    base_size_pt: float,
    letter_spacing: float,
    section_index: int | None,
) -> TypographyComposition:
    index_n = section_index if section_index and section_index > 0 else 1
    index_label = f"{index_n:02d}"
    # Prefer first line as Chinese title; optional english after separator.
    zh, en = _split_bilingual(text)
    runs: list[TypographyRunSpec] = [
        TypographyRunSpec(
            text=index_label,
            semantic_role=TypographyRunRole.INDEX,
            size_scale=0.55,
            font_weight=500,
            color_token="accent",
            tracking_em=0.18,
            break_after=True,
        ),
        TypographyRunSpec(
            text=zh,
            semantic_role=TypographyRunRole.HERO_WORD,
            size_scale=1.45,
            font_weight=700,
            color_token="primary",
            tracking_em=0.06,
            break_after=bool(en),
        ),
    ]
    if en:
        runs.append(
            TypographyRunSpec(
                text=en,
                semantic_role=TypographyRunRole.LABEL,
                size_scale=0.45,
                font_weight=400,
                color_token="muted_text",
                tracking_em=0.16,
                uppercase=True,
            )
        )
    return TypographyComposition(
        page_kind=page_kind,
        arrangement=TypographyArrangement.INDEX_TITLE,
        runs=runs,
        letter_spacing_em=letter_spacing,
        base_size_pt=base_size_pt,
        title_band_height_ratio=0.28,
    )


def _compose_outline_statement(
    text: str,
    *,
    page_kind: TypographyPageKind,
    base_size_pt: float,
    letter_spacing: float,
) -> TypographyComposition:
    """Hollow / outline hero keyword + quiet support line."""
    # Prefer the shortest punch word after connectors.
    parts = [p for p in _CONNECTOR.split(text) if p and not _CONNECTOR.fullmatch(p)]
    hero = parts[-1].strip() if parts else text
    support = text.replace(hero, "").strip(" —-:：/／")
    if len(hero) > 8:
        hero = hero[-min(4, len(hero)) :]
        support = text[: -len(hero)].strip() or support
    runs: list[TypographyRunSpec] = [
        TypographyRunSpec(
            text=hero,
            semantic_role=TypographyRunRole.HERO_WORD,
            size_scale=2.6,
            font_weight=300,
            color_token="primary",
            tracking_em=0.14,
            outline=True,
            outline_width_pt=1.2,
            fill_enabled=False,
            opacity=0.92,
            break_after=bool(support),
        )
    ]
    if support:
        runs.append(
            TypographyRunSpec(
                text=support,
                semantic_role=TypographyRunRole.SUPPORT_WORD,
                size_scale=0.55,
                font_weight=400,
                color_token="muted_text",
                tracking_em=0.04,
                opacity=0.85,
            )
        )
    return TypographyComposition(
        page_kind=page_kind,
        arrangement=TypographyArrangement.OUTLINE_STATEMENT,
        runs=runs,
        letter_spacing_em=letter_spacing,
        base_size_pt=base_size_pt,
        ghost_text=_ghost_fragment(hero),
        ghost_size_scale=4.0,
        ghost_opacity=0.04,
        title_band_height_ratio=0.36,
    )


def _compose_vertical_edge(
    text: str,
    *,
    page_kind: TypographyPageKind,
    base_size_pt: float,
    letter_spacing: float,
) -> TypographyComposition:
    compact = re.sub(r"\s+", "", text)
    # One character per line for magazine edge title.
    runs: list[TypographyRunSpec] = []
    chars = list(compact[:8]) if compact else list(text[:8])
    for index, ch in enumerate(chars):
        runs.append(
            TypographyRunSpec(
                text=ch,
                semantic_role=TypographyRunRole.HERO_WORD,
                size_scale=1.35,
                font_weight=600,
                color_token="primary",
                tracking_em=0.2,
                break_after=index < len(chars) - 1,
            )
        )
    return TypographyComposition(
        page_kind=page_kind,
        arrangement=TypographyArrangement.VERTICAL_EDGE,
        runs=runs,
        letter_spacing_em=max(letter_spacing, 0.12),
        base_size_pt=base_size_pt,
        rotation_deg=-90.0,
        title_band_height_ratio=0.55,
    )


def _band_ratio(page_kind: TypographyPageKind, *, tall: bool = False) -> float:
    base = {
        TypographyPageKind.COVER: 0.32,
        TypographyPageKind.SECTION: 0.26,
        TypographyPageKind.THESIS: 0.34,
        TypographyPageKind.CLOSING: 0.36,
        TypographyPageKind.METRIC: 0.4,
    }.get(page_kind, 0.22)
    return min(0.5, base + (0.06 if tall else 0.0))


def _split_bilingual(text: str) -> tuple[str, str]:
    for sep in ("\n", "——", "—", " / ", "/", "：", ":"):
        if sep in text:
            left, right = text.split(sep, 1)
            left, right = left.strip(), right.strip()
            if left and right:
                # Prefer latin on the right as english label.
                if re.search(r"[A-Za-z]", right) and not re.search(r"[A-Za-z]", left):
                    return left, right
                if re.search(r"[A-Za-z]", left) and not re.search(r"[A-Za-z]", right):
                    return right, left
                return left, right
    return text, ""


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
