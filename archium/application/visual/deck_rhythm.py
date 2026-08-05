"""VQ-006: Deck Rhythm — pacing directives that change the compiled picture.

Planning already assigns PacingRole / density / color modes. This module is the
missing bridge: turn those beats into title scale, motif budget, and ghost
opacity so pause pages stay quiet and climax pages carry weight.
"""

from __future__ import annotations

from archium.domain._base import DomainModel
from archium.domain.visual.deck_composition import (
    PacingRole,
    SlideCompositionDirective,
    VisualIntensity,
)
from archium.domain.visual.enums import DensityLevel
from archium.domain.visual.page_direction import PageDirection
from archium.domain.visual.render_scene import RenderScene, TextNode, TextRun, set_text_node_runs
from archium.domain.visual.visual_intent import VisualIntent


class PageRhythmStamp(DomainModel):
    """Executable per-page rhythm biases for RenderScene post-pass."""

    pacing_role: PacingRole = PacingRole.ANALYSIS
    visual_intensity: VisualIntensity = VisualIntensity.MEDIUM
    target_density: DensityLevel = DensityLevel.BALANCED
    background_mode: str | None = None
    should_contrast_previous: bool = False
    title_scale: float = 1.0
    motif_mark_bias: int = 0
    motif_opacity_scale: float = 1.0
    ghost_opacity_scale: float = 1.0
    quiet: bool = False
    source: str = "vq6:deck_rhythm"


def resolve_page_rhythm(
    *,
    directive: SlideCompositionDirective | None = None,
    page_direction: PageDirection | None = None,
    pacing_role: PacingRole | str | None = None,
    visual_intensity: VisualIntensity | str | None = None,
    target_density: DensityLevel | str | None = None,
    background_mode: str | None = None,
    should_contrast_previous: bool = False,
) -> PageRhythmStamp:
    """Compose a PageRhythmStamp from deck directive and/or stamped PageDirection."""
    role = _coerce_pacing(
        pacing_role
        or (directive.pacing_role if directive is not None else None)
        or (getattr(page_direction, "pacing_role", None) if page_direction else None)
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
    motif_bias = 0
    motif_opacity = 1.0
    ghost_opacity = 1.0
    quiet = False

    if role == PacingRole.OPENING:
        title_scale, motif_bias, ghost_opacity = 1.12, 0, 1.15
    elif role == PacingRole.CLIMAX:
        title_scale, motif_bias, motif_opacity, ghost_opacity = 1.18, 2, 1.15, 1.25
    elif role == PacingRole.CLOSING:
        title_scale, motif_bias, ghost_opacity = 1.1, -1, 1.1
        quiet = True
    elif role == PacingRole.PAUSE:
        title_scale, motif_bias, motif_opacity, ghost_opacity = 0.94, -2, 0.55, 0.45
        quiet = True
    elif role == PacingRole.TRANSITION:
        title_scale, motif_bias, motif_opacity = 1.04, -1, 0.7
        quiet = True
    elif role == PacingRole.EVIDENCE:
        title_scale, motif_bias = 0.96, 1
    elif role == PacingRole.ANALYSIS:
        title_scale, motif_bias = 1.0, 1
    elif role == PacingRole.DECISION:
        title_scale, motif_bias, ghost_opacity = 1.06, 0, 0.9

    if intensity == VisualIntensity.HERO:
        title_scale = min(1.28, title_scale + 0.08)
        motif_bias += 1
        ghost_opacity = min(1.4, ghost_opacity + 0.1)
    elif intensity == VisualIntensity.LOW:
        title_scale = max(0.88, title_scale - 0.06)
        motif_bias -= 1
        quiet = True
    elif intensity == VisualIntensity.HIGH:
        title_scale = min(1.22, title_scale + 0.04)

    if density == DensityLevel.SPACIOUS:
        title_scale = min(1.3, title_scale + 0.03)
        motif_bias = min(motif_bias, 1) if quiet else motif_bias
    elif density == DensityLevel.COMPACT:
        title_scale = max(0.9, title_scale - 0.03)
        if not quiet:
            motif_bias += 0

    if contrast and not quiet:
        title_scale = min(1.3, title_scale + 0.04)
        motif_opacity = min(1.25, motif_opacity + 0.1)

    return PageRhythmStamp(
        pacing_role=role,
        visual_intensity=intensity,
        target_density=density,
        background_mode=bg,
        should_contrast_previous=contrast,
        title_scale=round(title_scale, 3),
        motif_mark_bias=motif_bias,
        motif_opacity_scale=round(motif_opacity, 3),
        ghost_opacity_scale=round(ghost_opacity, 3),
        quiet=quiet,
    )


def apply_deck_rhythm_to_scene(
    scene: RenderScene,
    stamp: PageRhythmStamp | None,
) -> RenderScene:
    """Mutate scene nodes for pacing: title scale, ghost opacity, motif quieting."""
    if stamp is None or not isinstance(scene, RenderScene):
        return scene
    tag = f"deck_rhythm:{stamp.pacing_role.value}"
    if tag in scene.warnings:
        return scene

    nodes: list[object] = []
    for node in scene.nodes:
        node_id = str(getattr(node, "id", ""))
        role = str(getattr(node, "semantic_role", ""))

        if isinstance(node, TextNode) and role == "title" and stamp.title_scale != 1.0:
            boost = stamp.title_scale
            new_size = min(84.0, round(float(node.font_size) * boost, 1))
            updated = node.model_copy(update={"font_size": new_size})
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

        if node_id.startswith("vl_motif_") and (
            stamp.quiet or stamp.motif_opacity_scale != 1.0
        ):
            opacity = float(getattr(node, "opacity", 1.0))
            if stamp.quiet and stamp.pacing_role == PacingRole.PAUSE:
                # Drop connector/freeform noise on breath pages; keep a single rule.
                if "connector" in node_id or "path_poly" in node_id or "contour" in node_id:
                    continue
                if "node_" in node_id or "index_" in node_id:
                    continue
            scale = 0.45 if stamp.quiet else stamp.motif_opacity_scale
            nodes.append(node.model_copy(update={"opacity": round(opacity * scale, 3)}))
            continue

        nodes.append(node)

    warnings = list(scene.warnings)
    warnings.append(tag)
    if stamp.quiet:
        warnings.append("deck_rhythm:quiet")
    if stamp.should_contrast_previous:
        warnings.append("deck_rhythm:contrast")
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
