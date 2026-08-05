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


def apply_graphic_motif_to_scene(
    scene: object,
    motif: GraphicMotif | None,
    *,
    color_story: object | None = None,
    accent_hex: str | None = None,
) -> object:
    """Materialize motif geometry on RenderScene when LayoutPlan lacked vl_motif_*.

    Idempotent: skips if motif nodes already present (from plan inject or prior apply).
    VQ-004: flow/path motifs emit ConnectorNode + FreeformNode (not only rectangles).
    """
    from archium.domain.visual.render_scene import (
        ConnectorEndpoint,
        ConnectorNode,
        FreeformNode,
        Point,
        RenderScene,
        ShapeNode,
        refresh_connector_geometry,
        refresh_freeform_geometry,
    )
    from archium.domain.visual.visual_language.color_story import NAMED_SWATCHES, ColorStory
    from archium.domain.visual.visual_language.graphic_motif import MotifType

    if motif is None or motif.max_marks <= 0 or not isinstance(scene, RenderScene):
        return scene
    tag = f"graphic_motif:{motif.motif_type.value}"
    prior_motif_nodes = any(
        str(getattr(n, "id", "")).startswith("vl_motif_") for n in scene.nodes
    )
    has_path_freeform = any(
        str(getattr(n, "id", "")) == "vl_motif_path_poly" for n in scene.nodes
    )
    # Idempotent only when the same motif is already fully materialized. Allow
    # re-apply for PATH_SEQUENCE when freeform was skipped (budget < 3 centers).
    if tag in scene.warnings and not (
        motif.motif_type == MotifType.PATH_SEQUENCE and not has_path_freeform
    ):
        return scene
    # Replace weaker/prior motif geometry when upgrading motif type on re-apply.
    if prior_motif_nodes or (tag in scene.warnings and not has_path_freeform):
        cleaned = [
            n
            for n in scene.nodes
            if not str(getattr(n, "id", "")).startswith("vl_motif_")
        ]
        cleaned_warnings = [
            w
            for w in scene.warnings
            if not str(w).startswith("graphic_motif:")
            and str(w) not in {"vq4_connector_motif", "vq4_freeform_motif"}
        ]
        scene = scene.model_copy(update={"nodes": cleaned, "warnings": cleaned_warnings})

    stroke_hex = accent_hex or NAMED_SWATCHES.get("axis_line", "#2C2C2C")
    if isinstance(color_story, ColorStory):
        bias_name = color_story.roles.get(motif.color_role_bias)
        if bias_name:
            stroke_hex = (
                bias_name
                if bias_name.startswith("#")
                else NAMED_SWATCHES.get(bias_name, stroke_hex)
            )
        if motif.stroke.color_token == "accent":
            for role in ("conflict", "intervention", "accent"):
                name = color_story.roles.get(role)
                if not name:
                    continue
                stroke_hex = name if name.startswith("#") else NAMED_SWATCHES.get(name, stroke_hex)
                break

    nodes: list[object] = []
    marks = 0
    max_marks = motif.max_marks
    # Freeform polyline needs ≥3 centers; never let a sparse budget collapse a path
    # into a 2-node segment (common when non-P0 grammar floors max_marks at 2).
    if motif.motif_type == MotifType.PATH_SEQUENCE:
        max_marks = max(max_marks, 3)
    title = next(
        (
            n
            for n in scene.nodes
            if getattr(n, "semantic_role", "") == "title"
            and getattr(n, "node_type", "") == "text"
        ),
        None,
    )

    if motif.motif_type in {MotifType.QUIET_RULE, MotifType.SECTION_CUT} and title is not None:
        nodes.append(
            ShapeNode(
                id="vl_motif_title_rule",
                semantic_role="graphic_motif",
                x=title.x,
                y=title.y + title.height + 0.05,
                width=min(2.6, title.width * 0.4),
                height=max(0.012, motif.stroke.width_pt / 72.0),
                z_index=max(0, title.z_index - 1),
                opacity=motif.stroke.opacity,
                shape_kind="rectangle",
                fill_color=stroke_hex,
                stroke_color=stroke_hex,
                stroke_width=0,
            )
        )
        marks += 1

    if motif.motif_type == MotifType.AXIS_GRID and marks < max_marks:
        nodes.append(
            ShapeNode(
                id="vl_motif_axis",
                semantic_role="graphic_motif",
                x=scene.page_width * 0.08,
                y=scene.page_height * 0.16,
                width=max(0.01, motif.stroke.width_pt / 72.0),
                height=scene.page_height * 0.58,
                z_index=0,
                opacity=motif.stroke.opacity,
                shape_kind="rectangle",
                fill_color=stroke_hex,
                stroke_color=stroke_hex,
                stroke_width=0,
            )
        )
        marks += 1

    if motif.motif_type in {
        MotifType.FLOW_NODES,
        MotifType.PATH_SEQUENCE,
        MotifType.MODULE_INDEX,
    }:
        count = min(max_marks - marks, 3 if motif.repetition_rule == "sparse" else 4)
        if motif.motif_type == MotifType.PATH_SEQUENCE:
            count = max(3, count)
        size = motif.marker.size_pt / 72.0
        marker_ids: list[str] = []
        centers: list[tuple[float, float]] = []
        for index in range(max(0, count)):
            t = (index + 1) / (count + 1)
            y_ratio = 0.62 if motif.motif_type != MotifType.MODULE_INDEX else 0.78
            cx = scene.page_width * (0.18 + 0.55 * t)
            cy = scene.page_height * y_ratio
            node_id = f"vl_motif_node_{index}"
            marker_ids.append(node_id)
            centers.append((cx, cy))
            nodes.append(
                ShapeNode(
                    id=node_id,
                    semantic_role="graphic_motif",
                    x=cx - size / 2,
                    y=cy - size / 2,
                    width=size,
                    height=size,
                    z_index=4,
                    opacity=min(1.0, motif.stroke.opacity + 0.1),
                    shape_kind="ellipse" if motif.marker.shape == "circle" else "rectangle",
                    fill_color=stroke_hex if motif.marker.fill_token else None,
                    stroke_color=stroke_hex,
                    stroke_width=1.0,
                )
            )
            # Architectural index label beside each node (01 / 02 / …).
            from archium.domain.visual.render_scene import TextNode, TextParagraph

            label = f"{index + 1:02d}"
            nodes.append(
                TextNode(
                    id=f"vl_motif_index_{index}",
                    semantic_role="graphic_motif_index",
                    x=cx + size * 0.7,
                    y=cy - size * 0.9,
                    width=0.45,
                    height=0.28,
                    z_index=5,
                    text=label,
                    paragraphs=[TextParagraph(text=label, alignment="left")],
                    font_family="Arial",
                    font_family_cjk="Microsoft YaHei",
                    font_family_latin="Arial",
                    font_size=11,
                    font_weight=500,
                    color=stroke_hex,
                    typography_token="caption",
                    alignment="left",
                    line_height=14,
                    letter_spacing=0.08,
                    opacity=0.85,
                )
            )
            marks += 1

        # VQ-004: connect markers with real ConnectorNodes (arrowed flow).
        if (
            motif.motif_type in {MotifType.FLOW_NODES, MotifType.PATH_SEQUENCE}
            and len(marker_ids) >= 2
        ):
            for index in range(len(marker_ids) - 1):
                connector = ConnectorNode(
                    id=f"vl_motif_connector_{index}",
                    semantic_role="graphic_motif_connector",
                    x=centers[index][0],
                    y=centers[index][1],
                    width=max(0.2, abs(centers[index + 1][0] - centers[index][0])),
                    height=max(0.2, abs(centers[index + 1][1] - centers[index][1])),
                    z_index=3,
                    opacity=motif.stroke.opacity,
                    start=ConnectorEndpoint(node_id=marker_ids[index], anchor="right"),
                    end=ConnectorEndpoint(node_id=marker_ids[index + 1], anchor="left"),
                    routing="elbow" if motif.motif_type == MotifType.FLOW_NODES else "straight",
                    stroke_color=stroke_hex,
                    stroke_width=max(0.75, motif.stroke.width_pt),
                    arrow_start=False,
                    arrow_end=True,
                    label="" if motif.motif_type != MotifType.PATH_SEQUENCE else f"{index + 1:02d}",
                )
                nodes.append(connector)
                marks += 1

            # Path sequence also gets an open freeform polyline through centers.
            if motif.motif_type == MotifType.PATH_SEQUENCE and len(centers) >= 3:
                path_points = [Point(x=cx, y=cy) for cx, cy in centers]
                freeform = FreeformNode(
                    id="vl_motif_path_poly",
                    semantic_role="graphic_motif_freeform",
                    x=min(p.x for p in path_points),
                    y=min(p.y for p in path_points),
                    width=max(0.3, max(p.x for p in path_points) - min(p.x for p in path_points)),
                    height=max(0.3, max(p.y for p in path_points) - min(p.y for p in path_points)),
                    z_index=2,
                    opacity=max(0.35, motif.stroke.opacity - 0.2),
                    points=path_points,
                    closed=False,
                    fill_color=None,
                    stroke_color=stroke_hex,
                    stroke_width=max(0.5, motif.stroke.width_pt * 0.75),
                )
                refresh_freeform_geometry(freeform)
                nodes.append(freeform)

    if motif.motif_type == MotifType.CONTOUR and marks < max_marks:
        for index in range(min(2, max_marks)):
            t = (index + 1) / 3
            # Freeform ellipse approximation (8-point ring) — true ellipse ShapeNode also kept.
            cx = scene.page_width * 0.5
            cy = scene.page_height * 0.5
            rx = max(0.2, scene.page_width * t / 2)
            ry = max(0.15, scene.page_height * t / 2)
            import math

            ring = [
                Point(
                    x=cx + rx * math.cos(math.tau * i / 8),
                    y=cy + ry * math.sin(math.tau * i / 8),
                )
                for i in range(8)
            ]
            freeform = FreeformNode(
                id=f"vl_motif_contour_ff_{index}",
                semantic_role="graphic_motif_freeform",
                x=cx - rx,
                y=cy - ry,
                width=rx * 2,
                height=ry * 2,
                z_index=0,
                opacity=motif.stroke.opacity,
                points=ring,
                closed=True,
                fill_color=None,
                stroke_color=stroke_hex,
                stroke_width=motif.stroke.width_pt,
            )
            refresh_freeform_geometry(freeform)
            nodes.append(freeform)
            nodes.append(
                ShapeNode(
                    id=f"vl_motif_contour_{index}",
                    semantic_role="graphic_motif",
                    x=cx - rx,
                    y=cy - ry,
                    width=rx * 2,
                    height=ry * 2,
                    z_index=0,
                    opacity=motif.stroke.opacity * 0.85,
                    shape_kind="ellipse",
                    fill_color=None,
                    stroke_color=stroke_hex,
                    stroke_width=motif.stroke.width_pt,
                )
            )

    if motif.motif_type == MotifType.BEFORE_AFTER_SLICE and marks < max_marks:
        nodes.append(
            ShapeNode(
                id="vl_motif_slice",
                semantic_role="graphic_motif",
                x=scene.page_width * 0.48,
                y=scene.page_height * 0.2,
                width=max(0.015, motif.stroke.width_pt / 48.0),
                height=scene.page_height * 0.55,
                z_index=5,
                opacity=motif.stroke.opacity,
                shape_kind="rectangle",
                fill_color=stroke_hex,
                stroke_color=stroke_hex,
                stroke_width=0,
            )
        )

    if not nodes:
        return scene

    # Refresh connector hit-boxes now that marker nodes exist in the working set.
    draft = scene.model_copy(update={"nodes": [*nodes, *list(scene.nodes)]})
    for node in draft.nodes:
        if isinstance(node, ConnectorNode) and str(node.id).startswith("vl_motif_connector_"):
            refresh_connector_geometry(draft, node)

    warnings = list(scene.warnings)
    tag = f"graphic_motif:{motif.motif_type.value}"
    if tag not in warnings:
        warnings.append(tag)
    if any(isinstance(n, ConnectorNode) for n in nodes):
        warnings.append("vq4_connector_motif")
    if any(isinstance(n, FreeformNode) for n in nodes):
        warnings.append("vq4_freeform_motif")
    return draft.model_copy(update={"warnings": warnings})


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
