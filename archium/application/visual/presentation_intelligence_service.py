"""Presentation Intelligence service — Visual seat facade (no new Agent).

Unifies Style Preset, DeckComposition, and Page Director into a product brief
and applies page-level direction when building showcase / offline decks.
"""

from __future__ import annotations

from archium.application.visual.page_direction_service import PageDirectionService
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    VisualIntensity,
    climax_budget_for_deck,
    is_climax_peak,
)
from archium.domain.visual.presentation_intelligence import PresentationIntelligenceBrief
from archium.domain.visual.style import get_style_preset, resolve_style_preset_id
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    content_from_slide,
)


class PresentationIntelligenceService:
    """Product narrative over existing Visual services — not a parallel engine."""

    def __init__(self, director: PageDirectionService | None = None) -> None:
        self._director = director or PageDirectionService()

    def direct_deck_intents(
        self,
        slides: list[SlideSpec],
        intents: list[VisualIntent],
        composition: DeckCompositionPlan,
        *,
        style_preset_id: str | None = None,
    ) -> list[VisualIntent]:
        """Run Page Director per slide and stamp results onto VisualIntent."""
        preset = get_style_preset(resolve_style_preset_id(style_preset_id))
        out: list[VisualIntent] = []
        for slide, intent, directive in zip(
            slides, intents, composition.slide_directives, strict=True
        ):
            direction = self._director.direct(
                slide,
                deck_directive=directive,
                style_preset=preset,
                existing_intent=intent,
            )
            directed = self._director.apply_to_intent(intent, direction)
            # Rhythm density wins when Director did not override.
            if direction.density_override is None:
                directed = directed.model_copy(
                    update={"density_level": directive.target_density}
                )
            # Prefer director families; fall back to composition directive.
            families = list(directed.preferred_layout_families) or list(
                directive.preferred_layout_families
            )
            if families:
                directed = directed.model_copy(
                    update={"preferred_layout_families": families[:3]}
                )
            out.append(directed)
        return out

    def clip_slide_copy(self, slide: SlideSpec, intent: VisualIntent) -> SlideSpec:
        """Enforce PageDirection copy budget on slide text (deterministic)."""
        direction = intent.page_direction
        if direction is None:
            return slide
        budget = direction.copy_budget
        title = (slide.title or "")[: budget.max_title_chars]
        message = (slide.message or "")[: budget.max_message_chars]
        if direction.single_message:
            message = direction.single_message[: budget.max_message_chars]
        points = list(slide.key_points or [])[: budget.max_key_points]
        return slide.model_copy(
            update={
                "title": title or slide.title,
                "message": message or slide.message,
                "key_points": points,
            }
        )

    def content_for_intent(
        self, slide: SlideSpec, intent: VisualIntent
    ) -> LayoutContentBundle:
        clipped = self.clip_slide_copy(slide, intent)
        return content_from_slide(clipped, intent)

    def build_brief(
        self,
        *,
        style_preset_id: str,
        slides: list[SlideSpec],
        intents: list[VisualIntent],
        composition: DeckCompositionPlan,
        case_id: str | None = None,
        audience_summary: str = "",
        demo_tour_titles: list[str] | None = None,
    ) -> PresentationIntelligenceBrief:
        preset = get_style_preset(resolve_style_preset_id(style_preset_id))
        peaks = [
            slides[d.slide_index].title
            for d in composition.slide_directives
            if is_climax_peak(d) and 0 <= d.slide_index < len(slides)
        ]
        density = list(composition.density_curve)
        curve = _emotional_curve_labels(composition)
        hits = sum(1 for intent in intents if intent.page_direction is not None)
        rules = [
            intent.page_direction.situation_rule_id
            for intent in intents
            if intent.page_direction and intent.page_direction.situation_rule_id
        ]
        personality = preset.presentation_personality
        policy = preset.content_policy
        policy_summary = (
            f"msg≤{policy.max_message_chars} · pts≤{policy.max_key_points} · "
            f"img≤{policy.max_images} · diagram≤{policy.max_diagrams}"
        )
        checks = [
            f"气质：{preset.display_name}",
            (
                f"叙事：{personality.logic.value} / 情绪 {personality.emotion.value} / "
                f"图面 {personality.image_role.value}"
            ),
            f"内容政策：{policy_summary}",
            f"高潮页 ≤{climax_budget_for_deck(len(slides))}（实际 {len(peaks)}）",
            "密度波形非平" if density and max(density) > min(density) else "密度波形偏平",
            f"页面导演命中 {hits}/{len(intents)} 页",
        ]
        if demo_tour_titles:
            checks.append("Demo 导览：" + " → ".join(demo_tour_titles))

        rhythm = (
            f"{len(slides)} 页；高潮 {len(peaks)} 处"
            + (f"（{' / '.join(peaks)}）" if peaks else "")
            + (
                f"；密度 {min(density):.2f}–{max(density):.2f}"
                if density
                else ""
            )
        )
        return PresentationIntelligenceBrief(
            case_id=case_id,
            style_preset_id=preset.id.value,
            project_personality=preset.display_name,
            personality_blurb=preset.description[:400],
            narrative_logic=personality.logic.value,
            emotion_level=personality.emotion.value,
            image_role=personality.image_role.value,
            content_policy_summary=policy_summary,
            audience_summary=audience_summary
            or "院方 / 建设方 / 投资决策层（医院更新汇报）",
            story_rhythm=rhythm,
            emotional_curve=curve,
            climax_titles=peaks,
            density_min=min(density) if density else None,
            density_max=max(density) if density else None,
            page_direction_hits=hits,
            situation_rules_fired=list(dict.fromkeys(rules)),
            first_impression_checks=checks,
            demo_tour_titles=list(demo_tour_titles or []),
        )


def _emotional_curve_labels(composition: DeckCompositionPlan) -> list[str]:
    labels: list[str] = []
    for directive in composition.slide_directives:
        intensity = directive.visual_intensity
        if intensity == VisualIntensity.HERO:
            labels.append("peak")
        elif intensity == VisualIntensity.HIGH:
            labels.append("rise")
        elif intensity == VisualIntensity.LOW:
            labels.append("calm")
        else:
            labels.append("steady")
    return labels
