"""Compose page VisualLanguageSpec from concept + slide (Visual seat, rule catalog)."""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.page_direction import NarrativeEmotion, PageDirection
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
    TitleCase,
    TitleDecoration,
    TitleScale,
    Tracking,
    TypographyRecipe,
    TypographyRecipeId,
    VisualLanguageSpec,
)

# Case / product bilingual labels (architecture report convention).
_TITLE_EN: dict[str, str] = {
    "封面": "HOSPITAL RENEWAL",
    "设计策略": "DESIGN STRATEGY",
    "流线冲突": "CIRCULATION CONFLICT",
    "区位与交通": "SITE & ACCESS",
    "效果表达": "ATMOSPHERE",
    "现状问题总览": "SITE PROBLEMS",
}


class VisualLanguageService:
    """Rule-first visual rhetoric — no LLM required for v1."""

    def compose(
        self,
        slide: SlideSpec,
        direction: PageDirection,
        *,
        concept: VisualConcept | None = None,
    ) -> VisualLanguageSpec:
        concept = concept if concept is not None else direction.visual_concept
        typography = self._typography_for(slide, direction)
        color_story = self._color_story_for(concept, direction)
        decoration = self._decoration_for(slide, direction, typography)
        symbols = self._symbols_for(concept, direction)
        image_behavior = ImageBehavior.INHERIT
        if direction.narrative_emotion == NarrativeEmotion.CLIMAX:
            image_behavior = ImageBehavior.HERO_FULL
        return VisualLanguageSpec(
            typography=typography,
            color_story=color_story,
            decoration=decoration,
            symbols=symbols,
            image_behavior=image_behavior,
            source="visual_language_v1",
        )

    def apply(
        self,
        direction: PageDirection,
        language: VisualLanguageSpec | None,
    ) -> PageDirection:
        if language is None:
            return direction
        evidence = list(direction.evidence)
        evidence.append(f"visual_language:{language.typography.recipe.value}")
        if language.color_story.roles:
            evidence.append(
                "color_roles:"
                + ",".join(f"{k}={v}" for k, v in language.color_story.roles.items())
            )
        updates: dict[str, object] = {
            "visual_language": language,
            "evidence": evidence,
        }
        # Keep VisualConcept.color_story list in sync when concept exists.
        if direction.visual_concept is not None and language.color_story.roles:
            updates["visual_concept"] = direction.visual_concept.model_copy(
                update={"color_story": language.color_story.as_legacy_list()}
            )
        return direction.model_copy(update=updates)

    def _typography_for(
        self, slide: SlideSpec, direction: PageDirection
    ) -> TypographyRecipe:
        title = (slide.title or "").strip()
        english = _TITLE_EN.get(title)

        if title == "封面" or direction.narrative_emotion == NarrativeEmotion.CLIMAX and title in {
            "封面",
            "总体愿景",
            "效果表达",
        }:
            if title == "封面":
                return TypographyRecipe(
                    recipe=TypographyRecipeId.GIANT_BILINGUAL,
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

        # Overview pages must stay restrained (no giant title).
        return TypographyRecipe(recipe=TypographyRecipeId.DEFAULT)

    def _color_story_for(
        self,
        concept: VisualConcept | None,
        direction: PageDirection,
    ) -> ColorStory:
        if concept is not None and concept.visual_metaphor == VisualMetaphor.FRAGMENT_TO_NETWORK:
            return ColorStory(
                roles={
                    ColorRole.EXISTING.value: "gray",
                    ColorRole.CONFLICT.value: "red",
                    ColorRole.FUTURE.value: "white",
                },
                meaning={
                    "gray": "existing",
                    "stone_gray": "existing",
                    "red": "conflict",
                    "alert_red": "conflict",
                    "white": "future",
                    "warm_white": "future",
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
    ) -> DecorationRecipe:
        title = (slide.title or "").strip()
        decorations: list[DecorationId] = []
        divider: DividerKind | None = None
        section_index: str | None = None
        section_label: str | None = None
        card_style = CardStyle.NONE

        if typography.decoration == TitleDecoration.THIN_LINE:
            decorations.append(DecorationId.THIN_LINE)
            divider = DividerKind.HORIZONTAL_RULE

        if title == "设计策略":
            decorations.extend(
                [DecorationId.SECTION_LABEL_01, DecorationId.AXIS_LINE]
            )
            divider = DividerKind.SECTION_INDEX
            section_index = "01"
            section_label = "STRATEGY"
            card_style = CardStyle.TECHNICAL
        elif title == "封面":
            decorations.append(DecorationId.THIN_LINE)
        elif title in {"流线冲突", "交通冲突"}:
            decorations.append(DecorationId.AXIS_LINE)
            divider = DividerKind.VERTICAL_AXIS

        # Deduplicate while preserving order.
        seen: set[DecorationId] = set()
        unique: list[DecorationId] = []
        for item in decorations:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)

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
    ) -> list[ArchitecturalSymbolId]:
        if concept is not None and concept.visual_metaphor == VisualMetaphor.FRAGMENT_TO_NETWORK:
            return [ArchitecturalSymbolId.CIRCULATION_FLOW, ArchitecturalSymbolId.AXIS]
        if direction.situation_rule_id == "site_traffic_conflict":
            return [ArchitecturalSymbolId.CIRCULATION_FLOW]
        return []
