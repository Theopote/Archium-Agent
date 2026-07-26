"""v0.3 Deck rhythm: climax budget, density waveform, Deck QA rule codes."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.application.visual.deck_composition_service import DeckCompositionPlanningService
from archium.application.visual.deck_qa_service import DeckQAService
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    PacingRole,
    SlideCompositionDirective,
    VisualIntensity,
    climax_budget_for_deck,
    density_to_score,
    is_climax_peak,
)
from archium.domain.visual.deck_qa import (
    DECK_ADJACENT_HERO,
    DECK_CLIMAX_OVERLOAD,
    DECK_DENSITY_FLAT,
    DECK_REPEATED_LAYOUT_FAMILY,
)
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    LayoutIssueSeverity,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent

PRESENTATION_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
ART_DIRECTION_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

# Hospital renovation report outline (~20 pages).
_HOSPITAL_OUTLINE: tuple[tuple[str, SlideType, ContinuityRole, VisualContentType, LayoutFamily], ...] = (
    ("封面", SlideType.TITLE, ContinuityRole.OPENING, VisualContentType.HERO_IMAGE, LayoutFamily.HERO),
    ("项目背景", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.TEXT_ARGUMENT, LayoutFamily.TEXTUAL_ARGUMENT),
    ("任务与目标", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.TEXT_ARGUMENT, LayoutFamily.STRATEGY_CARDS),
    ("区位与交通", SlideType.CONTENT, ContinuityRole.EVIDENCE, VisualContentType.SITE_PLAN, LayoutFamily.DRAWING_FOCUS),
    ("现状问题总览", SlideType.CONTENT, ContinuityRole.EVIDENCE, VisualContentType.PHOTO_EVIDENCE, LayoutFamily.EVIDENCE_BOARD),
    ("流线冲突", SlideType.CONTENT, ContinuityRole.EVIDENCE, VisualContentType.PHOTO_EVIDENCE, LayoutFamily.EVIDENCE_BOARD),
    ("科室压力", SlideType.CONTENT, ContinuityRole.EVIDENCE, VisualContentType.METRICS, LayoutFamily.METRIC_DASHBOARD),
    ("规范约束", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.TEXT_ARGUMENT, LayoutFamily.TEXTUAL_ARGUMENT),
    ("设计策略", SlideType.SECTION, ContinuityRole.SECTION_OPENING, VisualContentType.TEXT_ARGUMENT, LayoutFamily.STRATEGY_CARDS),
    ("概念生成", SlideType.CONTENT, ContinuityRole.CLIMAX, VisualContentType.HERO_IMAGE, LayoutFamily.HERO),
    ("总图布局", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.SITE_PLAN, LayoutFamily.DRAWING_FOCUS),
    ("流线优化", SlideType.CONTENT, ContinuityRole.COMPARISON, VisualContentType.COMPARISON, LayoutFamily.COMPARATIVE_MATRIX),
    ("功能分区", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.FLOOR_PLAN, LayoutFamily.DRAWING_FOCUS),
    ("立面与氛围", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.ELEVATION, LayoutFamily.HYBRID_CANVAS),
    ("分期实施", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.PROCESS, LayoutFamily.PROCESS_NARRATIVE),
    ("指标对比", SlideType.CONTENT, ContinuityRole.COMPARISON, VisualContentType.METRICS, LayoutFamily.METRIC_DASHBOARD),
    ("风险与保障", SlideType.CONTENT, ContinuityRole.EXPLANATION, VisualContentType.TEXT_ARGUMENT, LayoutFamily.STRATEGY_CARDS),
    ("效果表达", SlideType.CONTENT, ContinuityRole.CLIMAX, VisualContentType.HERO_IMAGE, LayoutFamily.HERO),
    ("结论建议", SlideType.SUMMARY, ContinuityRole.SUMMARY, VisualContentType.TEXT_ARGUMENT, LayoutFamily.TEXTUAL_ARGUMENT),
    ("下一步", SlideType.CLOSING, ContinuityRole.CLOSING, VisualContentType.TEXT_ARGUMENT, LayoutFamily.TEXTUAL_ARGUMENT),
)


def _hospital_deck() -> tuple[list[SlideSpec], list[VisualIntent]]:
    slides: list[SlideSpec] = []
    intents: list[VisualIntent] = []
    for order, (title, slide_type, continuity, content, family) in enumerate(_HOSPITAL_OUTLINE):
        chapter = (
            "intro"
            if order < 3
            else "site"
            if order < 8
            else "strategy"
            if order < 14
            else "delivery"
        )
        slide = SlideSpec(
            presentation_id=PRESENTATION_ID,
            chapter_id=chapter,
            order=order,
            title=title,
            message=f"{title} — 医院更新汇报",
            slide_type=slide_type,
            key_points=[f"{title}-1", f"{title}-2"],
        )
        slides.append(slide)
        intents.append(
            VisualIntent(
                slide_id=slide.id,
                presentation_id=PRESENTATION_ID,
                communication_goal=f"传达{title}",
                audience_takeaway=slide.message,
                visual_priority="title > visual > body",
                dominant_content_type=content,
                preferred_layout_families=[family],
                density_level=DensityLevel.COMPACT,  # intentional: planner must not stay all-compact
                continuity_role=continuity,
            )
        )
    return slides, intents


def test_climax_budget_for_twenty_pages() -> None:
    assert climax_budget_for_deck(20) == 3
    assert climax_budget_for_deck(10) == 2
    assert climax_budget_for_deck(4) == 1


def test_hospital_20_slide_rhythm_curve() -> None:
    slides, intents = _hospital_deck()
    assert len(slides) == 20
    plan = DeckCompositionPlanningService().plan(
        presentation_id=PRESENTATION_ID,
        art_direction_id=ART_DIRECTION_ID,
        slides=slides,
        visual_intents=intents,
    )

    peaks = [d for d in plan.slide_directives if is_climax_peak(d)]
    assert len(peaks) <= climax_budget_for_deck(20)

    # No adjacent HERO intensity.
    for index in range(1, len(plan.slide_directives)):
        previous = plan.slide_directives[index - 1]
        current = plan.slide_directives[index]
        assert not (
            previous.visual_intensity == VisualIntensity.HERO
            and current.visual_intensity == VisualIntensity.HERO
        )

    # Density waveform: not flat / not all compact.
    density_values = set(plan.density_curve)
    assert len(density_values) >= 2
    assert not all(value >= 0.75 for value in plan.density_curve)

    # Opening spacious, evidence compact (first evidence page).
    opening = plan.slide_directives[0]
    assert opening.pacing_role == PacingRole.OPENING
    assert opening.target_density == DensityLevel.SPACIOUS
    evidence = next(d for d in plan.slide_directives if d.pacing_role == PacingRole.EVIDENCE)
    assert evidence.target_density == DensityLevel.COMPACT

    # Serializable rhythm snapshot for Showcase regression.
    snapshot = {
        "slide_count": len(plan.slide_directives),
        "climax_budget": climax_budget_for_deck(20),
        "peak_count": len(peaks),
        "density_curve": plan.density_curve,
        "intensity_curve": plan.visual_intensity_curve,
        "primary_families": [
            d.preferred_layout_families[0].value for d in plan.slide_directives
        ],
    }
    assert snapshot["peak_count"] <= snapshot["climax_budget"]
    assert max(snapshot["density_curve"]) > min(snapshot["density_curve"])


def test_deck_qa_flags_climax_overload_and_adjacent_hero() -> None:
    slide_ids = [uuid4() for _ in range(8)]
    directives = [
        SlideCompositionDirective(
            slide_id=slide_ids[i],
            slide_index=i,
            narrative_role=f"peak-{i}",
            pacing_role=PacingRole.CLIMAX if i < 5 else PacingRole.SETUP,
            visual_intensity=VisualIntensity.HERO if i < 5 else VisualIntensity.MEDIUM,
            target_density=DensityLevel.COMPACT,
            preferred_layout_families=[LayoutFamily.HERO],
        )
        for i in range(8)
    ]
    composition = DeckCompositionPlan(
        presentation_id=PRESENTATION_ID,
        art_direction_id=ART_DIRECTION_ID,
        composition_strategy="overload fixture",
        pacing_strategy="too many climaxes",
        slide_directives=directives,
        visual_intensity_curve=[1.0] * 5 + [0.5] * 3,
        density_curve=[density_to_score(DensityLevel.COMPACT)] * 8,
    )
    plans = [
        LayoutPlan(
            slide_id=slide_ids[i],
            layout_family=LayoutFamily.HERO,
            layout_variant="split",
            page_width=10,
            page_height=5.625,
            reading_order=[],
            whitespace_ratio=0.3,
            elements=[],
            design_system_id=uuid4(),
            visual_intent_id=uuid4(),
        )
        for i in range(8)
    ]
    report = DeckQAService().evaluate(plans, composition_plan=composition)
    codes = {item.rule_code for item in report.findings}
    assert DECK_CLIMAX_OVERLOAD in codes
    assert DECK_ADJACENT_HERO in codes
    assert DECK_DENSITY_FLAT in codes
    assert DECK_REPEATED_LAYOUT_FAMILY in codes
    family_finding = next(
        item for item in report.findings if item.rule_code == DECK_REPEATED_LAYOUT_FAMILY
    )
    assert family_finding.severity == LayoutIssueSeverity.ERROR


def test_selection_uses_hero_and_drawing_priority() -> None:
    """Directive priorities must change candidate sort order."""
    directive = SlideCompositionDirective(
        slide_id=uuid4(),
        slide_index=0,
        narrative_role="drawing page",
        pacing_role=PacingRole.EVIDENCE,
        visual_intensity=VisualIntensity.HIGH,
        target_density=DensityLevel.COMPACT,
        preferred_layout_families=[LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.DRAWING_FOCUS],
        hero_priority=0.2,
        text_priority=0.2,
        drawing_priority=0.95,
    )
    drawing = LayoutPlan(
        slide_id=directive.slide_id,
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="drawing_with_metrics",
        page_width=10,
        page_height=5.625,
        reading_order=[],
        whitespace_ratio=0.3,
        elements=[],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    text = LayoutPlan(
        slide_id=directive.slide_id,
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        reading_order=[],
        whitespace_ratio=0.3,
        elements=[],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    # Equal validation scores — priority should pick drawing.
    report = LayoutValidationReport(score=0.8, issues=[])
    report_b = LayoutValidationReport(score=0.8, issues=[])
    best = LayoutPlanningService.__new__(LayoutPlanningService).select_best_for_deck(
        [(text, report_b), (drawing, report)],
        deck_directive=directive,
    )
    assert best.layout_family == LayoutFamily.DRAWING_FOCUS
