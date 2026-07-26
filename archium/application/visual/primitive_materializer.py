"""Materialize PrimitiveDrawSpec → LayoutElements (Visual Primitive Engine v1)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.primitives.draw_spec import (
    DRAW_FLOW_LINE_EXISTING,
    GeometryType,
    PrimitiveDrawSpec,
    draw_spec_for,
)
from archium.domain.visual.visual_budget import VisualBudget
from archium.domain.visual.visual_language import NAMED_SWATCHES, SceneLayerRole
from archium.domain.visual.visual_language.color_story import ColorStory


@dataclass(frozen=True)
class FrameRect:
    x: float
    y: float
    w: float
    h: float


def resolve_role_hex(story: ColorStory, role: str, *, fallback: str = "#2C2C2C") -> str:
    """ColorStory role → named swatch → hex."""
    swatch = story.roles.get(role)
    if not swatch:
        # Allow role to already be a swatch id or direct color word.
        swatch = role
    if swatch.startswith("#") and len(swatch) >= 4:
        return swatch
    return NAMED_SWATCHES.get(swatch, NAMED_SWATCHES.get(role, fallback))


def default_diagram_frame(plan: LayoutPlan, elements: list[LayoutElement]) -> FrameRect:
    """Prefer hero/supporting visual; else right-half diagram stage."""
    hero = next(
        (
            el
            for el in elements
            if el.role
            in {LayoutElementRole.HERO_VISUAL, LayoutElementRole.SUPPORTING_VISUAL}
            and el.content_type
            in {LayoutContentType.IMAGE, LayoutContentType.DRAWING}
        ),
        None,
    )
    if hero is not None:
        return FrameRect(hero.x, hero.y, hero.width, hero.height)
    return FrameRect(
        plan.page_width * 0.48,
        plan.page_height * 0.16,
        plan.page_width * 0.44,
        plan.page_height * 0.66,
    )


def materialize_primitives(
    *,
    plan: LayoutPlan,
    elements: list[LayoutElement],
    primitive_ids: list[str],
    color_story: ColorStory,
    budget: VisualBudget,
    metaphor: str | None = None,
) -> list[LayoutElement]:
    """Append drawn primitive shapes. Counts against decorative_lines / icons / color_blocks."""
    if not primitive_ids:
        return elements
    if any(el.id.startswith("vl_draw_") for el in elements):
        return elements

    out = list(elements)
    frame = default_diagram_frame(plan, out)
    line_budget = max(0, budget.decorative_lines)
    icon_budget = max(0, budget.icons)
    wash_budget = max(0, budget.color_blocks)
    lines_used = 0
    icons_used = 0
    washes_used = 0

    # Rhetoric pack: fragment → network (existing gray + conflict node + green flow).
    wants_pack = metaphor == "fragment_to_network" or (
        "flow_line" in primitive_ids
        and ("conflict" in color_story.roles or "existing" in color_story.roles)
    )
    if wants_pack and ("flow_line" in primitive_ids or "node" in primitive_ids):
        pack = _materialize_fragment_to_network(
            frame=frame,
            color_story=color_story,
            line_budget=line_budget,
            icon_budget=icon_budget,
            wash_budget=wash_budget,
            include_overlay="overlay_map" in primitive_ids,
        )
        out.extend(pack.elements)
        lines_used += pack.lines_used
        icons_used += pack.icons_used
        washes_used += pack.washes_used
        # Skip individual flow/node/overlay — pack already spoke.
        skip = {"flow_line", "node", "overlay_map", "circulation"}
    else:
        skip = set()

    for prim_id in primitive_ids:
        if prim_id in skip:
            continue
        if prim_id in {"hero_statement", "section_index"}:
            continue
        spec = draw_spec_for(prim_id)
        if spec is None:
            continue
        kind = spec.geometry.type
        if kind == GeometryType.RECT_WASH:
            if washes_used >= wash_budget:
                continue
            out.extend(_emit_wash(f"vl_draw_{prim_id}", frame, spec, color_story))
            washes_used += 1
            continue
        if kind == GeometryType.DISK:
            if icons_used >= icon_budget:
                continue
            out.extend(_emit_disk(f"vl_draw_{prim_id}", frame, spec, color_story))
            icons_used += 1
            continue
        # Lines / rules / polylines / bezier
        remaining = line_budget - lines_used
        if remaining <= 0:
            continue
        drawn = _emit_path(f"vl_draw_{prim_id}", frame, spec, color_story, max_parts=remaining)
        out.extend(drawn)
        lines_used += len(drawn)

    return out


@dataclass
class _PackResult:
    elements: list[LayoutElement]
    lines_used: int
    icons_used: int
    washes_used: int


def _materialize_fragment_to_network(
    *,
    frame: FrameRect,
    color_story: ColorStory,
    line_budget: int,
    icon_budget: int,
    wash_budget: int,
    include_overlay: bool,
) -> _PackResult:
    """Gray broken existing path + red conflict node + green network curve."""
    elements: list[LayoutElement] = []
    lines_used = 0
    icons_used = 0
    washes_used = 0

    # Soft floor so gray+green still reads when Director budget is tight.
    effective = max(line_budget, 4) if line_budget > 0 else 0
    if effective <= 0 and icon_budget <= 0 and wash_budget <= 0:
        return _PackResult([], 0, 0, 0)

    if include_overlay and wash_budget > 0:
        wash_spec = draw_spec_for("overlay_map")
        if wash_spec is not None:
            elements.extend(
                _emit_wash("vl_draw_overlay_map", frame, wash_spec, color_story)
            )
            washes_used += 1

    # Reserve ≥2 slots for green network; existing gets 1–2 fragments.
    network_reserve = min(4, max(2, effective // 2))
    existing_cap = max(1, min(2, effective - network_reserve))

    if existing_cap > 0:
        existing = _emit_path(
            "vl_draw_flow_existing",
            frame,
            DRAW_FLOW_LINE_EXISTING,
            color_story,
            max_parts=existing_cap,
        )
        elements.extend(existing)
        lines_used += len(existing)

    flow = draw_spec_for("flow_line")
    if flow is not None and lines_used < effective:
        # Force intervention green for the "new network" voice.
        network_spec = flow.model_copy(
            update={
                "style": flow.style.model_copy(
                    update={"stroke_role": "intervention", "opacity": 0.9}
                )
            }
        )
        network = _emit_path(
            "vl_draw_flow_network",
            frame,
            network_spec,
            color_story,
            max_parts=max(2, min(network_reserve, effective - lines_used)),
        )
        elements.extend(network)
        lines_used += len(network)

    node = draw_spec_for("node")
    if node is not None and icon_budget > 0:
        conflict = PrimitiveDrawSpec(
            geometry=node.geometry.model_copy(
                update={"x0": 0.42, "y0": 0.55, "radius": 0.04}
            ),
            style=node.style.model_copy(
                update={"stroke_role": "conflict", "fill_role": "conflict"}
            ),
            meaning="conflict",
        )
        elements.extend(_emit_disk("vl_draw_node_conflict", frame, conflict, color_story))
        icons_used += 1

    return _PackResult(
        elements=elements,
        lines_used=lines_used,
        icons_used=icons_used,
        washes_used=washes_used,
    )


def _map_point(frame: FrameRect, nx: float, ny: float) -> tuple[float, float]:
    return frame.x + frame.w * nx, frame.y + frame.h * ny


def _bar_between(
    *,
    el_id: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    stroke: str,
    width_pt: float,
    opacity: float,
    z_index: int = 7,
) -> LayoutElement:
    """Approximate a stroke as a thin filled rect (pptxgen-safe)."""
    # Thickness in inches from pt (~72pt = 1in); clamp for visibility.
    thick = max(0.02, min(0.08, width_pt / 72.0 * 1.8))
    dx = x1 - x0
    dy = y1 - y0
    if abs(dx) >= abs(dy):
        left = min(x0, x1)
        width = max(abs(dx), 0.12)
        top = (y0 + y1) / 2.0 - thick / 2.0
        height = thick
    else:
        top = min(y0, y1)
        height = max(abs(dy), 0.12)
        left = (x0 + x1) / 2.0 - thick / 2.0
        width = thick
    return LayoutElement(
        id=el_id,
        role=LayoutElementRole.ANNOTATION,
        content_type=LayoutContentType.SHAPE,
        x=left,
        y=top,
        width=max(0.02, width),
        height=max(0.02, height),
        z_index=z_index,
        fill_color=stroke,
        stroke_color=stroke,
        stroke_width=0,
        opacity=opacity,
        layer_role=SceneLayerRole.ANNOTATION.value,
    )


def _emit_path(
    prefix: str,
    frame: FrameRect,
    spec: PrimitiveDrawSpec,
    story: ColorStory,
    *,
    max_parts: int,
) -> list[LayoutElement]:
    stroke = resolve_role_hex(story, spec.style.stroke_role)
    geo = spec.geometry
    opacity = spec.style.opacity
    width_pt = spec.style.width_pt
    points: list[tuple[float, float]] = []

    if geo.type == GeometryType.RULE:
        x0, y0 = _map_point(frame, geo.x0, geo.y0)
        x1, y1 = _map_point(frame, geo.x1, geo.y0)
        return [
            _bar_between(
                el_id=f"{prefix}_0",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                stroke=stroke,
                width_pt=width_pt,
                opacity=opacity,
            )
        ]

    if geo.type == GeometryType.SEGMENT:
        points = [
            _map_point(frame, geo.x0, geo.y0),
            _map_point(frame, geo.x1, geo.y1),
        ]
    elif geo.type == GeometryType.POLYLINE:
        if geo.broken:
            # Two fragments with a visual gap (fragment rhetoric).
            a0 = _map_point(frame, geo.x0, geo.y0)
            a1 = _map_point(frame, geo.cx, geo.cy)
            b0 = _map_point(frame, geo.cx + 0.08, geo.cy + 0.05)
            b1 = _map_point(frame, geo.x1, geo.y1)
            out: list[LayoutElement] = []
            if max_parts >= 1:
                out.append(
                    _bar_between(
                        el_id=f"{prefix}_a",
                        x0=a0[0],
                        y0=a0[1],
                        x1=a1[0],
                        y1=a1[1],
                        stroke=stroke,
                        width_pt=width_pt,
                        opacity=opacity,
                    )
                )
            if max_parts >= 2:
                out.append(
                    _bar_between(
                        el_id=f"{prefix}_b",
                        x0=b0[0],
                        y0=b0[1],
                        x1=b1[0],
                        y1=b1[1],
                        stroke=stroke,
                        width_pt=width_pt,
                        opacity=max(0.35, opacity - 0.1),
                    )
                )
            return out
        points = [
            _map_point(frame, geo.x0, geo.y0),
            _map_point(frame, geo.cx, geo.cy),
            _map_point(frame, geo.x1, geo.y1),
        ]
    elif geo.type == GeometryType.BEZIER_APPROX:
        # Quadratic Bezier sampled into bars; curvature nudges control point.
        cx = geo.cx
        cy = geo.cy * (0.5 + geo.curvature)
        cy = min(1.0, max(0.0, cy))
        n = max(3, min(geo.samples, max_parts + 1))
        for i in range(n):
            t = i / (n - 1)
            u = 1 - t
            nx = u * u * geo.x0 + 2 * u * t * cx + t * t * geo.x1
            ny = u * u * geo.y0 + 2 * u * t * cy + t * t * geo.y1
            points.append(_map_point(frame, nx, ny))
    else:
        return []

    out = []
    for i in range(min(len(points) - 1, max_parts)):
        p0, p1 = points[i], points[i + 1]
        out.append(
            _bar_between(
                el_id=f"{prefix}_{i}",
                x0=p0[0],
                y0=p0[1],
                x1=p1[0],
                y1=p1[1],
                stroke=stroke,
                width_pt=width_pt,
                opacity=opacity,
            )
        )
    return out


def _emit_disk(
    el_id: str,
    frame: FrameRect,
    spec: PrimitiveDrawSpec,
    story: ColorStory,
) -> list[LayoutElement]:
    fill_role = spec.style.fill_role or spec.style.stroke_role
    color = resolve_role_hex(story, fill_role)
    cx, cy = _map_point(frame, spec.geometry.x0, spec.geometry.y0)
    r = max(0.08, min(frame.w, frame.h) * spec.geometry.radius)
    return [
        LayoutElement(
            id=el_id,
            role=LayoutElementRole.ANNOTATION,
            content_type=LayoutContentType.SHAPE,
            x=cx - r,
            y=cy - r,
            width=r * 2,
            height=r * 2,
            z_index=8,
            fill_color=color,
            stroke_color=color,
            stroke_width=0,
            opacity=spec.style.opacity,
            corner_radius=r,  # hint: treat as circle in pptxgen when possible
            image_mask="circle",
            layer_role=SceneLayerRole.ANNOTATION.value,
        )
    ]


def _emit_wash(
    el_id: str,
    frame: FrameRect,
    spec: PrimitiveDrawSpec,
    story: ColorStory,
) -> list[LayoutElement]:
    fill_role = spec.style.fill_role or spec.style.stroke_role
    color = resolve_role_hex(story, fill_role)
    x0, y0 = _map_point(frame, spec.geometry.x0, spec.geometry.y0)
    x1, y1 = _map_point(frame, spec.geometry.x1, spec.geometry.y1)
    return [
        LayoutElement(
            id=el_id,
            role=LayoutElementRole.DECORATION,
            content_type=LayoutContentType.SHAPE,
            x=min(x0, x1),
            y=min(y0, y1),
            width=max(0.2, abs(x1 - x0)),
            height=max(0.2, abs(y1 - y0)),
            z_index=2,
            fill_color=color,
            stroke_color=resolve_role_hex(story, spec.style.stroke_role),
            stroke_width=0.5,
            opacity=spec.style.opacity,
            layer_role=SceneLayerRole.GEOMETRY.value,
        )
    ]
