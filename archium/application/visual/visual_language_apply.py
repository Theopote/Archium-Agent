"""Apply VisualLanguageSpec onto LayoutPlan / RenderScene (decoration + typography)."""

from __future__ import annotations

from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import RenderScene, ShapeNode, TextNode
from archium.domain.visual.visual_budget import VisualBudget
from archium.domain.visual.visual_language import (
    NAMED_SWATCHES,
    SYMBOL_GLYPHS,
    DecorationId,
    SceneLayerRole,
    TitleCase,
    TypographyRecipeId,
    TypographyRole,
    VisualLanguageSpec,
)
from archium.domain.visual.visual_language.color_story import ColorStory


def apply_visual_language_to_plan(
    plan: LayoutPlan,
    language: VisualLanguageSpec | None,
    *,
    page_order: int | None = None,
    visual_budget: VisualBudget | None = None,
) -> LayoutPlan:
    """Mutate title typography and inject decoration elements (returns new plan)."""
    if language is None:
        return plan
    budget = visual_budget or VisualBudget()
    elements = list(plan.elements)
    elements = _apply_typography(elements, language, plan=plan)
    elements = _inject_atmosphere(elements, language, plan=plan, budget=budget)
    elements = _inject_decorations(
        elements, language, plan=plan, page_order=page_order, budget=budget
    )
    elements = _inject_symbols(elements, language, plan=plan, budget=budget)
    elements = _inject_primitives(elements, language, plan=plan, budget=budget)
    elements = _apply_image_masks(elements, language)
    elements = _inject_image_composition(elements, language, plan=plan, budget=budget)
    reading = list(plan.reading_order)
    for element in elements:
        if element.id not in reading and element.role != LayoutElementRole.DECORATION:
            reading.append(element.id)
    return plan.model_copy(update={"elements": elements, "reading_order": reading})


def apply_visual_language_to_scene(
    scene: RenderScene,
    language: VisualLanguageSpec | None,
) -> RenderScene:
    """Post-compile: boost title nodes + append decoration shapes if missing."""
    if language is None:
        return scene
    nodes = list(scene.nodes)
    typo = language.typography
    primary = typo.resolve_role(typo.primary_role)
    for index, node in enumerate(nodes):
        if not isinstance(node, TextNode):
            continue
        if node.semantic_role not in {"title", "lead_statement"}:
            continue
        updates: dict[str, object] = {
            "letter_spacing": primary.resolved_letter_spacing(),
            "opacity": primary.opacity,
            "font_size": primary.font_size_pt,
            "font_weight": max(node.font_weight, primary.font_weight),
        }
        text = node.text
        if primary.case == TitleCase.UPPERCASE:
            text = text.upper()
            updates["text"] = text
            updates["paragraphs"] = list(node.paragraphs)
        nodes[index] = node.model_copy(update=updates)

    # Color story accent on stroke decorations.
    accent = _swatch_hex(language.color_story, prefer=("conflict", "intervention", "accent"))
    if not any(getattr(n, "id", "").startswith("vl_") for n in nodes):
        nodes.extend(_scene_decoration_nodes(scene, language, accent=accent))

    warnings = list(scene.warnings)
    tag = "visual_language_v1"
    if tag not in warnings:
        warnings.append(tag)
    return scene.model_copy(update={"nodes": nodes, "warnings": warnings})


def _apply_typography(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
) -> list[LayoutElement]:
    typo = language.typography
    if typo.recipe == TypographyRecipeId.DEFAULT:
        return _apply_secondary_roles(elements, language)

    primary = typo.resolve_role(typo.primary_role)
    tech = typo.resolve_role(TypographyRole.TECH_NOTE)
    out: list[LayoutElement] = []
    title_el: LayoutElement | None = None
    for element in elements:
        if element.role != LayoutElementRole.TITLE:
            out.append(element)
            continue
        text = element.text_content or ""
        if primary.case == TitleCase.UPPERCASE:
            text = text.upper()
        title_el = element.model_copy(
            update={
                "text_content": text,
                "font_size_override": primary.font_size_pt,
                "letter_spacing": primary.resolved_letter_spacing(),
                "opacity": primary.opacity,
                "style_token": primary.style_token,
                "layer_role": SceneLayerRole.TEXT.value,
            }
        )
        out.append(title_el)

    if typo.bilingual and typo.english_label and title_el is not None:
        # Avoid duplicate english if generator already placed subtitle matching label.
        existing_sub = next(
            (
                el
                for el in out
                if el.role == LayoutElementRole.SUBTITLE
                and (el.text_content or "").strip().upper()
                == typo.english_label.strip().upper()
            ),
            None,
        )
        if existing_sub is None:
            en_id = "vl_title_en"
            if not any(el.id == en_id for el in out):
                gap = 0.08
                en_text = typo.english_label
                if tech.case == TitleCase.UPPERCASE:
                    en_text = en_text.upper()
                out.append(
                    LayoutElement(
                        id=en_id,
                        role=LayoutElementRole.SUBTITLE,
                        content_type=LayoutContentType.TEXT,
                        text_content=en_text,
                        x=title_el.x,
                        y=title_el.y + title_el.height + gap,
                        width=title_el.width,
                        height=0.28,
                        z_index=title_el.z_index,
                        alignment=title_el.alignment,
                        style_token=tech.style_token,
                        font_size_override=tech.font_size_pt,
                        letter_spacing=tech.resolved_letter_spacing(),
                        opacity=tech.opacity,
                        layer_role=SceneLayerRole.TEXT.value,
                    )
                )
        else:
            en_text = existing_sub.text_content or ""
            if tech.case == TitleCase.UPPERCASE:
                en_text = en_text.upper()
            out = [
                (
                    el.model_copy(
                        update={
                            "text_content": en_text,
                            "font_size_override": tech.font_size_pt,
                            "letter_spacing": tech.resolved_letter_spacing(),
                            "opacity": tech.opacity,
                            "style_token": tech.style_token,
                        }
                    )
                    if el.id == existing_sub.id
                    else el
                )
                for el in out
            ]

    return _apply_secondary_roles(out, language)


def _apply_secondary_roles(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
) -> list[LayoutElement]:
    """Stamp CAPTION / DRAWING_LABEL / ANNOTATION roles onto existing text."""
    typo = language.typography
    caption = typo.resolve_role(TypographyRole.CAPTION)
    drawing = typo.resolve_role(TypographyRole.DRAWING_LABEL)
    out: list[LayoutElement] = []
    for element in elements:
        if element.id.startswith("vl_"):
            out.append(element)
            continue
        if element.role == LayoutElementRole.CAPTION:
            text = element.text_content or ""
            if caption.case == TitleCase.UPPERCASE:
                text = text.upper()
            out.append(
                element.model_copy(
                    update={
                        "text_content": text,
                        "font_size_override": element.font_size_override
                        or caption.font_size_pt,
                        "letter_spacing": caption.resolved_letter_spacing(),
                        "opacity": element.opacity or caption.opacity,
                        "style_token": element.style_token or caption.style_token,
                    }
                )
            )
            continue
        if element.role == LayoutElementRole.ANNOTATION:
            text = element.text_content or ""
            if drawing.case == TitleCase.UPPERCASE:
                text = text.upper()
            out.append(
                element.model_copy(
                    update={
                        "text_content": text,
                        "font_size_override": element.font_size_override
                        or drawing.font_size_pt,
                        "letter_spacing": drawing.resolved_letter_spacing(),
                        "opacity": element.opacity or drawing.opacity,
                        "style_token": element.style_token or drawing.style_token,
                    }
                )
            )
            continue
        out.append(element)
    return out


def _inject_decorations(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
    page_order: int | None,
    budget: VisualBudget,
) -> list[LayoutElement]:
    out = list(elements)
    if budget.decorative_lines <= 0 and not language.decoration.section_index:
        return out
    title = next((el for el in out if el.role == LayoutElementRole.TITLE), None)
    accent = _swatch_hex(
        language.color_story,
        prefer=("conflict", "intervention", "accent", "existing", "problem"),
    )
    ink = NAMED_SWATCHES.get("axis_line", "#2C2C2C")
    deco = language.decoration
    lines_added = 0

    if (
        DecorationId.THIN_LINE in deco.decorations or deco.divider_kind is not None
    ) and lines_added < budget.decorative_lines:
        if title is not None and not any(el.id == "vl_thin_line" for el in out):
            en = next((el for el in out if el.id == "vl_title_en"), None)
            anchor = en or title
            out.append(
                LayoutElement(
                    id="vl_thin_line",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=title.x,
                    y=anchor.y + anchor.height + 0.06,
                    width=min(2.4, title.width * 0.45),
                    height=0.015,
                    z_index=max(0, title.z_index - 1),
                    fill_color=accent or ink,
                    stroke_color=accent or ink,
                    stroke_width=0,
                    layer_role=SceneLayerRole.DECORATION.value,
                )
            )
            lines_added += 1

    if DecorationId.AXIS_LINE in deco.decorations and lines_added < budget.decorative_lines:
        if not any(el.id == "vl_axis_line" for el in out):
            out.append(
                LayoutElement(
                    id="vl_axis_line",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=plan.page_width * 0.08,
                    y=plan.page_height * 0.18,
                    width=0.012,
                    height=plan.page_height * 0.55,
                    z_index=0,
                    fill_color=ink,
                    stroke_color=ink,
                    stroke_width=0,
                    opacity=0.55,
                    layer_role=SceneLayerRole.DECORATION.value,
                )
            )
            lines_added += 1

    if DecorationId.SECTION_LABEL_01 in deco.decorations or deco.section_index:
        if not any(el.id == "vl_section_index" for el in out):
            index_role = language.typography.resolve_role(TypographyRole.INDEX)
            index_text = deco.section_index or (
                f"{(page_order or 0) + 1:02d}" if page_order is not None else "01"
            )
            label = deco.section_label or ""
            text = f"{index_text}  ·  {label}".strip(" ·") if label else index_text
            if index_role.case == TitleCase.UPPERCASE:
                text = text.upper()
            y = 0.35
            if title is not None:
                y = max(0.2, title.y - 0.32)
            out.append(
                LayoutElement(
                    id="vl_section_index",
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    text_content=text,
                    x=title.x if title else plan.page_width * 0.08,
                    y=y,
                    width=min(4.0, plan.page_width * 0.5),
                    height=0.28,
                    z_index=5,
                    style_token=index_role.style_token,
                    font_size_override=index_role.font_size_pt,
                    letter_spacing=index_role.resolved_letter_spacing(),
                    opacity=index_role.opacity,
                    layer_role=SceneLayerRole.ANNOTATION.value,
                )
            )
    return out


def _apply_image_masks(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
) -> list[LayoutElement]:
    """Stamp ImageMaskSpec onto hero / supporting image elements."""
    from archium.domain.visual.visual_language.image_mask import ImageMaskKind

    mask = language.image_mask
    if mask.kind == ImageMaskKind.NONE and language.image_behavior.value == "inherit":
        return elements
    targets = set(mask.target_roles or ["hero_visual", "supporting_visual"])
    out: list[LayoutElement] = []
    for element in elements:
        if element.content_type not in {
            LayoutContentType.IMAGE,
            LayoutContentType.DRAWING,
        }:
            out.append(element)
            continue
        if element.role.value not in targets:
            out.append(element)
            continue
        updates: dict[str, object] = {
            "image_mask": mask.kind.value,
            "layer_role": SceneLayerRole.IMAGE.value,
        }
        if mask.kind == ImageMaskKind.CIRCLE:
            updates["corner_radius"] = min(element.width, element.height) / 2.0
        elif mask.kind in {ImageMaskKind.ROUNDED, ImageMaskKind.GRADIENT_FADE}:
            updates["corner_radius"] = mask.corner_radius
        elif mask.kind == ImageMaskKind.SILHOUETTE:
            updates["opacity"] = max(0.55, 1.0 - mask.edge_softness * 0.35)
            updates["corner_radius"] = mask.corner_radius
        out.append(element.model_copy(update=updates))
    return out


def _inject_image_composition(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
    budget: VisualBudget,
) -> list[LayoutElement]:
    """Overlay analysis lines (and optional detail frame) on the hero image frame."""
    from archium.domain.visual.visual_language.image_composition import (
        ImageCompositionMode,
    )

    composition = language.image_composition
    if composition.mode == ImageCompositionMode.NONE:
        return elements
    out = list(elements)
    if any(el.id.startswith("vl_icp_") for el in out):
        return out

    hero = next(
        (
            el
            for el in out
            if el.role
            in {LayoutElementRole.HERO_VISUAL, LayoutElementRole.SUPPORTING_VISUAL}
            and el.content_type
            in {LayoutContentType.IMAGE, LayoutContentType.DRAWING}
        ),
        None,
    )
    # Fallback: largest image-like box, else a synthetic frame on the right half.
    if hero is None:
        candidates = [
            el
            for el in out
            if el.content_type
            in {LayoutContentType.IMAGE, LayoutContentType.DRAWING}
        ]
        hero = max(candidates, key=lambda el: el.width * el.height, default=None)
    if hero is None:
        # Synthetic analysis frame so rhetoric still shows on text-led layouts
        # that claim photo_plus_analysis (Case 001 conflict without assets).
        frame_x = plan.page_width * 0.48
        frame_y = plan.page_height * 0.18
        frame_w = plan.page_width * 0.44
        frame_h = plan.page_height * 0.62
    else:
        frame_x, frame_y = hero.x, hero.y
        frame_w, frame_h = hero.width, hero.height

    # Cap analysis lines with decorative_lines budget (at least 1 when mode asks).
    line_cap = max(1, min(len(composition.analysis_lines), budget.decorative_lines + 1))
    for index, line in enumerate(composition.analysis_lines[:line_cap]):
        stroke = NAMED_SWATCHES.get(
            line.stroke_swatch, NAMED_SWATCHES.get("axis_line", "#2C2C2C")
        )
        x0 = frame_x + frame_w * line.x0
        y0 = frame_y + frame_h * line.y0
        x1 = frame_x + frame_w * line.x1
        y1 = frame_y + frame_h * line.y1
        # Approximate a thin rectangle along the segment (axis-aligned bbox + min thickness).
        left = min(x0, x1)
        top = min(y0, y1)
        width = max(abs(x1 - x0), 0.02)
        height = max(abs(y1 - y0), 0.02)
        # Prefer stroke-only when the segment is nearly horizontal/vertical.
        if abs(x1 - x0) >= abs(y1 - y0):
            # Horizontal-ish: thin bar
            top = (y0 + y1) / 2.0 - 0.012
            height = 0.024
            width = max(width, 0.15)
            left = min(x0, x1)
        else:
            left = (x0 + x1) / 2.0 - 0.012
            width = 0.024
            height = max(height, 0.15)
            top = min(y0, y1)
        out.append(
            LayoutElement(
                id=f"vl_icp_line_{line.kind.value}_{index}",
                role=LayoutElementRole.ANNOTATION,
                content_type=LayoutContentType.SHAPE,
                x=left,
                y=top,
                width=width,
                height=height,
                z_index=7,
                fill_color=stroke,
                stroke_color=stroke,
                stroke_width=0,
                opacity=line.opacity,
                layer_role=SceneLayerRole.ANNOTATION.value,
            )
        )
        if line.label and budget.icons > 0:
            out.append(
                LayoutElement(
                    id=f"vl_icp_label_{line.kind.value}_{index}",
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    text_content=line.label.upper(),
                    x=left + 0.05,
                    y=max(0.1, top - 0.28),
                    width=min(1.6, frame_w * 0.4),
                    height=0.24,
                    z_index=8,
                    style_token="caption",
                    font_size_override=10,
                    letter_spacing=0.12,
                    layer_role=SceneLayerRole.ANNOTATION.value,
                )
            )

    # Detail inset frame (rhetoric placeholder — does not invent a second asset).
    wants_detail = composition.max_details > 0 and any(
        slot.role.value == "detail" for slot in composition.slots
    )
    if wants_detail and budget.color_blocks > 0:
        inset_w = min(2.2, frame_w * 0.28)
        inset_h = min(1.6, frame_h * 0.32)
        out.append(
            LayoutElement(
                id="vl_icp_detail_frame",
                role=LayoutElementRole.DECORATION,
                content_type=LayoutContentType.SHAPE,
                x=frame_x + frame_w - inset_w - 0.12,
                y=frame_y + 0.12,
                width=inset_w,
                height=inset_h,
                z_index=6,
                fill_color=None,
                stroke_color=NAMED_SWATCHES.get("axis_line", "#2C2C2C"),
                stroke_width=1.0,
                opacity=0.75,
                layer_role=SceneLayerRole.ANNOTATION.value,
            )
        )
    return out


def _inject_atmosphere(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
    budget: VisualBudget,
) -> list[LayoutElement]:
    """Emit CAD grid / contour / blueprint accents behind content (z≈0)."""
    from archium.domain.visual.visual_language.atmosphere import AtmosphereKind

    atm = language.atmosphere
    if atm.kind == AtmosphereKind.NONE:
        return elements
    out = list(elements)
    if any(el.id.startswith("vl_atm_") for el in out):
        return out
    stroke = NAMED_SWATCHES.get(atm.stroke_swatch, NAMED_SWATCHES.get("axis_line", "#2C2C2C"))
    opacity = atm.opacity
    # Cap line count with decoration budget (+2 for atmosphere soft allowance).
    density = min(atm.density, max(2, budget.decorative_lines + 4))
    margin_x = plan.page_width * 0.06
    margin_y = plan.page_height * 0.1
    usable_w = plan.page_width - 2 * margin_x
    usable_h = plan.page_height - 2 * margin_y

    if atm.kind == AtmosphereKind.CAD_GRID:
        cols = max(2, density)
        rows = max(2, density - 1)
        for i in range(cols + 1):
            x = margin_x + usable_w * (i / cols)
            out.append(
                LayoutElement(
                    id=f"vl_atm_v_{i}",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=x,
                    y=margin_y,
                    width=0.01,
                    height=usable_h,
                    z_index=0,
                    fill_color=stroke,
                    stroke_color=stroke,
                    stroke_width=0,
                    opacity=opacity,
                    layer_role=SceneLayerRole.BACKGROUND.value,
                )
            )
        for j in range(rows + 1):
            y = margin_y + usable_h * (j / rows)
            out.append(
                LayoutElement(
                    id=f"vl_atm_h_{j}",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=margin_x,
                    y=y,
                    width=usable_w,
                    height=0.01,
                    z_index=0,
                    fill_color=stroke,
                    stroke_color=stroke,
                    stroke_width=0,
                    opacity=opacity,
                    layer_role=SceneLayerRole.BACKGROUND.value,
                )
            )
        return out

    if atm.kind == AtmosphereKind.CONTOUR:
        for i in range(density):
            t = (i + 1) / (density + 1)
            out.append(
                LayoutElement(
                    id=f"vl_atm_contour_{i}",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=margin_x + usable_w * (0.5 - t / 2),
                    y=margin_y + usable_h * (0.5 - t / 2),
                    width=max(0.4, usable_w * t),
                    height=max(0.3, usable_h * t),
                    z_index=0,
                    fill_color=None,
                    stroke_color=stroke,
                    stroke_width=0.75,
                    opacity=opacity + 0.05 * (1 - t),
                    layer_role=SceneLayerRole.BACKGROUND.value,
                )
            )
        return out

    if atm.kind == AtmosphereKind.BLUEPRINT:
        out.append(
            LayoutElement(
                id="vl_atm_blueprint_wash",
                role=LayoutElementRole.DECORATION,
                content_type=LayoutContentType.SHAPE,
                x=0,
                y=0,
                width=plan.page_width,
                height=plan.page_height,
                z_index=0,
                fill_color="#E8EEF5",
                stroke_color="#E8EEF5",
                stroke_width=0,
                opacity=min(0.35, opacity * 2.5),
                layer_role=SceneLayerRole.BACKGROUND.value,
            )
        )
        # Light horizontal rules like a drafting sheet.
        for j in range(min(density, 6)):
            y = margin_y + usable_h * ((j + 1) / (min(density, 6) + 1))
            out.append(
                LayoutElement(
                    id=f"vl_atm_bp_h_{j}",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=margin_x,
                    y=y,
                    width=usable_w,
                    height=0.008,
                    z_index=0,
                    fill_color=stroke,
                    stroke_color=stroke,
                    stroke_width=0,
                    opacity=opacity,
                    layer_role=SceneLayerRole.BACKGROUND.value,
                )
            )
        return out

    if atm.kind == AtmosphereKind.DOT_FIELD:
        # Sparse dots as tiny squares (SVG-less, deterministic).
        cols = density
        rows = max(2, density - 2)
        for i in range(cols):
            for j in range(rows):
                out.append(
                    LayoutElement(
                        id=f"vl_atm_dot_{i}_{j}",
                        role=LayoutElementRole.DECORATION,
                        content_type=LayoutContentType.SHAPE,
                        x=margin_x + usable_w * ((i + 0.5) / cols),
                        y=margin_y + usable_h * ((j + 0.5) / rows),
                        width=0.04,
                        height=0.04,
                        z_index=0,
                        fill_color=stroke,
                        stroke_color=stroke,
                        stroke_width=0,
                        opacity=opacity,
                        layer_role=SceneLayerRole.BACKGROUND.value,
                    )
                )
        return out

    return out


def _inject_primitives(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
    budget: VisualBudget,
) -> list[LayoutElement]:
    """Materialize primitives via DrawSpec engine; fall back to icons/glyphs."""
    from archium.application.visual.primitive_materializer import materialize_primitives
    from archium.domain.visual.primitives import PrimitiveKind, resolve_primitives
    from archium.domain.visual.primitives.draw_spec import draw_spec_for
    from archium.domain.visual.visual_language.primitive_icons import (
        icon_ref_for_primitive,
    )

    if not language.primitive_ids:
        return elements

    # Infer metaphor hint from color rhetoric / pack-friendly roles.
    metaphor = None
    roles = language.color_story.roles
    if "conflict" in roles and ("existing" in roles or "intervention" in roles):
        metaphor = "fragment_to_network"
    if language.image_composition.mode.value == "photo_plus_analysis":
        metaphor = metaphor or "fragment_to_network"

    out = materialize_primitives(
        plan=plan,
        elements=elements,
        primitive_ids=list(language.primitive_ids),
        color_story=language.color_story,
        budget=budget,
        metaphor=metaphor,
    )

    # Glyph / SVG fallback for primitives without draw specs (or leftover budget).
    if budget.icons <= 0:
        return out
    title = next((el for el in out if el.role == LayoutElementRole.TITLE), None)
    placed = sum(1 for el in out if el.id.startswith("vl_draw_node") or el.id.startswith("vl_prim_"))
    drawable = {pid for pid in language.primitive_ids if draw_spec_for(pid) is not None}
    for prim in resolve_primitives(language.primitive_ids):
        if placed >= budget.icons:
            break
        if prim.id in drawable or prim.id in {
            "thin_rule",
            "axis_line",
            "hero_statement",
            "section_index",
            "flow_line",
            "node",
            "overlay_map",
            "circulation",
        }:
            continue
        el_id = f"vl_prim_{prim.id}"
        if any(el.id == el_id for el in out):
            continue
        icon_ref = icon_ref_for_primitive(prim.id)
        if icon_ref and prim.kind in {
            PrimitiveKind.SYMBOL,
            PrimitiveKind.DIAGRAM,
            PrimitiveKind.LINE,
            PrimitiveKind.ANNOTATION,
        }:
            out.append(
                LayoutElement(
                    id=el_id,
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=icon_ref,
                    x=(title.x if title else plan.page_width * 0.1) + placed * 0.85,
                    y=plan.page_height * 0.82,
                    width=0.55,
                    height=0.55,
                    z_index=6,
                    layer_role=SceneLayerRole.ANNOTATION.value,
                )
            )
            placed += 1
            continue
        if prim.kind in {
            PrimitiveKind.SYMBOL,
            PrimitiveKind.DIAGRAM,
            PrimitiveKind.ANNOTATION,
        }:
            glyph = prim.glyph or prim.id
            out.append(
                LayoutElement(
                    id=el_id,
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.TEXT,
                    text_content=glyph,
                    x=(title.x if title else plan.page_width * 0.1) + placed * 1.15,
                    y=plan.page_height * 0.84,
                    width=1.0,
                    height=0.28,
                    z_index=6,
                    style_token="caption",
                    font_size_override=12,
                    letter_spacing=0.12,
                    layer_role=SceneLayerRole.ANNOTATION.value,
                )
            )
            placed += 1
    return out


def _inject_symbols(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
    budget: VisualBudget,
) -> list[LayoutElement]:
    if not language.symbols or budget.icons <= 0:
        return elements
    out = list(elements)
    title = next((el for el in out if el.role == LayoutElementRole.TITLE), None)
    for index, symbol in enumerate(language.symbols[: budget.icons]):
        el_id = f"vl_symbol_{symbol.value}"
        if any(el.id == el_id for el in out):
            continue
        glyph = SYMBOL_GLYPHS.get(symbol, "→")
        x = (title.x if title else plan.page_width * 0.1) + index * 1.2
        y = plan.page_height * 0.82
        out.append(
            LayoutElement(
                id=el_id,
                role=LayoutElementRole.ANNOTATION,
                content_type=LayoutContentType.TEXT,
                text_content=glyph,
                x=x,
                y=y,
                width=1.1,
                height=0.3,
                z_index=6,
                style_token="caption",
                font_size_override=14,
                letter_spacing=0.2,
                layer_role=SceneLayerRole.ANNOTATION.value,
            )
        )
    return out


def _scene_decoration_nodes(
    scene: RenderScene,
    language: VisualLanguageSpec,
    *,
    accent: str | None,
) -> list[ShapeNode | TextNode]:
    nodes: list[ShapeNode | TextNode] = []
    ink = NAMED_SWATCHES.get("axis_line", "#2C2C2C")
    color = accent or ink
    if DecorationId.THIN_LINE in language.decoration.decorations:
        nodes.append(
            ShapeNode(
                id="vl_thin_line",
                semantic_role="vl_decoration",
                x=scene.page_width * 0.08,
                y=scene.page_height * 0.28,
                width=min(2.4, scene.page_width * 0.25),
                height=0.015,
                z_index=1,
                shape_kind="rectangle",
                fill_color=color,
                stroke_color=color,
                stroke_width=0,
            )
        )
    if DecorationId.AXIS_LINE in language.decoration.decorations:
        nodes.append(
            ShapeNode(
                id="vl_axis_line",
                semantic_role="vl_decoration",
                x=scene.page_width * 0.08,
                y=scene.page_height * 0.18,
                width=0.012,
                height=scene.page_height * 0.55,
                z_index=0,
                opacity=0.55,
                shape_kind="rectangle",
                fill_color=ink,
                stroke_color=ink,
                stroke_width=0,
            )
        )
    for symbol in language.symbols[:2]:
        glyph = SYMBOL_GLYPHS.get(symbol, "→")
        nodes.append(
            TextNode(
                id=f"vl_symbol_{symbol.value}",
                semantic_role="vl_symbol",
                x=scene.page_width * 0.1,
                y=scene.page_height * 0.82,
                width=1.2,
                height=0.3,
                z_index=6,
                text=glyph,
                font_family="Arial",
                font_size=14,
                font_weight=400,
                color=color,
                line_height=1.2,
                letter_spacing=0.2,
            )
        )
    return nodes


def _swatch_hex(story: ColorStory, *, prefer: tuple[str, ...]) -> str | None:
    for role in prefer:
        name = story.roles.get(role)
        if name:
            return NAMED_SWATCHES.get(name, name if name.startswith("#") else None)
    for name in story.roles.values():
        hex_color = NAMED_SWATCHES.get(name)
        if hex_color:
            return hex_color
    return None
