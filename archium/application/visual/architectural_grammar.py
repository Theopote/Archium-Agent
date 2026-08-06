"""Select and apply Architectural Visual Grammar (VQ-005) on the main chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archium.domain.visual.architectural_visual_grammar import (
    ArchitecturalGrammarId,
    ArchitecturalVisualGrammar,
    get_architectural_grammar,
    grammar_for_formula,
    list_architectural_grammars,
)
from archium.domain.visual.page_visual_grammar import PageGrammarId, select_page_formula
from archium.domain.visual.visual_language.typography_composition import TypographyPageKind

if TYPE_CHECKING:
    from archium.domain.slide import SlideSpec
    from archium.domain.visual.page_direction import PageDirection
    from archium.domain.visual.render_scene import RenderScene
    from archium.domain.visual.visual_concept import VisualConcept
    from archium.domain.visual.visual_intent import VisualIntent
    from archium.domain.visual.visual_language import VisualLanguageSpec


def select_architectural_grammar(
    *,
    slide: SlideSpec | None = None,
    page_direction: PageDirection | None = None,
    concept: VisualConcept | None = None,
    page_kind: TypographyPageKind | None = None,
    formula_id: PageGrammarId | str | None = None,
) -> ArchitecturalVisualGrammar:
    """Pick a product grammar from formula / page kind / title heuristics."""
    title = (slide.title if slide is not None else "") or ""
    title = title.strip()

    # Explicit title shortcuts for P0 showcase pages.
    if title in {"封面", "开篇", "项目封面"} or (
        slide is not None and getattr(slide.slide_type, "value", "") == "title"
    ):
        return get_architectural_grammar(ArchitecturalGrammarId.MONUMENTAL_STATEMENT)
    if title in {"结尾", "结语", "总结", "致谢"} or (
        slide is not None and getattr(slide.slide_type, "value", "") == "closing"
    ):
        return get_architectural_grammar(ArchitecturalGrammarId.FINAL_VISION)
    if title in {"核心理念", "设计理念", "愿景", "主张"}:
        return get_architectural_grammar(ArchitecturalGrammarId.MONUMENTAL_STATEMENT)
    if title in {"关键指标", "指标", "数据"} or (
        slide is not None and getattr(slide.slide_type, "value", "") == "data"
    ):
        return get_architectural_grammar(ArchitecturalGrammarId.METRIC_MONUMENT)
    if title in {"章节", "篇章"} or (
        slide is not None and getattr(slide.slide_type, "value", "") == "section"
    ):
        return get_architectural_grammar(ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL)

    if formula_id is not None:
        return grammar_for_formula(formula_id)

    emotion = "calm"
    situation = None
    expression = None
    metaphor = None
    if page_direction is not None:
        emotion = page_direction.narrative_emotion.value
        situation = page_direction.situation_rule_id
        expression = page_direction.expression_mode_id
        if page_direction.page_grammar is not None:
            return grammar_for_formula(page_direction.page_grammar.id)
    if concept is not None:
        metaphor = concept.visual_metaphor.value

    formula = select_page_formula(
        emotion=emotion,
        situation_rule_id=situation,
        expression_mode_id=expression,
        metaphor=metaphor,
        title=title,
    )
    grammar = grammar_for_formula(formula.id)

    # Page-kind soft override for P0 kinds when formula is generic.
    if page_kind == TypographyPageKind.COVER:
        return get_architectural_grammar(ArchitecturalGrammarId.MONUMENTAL_STATEMENT)
    if page_kind == TypographyPageKind.CLOSING:
        return get_architectural_grammar(ArchitecturalGrammarId.FINAL_VISION)
    if page_kind == TypographyPageKind.METRIC:
        return get_architectural_grammar(ArchitecturalGrammarId.METRIC_MONUMENT)
    if page_kind == TypographyPageKind.SECTION:
        return get_architectural_grammar(ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL)
    return grammar


def apply_grammar_to_language(
    language: VisualLanguageSpec,
    grammar: ArchitecturalVisualGrammar,
) -> VisualLanguageSpec:
    """Stamp grammar cues onto VisualLanguageSpec (color / motif / primitives)."""
    from archium.application.visual.graphic_motif import merge_motif_into_primitives
    from archium.domain.visual.visual_language.graphic_motif import (
        GraphicMotif,
        MarkerStyle,
        StrokeStyle,
    )

    motif = GraphicMotif(
        motif_id=f"grammar:{grammar.grammar_id.value}",
        motif_type=grammar.motif_type,
        usage_rules=[f"grammar:{grammar.grammar_id.value}"],
        stroke=StrokeStyle(
            color_token="accent" if grammar.accent_ratio >= 0.1 else "primary",
            width_pt=0.85,
            opacity=0.75,
        ),
        marker=MarkerStyle(shape="circle", fill_token="accent"),
        shape_vocabulary=list(language.primitive_ids[:6]),
        max_marks=4 if grammar.p0_showcase else 3,
        color_role_bias="conflict" if grammar.accent_ratio >= 0.1 else "intervention",
        source=f"vq5:{grammar.grammar_id.value}",
    )
    primitives = merge_motif_into_primitives(list(language.primitive_ids), motif)

    color_comp = language.color_composition
    if color_comp is not None:
        color_comp = color_comp.model_copy(
            update={
                "background_mode": grammar.background_mode,
                "accent_ratio": max(color_comp.accent_ratio, grammar.accent_ratio),
                "section_override": grammar.typography_page_kind.value
                in {"cover", "section", "closing"},
                "source": f"vq5:{grammar.grammar_id.value}",
            }
        )
    return language.model_copy(
        update={
            "graphic_motif": motif,
            "color_composition": color_comp,
            "primitive_ids": primitives,
            "source": f"vq5:{grammar.grammar_id.value}",
        }
    )


def apply_grammar_to_direction(
    direction: PageDirection,
    grammar: ArchitecturalVisualGrammar,
) -> PageDirection:
    """Push layout family / hide / evidence stamps from grammar."""
    families = list(direction.preferred_layout_families)
    for family in grammar.preferred_families:
        if family not in families:
            families.insert(0, family)
    hide = list(dict.fromkeys([*direction.must_hide, *grammar.forbidden_conditions]))
    evidence = list(direction.evidence)
    evidence.append(f"arch_grammar:{grammar.grammar_id.value}")
    evidence.append(f"composition:{grammar.composition_strategy.value}")
    updates: dict[str, object] = {
        "preferred_layout_families": families[:6],
        "must_hide": hide,
        "evidence": evidence,
        "background_mode": grammar.background_mode.value,
    }
    if grammar.preferred_variants and not direction.locked_layout_variant:
        updates["locked_layout_variant"] = grammar.preferred_variants[0]
    return direction.model_copy(update=updates)


def apply_grammar_to_scene(
    scene: RenderScene,
    grammar: ArchitecturalVisualGrammar | None,
    *,
    visual_intent: VisualIntent | None = None,
) -> RenderScene:
    """Post-compile: boost title scale + enforce motif/color for P0 grammars."""
    from archium.application.visual.color_composition import (
        apply_color_composition_to_scene,
        compose_color_composition,
    )
    from archium.application.visual.graphic_motif import (
        apply_graphic_motif_to_scene,
        compose_graphic_motif,
    )
    from archium.domain.visual.render_scene import TextNode, TextRun, set_text_node_runs

    if grammar is None:
        return scene

    warnings = list(scene.warnings)
    tag = f"arch_grammar:{grammar.grammar_id.value}"
    if tag in warnings:
        return scene
    warnings.append(tag)
    if grammar.p0_showcase:
        warnings.append(f"vq5_p0:{grammar.grammar_id.value}")

    nodes = list(scene.nodes)
    for index, node in enumerate(nodes):
        if not isinstance(node, TextNode) or node.semantic_role != "title":
            continue
        boost = grammar.title_size_boost
        new_size = min(72.0, round(node.font_size * boost, 1))
        updates: dict[str, object] = {
            "font_size": new_size,
            "letter_spacing": max(node.letter_spacing, grammar.letter_spacing_em),
            "font_weight": max(node.font_weight, 700),
        }
        updated = node.model_copy(update=updates)
        if node.runs:
            scaled = [
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
                    font_weight=max(run.font_weight or 400, 700),
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
            set_text_node_runs(updated, scaled)
        nodes[index] = updated
        break

    scene = scene.model_copy(update={"nodes": nodes, "warnings": warnings})

    # Re-compose color with grammar background mode when we can resolve hex.
    from archium.domain.visual.defaults import default_presentation_design_system

    design = default_presentation_design_system()
    # Prefer scene theme tokens when present.
    if scene.theme_tokens.colors.get("background"):
        try:
            design = design.model_copy(
                update={
                    "colors": design.colors.model_copy(
                        update={
                            "background": scene.theme_tokens.colors.get(
                                "background", design.colors.background
                            ),
                            "accent": scene.theme_tokens.colors.get(
                                "accent", design.colors.accent
                            ),
                            "primary": scene.theme_tokens.colors.get(
                                "primary", design.colors.primary
                            ),
                            "primary_text": scene.theme_tokens.colors.get(
                                "primary_text", design.colors.primary_text
                            ),
                        }
                    )
                }
            )
        except Exception:
            pass
    color = compose_color_composition(
        design_system=design,
        page_kind=grammar.typography_page_kind,
        background_mode_override=grammar.background_mode,
        visual_intent=visual_intent,
        palette_locked=any(
            str(w).startswith("style_overlay:colors=")
            or str(w) == "color_composition:palette_locked"
            for w in scene.warnings
        ),
    )
    color = color.model_copy(
        update={
            "accent_ratio": max(color.accent_ratio, grammar.accent_ratio),
            "source": f"vq5:{grammar.grammar_id.value}",
        }
    )
    scene = apply_color_composition_to_scene(scene, color)

    motif = compose_graphic_motif(
        page_kind=grammar.typography_page_kind,
        visual_intent=visual_intent,
    )
    motif = motif.model_copy(
        update={
            "motif_type": grammar.motif_type,
            "motif_id": f"grammar:{grammar.grammar_id.value}",
            "source": f"vq5:{grammar.grammar_id.value}",
            # PATH_SEQUENCE freeform needs ≥3 centers; never floor below that.
            "max_marks": max(
                motif.max_marks,
                3
                if grammar.p0_showcase
                or grammar.motif_type.value == "path_sequence"
                else 2,
            ),
        }
    )
    return apply_graphic_motif_to_scene(scene, motif, accent_hex=color.accent_hex)


__all__ = [
    "apply_grammar_to_direction",
    "apply_grammar_to_language",
    "apply_grammar_to_scene",
    "list_architectural_grammars",
    "select_architectural_grammar",
]
