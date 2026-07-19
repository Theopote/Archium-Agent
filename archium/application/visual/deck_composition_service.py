"""Plan deck-wide visual rhythm before per-slide layout candidate generation."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    PacingRole,
    SectionCompositionPlan,
    SlideCompositionDirective,
    VisualIntensity,
    density_to_score,
    intensity_to_score,
)
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry

_TEXT_FAMILIES = frozenset({LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.STRATEGY_CARDS})
_VISUAL_STRONG_FAMILIES = frozenset(
    {
        LayoutFamily.HERO,
        LayoutFamily.DRAWING_FOCUS,
        LayoutFamily.EVIDENCE_BOARD,
        LayoutFamily.HYBRID_CANVAS,
    }
)
_DRAWING_FAMILIES = frozenset({LayoutFamily.DRAWING_FOCUS, LayoutFamily.ANALYTICAL_DIAGRAM})
_DEFAULT_VARIETY_RULES = (
    "连续三页不得使用相同 LayoutFamily",
    "连续两页不得使用完全相同 Variant",
    "每个主要章节至少有一个视觉强页",
    "章节开头应有明确过渡",
    "高密度页后优先安排低密度页",
    "纯文字页不得连续出现三页",
    "大图页不宜连续过多",
    "图纸页之间应有分析或结论页调节",
    "总结页必须形成视觉收束",
)


class DeckCompositionPlanningService:
    """Derive deck rhythm directives from slides, intents, and art direction."""

    def plan(
        self,
        *,
        presentation_id: UUID,
        art_direction_id: UUID,
        slides: list[SlideSpec],
        visual_intents: list[VisualIntent],
        art_direction: ArtDirection | None = None,
        auto_approve: bool = True,
    ) -> DeckCompositionPlan:
        ordered = sorted(slides, key=lambda item: item.order)
        intent_by_slide = {intent.slide_id: intent for intent in visual_intents}
        missing = [slide.id for slide in ordered if slide.id not in intent_by_slide]
        if missing:
            msg = f"Missing VisualIntent for slide(s): {missing[:3]}"
            raise ValueError(msg)

        directives = [
            self._initial_directive(
                index=index,
                slide=slide,
                intent=intent_by_slide[slide.id],
                previous=intent_by_slide[ordered[index - 1].id] if index > 0 else None,
            )
            for index, slide in enumerate(ordered)
        ]
        variety_notes: list[str] = []
        self._apply_family_variety(directives, variety_notes)
        self._apply_density_pacing(directives, variety_notes)
        self._apply_text_rhythm(directives, variety_notes)
        self._apply_drawing_rhythm(directives, variety_notes)

        section_strategies = self._build_section_strategies(ordered, directives)
        hero_ids, transition_ids, climax_ids = self._identify_anchor_slides(
            ordered, directives
        )
        distribution = Counter(
            directive.preferred_layout_families[0].value for directive in directives
        )

        pacing_strategy = (
            art_direction.pacing_strategy
            if art_direction is not None
            else "开篇建立语境 → 证据展开 → 分析比较 → 收束决策"
        )
        composition_strategy = (
            art_direction.content_strategy
            if art_direction is not None
            else "保持标题与页脚稳定，章节间形成视觉对比，关键页放大主图或图纸。"
        )

        plan = DeckCompositionPlan(
            presentation_id=presentation_id,
            art_direction_id=art_direction_id,
            composition_strategy=composition_strategy,
            pacing_strategy=pacing_strategy,
            section_strategies=section_strategies,
            slide_directives=directives,
            layout_family_distribution=dict(distribution),
            visual_intensity_curve=[
                intensity_to_score(item.visual_intensity) for item in directives
            ],
            density_curve=[density_to_score(item.target_density) for item in directives],
            hero_slide_ids=hero_ids,
            section_transition_slide_ids=transition_ids,
            climax_slide_ids=climax_ids,
            consistency_rules=list(art_direction.consistency_rules)
            if art_direction and art_direction.consistency_rules
            else [
                "标题与页脚位置跨页保持一致",
                "同一章节内色彩与字体 token 不漂移",
            ],
            variety_rules=list(_DEFAULT_VARIETY_RULES) + variety_notes,
        )
        if auto_approve:
            plan.approve()
        return plan

    def revise(
        self,
        plan: DeckCompositionPlan,
        feedback: str,
        *,
        slides: list[SlideSpec],
        visual_intents: list[VisualIntent],
        art_direction: ArtDirection | None = None,
    ) -> DeckCompositionPlan:
        """Re-plan with lightweight feedback hints."""
        normalized = feedback.strip().lower()
        revised = self.plan(
            presentation_id=plan.presentation_id,
            art_direction_id=plan.art_direction_id,
            slides=slides,
            visual_intents=visual_intents,
            art_direction=art_direction,
            auto_approve=False,
        )
        revised.id = plan.id
        revised.version = plan.version + 1
        revised.composition_strategy = f"{plan.composition_strategy}（修订：{feedback.strip()}）"

        if any(token in normalized for token in ("节奏", "pacing", "单调")):
            for directive in revised.slide_directives:
                if directive.pacing_role not in {
                    PacingRole.OPENING,
                    PacingRole.CLOSING,
                }:
                    directive.should_contrast_previous = True
        if any(token in normalized for token in ("视觉", "hero", "主图", "图纸")):
            for directive in revised.slide_directives:
                if directive.drawing_priority >= 0.5 or directive.hero_priority >= 0.5:
                    directive.visual_intensity = VisualIntensity.HERO
                    directive.hero_priority = min(1.0, directive.hero_priority + 0.15)
            revised.visual_intensity_curve = [
                intensity_to_score(item.visual_intensity) for item in revised.slide_directives
            ]
        if any(token in normalized for token in ("文字", "text", "密度", "density")):
            for directive in revised.slide_directives:
                if directive.text_priority >= 0.6:
                    directive.target_density = DensityLevel.SPACIOUS
                    directive.text_priority = max(0.2, directive.text_priority - 0.1)
            revised.density_curve = [
                density_to_score(item.target_density) for item in revised.slide_directives
            ]

        revised.approval_status = plan.approval_status
        revised.touch()
        return revised

    def _initial_directive(
        self,
        *,
        index: int,
        slide: SlideSpec,
        intent: VisualIntent,
        previous: VisualIntent | None,
    ) -> SlideCompositionDirective:
        pacing_role = _pacing_role_for(slide, intent)
        visual_intensity = _visual_intensity_for(slide, intent, pacing_role)
        hero_priority, text_priority, drawing_priority = _content_priorities(intent)
        preferred = list(intent.preferred_layout_families) or [LayoutFamily.TEXTUAL_ARGUMENT]
        preferred = _implemented_families(preferred)

        transition_mode = None
        should_contrast = False
        should_match = False
        if slide.slide_type == SlideType.SECTION or intent.continuity_role in {
            ContinuityRole.SECTION_OPENING,
            ContinuityRole.TRANSITION,
        }:
            transition_mode = "section_break"
            should_contrast = True
        elif previous is not None and previous.density_level == DensityLevel.COMPACT:
            should_contrast = True
        elif pacing_role == PacingRole.CLOSING:
            should_match = True

        return SlideCompositionDirective(
            slide_id=slide.id,
            slide_index=index,
            narrative_role=_narrative_role(slide, intent, pacing_role),
            pacing_role=pacing_role,
            visual_intensity=visual_intensity,
            target_density=intent.density_level,
            preferred_layout_families=preferred,
            hero_priority=hero_priority,
            text_priority=text_priority,
            drawing_priority=drawing_priority,
            transition_mode=transition_mode,
            continuity_group=slide.chapter_id,
            should_contrast_previous=should_contrast,
            should_match_previous=should_match,
        )

    @staticmethod
    def _apply_family_variety(
        directives: list[SlideCompositionDirective],
        notes: list[str],
    ) -> None:
        for index in range(2, len(directives)):
            current = directives[index]
            prev = directives[index - 1].preferred_layout_families[0]
            prev2 = directives[index - 2].preferred_layout_families[0]
            candidate = current.preferred_layout_families[0]
            if candidate == prev == prev2:
                alternate = _pick_alternate_family(current.preferred_layout_families, prev)
                if alternate is not None:
                    current.preferred_layout_families = [alternate, *current.preferred_layout_families]
                    current.forbidden_layout_families = list(
                        dict.fromkeys([*current.forbidden_layout_families, prev])
                    )
                    current.should_contrast_previous = True
                    notes.append(
                        f"slide_index={index}: 避免连续三页 {prev.value}，改推 {alternate.value}"
                    )

    @staticmethod
    def _apply_density_pacing(
        directives: list[SlideCompositionDirective],
        notes: list[str],
    ) -> None:
        for index in range(1, len(directives)):
            previous = directives[index - 1]
            current = directives[index]
            if previous.target_density == DensityLevel.COMPACT:
                current.target_density = DensityLevel.SPACIOUS
                current.visual_intensity = VisualIntensity.LOW
                notes.append(f"slide_index={index}: 高密度页后安排低密度缓冲")

    @staticmethod
    def _apply_text_rhythm(
        directives: list[SlideCompositionDirective],
        notes: list[str],
    ) -> None:
        streak = 0
        for index, directive in enumerate(directives):
            if directive.preferred_layout_families[0] in _TEXT_FAMILIES:
                streak += 1
            else:
                streak = 0
            if streak >= 3:
                alternate = _pick_alternate_family(
                    directive.preferred_layout_families,
                    LayoutFamily.TEXTUAL_ARGUMENT,
                )
                if alternate is not None:
                    directive.preferred_layout_families = [
                        alternate,
                        *directive.preferred_layout_families,
                    ]
                    directive.forbidden_layout_families.append(LayoutFamily.TEXTUAL_ARGUMENT)
                    directive.should_contrast_previous = True
                    notes.append(
                        f"slide_index={index}: 打断连续纯文字页，改推 {alternate.value}"
                    )
                streak = 0

    @staticmethod
    def _apply_drawing_rhythm(
        directives: list[SlideCompositionDirective],
        notes: list[str],
    ) -> None:
        drawing_streak = 0
        for index, directive in enumerate(directives):
            primary = directive.preferred_layout_families[0]
            if primary in _DRAWING_FAMILIES:
                drawing_streak += 1
            else:
                drawing_streak = 0
            if drawing_streak >= 3:
                directive.preferred_layout_families = [
                    LayoutFamily.TEXTUAL_ARGUMENT,
                    LayoutFamily.STRATEGY_CARDS,
                    *directive.preferred_layout_families,
                ]
                directive.pacing_role = PacingRole.ANALYSIS
                directive.visual_intensity = VisualIntensity.LOW
                directive.text_priority = 0.7
                directive.drawing_priority = 0.3
                directive.should_contrast_previous = True
                notes.append(f"slide_index={index}: 图纸页过多，插入分析/结论文本页调节")
                drawing_streak = 0

    @staticmethod
    def _build_section_strategies(
        slides: list[SlideSpec],
        directives: list[SlideCompositionDirective],
    ) -> list[SectionCompositionPlan]:
        by_chapter: dict[str, list[tuple[SlideSpec, SlideCompositionDirective]]] = {}
        directive_by_slide = {item.slide_id: item for item in directives}
        for slide in slides:
            by_chapter.setdefault(slide.chapter_id, []).append(
                (slide, directive_by_slide[slide.id])
            )

        sections: list[SectionCompositionPlan] = []
        for chapter_id, items in by_chapter.items():
            opening_slide_id = items[0][0].id
            climax_candidate = max(
                items,
                key=lambda pair: intensity_to_score(pair[1].visual_intensity),
            )
            sections.append(
                SectionCompositionPlan(
                    section_id=chapter_id,
                    title=items[0][0].title,
                    opening_slide_id=opening_slide_id,
                    climax_slide_id=climax_candidate[0].id,
                    pacing_notes=f"章节 {chapter_id} 以 {climax_candidate[1].pacing_role.value} 形成高潮",
                    target_visual_intensity=climax_candidate[1].visual_intensity,
                )
            )
        return sections

    @staticmethod
    def _identify_anchor_slides(
        slides: list[SlideSpec],
        directives: list[SlideCompositionDirective],
    ) -> tuple[list[UUID], list[UUID], list[UUID]]:
        directive_by_slide = {item.slide_id: item for item in directives}
        hero_ids: list[UUID] = []
        transition_ids: list[UUID] = []
        climax_ids: list[UUID] = []

        section_seen: set[str] = set()
        for slide in slides:
            directive = directive_by_slide[slide.id]
            if (
                directive.visual_intensity in {VisualIntensity.HERO, VisualIntensity.HIGH}
                or directive.preferred_layout_families[0] in _VISUAL_STRONG_FAMILIES
            ):
                hero_ids.append(slide.id)
            if slide.slide_type == SlideType.SECTION or directive.transition_mode:
                transition_ids.append(slide.id)
            if directive.pacing_role == PacingRole.CLIMAX or directive.visual_intensity == VisualIntensity.HERO:
                climax_ids.append(slide.id)
            if slide.chapter_id not in section_seen:
                section_seen.add(slide.chapter_id)
                if slide.id not in transition_ids:
                    transition_ids.append(slide.id)

        if slides and slides[-1].id not in climax_ids:
            climax_ids.append(slides[-1].id)

        return hero_ids, transition_ids, climax_ids


def _pacing_role_for(slide: SlideSpec, intent: VisualIntent) -> PacingRole:
    if slide.slide_type == SlideType.TITLE or intent.continuity_role == ContinuityRole.OPENING:
        return PacingRole.OPENING
    if slide.slide_type == SlideType.SECTION or intent.continuity_role == ContinuityRole.SECTION_OPENING:
        return PacingRole.TRANSITION
    if slide.slide_type in {SlideType.SUMMARY, SlideType.CLOSING} or intent.continuity_role in {
        ContinuityRole.SUMMARY,
        ContinuityRole.CLOSING,
    }:
        return PacingRole.CLOSING
    if intent.continuity_role == ContinuityRole.EVIDENCE:
        return PacingRole.EVIDENCE
    if intent.continuity_role == ContinuityRole.COMPARISON:
        return PacingRole.ANALYSIS
    if intent.continuity_role == ContinuityRole.CLIMAX:
        return PacingRole.CLIMAX
    if intent.continuity_role == ContinuityRole.TRANSITION:
        return PacingRole.TRANSITION
    if intent.dominant_content_type == VisualContentType.METRICS:
        return PacingRole.DECISION
    return PacingRole.SETUP


def _visual_intensity_for(
    slide: SlideSpec,
    intent: VisualIntent,
    pacing_role: PacingRole,
) -> VisualIntensity:
    if pacing_role in {PacingRole.OPENING, PacingRole.CLOSING}:
        return VisualIntensity.HERO if slide.slide_type == SlideType.TITLE else VisualIntensity.MEDIUM
    if intent.dominant_content_type in {
        VisualContentType.SITE_PLAN,
        VisualContentType.FLOOR_PLAN,
        VisualContentType.SECTION,
        VisualContentType.ELEVATION,
        VisualContentType.HERO_IMAGE,
    }:
        return VisualIntensity.HERO
    if intent.dominant_content_type in {
        VisualContentType.PHOTO_EVIDENCE,
        VisualContentType.ANALYTICAL_DIAGRAM,
        VisualContentType.COMPARISON,
    }:
        return VisualIntensity.HIGH
    if intent.dominant_content_type == VisualContentType.TEXT_ARGUMENT:
        return VisualIntensity.LOW
    if intent.density_level == DensityLevel.COMPACT:
        return VisualIntensity.MEDIUM
    return VisualIntensity.MEDIUM


def _content_priorities(intent: VisualIntent) -> tuple[float, float, float]:
    content = intent.dominant_content_type
    if content in {
        VisualContentType.SITE_PLAN,
        VisualContentType.FLOOR_PLAN,
        VisualContentType.SECTION,
        VisualContentType.ELEVATION,
    }:
        return 0.35, 0.25, 0.9
    if content == VisualContentType.TEXT_ARGUMENT:
        return 0.2, 0.9, 0.1
    if content == VisualContentType.PHOTO_EVIDENCE:
        return 0.75, 0.25, 0.35
    if content == VisualContentType.METRICS:
        return 0.35, 0.55, 0.2
    if content == VisualContentType.COMPARISON:
        return 0.65, 0.35, 0.35
    return 0.55, 0.45, 0.45


def _narrative_role(
    slide: SlideSpec,
    intent: VisualIntent,
    pacing_role: PacingRole,
) -> str:
    return (
        f"{pacing_role.value}: {slide.title} — "
        f"{intent.communication_goal[:48]}"
    ).strip()


def _implemented_families(families: list[LayoutFamily]) -> list[LayoutFamily]:
    implemented = {item.family for item in get_layout_family_registry().implemented()}
    filtered = [family for family in families if family in implemented]
    return filtered or [LayoutFamily.TEXTUAL_ARGUMENT]


def _pick_alternate_family(
    preferred: list[LayoutFamily],
    blocked: LayoutFamily,
) -> LayoutFamily | None:
    for family in preferred:
        if family != blocked:
            return family
    for definition in get_layout_family_registry().implemented():
        if definition.family != blocked:
            return definition.family
    return None
