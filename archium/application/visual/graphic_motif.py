"""Compose GraphicMotif from concept / page kind (VQ-003)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archium.application.visual.typography_composition import infer_typography_page_kind
from archium.domain.visual.visual_concept import VisualMetaphor
from archium.domain.visual.visual_language.graphic_motif import (
    GraphicMotif,
    MarkerStyle,
    MotifType,
    StrokeStyle,
)
from archium.domain.visual.visual_language.typography_composition import TypographyPageKind

if TYPE_CHECKING:
    from archium.domain.slide import SlideSpec
    from archium.domain.visual.layout import LayoutPlan
    from archium.domain.visual.page_direction import PageDirection
    from archium.domain.visual.visual_concept import VisualConcept
    from archium.domain.visual.visual_intent import VisualIntent


_METAPHOR_MOTIF: dict[VisualMetaphor, MotifType] = {
    VisualMetaphor.FRAGMENT_TO_NETWORK: MotifType.FLOW_NODES,
    VisualMetaphor.EXISTING_TO_TRANSFORMATION: MotifType.BEFORE_AFTER_SLICE,
    VisualMetaphor.LAYERED_SITE: MotifType.CONTOUR,
    VisualMetaphor.CORE_TO_EXPANSION: MotifType.MODULE_INDEX,
    VisualMetaphor.PATH_TO_EXPERIENCE: MotifType.PATH_SEQUENCE,
    VisualMetaphor.MONUMENT_SINGLE: MotifType.QUIET_RULE,
    VisualMetaphor.BEFORE_AFTER_CUT: MotifType.BEFORE_AFTER_SLICE,
    VisualMetaphor.QUIET_ARGUMENT: MotifType.QUIET_RULE,
}

_MOTIF_VOCAB: dict[MotifType, list[str]] = {
    MotifType.AXIS_GRID: ["axis_line", "thin_rule", "section_index"],
    MotifType.FLOW_NODES: ["flow_line", "node", "circulation", "overlay_map"],
    MotifType.CONTOUR: ["overlay_map", "thin_rule", "axis_line"],
    MotifType.SECTION_CUT: ["section_index", "thin_rule", "transition_arrow"],
    MotifType.BEFORE_AFTER_SLICE: ["transition_arrow", "overlay_map", "thin_rule"],
    MotifType.MODULE_INDEX: ["node", "section_index", "thin_rule"],
    MotifType.PATH_SEQUENCE: ["flow_line", "node", "entrance", "circulation"],
    MotifType.QUIET_RULE: ["thin_rule", "section_index"],
}

_MOTIF_RULES: dict[MotifType, list[str]] = {
    MotifType.AXIS_GRID: [
        "Prefer vertical axis + sparse horizontal rules",
        "Do not place axis through drawing titles",
    ],
    MotifType.FLOW_NODES: [
        "Connect conflict nodes with continuous path",
        "Limit to max_marks circular nodes",
    ],
    MotifType.CONTOUR: [
        "Concentric soft frames behind site reading",
        "Keep opacity low so drawings stay primary",
    ],
    MotifType.SECTION_CUT: [
        "One cut index + thin rule near title",
        "Avoid dense hatch",
    ],
    MotifType.BEFORE_AFTER_SLICE: [
        "Gray existing vs accent intervention",
        "Use one transition arrow max",
    ],
    MotifType.MODULE_INDEX: [
        "Number modules, not decorate randomly",
        "Keep index typography small and tracked",
    ],
    MotifType.PATH_SEQUENCE: [
        "Start/end emphasis only",
        "Path continuity over icon clutter",
    ],
    MotifType.QUIET_RULE: [
        "One thin rule under title",
        "No axis unless section opener",
    ],
}


def compose_graphic_motif(
    *,
    slide: SlideSpec | None = None,
    layout_plan: LayoutPlan | None = None,
    visual_intent: VisualIntent | None = None,
    page_direction: PageDirection | None = None,
    concept: VisualConcept | None = None,
    page_kind: TypographyPageKind | None = None,
) -> GraphicMotif:
    """Pick a motif from VisualConcept metaphor, else page-kind defaults."""
    kind = page_kind or infer_typography_page_kind(
        slide=slide,
        layout_plan=layout_plan,
        visual_intent=visual_intent,
    )
    metaphor = None
    if concept is not None:
        metaphor = concept.visual_metaphor
    elif page_direction is not None and page_direction.visual_concept is not None:
        metaphor = page_direction.visual_concept.visual_metaphor
    elif (
        visual_intent is not None
        and visual_intent.page_direction is not None
        and visual_intent.page_direction.visual_concept is not None
    ):
        metaphor = visual_intent.page_direction.visual_concept.visual_metaphor

    motif_type = _METAPHOR_MOTIF.get(metaphor) if metaphor is not None else None
    if motif_type is None:
        motif_type = _default_motif_for_page_kind(kind)

    vocab = list(_MOTIF_VOCAB[motif_type])
    stroke, marker, bias, repetition, max_marks = _style_for(motif_type, kind)
    return GraphicMotif(
        motif_id=f"{motif_type.value}:{kind.value}",
        motif_type=motif_type,
        usage_rules=list(_MOTIF_RULES.get(motif_type, [])),
        stroke=stroke,
        marker=marker,
        shape_vocabulary=vocab,
        corner_language="sharp" if motif_type != MotifType.CONTOUR else "soft",
        repetition_rule=repetition,
        color_role_bias=bias,
        max_marks=max_marks,
        source=f"graphic_motif:{motif_type.value}",
    )


def merge_motif_into_primitives(
    primitive_ids: list[str],
    motif: GraphicMotif | None,
) -> list[str]:
    """Prefer motif vocabulary while keeping existing ids (capped)."""
    if motif is None:
        return list(primitive_ids)
    merged: list[str] = []
    for pid in [*motif.shape_vocabulary, *primitive_ids]:
        if pid not in merged:
            merged.append(pid)
        if len(merged) >= max(6, motif.max_marks + 2):
            break
    return merged


def _default_motif_for_page_kind(kind: TypographyPageKind) -> MotifType:
    return {
        TypographyPageKind.COVER: MotifType.QUIET_RULE,
        TypographyPageKind.SECTION: MotifType.AXIS_GRID,
        TypographyPageKind.THESIS: MotifType.FLOW_NODES,
        TypographyPageKind.METRIC: MotifType.MODULE_INDEX,
        TypographyPageKind.CLOSING: MotifType.QUIET_RULE,
        TypographyPageKind.DEFAULT: MotifType.QUIET_RULE,
    }.get(kind, MotifType.QUIET_RULE)


def _style_for(
    motif_type: MotifType,
    kind: TypographyPageKind,
) -> tuple[StrokeStyle, MarkerStyle, str, str, int]:
    if motif_type == MotifType.FLOW_NODES:
        return (
            StrokeStyle(color_token="accent", width_pt=1.0, dash="solid", opacity=0.85),
            MarkerStyle(shape="circle", size_pt=9, fill_token="accent"),
            "conflict",
            "measured",
            5 if kind == TypographyPageKind.THESIS else 4,
        )
    if motif_type == MotifType.AXIS_GRID:
        return (
            StrokeStyle(color_token="primary", width_pt=0.6, dash="solid", opacity=0.55),
            MarkerStyle(shape="none", size_pt=6, fill_token=None),
            "neutral",
            "sparse",
            3,
        )
    if motif_type == MotifType.CONTOUR:
        return (
            StrokeStyle(color_token="primary", width_pt=0.7, dash="dot", opacity=0.45),
            MarkerStyle(shape="none", size_pt=6, fill_token=None),
            "existing",
            "sparse",
            3,
        )
    if motif_type == MotifType.BEFORE_AFTER_SLICE:
        return (
            StrokeStyle(color_token="accent", width_pt=1.1, dash="solid", opacity=0.9),
            MarkerStyle(shape="square", size_pt=7, fill_token="accent"),
            "intervention",
            "sparse",
            3,
        )
    if motif_type == MotifType.PATH_SEQUENCE:
        return (
            StrokeStyle(color_token="accent", width_pt=1.0, dash="solid", opacity=0.8),
            MarkerStyle(shape="circle", size_pt=8, fill_token="accent"),
            "intervention",
            "measured",
            5,
        )
    if motif_type == MotifType.MODULE_INDEX:
        return (
            StrokeStyle(color_token="primary", width_pt=0.5, dash="solid", opacity=0.6),
            MarkerStyle(shape="cross", size_pt=7, fill_token="accent"),
            "accent",
            "sparse",
            4,
        )
    if motif_type == MotifType.SECTION_CUT:
        return (
            StrokeStyle(color_token="primary", width_pt=0.9, dash="dash", opacity=0.75),
            MarkerStyle(shape="square", size_pt=6, fill_token=None),
            "neutral",
            "sparse",
            2,
        )
    # QUIET_RULE
    return (
        StrokeStyle(color_token="accent", width_pt=0.8, dash="solid", opacity=0.9),
        MarkerStyle(shape="none", size_pt=6, fill_token=None),
        "accent",
        "sparse",
        1,
    )
