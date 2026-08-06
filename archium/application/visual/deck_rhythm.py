"""VQ-006: Deck Rhythm — pacing directives that change the compiled picture (v1.1).

Planning already assigns PacingRole / density / color modes. This module is the
missing bridge: turn those beats into title scale, motif budget, ghost opacity,
and color-geometry quieting so pause pages stay quiet and climax pages carry weight.
"""

from __future__ import annotations

from archium.domain._base import DomainModel
from archium.domain.enums import SlideType
from archium.domain.visual.deck_composition import (
    PacingRole,
    SlideCompositionDirective,
    VisualIntensity,
)
from archium.domain.visual.enums import ContinuityRole, DensityLevel
from archium.domain.visual.page_direction import PageDirection
from archium.domain.visual.render_scene import RenderScene, TextNode, TextRun, set_text_node_runs
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.visual_language.typography_composition import TypographyPageKind


class PageRhythmStamp(DomainModel):
    """Executable per-page rhythm biases for RenderScene post-pass."""

    pacing_role: PacingRole = PacingRole.ANALYSIS
    visual_intensity: VisualIntensity = VisualIntensity.MEDIUM
    target_density: DensityLevel = DensityLevel.BALANCED
    background_mode: str | None = None
    should_contrast_previous: bool = False
    title_scale: float = 1.0
    lead_scale: float = 1.0
    letter_spacing_bias: float = 0.0
    motif_mark_bias: int = 0
    motif_opacity_scale: float = 1.0
    ghost_opacity_scale: float = 1.0
    color_geometry_opacity_scale: float = 1.0
    quiet: bool = False
    source: str = "vq6:deck_rhythm"


_CONTINUITY_PACING: dict[ContinuityRole, PacingRole] = {
    ContinuityRole.OPENING: PacingRole.OPENING,
    ContinuityRole.CLOSING: PacingRole.CLOSING,
    ContinuityRole.CLIMAX: PacingRole.CLIMAX,
    ContinuityRole.EVIDENCE: PacingRole.EVIDENCE,
    ContinuityRole.SECTION_OPENING: PacingRole.TRANSITION,
    ContinuityRole.COMPARISON: PacingRole.ANALYSIS,
    ContinuityRole.SUMMARY: PacingRole.CLOSING,
}

_PAGE_KIND_PACING: dict[TypographyPageKind, PacingRole] = {
    TypographyPageKind.COVER: PacingRole.OPENING,
    TypographyPageKind.SECTION: PacingRole.TRANSITION,
    TypographyPageKind.THESIS: PacingRole.CLIMAX,
    TypographyPageKind.METRIC: PacingRole.EVIDENCE,
    TypographyPageKind.CLOSING: PacingRole.CLOSING,
}

_COLOR_GEOMETRY_PREFIXES = (
    "color_accent_",
    "color_top_masthead",
    "color_metric_panel",
    "color_closing_field",
    "color_mono_rule",
)


def resolve_page_rhythm(
    *,
    directive: SlideCompositionDirective | None = None,
    page_direction: PageDirection | None = None,
    pacing_role: PacingRole | str | None = None,
    visual_intensity: VisualIntensity | str | None = None,
    target_density: DensityLevel | str | None = None,
    background_mode: str | None = None,
    should_contrast_previous: bool = False,
    continuity_role: ContinuityRole | None = None,
    page_kind: TypographyPageKind | None = None,
    slide_type: SlideType | None = None,
) -> PageRhythmStamp:
    """Compose a PageRhythmStamp from deck directive and/or stamped PageDirection."""
    inferred = _infer_pacing_role(
        continuity_role=continuity_role,
        page_kind=page_kind,
        slide_type=slide_type,
    )
    role = _coerce_pacing(
        pacing_role
        or (directive.pacing_role if directive is not None else None)
        or (getattr(page_direction, "pacing_role", None) if page_direction else None)
        or inferred
        or PacingRole.ANALYSIS
    )
    intensity = _coerce_intensity(
        visual_intensity
        or (directive.visual_intensity if directive is not None else None)
        or (getattr(page_direction, "visual_intensity", None) if page_direction else None)
        or VisualIntensity.MEDIUM
    )
    density = _coerce_density(
        target_density
        or (directive.target_density if directive is not None else None)
        or (
            page_direction.density_override
            if page_direction is not None and page_direction.density_override is not None
            else None
        )
        or DensityLevel.BALANCED
    )
    bg = background_mode or (
        directive.background_mode if directive is not None else None
    ) or (page_direction.background_mode if page_direction is not None else None)
    contrast = should_contrast_previous or (
        directive.should_contrast_previous if directive is not None else False
    ) or bool(
        getattr(page_direction, "should_contrast_previous", False) if page_direction else False
    )

    title_scale = 1.0
    lead_scale = 1.0
    letter_spacing_bias = 0.0
    motif_bias = 0
    motif_opacity = 1.0
    ghost_opacity = 1.0
    color_geo_opacity = 1.0
    quiet = False

    if role == PacingRole.OPENING:
        title_scale, motif_bias, ghost_opacity = 1.12, 0, 1.15
        letter_spacing_bias = 0.02
        lead_scale = 1.06
    elif role == PacingRole.CLIMAX:
        title_scale, motif_bias, motif_opacity, ghost_opacity = 1.18, 2, 1.15, 1.25
        letter_spacing_bias = 0.03
        lead_scale = 1.08
        color_geo_opacity = 1.12
    elif role == PacingRole.CLOSING:
        title_scale, motif_bias, ghost_opacity = 1.1, -1, 1.1
        letter_spacing_bias = 0.04
        quiet = True
        color_geo_opacity = 0.75
    elif role == PacingRole.PAUSE:
        title_scale, motif_bias, motif_opacity, ghost_opacity = 0.94, -2, 0.55, 0.45
        quiet = True
        color_geo_opacity = 0.4
        lead_scale = 0.96
    elif role == PacingRole.TRANSITION:
        title_scale, motif_bias, motif_opacity = 1.04, -1, 0.7
        quiet = True
        color_geo_opacity = 0.65
    elif role == PacingRole.EVIDENCE:
        title_scale, motif_bias = 0.96, 1
        lead_scale = 0.98
    elif role == PacingRole.ANALYSIS:
        title_scale, motif_bias = 1.0, 1
    elif role == PacingRole.DECISION:
        title_scale, motif_bias, ghost_opacity = 1.06, 0, 0.9
        letter_spacing_bias = 0.015

    if intensity == VisualIntensity.HERO:
        title_scale = min(1.28, title_scale + 0.08)
        motif_bias += 1
        ghost_opacity = min(1.4, ghost_opacity + 0.1)
        letter_spacing_bias = min(0.08, letter_spacing_bias + 0.02)
        color_geo_opacity = min(1.25, color_geo_opacity + 0.08)
    elif intensity == VisualIntensity.LOW:
        title_scale = max(0.88, title_scale - 0.06)
        motif_bias -= 1
        quiet = True
        color_geo_opacity = min(color_geo_opacity, 0.55)
    elif intensity == VisualIntensity.HIGH:
        title_scale = min(1.22, title_scale + 0.04)

    if density == DensityLevel.SPACIOUS:
        title_scale = min(1.3, title_scale + 0.03)
        motif_bias = min(motif_bias, 1) if quiet else motif_bias
    elif density == DensityLevel.COMPACT:
        title_scale = max(0.9, title_scale - 0.03)

    if contrast and not quiet:
        title_scale = min(1.3, title_scale + 0.04)
        motif_opacity = min(1.25, motif_opacity + 0.1)
        color_geo_opacity = min(1.3, color_geo_opacity + 0.1)

    source = f"vq6:deck_rhythm:{role.value}"
    if inferred is not None and pacing_role is None and (
        page_direction is None or not getattr(page_direction, "pacing_role", None)
    ):
        source = f"{source}|inferred"

    return PageRhythmStamp(
        pacing_role=role,
        visual_intensity=intensity,
        target_density=density,
        background_mode=bg,
        should_contrast_previous=contrast,
        title_scale=round(title_scale, 3),
        lead_scale=round(lead_scale, 3),
        letter_spacing_bias=round(letter_spacing_bias, 3),
        motif_mark_bias=motif_bias,
        motif_opacity_scale=round(motif_opacity, 3),
        ghost_opacity_scale=round(ghost_opacity, 3),
        color_geometry_opacity_scale=round(color_geo_opacity, 3),
        quiet=quiet,
        source=source,
    )


def apply_deck_rhythm_to_scene(
    scene: RenderScene,
    stamp: PageRhythmStamp | None,
) -> RenderScene:
    """Mutate scene nodes for pacing: title/lead scale, ghost, motif budget, color quiet."""
    if stamp is None or not isinstance(scene, RenderScene):
        return scene
    tag = f"deck_rhythm:{stamp.pacing_role.value}"
    if tag in scene.warnings:
        return scene

    # Cap motif mark count using motif_mark_bias (negative = drop extras).
    motif_keep_budget = _motif_keep_budget(scene, stamp)

    nodes: list[object] = []
    motif_kept = 0
    for node in scene.nodes:
        node_id = str(getattr(node, "id", ""))
        role = str(getattr(node, "semantic_role", ""))

        if isinstance(node, TextNode) and role == "title" and (
            stamp.title_scale != 1.0 or abs(stamp.letter_spacing_bias) > 1e-6
        ):
            boost = stamp.title_scale
            new_size = min(84.0, round(float(node.font_size) * boost, 1))
            spacing = float(node.letter_spacing or 0.0) + stamp.letter_spacing_bias
            updated = node.model_copy(
                update={
                    "font_size": new_size,
                    "letter_spacing": max(-0.05, min(0.25, spacing)),
                }
            )
            if node.runs:
                new_runs = [
                    TextRun(
                        text=run.text,
                        font_family=run.font_family,
                        font_family_cjk=run.font_family_cjk,
                        font_family_latin=run.font_family_latin,
                        font_size=(
                            min(96.0, round(float(run.font_size) * boost, 1))
                            if run.font_size is not None
                            else new_size
                        ),
                        font_weight=run.font_weight,
                        font_style=run.font_style,
                        color=run.color,
                        color_token=run.color_token,
                        letter_spacing=(
                            max(
                                -0.1,
                                min(
                                    0.5,
                                    float(
                                        run.letter_spacing
                                        if run.letter_spacing is not None
                                        else node.letter_spacing
                                    )
                                    + stamp.letter_spacing_bias,
                                ),
                            )
                            if abs(stamp.letter_spacing_bias) > 1e-6
                            else run.letter_spacing
                        ),
                        opacity=run.opacity,
                        outline=run.outline,
                        outline_width_pt=run.outline_width_pt,
                        outline_color=run.outline_color,
                        fill_enabled=run.fill_enabled,
                    )
                    for run in node.runs
                ]
                set_text_node_runs(updated, new_runs)
            nodes.append(updated)
            continue

        if (
            isinstance(node, TextNode)
            and role == "lead_statement"
            and stamp.lead_scale != 1.0
        ):
            new_size = min(48.0, round(float(node.font_size) * stamp.lead_scale, 1))
            updated = node.model_copy(update={"font_size": new_size})
            if node.runs:
                new_runs = [
                    TextRun(
                        text=run.text,
                        font_family=run.font_family,
                        font_family_cjk=run.font_family_cjk,
                        font_family_latin=run.font_family_latin,
                        font_size=(
                            min(56.0, round(float(run.font_size) * stamp.lead_scale, 1))
                            if run.font_size is not None
                            else new_size
                        ),
                        font_weight=run.font_weight,
                        font_style=run.font_style,
                        color=run.color,
                        color_token=run.color_token,
                        letter_spacing=run.letter_spacing,
                        opacity=run.opacity,
                        outline=run.outline,
                        outline_width_pt=run.outline_width_pt,
                        outline_color=run.outline_color,
                        fill_enabled=run.fill_enabled,
                    )
                    for run in node.runs
                ]
                set_text_node_runs(updated, new_runs)
            nodes.append(updated)
            continue

        if (
            isinstance(node, TextNode)
            and ("ghost" in role or "ghost" in node_id)
            and stamp.ghost_opacity_scale != 1.0
        ):
            opacity = max(0.05, min(0.55, float(node.opacity) * stamp.ghost_opacity_scale))
            nodes.append(node.model_copy(update={"opacity": round(opacity, 3)}))
            continue

        if node_id.startswith("vl_motif_"):
            if stamp.quiet and stamp.pacing_role == PacingRole.PAUSE:
                # Drop connector/freeform noise on breath pages; keep a single rule.
                if "connector" in node_id or "path_poly" in node_id or "contour" in node_id:
                    continue
                if "node_" in node_id or "index_" in node_id:
                    continue
            # Negative bias: keep only title_rule / axis / first N marks.
            if motif_keep_budget is not None and _is_motif_mark(node_id):
                if motif_kept >= motif_keep_budget:
                    continue
                motif_kept += 1
            if stamp.quiet or stamp.motif_opacity_scale != 1.0:
                opacity = float(getattr(node, "opacity", 1.0))
                scale = 0.45 if stamp.quiet else stamp.motif_opacity_scale
                # Positive bias slightly lifts remaining marks.
                if stamp.motif_mark_bias > 0 and not stamp.quiet:
                    scale = min(1.35, scale * (1.0 + 0.06 * stamp.motif_mark_bias))
                nodes.append(node.model_copy(update={"opacity": round(opacity * scale, 3)}))
                continue
            nodes.append(node)
            continue

        if any(node_id.startswith(prefix) for prefix in _COLOR_GEOMETRY_PREFIXES):
            if stamp.quiet and stamp.pacing_role == PacingRole.PAUSE:
                # Soften color washes on breath pages instead of stacking decoration.
                opacity = float(getattr(node, "opacity", 1.0))
                nodes.append(
                    node.model_copy(
                        update={"opacity": round(opacity * 0.35, 3)}
                    )
                )
                continue
            if stamp.color_geometry_opacity_scale != 1.0:
                opacity = float(getattr(node, "opacity", 1.0))
                nodes.append(
                    node.model_copy(
                        update={
                            "opacity": round(
                                max(0.05, min(1.0, opacity * stamp.color_geometry_opacity_scale)),
                                3,
                            )
                        }
                    )
                )
                continue

        nodes.append(node)

    warnings = list(scene.warnings)
    warnings.append(tag)
    if stamp.quiet:
        warnings.append("deck_rhythm:quiet")
    if stamp.should_contrast_previous:
        warnings.append("deck_rhythm:contrast")
    if stamp.motif_mark_bias != 0:
        warnings.append(f"deck_rhythm:motif_bias:{stamp.motif_mark_bias}")
    if "|inferred" in stamp.source:
        warnings.append("deck_rhythm:inferred")
    return scene.model_copy(update={"nodes": nodes, "warnings": warnings})


def stamp_deck_rhythm_onto_intents(
    *,
    deck_plan: object,
    intents: list[object],
    design_system: object | None = None,
) -> list[object]:
    """Stamp pacing + color rhythm onto PageDirection for compile-time apply."""
    from archium.application.visual.color_composition import (
        stamp_deck_color_rhythm_onto_intents,
    )
    from archium.domain.visual.deck_composition import DeckCompositionPlan

    # Color modes first (existing VQ-002 path).
    colored = stamp_deck_color_rhythm_onto_intents(
        deck_plan=deck_plan,
        intents=intents,
        design_system=design_system,  # type: ignore[arg-type]
    )
    if not isinstance(deck_plan, DeckCompositionPlan):
        return list(colored)

    by_slide = {d.slide_id: d for d in deck_plan.slide_directives}
    updated: list[object] = []
    for intent in colored:
        if not isinstance(intent, VisualIntent):
            updated.append(intent)
            continue
        directive = by_slide.get(intent.slide_id)
        if directive is None or intent.page_direction is None:
            updated.append(intent)
            continue
        direction = intent.page_direction.model_copy(
            update={
                "pacing_role": directive.pacing_role.value,
                "visual_intensity": directive.visual_intensity.value,
                "should_contrast_previous": directive.should_contrast_previous,
                "density_override": directive.target_density,
                "evidence": [
                    *list(intent.page_direction.evidence),
                    f"deck_pacing:{directive.pacing_role.value}",
                    f"deck_intensity:{directive.visual_intensity.value}",
                ],
            }
        )
        updated.append(intent.model_copy(update={"page_direction": direction}))
    return updated


def _infer_pacing_role(
    *,
    continuity_role: ContinuityRole | None,
    page_kind: TypographyPageKind | None,
    slide_type: SlideType | None,
) -> PacingRole | None:
    if continuity_role is not None and continuity_role in _CONTINUITY_PACING:
        return _CONTINUITY_PACING[continuity_role]
    if page_kind is not None and page_kind in _PAGE_KIND_PACING:
        return _PAGE_KIND_PACING[page_kind]
    if slide_type == SlideType.TITLE:
        return PacingRole.OPENING
    if slide_type == SlideType.CLOSING:
        return PacingRole.CLOSING
    if slide_type == SlideType.SECTION:
        return PacingRole.TRANSITION
    return None


def _is_motif_mark(node_id: str) -> bool:
    return (
        "node_" in node_id
        or "index_" in node_id
        or "connector_" in node_id
        or "path_poly" in node_id
        or "contour" in node_id
        or "slice" in node_id
    )


def _motif_keep_budget(scene: RenderScene, stamp: PageRhythmStamp) -> int | None:
    """When bias is negative, cap how many motif marks survive."""
    if stamp.motif_mark_bias >= 0:
        return None
    marks = sum(
        1
        for n in scene.nodes
        if str(getattr(n, "id", "")).startswith("vl_motif_")
        and _is_motif_mark(str(getattr(n, "id", "")))
    )
    if marks <= 0:
        return None
    # bias -1 → keep ~half; bias -2 → keep at most 1 mark family member.
    keep = max(0, marks + stamp.motif_mark_bias)
    if stamp.motif_mark_bias <= -2:
        keep = min(keep, 1)
    return keep


def _coerce_pacing(value: object) -> PacingRole:
    if isinstance(value, PacingRole):
        return value
    try:
        return PacingRole(str(value))
    except ValueError:
        return PacingRole.ANALYSIS


def _coerce_intensity(value: object) -> VisualIntensity:
    if isinstance(value, VisualIntensity):
        return value
    try:
        return VisualIntensity(str(value))
    except ValueError:
        return VisualIntensity.MEDIUM


def _coerce_density(value: object) -> DensityLevel:
    if isinstance(value, DensityLevel):
        return value
    try:
        return DensityLevel(str(value))
    except ValueError:
        return DensityLevel.BALANCED


__all__ = [
    "PageRhythmStamp",
    "apply_deck_rhythm_to_scene",
    "resolve_page_rhythm",
    "stamp_deck_rhythm_onto_intents",
]
