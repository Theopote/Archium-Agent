"""Unit tests for deck composition planning."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from archium.application.visual.deck_composition_service import DeckCompositionPlanningService
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    PacingRole,
    VisualIntensity,
)
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.visual_intent import VisualIntent

PRESENTATION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ART_DIRECTION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _slide(
    *,
    order: int,
    chapter_id: str = "analysis",
    slide_type: SlideType = SlideType.CONTENT,
    title: str | None = None,
) -> SlideSpec:
    return SlideSpec(
        presentation_id=PRESENTATION_ID,
        chapter_id=chapter_id,
        order=order,
        title=title or f"Slide {order}",
        message=f"Message for slide {order}",
        slide_type=slide_type,
        key_points=[f"point-{order}"],
    )


def _intent(
    slide: SlideSpec,
    *,
    content: VisualContentType = VisualContentType.TEXT_ARGUMENT,
    families: list[LayoutFamily] | None = None,
    density: DensityLevel = DensityLevel.BALANCED,
    continuity: ContinuityRole = ContinuityRole.EXPLANATION,
) -> VisualIntent:
    return VisualIntent(
        slide_id=slide.id,
        presentation_id=PRESENTATION_ID,
        communication_goal=f"Explain slide {slide.order}",
        audience_takeaway=slide.message,
        visual_priority="title > body",
        dominant_content_type=content,
        preferred_layout_families=families or [LayoutFamily.TEXTUAL_ARGUMENT],
        density_level=density,
        continuity_role=continuity,
    )


class TestDeckCompositionPlanningService:
    def test_plan_produces_directive_per_slide(self) -> None:
        slides = [_slide(order=0, chapter_id="intro"), _slide(order=1, chapter_id="body")]
        intents = [
            _intent(slides[0], continuity=ContinuityRole.OPENING),
            _intent(
                slides[1],
                content=VisualContentType.PHOTO_EVIDENCE,
                families=[LayoutFamily.EVIDENCE_BOARD],
                continuity=ContinuityRole.EVIDENCE,
            ),
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        assert len(plan.slide_directives) == 2
        assert plan.slide_directives[0].slide_index == 0
        assert plan.slide_directives[1].pacing_role == PacingRole.EVIDENCE
        assert plan.approval_status == ApprovalStatus.APPROVED
        assert len(plan.visual_intensity_curve) == 2
        assert len(plan.density_curve) == 2

    def test_opening_and_closing_roles(self) -> None:
        slides = [
            _slide(order=0, slide_type=SlideType.TITLE, chapter_id="intro"),
            _slide(order=1, chapter_id="body"),
            _slide(order=2, slide_type=SlideType.CLOSING, chapter_id="outro"),
        ]
        intents = [
            _intent(slides[0], continuity=ContinuityRole.OPENING),
            _intent(
                slides[1],
                content=VisualContentType.METRICS,
                families=[LayoutFamily.METRIC_DASHBOARD],
            ),
            _intent(slides[2], continuity=ContinuityRole.CLOSING),
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        assert plan.slide_directives[0].pacing_role == PacingRole.OPENING
        assert plan.slide_directives[2].pacing_role == PacingRole.CLOSING
        assert slides[0].id in plan.hero_slide_ids
        assert slides[-1].id in plan.climax_slide_ids

    def test_avoids_three_consecutive_same_family(self) -> None:
        slides = [_slide(order=i) for i in range(4)]
        intents = [
            _intent(slides[i], families=[LayoutFamily.EVIDENCE_BOARD]) for i in range(4)
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        primary = [item.preferred_layout_families[0] for item in plan.slide_directives]
        for index in range(2, len(primary)):
            window = primary[index - 2 : index + 1]
            assert not (window[0] == window[1] == window[2])

    def test_density_buffer_after_compact_slide(self) -> None:
        slides = [_slide(order=0), _slide(order=1)]
        intents = [
            _intent(slides[0], density=DensityLevel.COMPACT),
            _intent(slides[1], density=DensityLevel.COMPACT),
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        assert plan.slide_directives[1].target_density == DensityLevel.SPACIOUS
        assert plan.slide_directives[1].visual_intensity == VisualIntensity.LOW

    def test_section_transition_and_distribution(self) -> None:
        slides = [
            _slide(order=0, chapter_id="intro"),
            _slide(order=1, chapter_id="analysis", slide_type=SlideType.SECTION),
            _slide(order=2, chapter_id="analysis"),
        ]
        intents = [
            _intent(slides[0], continuity=ContinuityRole.OPENING),
            _intent(
                slides[1],
                content=VisualContentType.SITE_PLAN,
                families=[LayoutFamily.DRAWING_FOCUS],
                continuity=ContinuityRole.SECTION_OPENING,
            ),
            _intent(
                slides[2],
                content=VisualContentType.COMPARISON,
                families=[LayoutFamily.COMPARATIVE_MATRIX],
                continuity=ContinuityRole.COMPARISON,
            ),
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        assert slides[1].id in plan.section_transition_slide_ids
        assert len(plan.section_strategies) == 2
        assert sum(plan.layout_family_distribution.values()) == 3
        assert plan.directive_for_slide(slides[2].id) is not None

    def test_intensity_curve_reflects_content(self) -> None:
        slides = [_slide(order=0), _slide(order=1), _slide(order=2)]
        intents = [
            _intent(slides[0], content=VisualContentType.TEXT_ARGUMENT),
            _intent(
                slides[1],
                content=VisualContentType.SITE_PLAN,
                families=[LayoutFamily.DRAWING_FOCUS],
            ),
            _intent(
                slides[2],
                content=VisualContentType.PHOTO_EVIDENCE,
                families=[LayoutFamily.EVIDENCE_BOARD],
            ),
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        assert plan.visual_intensity_curve[0] < plan.visual_intensity_curve[1]
        assert plan.visual_intensity_curve[1] >= plan.visual_intensity_curve[2]

    def test_revise_increases_contrast_on_pacing_feedback(self) -> None:
        slides = [_slide(order=0), _slide(order=1)]
        intents = [_intent(slides[0]), _intent(slides[1])]
        service = DeckCompositionPlanningService()
        original = service.plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
            auto_approve=False,
        )
        revised = service.revise(
            original,
            "节奏太单调，需要更多变化",
            slides=slides,
            visual_intents=intents,
        )
        assert revised.version == original.version + 1
        assert revised.slide_directives[1].should_contrast_previous is True
        assert "修订" in revised.composition_strategy

    def test_breaks_three_consecutive_text_pages(self) -> None:
        slides = [_slide(order=i) for i in range(3)]
        intents = [
            _intent(slides[i], families=[LayoutFamily.TEXTUAL_ARGUMENT]) for i in range(3)
        ]
        plan = DeckCompositionPlanningService().plan(
            presentation_id=PRESENTATION_ID,
            art_direction_id=ART_DIRECTION_ID,
            slides=slides,
            visual_intents=intents,
        )
        assert (
            plan.slide_directives[2].preferred_layout_families[0] != LayoutFamily.TEXTUAL_ARGUMENT
        )

    def test_missing_intent_raises(self) -> None:
        slide = _slide(order=0)
        with pytest.raises(ValueError, match="Missing VisualIntent"):
            DeckCompositionPlanningService().plan(
                presentation_id=PRESENTATION_ID,
                art_direction_id=ART_DIRECTION_ID,
                slides=[slide],
                visual_intents=[],
            )


class TestDeckCompositionPlanValidation:
    def test_rejects_mismatched_intensity_curve(self) -> None:
        slide_id = uuid4()
        with pytest.raises(ValueError, match="visual_intensity_curve"):
            DeckCompositionPlan(
                presentation_id=PRESENTATION_ID,
                art_direction_id=ART_DIRECTION_ID,
                composition_strategy="test",
                pacing_strategy="test",
                slide_directives=[
                    {
                        "slide_id": slide_id,
                        "slide_index": 0,
                        "narrative_role": "setup",
                        "pacing_role": PacingRole.SETUP,
                        "visual_intensity": VisualIntensity.MEDIUM,
                        "target_density": DensityLevel.BALANCED,
                        "preferred_layout_families": [LayoutFamily.TEXTUAL_ARGUMENT],
                    }
                ],
                visual_intensity_curve=[0.5, 0.75],
            )
