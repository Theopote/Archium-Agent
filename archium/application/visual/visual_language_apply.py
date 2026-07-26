"""Apply VisualLanguageSpec onto LayoutPlan / RenderScene (decoration + typography)."""

from __future__ import annotations

from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import RenderScene, ShapeNode, TextNode
from archium.domain.visual.visual_language import (
    NAMED_SWATCHES,
    SYMBOL_GLYPHS,
    DecorationId,
    SceneLayerRole,
    TitleCase,
    TypographyRecipeId,
    VisualLanguageSpec,
)
from archium.domain.visual.visual_language.color_story import ColorStory


def apply_visual_language_to_plan(
    plan: LayoutPlan,
    language: VisualLanguageSpec | None,
    *,
    page_order: int | None = None,
) -> LayoutPlan:
    """Mutate title typography and inject decoration elements (returns new plan)."""
    if language is None:
        return plan
    elements = list(plan.elements)
    elements = _apply_typography(elements, language, plan=plan)
    elements = _inject_decorations(elements, language, plan=plan, page_order=page_order)
    elements = _inject_symbols(elements, language, plan=plan)
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
    for index, node in enumerate(nodes):
        if not isinstance(node, TextNode):
            continue
        if node.semantic_role not in {"title", "lead_statement"}:
            continue
        updates: dict[str, object] = {
            "letter_spacing": typo.letter_spacing_em,
            "opacity": typo.opacity,
        }
        if typo.title_font_size_pt is not None:
            updates["font_size"] = typo.title_font_size_pt
        if typo.recipe != TypographyRecipeId.DEFAULT:
            updates["font_weight"] = max(node.font_weight, 600)
        text = node.text
        if typo.case == TitleCase.UPPERCASE:
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
        return elements
    out: list[LayoutElement] = []
    title_el: LayoutElement | None = None
    for element in elements:
        if element.role != LayoutElementRole.TITLE:
            out.append(element)
            continue
        text = element.text_content or ""
        if typo.case == TitleCase.UPPERCASE:
            text = text.upper()
        title_el = element.model_copy(
            update={
                "text_content": text,
                "font_size_override": typo.title_font_size_pt,
                "letter_spacing": typo.letter_spacing_em,
                "opacity": typo.opacity,
                "style_token": "display" if typo.scale.value == "giant" else "title",
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
                out.append(
                    LayoutElement(
                        id=en_id,
                        role=LayoutElementRole.SUBTITLE,
                        content_type=LayoutContentType.TEXT,
                        text_content=typo.english_label.upper()
                        if typo.case != TitleCase.AS_IS
                        else typo.english_label,
                        x=title_el.x,
                        y=title_el.y + title_el.height + gap,
                        width=title_el.width,
                        height=0.28,
                        z_index=title_el.z_index,
                        alignment=title_el.alignment,
                        style_token="caption",
                        font_size_override=typo.english_font_size_pt,
                        letter_spacing=0.12,
                        opacity=0.85,
                        layer_role=SceneLayerRole.TEXT.value,
                    )
                )
    return out


def _inject_decorations(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
    page_order: int | None,
) -> list[LayoutElement]:
    out = list(elements)
    title = next((el for el in out if el.role == LayoutElementRole.TITLE), None)
    accent = _swatch_hex(
        language.color_story,
        prefer=("conflict", "intervention", "accent", "existing"),
    )
    ink = NAMED_SWATCHES.get("axis_line", "#2C2C2C")
    deco = language.decoration

    if DecorationId.THIN_LINE in deco.decorations or deco.divider_kind is not None:
        if title is not None and not any(el.id == "vl_thin_line" for el in out):
            # Place under bilingual english if present.
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

    if DecorationId.AXIS_LINE in deco.decorations:
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

    if DecorationId.SECTION_LABEL_01 in deco.decorations or deco.section_index:
        if not any(el.id == "vl_section_index" for el in out):
            index_text = deco.section_index or (
                f"{(page_order or 0) + 1:02d}" if page_order is not None else "01"
            )
            label = deco.section_label or ""
            text = f"{index_text}  ·  {label}".strip(" ·") if label else index_text
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
                    style_token="caption",
                    font_size_override=11,
                    letter_spacing=0.14,
                    layer_role=SceneLayerRole.ANNOTATION.value,
                )
            )
    return out


def _inject_symbols(
    elements: list[LayoutElement],
    language: VisualLanguageSpec,
    *,
    plan: LayoutPlan,
) -> list[LayoutElement]:
    if not language.symbols:
        return elements
    out = list(elements)
    title = next((el for el in out if el.role == LayoutElementRole.TITLE), None)
    for index, symbol in enumerate(language.symbols[:2]):
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
