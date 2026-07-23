"""Visual intent generation from SlideSpec (LLM optional, rule fallback)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from archium.application.visual.design_brief_intent import apply_design_brief_to_intent
from archium.domain.enums import ApprovalStatus, SlideType, VisualType
from archium.domain.slide import SlideSpec
from archium.domain.slide_design_brief import BriefStatus, SlideDesignBrief
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.visual_repositories import VisualIntentRepository
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.visual_schemas import VisualIntentDraft
from archium.prompts.visual_intent import (
    VISUAL_INTENT_SYSTEM_PROMPT,
    build_visual_intent_user_prompt,
)

_USABLE_BRIEF_STATUSES = frozenset(
    {BriefStatus.APPROVED, BriefStatus.READY_FOR_REVIEW}
)

_VISUAL_TYPE_MAP: dict[VisualType, VisualContentType] = {
    VisualType.SITE_PLAN: VisualContentType.SITE_PLAN,
    VisualType.FLOOR_PLAN: VisualContentType.FLOOR_PLAN,
    VisualType.SECTION: VisualContentType.SECTION,
    VisualType.ELEVATION: VisualContentType.ELEVATION,
    VisualType.SITE_PHOTO: VisualContentType.PHOTO_EVIDENCE,
    VisualType.RENDERING: VisualContentType.HERO_IMAGE,
    VisualType.DIAGRAM: VisualContentType.ANALYTICAL_DIAGRAM,
    VisualType.CHART: VisualContentType.METRICS,
    VisualType.TABLE: VisualContentType.METRICS,
    VisualType.TIMELINE: VisualContentType.PROCESS,
    VisualType.COMPARISON: VisualContentType.COMPARISON,
    VisualType.REFERENCE_CASE: VisualContentType.COMPARISON,
    VisualType.MAP: VisualContentType.SITE_PLAN,
    VisualType.ICON: VisualContentType.MIXED,
    VisualType.TEXT_ONLY: VisualContentType.TEXT_ARGUMENT,
}

_CONTENT_FAMILY_PRESETS: dict[VisualContentType, list[LayoutFamily]] = {
    VisualContentType.SITE_PLAN: [LayoutFamily.DRAWING_FOCUS, LayoutFamily.HYBRID_CANVAS],
    VisualContentType.FLOOR_PLAN: [LayoutFamily.DRAWING_FOCUS],
    VisualContentType.SECTION: [LayoutFamily.DRAWING_FOCUS],
    VisualContentType.ELEVATION: [LayoutFamily.DRAWING_FOCUS],
    VisualContentType.PHOTO_EVIDENCE: [
        LayoutFamily.EVIDENCE_BOARD,
        LayoutFamily.ANALYTICAL_DIAGRAM,
    ],
    VisualContentType.HERO_IMAGE: [LayoutFamily.HERO, LayoutFamily.HYBRID_CANVAS],
    VisualContentType.COMPARISON: [
        LayoutFamily.COMPARATIVE_MATRIX,
        LayoutFamily.STRATEGY_CARDS,
    ],
    VisualContentType.METRICS: [
        LayoutFamily.METRIC_DASHBOARD,
        LayoutFamily.STRATEGY_CARDS,
    ],
    VisualContentType.TEXT_ARGUMENT: [
        LayoutFamily.TEXTUAL_ARGUMENT,
        LayoutFamily.STRATEGY_CARDS,
    ],
    VisualContentType.ANALYTICAL_DIAGRAM: [
        LayoutFamily.ANALYTICAL_DIAGRAM,
        LayoutFamily.DRAWING_FOCUS,
    ],
    VisualContentType.PROCESS: [
        LayoutFamily.PROCESS_NARRATIVE,
        LayoutFamily.STRATEGY_CARDS,
    ],
    VisualContentType.MIXED: [
        LayoutFamily.HYBRID_CANVAS,
        LayoutFamily.STRATEGY_CARDS,
        LayoutFamily.TEXTUAL_ARGUMENT,
    ],
}


class VisualIntentService:
    """Derive VisualIntent for a SlideSpec without emitting coordinates."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._intents = VisualIntentRepository(session)

    def generate_for_slide(
        self,
        slide: SlideSpec,
        *,
        art_direction: ArtDirection | None = None,
        previous_slide: SlideSpec | None = None,
        next_slide: SlideSpec | None = None,
        design_brief: SlideDesignBrief | None = None,
        use_llm: bool = True,
    ) -> VisualIntent:
        draft: VisualIntentDraft | None = None
        if use_llm and self._llm is not None:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=VISUAL_INTENT_SYSTEM_PROMPT,
                    user_prompt=build_visual_intent_user_prompt(
                        slide=slide,
                        art_direction=art_direction,
                        previous_slide=previous_slide,
                        next_slide=next_slide,
                    ),
                    temperature=0.3,
                ),
                VisualIntentDraft,
            )

        if draft is None:
            draft = self._rule_based_draft(slide)

        hero_asset_id = draft.hero_asset_id
        supporting = list(draft.supporting_asset_ids)
        if hero_asset_id is None and slide.visual_requirements:
            hero_asset_id = slide.visual_requirements[0].primary_asset_id
            for req in slide.visual_requirements[1:]:
                supporting.extend(req.bound_asset_ids())

        intent = VisualIntent(
            slide_id=slide.id,
            presentation_id=slide.presentation_id,
            art_direction_id=art_direction.id if art_direction else None,
            communication_goal=draft.communication_goal,
            audience_takeaway=draft.audience_takeaway,
            visual_priority=draft.visual_priority,
            dominant_content_type=draft.dominant_content_type,
            hero_asset_id=hero_asset_id,
            supporting_asset_ids=supporting,
            hierarchy=list(draft.hierarchy),
            reading_order=list(draft.reading_order),
            preferred_layout_families=self._implemented_preferred_families(
                draft.preferred_layout_families
            ),
            composition_strategy=draft.composition_strategy,
            image_treatment=draft.image_treatment,
            annotation_strategy=draft.annotation_strategy,
            background_strategy=draft.background_strategy,
            density_level=draft.density_level,
            emotional_tone=draft.emotional_tone,
            continuity_role=draft.continuity_role,
            approval_status=ApprovalStatus.PENDING,
        )
        if design_brief is not None and design_brief.status in _USABLE_BRIEF_STATUSES:
            intent = apply_design_brief_to_intent(intent, design_brief)
        return self._intents.save(intent)

    @staticmethod
    def _implemented_preferred_families(
        families: list[LayoutFamily],
    ) -> list[LayoutFamily]:
        implemented = {item.family for item in get_layout_family_registry().implemented()}
        filtered = [family for family in families if family in implemented]
        return filtered or [LayoutFamily.TEXTUAL_ARGUMENT]

    def _rule_based_draft(self, slide: SlideSpec) -> VisualIntentDraft:
        primary_type = VisualType.TEXT_ONLY
        asset_count = 0
        for req in slide.visual_requirements:
            if req.type != VisualType.TEXT_ONLY:
                primary_type = req.type
                asset_count += len(req.bound_asset_ids()) or (1 if req.required else 0)
                break
        for req in slide.visual_requirements[1:]:
            asset_count += len(req.bound_asset_ids()) or (1 if req.required else 0)

        # Heuristic: many site photos → evidence board.
        photo_reqs = [
            req
            for req in slide.visual_requirements
            if req.type in {VisualType.SITE_PHOTO, VisualType.RENDERING}
        ]
        if len(photo_reqs) >= 3:
            content = VisualContentType.PHOTO_EVIDENCE
        elif primary_type == VisualType.COMPARISON or slide.slide_type == SlideType.COMPARISON:
            content = VisualContentType.COMPARISON
        else:
            content = _VISUAL_TYPE_MAP.get(primary_type, VisualContentType.MIXED)

        families = list(_CONTENT_FAMILY_PRESETS.get(content, [LayoutFamily.TEXTUAL_ARGUMENT]))
        families = self._implemented_preferred_families(families)

        hierarchy = ["title", "hero", "supporting", "source"]
        if content == VisualContentType.TEXT_ARGUMENT:
            hierarchy = ["title", "lead", "points", "source"]
        elif content == VisualContentType.PHOTO_EVIDENCE:
            hierarchy = ["title", "lead", "photos", "annotations", "source"]
        elif content == VisualContentType.COMPARISON:
            hierarchy = ["title", "cases", "dimensions", "insight", "source"]

        continuity = ContinuityRole.EXPLANATION
        if slide.slide_type == SlideType.TITLE:
            continuity = ContinuityRole.OPENING
        elif slide.slide_type == SlideType.SECTION:
            continuity = ContinuityRole.SECTION_OPENING
        elif slide.slide_type in {SlideType.SUMMARY, SlideType.CLOSING}:
            continuity = ContinuityRole.CLOSING
        elif content == VisualContentType.PHOTO_EVIDENCE:
            continuity = ContinuityRole.EVIDENCE
        elif content == VisualContentType.COMPARISON:
            continuity = ContinuityRole.COMPARISON

        density = DensityLevel.BALANCED
        if len(slide.key_points) >= 5 or asset_count >= 4:
            density = DensityLevel.COMPACT
        elif len(slide.key_points) <= 1 and asset_count <= 1:
            density = DensityLevel.SPACIOUS

        image_treatment = "photo_cover"
        if content in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }:
            image_treatment = "drawing_contain"

        return VisualIntentDraft(
            communication_goal=f"让受众理解：{slide.message}",
            audience_takeaway=slide.message,
            visual_priority=" > ".join(hierarchy),
            dominant_content_type=content,
            hierarchy=hierarchy,
            reading_order=hierarchy,
            preferred_layout_families=families[:3],
            composition_strategy=f"以 {families[0].value} 表达主信息",
            image_treatment=image_treatment,
            annotation_strategy="编号对应" if content == VisualContentType.PHOTO_EVIDENCE else "图注补充",
            background_strategy="surface",
            density_level=density,
            emotional_tone="克制专业",
            continuity_role=continuity,
        )
