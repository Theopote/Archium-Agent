"""Compose page VisualLanguageSpec from concept + slide (Visual seat, rule catalog)."""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.page_direction import NarrativeEmotion, PageDirection
from archium.domain.visual.page_visual_grammar import (
    PageVisualFormula,
    select_page_formula,
)
from archium.domain.visual.primitives import resolve_primitives
from archium.domain.visual.visual_budget import (
    BUDGET_CALM,
    BUDGET_CLIMAX,
    BUDGET_DECISION,
    BUDGET_PROBLEM,
    BUDGET_STRATEGY,
    VisualBudget,
)
from archium.domain.visual.style.presets import StylePreset
from archium.domain.visual.visual_concept import VisualConcept, VisualMetaphor
from archium.domain.visual.visual_language import (
    ArchitecturalSymbolId,
    CardStyle,
    ColorRole,
    ColorStory,
    DecorationId,
    DecorationRecipe,
    DividerKind,
    ImageBehavior,
    ImageMaskKind,
    ImageMaskSpec,
    TitleCase,
    TitleDecoration,
    TitleScale,
    Tracking,
    TypographyRecipe,
    TypographyRecipeId,
    TypographyRole,
    VisualLanguageSpec,
    primary_role_for_recipe,
)
from archium.domain.visual.visual_language.atmosphere import atmosphere_for_context
from archium.domain.visual.visual_language.image_composition import (
    image_composition_for_context,
)
from archium.domain.visual.visual_language.image_mask import mask_for_image_behavior

# Case / product bilingual labels (architecture report convention).
_TITLE_EN: dict[str, str] = {
    "封面": "HOSPITAL RENEWAL",
    "设计策略": "DESIGN STRATEGY",
    "流线冲突": "CIRCULATION CONFLICT",
    "区位与交通": "SITE & ACCESS",
    "效果表达": "ATMOSPHERE",
    "现状问题总览": "SITE PROBLEMS",
}

_BUDGET_BY_EMOTION: dict[NarrativeEmotion, VisualBudget] = {
    NarrativeEmotion.PROBLEM: BUDGET_PROBLEM,
    NarrativeEmotion.STRATEGY: BUDGET_STRATEGY,
    NarrativeEmotion.CLIMAX: BUDGET_CLIMAX,
    NarrativeEmotion.CALM: BUDGET_CALM,
    NarrativeEmotion.DECISION: BUDGET_DECISION,
}


class VisualLanguageService:
    """Rule-first visual rhetoric — VisualLanguage + budget + primitives."""

    def compose(
        self,
        slide: SlideSpec,
        direction: PageDirection,
        *,
        concept: VisualConcept | None = None,
        style_preset: StylePreset | None = None,
    ) -> VisualLanguageSpec:
        concept = concept if concept is not None else direction.visual_concept
        formula = self._formula_for(slide, direction, concept)
        budget = self._budget_for(direction, concept)
        typography = self._typography_for(slide, direction)
        color_story = self._color_story_for(concept, direction)
        decoration = self._decoration_for(slide, direction, typography, budget)
        symbols = self._symbols_for(concept, direction, budget)
        primitives = self._primitives_for(concept, budget, typography, formula)
        image_behavior = ImageBehavior.INHERIT
        if direction.narrative_emotion == NarrativeEmotion.CLIMAX:
            image_behavior = ImageBehavior.HERO_FULL
        if concept is not None and concept.visual_metaphor in {
            VisualMetaphor.EXISTING_TO_TRANSFORMATION,
            VisualMetaphor.CORE_TO_EXPANSION,
        }:
            image_behavior = ImageBehavior.MASKED_OVERLAY
        image_mask = self._image_mask_for(concept, image_behavior, formula)
        atmosphere = atmosphere_for_context(
            formula_id=formula.id.value if formula else None,
            metaphor=(
                concept.visual_metaphor.value if concept is not None else None
            ),
            emotion=direction.narrative_emotion.value,
        )
        image_composition = image_composition_for_context(
            formula_id=formula.id.value if formula else None,
            metaphor=(
                concept.visual_metaphor.value if concept is not None else None
            ),
            emotion=direction.narrative_emotion.value,
        )
        spec = VisualLanguageSpec(
            typography=typography,
            color_story=color_story,
            decoration=decoration,
            symbols=symbols,
            primitive_ids=primitives,
            image_behavior=image_behavior,
            image_mask=image_mask,
            atmosphere=atmosphere,
            image_composition=image_composition,
            source="visual_rhetoric_v1",
        )
        if style_preset is not None:
            from archium.domain.visual.art_direction_profile import (
                apply_profile_to_language,
                profile_for_style_preset,
            )

            profile = profile_for_style_preset(style_preset)
            spec, _budget = apply_profile_to_language(spec, budget, profile)
            spec = spec.model_copy(update={"source": f"ad:{profile.style_preset_id}"})
        return spec

    def apply(
        self,
        direction: PageDirection,
        language: VisualLanguageSpec | None,
        *,
        concept: VisualConcept | None = None,
        slide: SlideSpec | None = None,
        style_preset: StylePreset | None = None,
    ) -> PageDirection:
        if language is None:
            return direction
        concept = concept if concept is not None else direction.visual_concept
        budget = self._budget_for(direction, concept)
        if style_preset is not None:
            from archium.domain.visual.art_direction_profile import (
                apply_profile_to_typography_and_budget,
                profile_for_style_preset,
            )

            profile = profile_for_style_preset(style_preset)
            _, budget = apply_profile_to_typography_and_budget(
                language.typography, budget, profile
            )
        formula = None
        if slide is not None:
            formula = self._formula_for(slide, direction, concept)
        evidence = list(direction.evidence)
        evidence.append(f"visual_language:{language.typography.recipe.value}")
        if formula is not None:
            evidence.append(f"page_grammar:{formula.id.value}")
        if language.primitive_ids:
            evidence.append("primitives:" + ",".join(language.primitive_ids[:6]))
        evidence.append(
            f"visual_budget:lines≤{budget.decorative_lines}/icons≤{budget.icons}"
        )
        if language.color_story.roles:
            evidence.append(
                "color_roles:"
                + ",".join(f"{k}={v}" for k, v in language.color_story.roles.items())
            )
        hide = list(direction.must_hide)
        if formula is not None:
            hide = list(dict.fromkeys([*hide, *formula.must_hide]))
        updates: dict[str, object] = {
            "visual_language": language,
            "visual_budget": budget,
            "page_grammar": formula,
            "must_hide": hide,
            "evidence": evidence,
        }
        if direction.visual_concept is not None and language.color_story.roles:
            updates["visual_concept"] = direction.visual_concept.model_copy(
                update={"color_story": language.color_story.as_legacy_list()}
            )
        return direction.model_copy(update=updates)

    def _formula_for(
        self,
        slide: SlideSpec,
        direction: PageDirection,
        concept: VisualConcept | None,
    ) -> PageVisualFormula:
        metaphor = (
            concept.visual_metaphor.value if concept is not None else None
        )
        return select_page_formula(
            emotion=direction.narrative_emotion.value,
            situation_rule_id=direction.situation_rule_id,
            expression_mode_id=direction.expression_mode_id,
            metaphor=metaphor,
            title=slide.title,
        )

    def _image_mask_for(
        self,
        concept: VisualConcept | None,
        behavior: ImageBehavior,
        formula: PageVisualFormula | None,
    ) -> ImageMaskSpec:
        if concept is not None and concept.visual_metaphor == VisualMetaphor.EXISTING_TO_TRANSFORMATION:
            return ImageMaskSpec(
                kind=ImageMaskKind.GRADIENT_FADE,
                corner_radius=0.05,
                edge_softness=0.5,
                source="concept:existing_to_transformation",
            )
        if concept is not None and concept.visual_metaphor == VisualMetaphor.CORE_TO_EXPANSION:
            return ImageMaskSpec(
                kind=ImageMaskKind.CIRCLE,
                corner_radius=0.0,
                edge_softness=0.2,
                target_roles=["hero_visual", "supporting_visual"],
                source="concept:core_to_expansion",
            )
        if formula is not None and formula.id.value == "hero_statement":
            return ImageMaskSpec(
                kind=ImageMaskKind.NONE,
                corner_radius=0.0,
                source="formula:hero_statement",
            )
        if formula is not None and formula.id.value == "monument_image":
            return ImageMaskSpec(
                kind=ImageMaskKind.SILHOUETTE,
                corner_radius=0.0,
                edge_softness=0.55,
                source="formula:monument_image",
            )
        return mask_for_image_behavior(behavior.value)

    def _budget_for(
        self,
        direction: PageDirection,
        concept: VisualConcept | None,
    ) -> VisualBudget:
        base = _BUDGET_BY_EMOTION.get(direction.narrative_emotion, BUDGET_CALM)
        if concept is None:
            return base.model_copy(deep=True)
        # Concept may tighten hero_ratio via drawing_min_area_ratio.
        hero = base.hero_ratio
        if concept.drawing_min_area_ratio is not None:
            hero = max(hero, concept.drawing_min_area_ratio)
        if concept.visual_metaphor == VisualMetaphor.FRAGMENT_TO_NETWORK:
            # Need room for gray existing + green network segments (Primitive Engine pack).
            return base.model_copy(
                update={
                    "hero_ratio": min(0.65, hero),
                    "accent_elements": min(base.accent_elements, 3),
                    "decorative_lines": max(5, min(base.decorative_lines, 6)),
                    "icons": min(base.icons, 2),
                    "color_blocks": min(base.color_blocks, 1),
                }
            )
        if concept.visual_metaphor == VisualMetaphor.EXISTING_TO_TRANSFORMATION:
            return base.model_copy(
                update={
                    "hero_ratio": max(0.55, hero),
                    "decorative_lines": min(base.decorative_lines, 2),
                    "icons": min(base.icons, 2),
                    "color_blocks": min(base.color_blocks, 1),
                }
            )
        return base.model_copy(update={"hero_ratio": hero})

    def _typography_for(
        self, slide: SlideSpec, direction: PageDirection
    ) -> TypographyRecipe:
        title = (slide.title or "").strip()
        english = _TITLE_EN.get(title)

        if title == "封面":
            return TypographyRecipe(
                recipe=TypographyRecipeId.GIANT_BILINGUAL,
                primary_role=TypographyRole.HERO_TITLE,
                scale=TitleScale.GIANT,
                tracking=Tracking.WIDE,
                case=TitleCase.AS_IS,
                decoration=TitleDecoration.THIN_LINE,
                bilingual=True,
                english_label=english or "CAMPUS UPDATE",
                title_font_size_pt=54,
                english_font_size_pt=14,
                letter_spacing_em=0.08,
                opacity=0.95,
            )

        if title == "设计策略" or (
            direction.narrative_emotion == NarrativeEmotion.STRATEGY
            and title in {"设计策略", "策略总览"}
        ):
            return TypographyRecipe(
                recipe=TypographyRecipeId.ARCHITECTURAL_TITLE,
                primary_role=TypographyRole.SECTION_TITLE,
                scale=TitleScale.LARGE,
                tracking=Tracking.WIDE,
                case=TitleCase.AS_IS,
                decoration=TitleDecoration.THIN_LINE,
                bilingual=True,
                english_label=english or "DESIGN STRATEGY",
                title_font_size_pt=36,
                english_font_size_pt=12,
                letter_spacing_em=0.06,
                opacity=1.0,
            )

        if title in {"流线冲突", "交通冲突", "人车混行"}:
            return TypographyRecipe(
                recipe=TypographyRecipeId.ARCHITECTURAL_TITLE,
                primary_role=TypographyRole.SECTION_TITLE,
                scale=TitleScale.LARGE,
                tracking=Tracking.NORMAL,
                case=TitleCase.AS_IS,
                decoration=TitleDecoration.THIN_LINE,
                bilingual=True,
                english_label=english or "CIRCULATION CONFLICT",
                title_font_size_pt=32,
                english_font_size_pt=11,
                letter_spacing_em=0.04,
                opacity=1.0,
            )

        return TypographyRecipe(
            recipe=TypographyRecipeId.DEFAULT,
            primary_role=primary_role_for_recipe(TypographyRecipeId.DEFAULT),
        )

    def _color_story_for(
        self,
        concept: VisualConcept | None,
        direction: PageDirection,
    ) -> ColorStory:
        # Prefer full VisualNarrative color roles when present.
        if concept is not None and concept.narrative is not None and concept.narrative.color_roles:
            roles = dict(concept.narrative.color_roles)
            meaning = {swatch: role for role, swatch in roles.items()}
            return ColorStory(
                roles=roles,
                meaning=meaning,
                source=concept.narrative.source,
            )
        if concept is not None and concept.visual_metaphor == VisualMetaphor.FRAGMENT_TO_NETWORK:
            return ColorStory(
                roles={
                    ColorRole.EXISTING.value: "gray",
                    ColorRole.CONFLICT.value: "red",
                    ColorRole.INTERVENTION.value: "renew_green",
                    ColorRole.FUTURE.value: "white",
                },
                meaning={
                    "gray": "existing",
                    "red": "conflict",
                    "renew_green": "intervention",
                    "white": "future",
                },
                source="grammar_v1:fragment_to_network",
            )
        if direction.narrative_emotion == NarrativeEmotion.CLIMAX:
            return ColorStory(
                roles={
                    ColorRole.NEUTRAL.value: "ink_black",
                    ColorRole.ACCENT.value: "warm_white",
                },
                meaning={"ink_black": "structure", "warm_white": "atmosphere"},
                source="visual_language_v1:climax",
            )
        if direction.narrative_emotion == NarrativeEmotion.STRATEGY:
            return ColorStory(
                roles={
                    ColorRole.EXISTING.value: "stone_gray",
                    ColorRole.INTERVENTION.value: "renew_green",
                },
                meaning={
                    "stone_gray": "existing",
                    "renew_green": "intervention",
                },
                source="visual_language_v1:strategy",
            )
        if concept is not None and concept.color_story:
            roles: dict[str, str] = {}
            meaning: dict[str, str] = {}
            palette = list(concept.color_story)
            role_order = [
                ColorRole.EXISTING,
                ColorRole.CONFLICT,
                ColorRole.FUTURE,
                ColorRole.ACCENT,
            ]
            for index, swatch in enumerate(palette[:4]):
                roles[role_order[index].value] = swatch
                meaning[swatch] = role_order[index].value
            return ColorStory(roles=roles, meaning=meaning, source=concept.source)
        return ColorStory()

    def _decoration_for(
        self,
        slide: SlideSpec,
        direction: PageDirection,
        typography: TypographyRecipe,
        budget: VisualBudget,
    ) -> DecorationRecipe:
        title = (slide.title or "").strip()
        decorations: list[DecorationId] = []
        divider: DividerKind | None = None
        section_index: str | None = None
        section_label: str | None = None
        card_style = CardStyle.NONE

        if typography.decoration == TitleDecoration.THIN_LINE and budget.decorative_lines > 0:
            decorations.append(DecorationId.THIN_LINE)
            divider = DividerKind.HORIZONTAL_RULE

        if title == "设计策略":
            if budget.decorative_lines >= 1:
                decorations.append(DecorationId.SECTION_LABEL_01)
            if budget.decorative_lines >= 2:
                decorations.append(DecorationId.AXIS_LINE)
            divider = DividerKind.SECTION_INDEX
            section_index = "01"
            section_label = "STRATEGY"
            card_style = CardStyle.TECHNICAL
        elif title == "封面":
            if budget.decorative_lines >= 1:
                decorations.append(DecorationId.THIN_LINE)
        elif title in {"流线冲突", "交通冲突"}:
            if budget.decorative_lines >= 1:
                decorations.append(DecorationId.AXIS_LINE)
            divider = DividerKind.VERTICAL_AXIS

        # Cap decoration list by visual_budget.decorative_lines (+ section label counts as one).
        unique: list[DecorationId] = []
        seen: set[DecorationId] = set()
        for item in decorations:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        line_like = [
            d
            for d in unique
            if d in {DecorationId.THIN_LINE, DecorationId.AXIS_LINE}
        ]
        other = [d for d in unique if d not in set(line_like)]
        line_like = line_like[: budget.decorative_lines]
        unique = other + line_like

        return DecorationRecipe(
            decorations=unique,
            divider_kind=divider,
            section_index=section_index,
            section_label=section_label,
            card_style=card_style,
        )

    def _symbols_for(
        self,
        concept: VisualConcept | None,
        direction: PageDirection,
        budget: VisualBudget,
    ) -> list[ArchitecturalSymbolId]:
        if budget.icons <= 0:
            return []
        symbols: list[ArchitecturalSymbolId] = []
        if concept is not None and concept.visual_metaphor == VisualMetaphor.FRAGMENT_TO_NETWORK:
            symbols = [
                ArchitecturalSymbolId.CIRCULATION_FLOW,
                ArchitecturalSymbolId.AXIS,
            ]
        elif direction.situation_rule_id == "site_traffic_conflict":
            symbols = [ArchitecturalSymbolId.CIRCULATION_FLOW]
        return symbols[: budget.icons]

    def _primitives_for(
        self,
        concept: VisualConcept | None,
        budget: VisualBudget,
        typography: TypographyRecipe,
        formula: PageVisualFormula | None = None,
    ) -> list[str]:
        ids: list[str] = []
        if typography.recipe == TypographyRecipeId.GIANT_BILINGUAL:
            ids.append("hero_statement")
        if formula is not None:
            ids.extend(formula.default_primitive_ids)
        if concept is not None and concept.narrative is not None:
            ids.extend(concept.narrative.recommended_components)
        cap = max(1, budget.accent_elements + budget.icons)
        resolved = resolve_primitives(ids)
        return [p.id for p in resolved[:cap]]
