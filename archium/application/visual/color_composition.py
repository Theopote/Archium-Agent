"""Compose page ColorComposition + soft deck color rhythm (VQ-002)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archium.application.visual.typography_composition import infer_typography_page_kind
from archium.domain.enums import SlideType
from archium.domain.visual.enums import ContinuityRole, LayoutFamily
from archium.domain.visual.page_direction import NarrativeEmotion
from archium.domain.visual.visual_language.color_composition import (
    BackgroundMode,
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


def compose_color_composition(
    *,
    design_system: DesignSystem | None = None,
    slide: SlideSpec | None = None,
    layout_plan: LayoutPlan | None = None,
    visual_intent: VisualIntent | None = None,
    page_direction: PageDirection | None = None,
    color_story: ColorStory | None = None,
    page_kind: TypographyPageKind | None = None,
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
    accent_token = "accent"
    accent_hex = None
    background_hex = None
    primary_text_hex = None
    if design_system is not None:
        accent_token, accent_hex = _resolve_accent(design_system, color_story)
        background_hex, primary_text_hex = _resolve_background_pair(
            design_system, mode=mode, accent_hex=accent_hex
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

    return ColorComposition(
        background_mode=mode,
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
        background_hex=background_hex,
        accent_hex=accent_hex,
        primary_text_hex=primary_text_hex,
        source=f"color_composition:{kind.value}:{mode.value}",
    )


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
    """Mutate RenderScene background + title/ghost colors for dark/wash modes."""
    from archium.domain.visual.render_scene import (
        BackgroundStyle,
        RenderScene,
        TextNode,
        set_text_node_runs,
        TextRun,
        effective_run_style,
    )

    if composition is None or not isinstance(scene, RenderScene):
        return scene
    if not composition.background_hex:
        return scene

    # Drop prior composition geometry so re-apply is idempotent.
    nodes = [
        node
        for node in scene.nodes
        if getattr(node, "id", "")
        not in {"color_accent_wash", "color_accent_edge"}
    ]
    bg = composition.background_hex
    text_color = composition.primary_text_hex
    accent = composition.accent_hex

    # Inject accent wash band when ratio is high (climax / thesis punch).
    wash_nodes = []
    if (
        composition.background_mode == BackgroundMode.ACCENT_WASH
        and accent
        and composition.accent_ratio >= 0.12
    ):
        from archium.domain.visual.render_scene import ShapeNode

        wash_h = scene.page_height * min(0.42, 0.15 + composition.accent_ratio)
        wash_nodes.append(
            ShapeNode(
                id="color_accent_wash",
                semantic_role="color_composition_wash",
                x=0,
                y=scene.page_height - wash_h,
                width=scene.page_width,
                height=wash_h,
                z_index=0,
                opacity=min(0.35, 0.12 + composition.accent_ratio),
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
        )
    elif (
        composition.section_override
        and composition.background_mode == BackgroundMode.DARK
        and accent
        and composition.accent_ratio >= 0.04
    ):
        from archium.domain.visual.render_scene import ShapeNode

        # Narrow accent edge — not a decorative party.
        wash_nodes.append(
            ShapeNode(
                id="color_accent_edge",
                semantic_role="color_composition_edge",
                x=0,
                y=0,
                width=max(0.08, scene.page_width * composition.accent_ratio * 0.35),
                height=scene.page_height,
                z_index=0,
                opacity=0.95,
                shape_kind="rectangle",
                fill_color=accent,
                stroke_color=accent,
                stroke_width=0,
            )
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

    return scene.model_copy(
        update={
            "background": BackgroundStyle(color=bg),
            "nodes": [*wash_nodes, *nodes],
            "warnings": warnings,
        }
    )


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
        out.append(
            composition.model_copy(
                update={
                    "background_mode": mode,
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
) -> tuple[str, str]:
    colors = design_system.colors
    if mode == BackgroundMode.DARK:
        return colors.resolve("primary"), colors.resolve("surface")
    if mode == BackgroundMode.LIGHT:
        # Near-white board for evidence / drawing pages.
        return "#F4F7FA", colors.resolve("primary_text")
    if mode == BackgroundMode.ACCENT_WASH:
        # Soft tint derived toward accent without full saturation.
        return _blend_hex(colors.resolve("background"), accent_hex, 0.18), colors.resolve(
            "primary_text"
        )
    if mode == BackgroundMode.MONOCHROME:
        return "#E8E8E6", "#1A1A1A"
    # TINTED — keep design system board tint.
    return colors.resolve("background"), colors.resolve("primary_text")


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
