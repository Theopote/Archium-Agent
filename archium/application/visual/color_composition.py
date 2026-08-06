"""Compose page ColorComposition + soft deck color rhythm (VQ-002)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archium.application.visual.typography_composition import infer_typography_page_kind
from archium.domain.enums import SlideType
from archium.domain.visual.enums import ContinuityRole, LayoutFamily
from archium.domain.visual.page_direction import NarrativeEmotion
from archium.domain.visual.visual_language.color_composition import (
    BackgroundMode,
    ColorArrangement,
    ColorComposition,
)
from archium.domain.visual.visual_language.color_story import NAMED_SWATCHES, ColorStory
from archium.domain.visual.visual_language.typography_composition import TypographyPageKind

if TYPE_CHECKING:
    from archium.domain.slide import SlideSpec
    from archium.domain.visual.design_system import DesignSystem
    from archium.domain.visual.layout import LayoutPlan
    from archium.domain.visual.page_direction import PageDirection
    from archium.domain.visual.visual_intent import VisualIntent


# Deck rhythm: opening/closing dark; evidence light; strategy tinted; climax wash.
_DECK_BG: dict[TypographyPageKind, BackgroundMode] = {
    TypographyPageKind.COVER: BackgroundMode.DARK,
    TypographyPageKind.SECTION: BackgroundMode.DARK,
    TypographyPageKind.THESIS: BackgroundMode.TINTED,
    TypographyPageKind.METRIC: BackgroundMode.LIGHT,
    TypographyPageKind.CLOSING: BackgroundMode.DARK,
    TypographyPageKind.DEFAULT: BackgroundMode.TINTED,
}

_EMOTION_BG: dict[NarrativeEmotion, BackgroundMode] = {
    NarrativeEmotion.PROBLEM: BackgroundMode.LIGHT,
    NarrativeEmotion.STRATEGY: BackgroundMode.TINTED,
    NarrativeEmotion.CLIMAX: BackgroundMode.ACCENT_WASH,
    NarrativeEmotion.CALM: BackgroundMode.LIGHT,
    NarrativeEmotion.DECISION: BackgroundMode.TINTED,
}

_COLOR_NODE_IDS = frozenset(
    {
        "color_accent_wash",
        "color_accent_edge",
        "color_top_masthead",
        "color_metric_panel",
        "color_closing_field",
        "color_mono_rule",
    }
)


def compose_color_composition(
    *,
    design_system: DesignSystem | None = None,
    slide: SlideSpec | None = None,
    layout_plan: LayoutPlan | None = None,
    visual_intent: VisualIntent | None = None,
    page_direction: PageDirection | None = None,
    color_story: ColorStory | None = None,
    page_kind: TypographyPageKind | None = None,
    background_mode_override: BackgroundMode | str | None = None,
    palette_locked: bool = False,
) -> ColorComposition:
    """Build page color mix from page kind + emotion + ColorStory accents."""
    kind = page_kind or infer_typography_page_kind(
        slide=slide,
        layout_plan=layout_plan,
        visual_intent=visual_intent,
    )
    emotion = None
    if page_direction is not None:
        emotion = page_direction.narrative_emotion
    elif visual_intent is not None and visual_intent.page_direction is not None:
        emotion = visual_intent.page_direction.narrative_emotion

    mode = _background_mode_for(
        kind=kind,
        emotion=emotion,
        slide=slide,
        layout_plan=layout_plan,
        visual_intent=visual_intent,
    )
    if background_mode_override is not None:
        if isinstance(background_mode_override, BackgroundMode):
            mode = background_mode_override
        else:
            try:
                mode = BackgroundMode(str(background_mode_override))
            except ValueError:
                pass

    # Style-overlay / art-direction palette owns the ground — don't force dark→primary.
    if palette_locked and mode == BackgroundMode.DARK:
        mode = BackgroundMode.TINTED

    accent_token = "accent"
    accent_hex = None
    background_hex = None
    primary_text_hex = None
    if design_system is not None:
        accent_token, accent_hex = _resolve_accent(design_system, color_story)
        background_hex, primary_text_hex = _resolve_background_pair(
            design_system,
            mode=mode,
            accent_hex=accent_hex,
            palette_locked=palette_locked,
        )
    elif color_story is not None:
        for role in ("conflict", "intervention", "accent", "problem"):
            name = color_story.roles.get(role)
            if not name:
                continue
            accent_token = role if role != "problem" else "accent"
            if name.startswith("#"):
                accent_hex = name
            else:
                accent_hex = NAMED_SWATCHES.get(name)
            if accent_hex:
                break

    accent_ratio = _accent_ratio_for(kind, emotion, mode)
    dominant_ratio = 0.12 if mode == BackgroundMode.DARK else 0.18
    if mode == BackgroundMode.ACCENT_WASH:
        dominant_ratio = 0.22
        accent_ratio = max(accent_ratio, 0.18)

    arrangement = select_color_arrangement(kind=kind, mode=mode, emotion=emotion)

    image_tint = None
    drawing_recolor = "primary"
    if mode == BackgroundMode.DARK:
        image_tint = "cool"
        drawing_recolor = "ink"
    elif mode == BackgroundMode.MONOCHROME:
        image_tint = "mono"
        drawing_recolor = "ink"
    elif mode == BackgroundMode.ACCENT_WASH:
        drawing_recolor = "accent"
    elif kind == TypographyPageKind.METRIC:
        drawing_recolor = "none"

    support = ["surface", "secondary_text"]
    if mode == BackgroundMode.DARK:
        support = ["overlay", "muted_text"]

    source = f"color_composition:{kind.value}:{mode.value}:{arrangement.value}"
    if palette_locked:
        source = f"{source}|palette_locked"

    return ColorComposition(
        background_mode=mode,
        arrangement=arrangement,
        dominant_token="primary" if mode != BackgroundMode.LIGHT else "background",
        support_tokens=support,
        accent_token=accent_token,
        background_ratio=max(0.55, 1.0 - dominant_ratio - accent_ratio),
        dominant_ratio=dominant_ratio,
        accent_ratio=accent_ratio,
        image_tint=image_tint,
        drawing_recolor=drawing_recolor,
        section_override=kind
        in {TypographyPageKind.COVER, TypographyPageKind.SECTION, TypographyPageKind.CLOSING},
        palette_locked=palette_locked,
        background_hex=background_hex,
        accent_hex=accent_hex,
        primary_text_hex=primary_text_hex,
        source=source,
    )


def select_color_arrangement(
    *,
    kind: TypographyPageKind,
    mode: BackgroundMode,
    emotion: NarrativeEmotion | None = None,
) -> ColorArrangement:
    """Pick v1.1 spatial color recipe from page kind + mode."""
    if mode == BackgroundMode.MONOCHROME:
        return ColorArrangement.MONO_RULE
    if mode == BackgroundMode.ACCENT_WASH or emotion == NarrativeEmotion.CLIMAX:
        return ColorArrangement.BOTTOM_WASH
    if kind == TypographyPageKind.METRIC:
        return ColorArrangement.METRIC_PANEL
    if kind == TypographyPageKind.CLOSING and mode == BackgroundMode.DARK:
        return ColorArrangement.CLOSING_FIELD
    if kind == TypographyPageKind.SECTION:
        return (
            ColorArrangement.ACCENT_EDGE
            if mode == BackgroundMode.DARK
            else ColorArrangement.TOP_MASTHEAD
        )
    if kind == TypographyPageKind.COVER and mode == BackgroundMode.DARK:
        return ColorArrangement.ACCENT_EDGE
    if kind == TypographyPageKind.THESIS:
        return ColorArrangement.TOP_MASTHEAD
    if mode == BackgroundMode.DARK:
        return ColorArrangement.ACCENT_EDGE
    if mode == BackgroundMode.TINTED:
        return ColorArrangement.TOP_MASTHEAD
    return ColorArrangement.PLAIN


def resolve_color_composition(
    composition: ColorComposition,
    design_system: DesignSystem,
    *,
    color_story: ColorStory | None = None,
) -> ColorComposition:
    """Fill resolved hex values from DesignSystem when composer ran without it."""
    if composition.background_hex and composition.accent_hex and composition.primary_text_hex:
        return composition
    accent_token, accent_hex = _resolve_accent(design_system, color_story)
    background_hex, primary_text_hex = _resolve_background_pair(
        design_system,
        mode=composition.background_mode,
        accent_hex=accent_hex or design_system.colors.resolve("accent"),
        palette_locked=composition.palette_locked,
    )
    return composition.model_copy(
        update={
            "accent_token": accent_token,
            "accent_hex": composition.accent_hex or accent_hex,
            "background_hex": composition.background_hex or background_hex,
            "primary_text_hex": composition.primary_text_hex or primary_text_hex,
        }
    )


def apply_color_composition_to_scene(
    scene: object,
    composition: ColorComposition | None,
) -> object:
    """Mutate RenderScene background + title/ghost colors for page color recipes."""
    from archium.domain.visual.render_scene import (
        BackgroundStyle,
        RenderScene,
        ShapeNode,
        TextNode,
        TextRun,
        effective_run_style,
        set_text_node_runs,
    )

    if composition is None or not isinstance(scene, RenderScene):
        return scene
    if not composition.background_hex:
        return scene

    # Drop prior composition geometry so re-apply is idempotent.
    nodes = [
        node
        for node in scene.nodes
        if getattr(node, "id", "") not in _COLOR_NODE_IDS
    ]
    bg = composition.background_hex
    text_color = composition.primary_text_hex
    accent = composition.accent_hex

    wash_nodes = _arrangement_nodes(
        scene,
        composition,
        accent=accent,
        shape_cls=ShapeNode,
    )

    if text_color:
        for index, node in enumerate(nodes):
            if not isinstance(node, TextNode):
                continue
            if node.semantic_role not in {
                "title",
                "subtitle",
                "lead_statement",
                "typography_ghost",
                "metric",
            }:
                continue
            # Don't recolor metrics that already use accent as the hero number.
            if node.semantic_role == "metric" and composition.background_mode == BackgroundMode.LIGHT:
                continue
            updates: dict[str, object] = {"color": text_color, "color_token": ""}
            updated = node.model_copy(update=updates)
            if node.runs:
                scaled = []
                for run in node.runs:
                    style = effective_run_style(node, run)
                    # Keep accent-colored hero numbers / keywords.
                    keep_accent = (
                        accent
                        and style["color"]
                        and accent.lstrip("#").upper()
                        == str(style["color"]).lstrip("#").upper()
                    )
                    run_color = style["color"] if keep_accent else text_color
                    scaled.append(
                        TextRun(
                            text=run.text,
                            font_family=run.font_family,
                            font_family_cjk=run.font_family_cjk,
                            font_family_latin=run.font_family_latin,
                            font_size=run.font_size,
                            font_weight=run.font_weight,
                            font_style=run.font_style,
                            color=run_color,
                            color_token=run.color_token if keep_accent else "",
                            letter_spacing=run.letter_spacing,
                            opacity=run.opacity,
                            outline=run.outline,
                            outline_width_pt=run.outline_width_pt,
                            outline_color=run.outline_color,
                            fill_enabled=run.fill_enabled,
                        )
                    )
                set_text_node_runs(updated, scaled)
            if node.semantic_role == "typography_ghost":
                # Ghost stays primary-tinted but more transparent on dark grounds.
                updated = updated.model_copy(
                    update={"opacity": min(node.opacity, 0.12), "color": text_color}
                )
            nodes[index] = updated

    warnings = list(scene.warnings)
    tag = f"color_composition:{composition.background_mode.value}"
    if tag not in warnings:
        warnings.append(tag)
    arr_tag = f"color_arrangement:{composition.arrangement.value}"
    if arr_tag not in warnings:
        warnings.append(arr_tag)
    if composition.palette_locked and "color_composition:palette_locked" not in warnings:
        warnings.append("color_composition:palette_locked")

    scene = scene.model_copy(
        update={
            "background": BackgroundStyle(color=bg),
            "nodes": [*wash_nodes, *nodes],
            "warnings": warnings,
        }
    )
    from archium.application.visual.text_contrast_guard import (
        apply_text_background_contrast_to_scene,
    )

    return apply_text_background_contrast_to_scene(scene)


def _arrangement_nodes(
    scene: object,
    composition: ColorComposition,
    *,
    accent: str | None,
    shape_cls: type,
) -> list[object]:
    """Materialize spatial color geometry for the selected arrangement."""
    if not accent:
        return []
    page_w = float(getattr(scene, "page_width", 10.0) or 10.0)
    page_h = float(getattr(scene, "page_height", 5.625) or 5.625)
    arrangement = composition.arrangement
    ratio = composition.accent_ratio

    if arrangement == ColorArrangement.BOTTOM_WASH and ratio >= 0.12:
        wash_h = page_h * min(0.42, 0.15 + ratio)
        return [
            shape_cls(
                id="color_accent_wash",
                semantic_role="color_composition_wash",
                x=0,
                y=page_h - wash_h,
                width=page_w,
                height=wash_h,
                z_index=0,
                opacity=min(0.35, 0.12 + ratio),
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]

    if arrangement == ColorArrangement.ACCENT_EDGE and ratio >= 0.04:
        return [
            shape_cls(
                id="color_accent_edge",
                semantic_role="color_composition_edge",
                x=0,
                y=0,
                width=max(0.08, page_w * ratio * 0.35),
                height=page_h,
                z_index=0,
                opacity=0.95,
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]

    if arrangement == ColorArrangement.TOP_MASTHEAD:
        mast_h = page_h * min(0.18, 0.08 + ratio)
        return [
            shape_cls(
                id="color_top_masthead",
                semantic_role="color_composition_masthead",
                x=0,
                y=0,
                width=page_w,
                height=mast_h,
                z_index=0,
                opacity=min(0.22, 0.08 + ratio),
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]

    if arrangement == ColorArrangement.METRIC_PANEL:
        panel_w = page_w * min(0.42, 0.28 + ratio)
        return [
            shape_cls(
                id="color_metric_panel",
                semantic_role="color_composition_metric_panel",
                x=page_w - panel_w - 0.35,
                y=page_h * 0.22,
                width=panel_w,
                height=page_h * 0.55,
                z_index=0,
                opacity=min(0.18, 0.08 + ratio * 0.5),
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]

    if arrangement == ColorArrangement.CLOSING_FIELD:
        return [
            shape_cls(
                id="color_closing_field",
                semantic_role="color_composition_closing_field",
                x=page_w * 0.08,
                y=page_h * 0.18,
                width=page_w * 0.84,
                height=page_h * 0.64,
                z_index=0,
                opacity=0.1,
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]

    if arrangement == ColorArrangement.MONO_RULE:
        return [
            shape_cls(
                id="color_mono_rule",
                semantic_role="color_composition_mono_rule",
                x=0.5,
                y=0.35,
                width=page_w - 1.0,
                height=0.02,
                z_index=0,
                opacity=0.55,
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]

    # Legacy fallback for dark section_override without explicit arrangement.
    if (
        composition.section_override
        and composition.background_mode == BackgroundMode.DARK
        and ratio >= 0.04
    ):
        return [
            shape_cls(
                id="color_accent_edge",
                semantic_role="color_composition_edge",
                x=0,
                y=0,
                width=max(0.08, page_w * ratio * 0.35),
                height=page_h,
                z_index=0,
                opacity=0.95,
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        ]
    return []


def plan_deck_color_modes(
    modes: list[BackgroundMode],
) -> list[BackgroundMode]:
    """Soft deck rhythm: avoid three consecutive dark (or wash) pages.

    Cover/closing may stay dark; intervening pages soften to tinted/light.
    """
    if len(modes) < 3:
        return list(modes)
    out = list(modes)
    heavy = {BackgroundMode.DARK, BackgroundMode.ACCENT_WASH}
    for index in range(2, len(out)):
        window = out[index - 2 : index + 1]
        if all(mode in heavy for mode in window):
            # Soften the middle of the streak when possible.
            mid = index - 1
            if out[mid] == BackgroundMode.DARK:
                out[mid] = BackgroundMode.TINTED
            elif out[mid] == BackgroundMode.ACCENT_WASH:
                out[mid] = BackgroundMode.TINTED
    # Also break back-to-back accent washes.
    for index in range(1, len(out)):
        if (
            out[index] == BackgroundMode.ACCENT_WASH
            and out[index - 1] == BackgroundMode.ACCENT_WASH
        ):
            out[index] = BackgroundMode.TINTED
    return out


def apply_deck_color_rhythm(
    compositions: list[ColorComposition],
) -> list[ColorComposition]:
    """Recompute background hex is caller's job; this only adjusts modes/ratios."""
    modes = plan_deck_color_modes([item.background_mode for item in compositions])
    out: list[ColorComposition] = []
    for composition, mode in zip(compositions, modes, strict=True):
        if mode == composition.background_mode:
            out.append(composition)
            continue
        accent_ratio = composition.accent_ratio
        if mode == BackgroundMode.TINTED:
            accent_ratio = min(accent_ratio, 0.08)
        arrangement = select_color_arrangement(
            kind=TypographyPageKind.DEFAULT,
            mode=mode,
        )
        # Prefer masthead when softening a dark streak into tinted.
        if mode == BackgroundMode.TINTED:
            arrangement = ColorArrangement.TOP_MASTHEAD
        out.append(
            composition.model_copy(
                update={
                    "background_mode": mode,
                    "arrangement": arrangement,
                    "accent_ratio": accent_ratio,
                    "section_override": mode == BackgroundMode.DARK,
                    # Force re-resolve of hex on next apply.
                    "background_hex": None,
                    "primary_text_hex": None,
                    "source": f"{composition.source}|deck_rhythm:{mode.value}",
                }
            )
        )
    return out


def stamp_deck_color_rhythm_onto_intents(
    *,
    deck_plan: object,
    intents: list[object],
    design_system: DesignSystem | None = None,
) -> list[object]:
    """Copy directive.background_mode onto PageDirection + refresh ColorComposition.

    Returns updated VisualIntent list (same length/order as input). Call after
    DeckCompositionPlanningService.plan so scene compile sees the rhythm stamp.
    """
    from archium.domain.visual.deck_composition import DeckCompositionPlan
    from archium.domain.visual.visual_intent import VisualIntent

    if not isinstance(deck_plan, DeckCompositionPlan):
        return list(intents)
    by_slide = {d.slide_id: d for d in deck_plan.slide_directives}
    updated: list[object] = []
    for intent in intents:
        if not isinstance(intent, VisualIntent):
            updated.append(intent)
            continue
        directive = by_slide.get(intent.slide_id)
        mode = directive.background_mode if directive is not None else None
        if not mode:
            updated.append(intent)
            continue
        direction = intent.page_direction
        if direction is None:
            updated.append(intent)
            continue
        language = direction.visual_language
        if language is not None and language.color_composition is not None:
            recomposed = compose_color_composition(
                design_system=design_system,
                visual_intent=intent,
                page_direction=direction,
                color_story=language.color_story,
                background_mode_override=mode,
            )
            if design_system is not None:
                recomposed = resolve_color_composition(
                    recomposed,
                    design_system,
                    color_story=language.color_story,
                )
            language = language.model_copy(update={"color_composition": recomposed})
        direction = direction.model_copy(
            update={
                "background_mode": mode,
                "visual_language": language,
                "evidence": [
                    *list(direction.evidence),
                    f"deck_color_rhythm:{mode}",
                ],
            }
        )
        updated.append(intent.model_copy(update={"page_direction": direction}))
    return updated


def _background_mode_for(
    *,
    kind: TypographyPageKind,
    emotion: NarrativeEmotion | None,
    slide: SlideSpec | None,
    layout_plan: LayoutPlan | None,
    visual_intent: VisualIntent | None,
) -> BackgroundMode:
    if kind in _DECK_BG and kind != TypographyPageKind.DEFAULT:
        mode = _DECK_BG[kind]
        # Thesis under climax emotion escalates to accent wash.
        if kind == TypographyPageKind.THESIS and emotion == NarrativeEmotion.CLIMAX:
            return BackgroundMode.ACCENT_WASH
        return mode
    if emotion is not None and emotion in _EMOTION_BG:
        return _EMOTION_BG[emotion]
    continuity = visual_intent.continuity_role if visual_intent is not None else None
    if continuity == ContinuityRole.OPENING:
        return BackgroundMode.DARK
    if continuity == ContinuityRole.CLOSING:
        return BackgroundMode.DARK
    if continuity == ContinuityRole.EVIDENCE:
        return BackgroundMode.LIGHT
    if continuity == ContinuityRole.CLIMAX:
        return BackgroundMode.ACCENT_WASH
    family = layout_plan.layout_family if layout_plan is not None else None
    if family == LayoutFamily.EVIDENCE_BOARD:
        return BackgroundMode.LIGHT
    if family == LayoutFamily.DRAWING_FOCUS:
        return BackgroundMode.LIGHT
    if slide is not None and slide.slide_type == SlideType.IMAGE:
        return BackgroundMode.DARK
    return BackgroundMode.TINTED


def _accent_ratio_for(
    kind: TypographyPageKind,
    emotion: NarrativeEmotion | None,
    mode: BackgroundMode,
) -> float:
    base = {
        TypographyPageKind.COVER: 0.06,
        TypographyPageKind.SECTION: 0.05,
        TypographyPageKind.THESIS: 0.08,
        TypographyPageKind.METRIC: 0.12,
        TypographyPageKind.CLOSING: 0.04,
        TypographyPageKind.DEFAULT: 0.05,
    }.get(kind, 0.05)
    if emotion == NarrativeEmotion.CLIMAX:
        base = max(base, 0.16)
    if emotion == NarrativeEmotion.PROBLEM:
        base = max(base, 0.09)
    if mode == BackgroundMode.ACCENT_WASH:
        base = max(base, 0.18)
    if mode == BackgroundMode.MONOCHROME:
        base = min(base, 0.03)
    return round(base, 3)


def _resolve_accent(
    design_system: DesignSystem,
    color_story: ColorStory | None,
) -> tuple[str, str]:
    if color_story is not None:
        for role in ("conflict", "intervention", "accent", "problem"):
            name = color_story.roles.get(role)
            if not name:
                continue
            if name.startswith("#"):
                return "accent", name
            hex_color = NAMED_SWATCHES.get(name)
            if hex_color:
                return role if role != "problem" else "accent", hex_color
    return "accent", design_system.colors.resolve("accent")


def _resolve_background_pair(
    design_system: DesignSystem,
    *,
    mode: BackgroundMode,
    accent_hex: str,
    palette_locked: bool = False,
) -> tuple[str, str]:
    from archium.application.visual.color_contrast import ensure_readable_pair

    colors = design_system.colors
    if palette_locked:
        # Art Direction / ReferenceStyle owns the ground color.
        bg, text = colors.resolve("background"), colors.resolve("primary_text")
        return ensure_readable_pair(bg, text)
    if mode == BackgroundMode.DARK:
        bg, text = colors.resolve("primary"), colors.resolve("surface")
    elif mode == BackgroundMode.LIGHT:
        bg, text = "#F4F7FA", colors.resolve("primary_text")
    elif mode == BackgroundMode.ACCENT_WASH:
        bg = _blend_hex(colors.resolve("background"), accent_hex, 0.18)
        text = colors.resolve("primary_text")
    elif mode == BackgroundMode.MONOCHROME:
        bg, text = "#E8E8E6", "#1A1A1A"
    else:
        bg, text = colors.resolve("background"), colors.resolve("primary_text")
    return ensure_readable_pair(bg, text)


def _blend_hex(base: str, accent: str, amount: float) -> str:
    def _rgb(value: str) -> tuple[int, int, int]:
        cleaned = value.lstrip("#")
        if len(cleaned) == 3:
            cleaned = "".join(ch * 2 for ch in cleaned)
        return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)

    amount = max(0.0, min(1.0, amount))
    br, bg, bb = _rgb(base)
    ar, ag, ab = _rgb(accent)
    r = round(br * (1 - amount) + ar * amount)
    g = round(bg * (1 - amount) + ag * amount)
    b = round(bb * (1 - amount) + ab * amount)
    return f"#{r:02X}{g:02X}{b:02X}"
