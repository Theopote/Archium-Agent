"""Unit tests for deck-aware layout planning."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.domain.visual.deck_composition import (
    PacingRole,
    SlideCompositionDirective,
    VisualIntensity,
)
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent


def _plan(family: LayoutFamily, *, variant: str = "numbered_grid") -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=family,
        layout_variant=variant,
        page_width=10,
        page_height=5.625,
        reading_order=[],
        whitespace_ratio=0.3,
        elements=[],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


def _report(*, score: float = 0.9) -> LayoutValidationReport:
    return LayoutValidationReport(issues=[], score=score)


def _directive(
    *,
    preferred: list[LayoutFamily],
    forbidden: list[LayoutFamily] | None = None,
    contrast: bool = False,
) -> SlideCompositionDirective:
    return SlideCompositionDirective(
        slide_id=uuid4(),
        slide_index=1,
        narrative_role="evidence",
        pacing_role=PacingRole.EVIDENCE,
        visual_intensity=VisualIntensity.HIGH,
        target_density=DensityLevel.BALANCED,
        preferred_layout_families=preferred,
        forbidden_layout_families=forbidden or [],
        should_contrast_previous=contrast,
    )


def _closing_directive() -> SlideCompositionDirective:
    directive = _directive(preferred=[LayoutFamily.TEXTUAL_ARGUMENT])
    directive.pacing_role = PacingRole.CLOSING
    directive.target_density = DensityLevel.SPACIOUS
    return directive


class TestLayoutPlanningDeckDirective:
    def test_select_best_prefers_directive_family(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        directive = _directive(preferred=[LayoutFamily.EVIDENCE_BOARD])
        candidates = [
            (_plan(LayoutFamily.TEXTUAL_ARGUMENT), _report(score=0.95)),
            (_plan(LayoutFamily.EVIDENCE_BOARD), _report(score=0.88)),
        ]
        selected = service.select_best_for_deck(candidates, deck_directive=directive)
        assert selected.layout_family == LayoutFamily.EVIDENCE_BOARD

    def test_select_best_protects_semantic_specialist_family(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        directive = _directive(preferred=[LayoutFamily.PROCESS_NARRATIVE])
        candidates = [
            (_plan(LayoutFamily.STRATEGY_CARDS), _report(score=0.99)),
            (_plan(LayoutFamily.PROCESS_NARRATIVE), _report(score=0.84)),
        ]
        selected = service.select_best_for_deck(candidates, deck_directive=directive)
        assert selected.layout_family == LayoutFamily.PROCESS_NARRATIVE

    def test_select_best_avoids_forbidden_family(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        directive = _directive(
            preferred=[LayoutFamily.COMPARATIVE_MATRIX],
            forbidden=[LayoutFamily.EVIDENCE_BOARD],
        )
        candidates = [
            (_plan(LayoutFamily.EVIDENCE_BOARD), _report(score=0.99)),
            (_plan(LayoutFamily.COMPARATIVE_MATRIX), _report(score=0.8)),
        ]
        selected = service.select_best_for_deck(candidates, deck_directive=directive)
        assert selected.layout_family == LayoutFamily.COMPARATIVE_MATRIX

    def test_select_best_contrasts_previous_family(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        previous = _plan(LayoutFamily.EVIDENCE_BOARD)
        directive = _directive(preferred=[LayoutFamily.EVIDENCE_BOARD], contrast=True)
        candidates = [
            (_plan(LayoutFamily.EVIDENCE_BOARD, variant="numbered_grid"), _report(score=0.95)),
            (_plan(LayoutFamily.COMPARATIVE_MATRIX), _report(score=0.85)),
        ]
        selected = service.select_best_for_deck(
            candidates,
            deck_directive=directive,
            previous_layout_plan=previous,
        )
        assert selected.layout_family == LayoutFamily.COMPARATIVE_MATRIX

    def test_apply_directive_filters_forbidden(self) -> None:
        from archium.infrastructure.llm.visual_schemas import LayoutDecisionDraft

        decisions = [
            LayoutDecisionDraft(
                layout_family=LayoutFamily.EVIDENCE_BOARD.value,
                layout_variant="numbered_grid",
            ),
            LayoutDecisionDraft(
                layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                layout_variant="lead_and_points",
            ),
        ]
        directive = _directive(
            preferred=[LayoutFamily.TEXTUAL_ARGUMENT],
            forbidden=[LayoutFamily.EVIDENCE_BOARD],
        )
        filtered = LayoutPlanningService._apply_directive_to_decisions(
            decisions,
            directive,
            candidate_count=2,
        )
        assert filtered[0].layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value

    def test_rule_decisions_respects_forbidden(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        service._registry = __import__(
            "archium.infrastructure.layout.layout_family_registry",
            fromlist=["get_layout_family_registry"],
        ).get_layout_family_registry()
        intent = VisualIntent(
            slide_id=uuid4(),
            communication_goal="test",
            audience_takeaway="test",
            visual_priority="title",
            dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
            preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
        )
        directive = _directive(
            preferred=[LayoutFamily.EVIDENCE_BOARD],
            forbidden=[LayoutFamily.EVIDENCE_BOARD],
        )
        decisions = service._rule_decisions(
            intent,
            asset_count=4,
            candidate_count=3,
            deck_directive=directive,
        )
        assert all(item.layout_family != LayoutFamily.EVIDENCE_BOARD.value for item in decisions)

    def test_rule_decisions_allows_deck_semantics_to_refine_generic_text(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        service._registry = __import__(
            "archium.infrastructure.layout.layout_family_registry",
            fromlist=["get_layout_family_registry"],
        ).get_layout_family_registry()
        intent = VisualIntent(
            slide_id=uuid4(),
            communication_goal="show the implementation sequence",
            audience_takeaway="three ordered actions",
            visual_priority="title",
            dominant_content_type=VisualContentType.TEXT_ARGUMENT,
            preferred_layout_families=[LayoutFamily.STRATEGY_CARDS],
        )
        directive = _directive(preferred=[LayoutFamily.PROCESS_NARRATIVE])
        decisions = service._rule_decisions(
            intent,
            asset_count=0,
            candidate_count=3,
            deck_directive=directive,
        )
        assert decisions[0].layout_family == LayoutFamily.PROCESS_NARRATIVE.value

    def test_transition_with_asset_always_gets_hero_candidate(self) -> None:
        service = LayoutPlanningService.__new__(LayoutPlanningService)
        service._registry = __import__(
            "archium.infrastructure.layout.layout_family_registry",
            fromlist=["get_layout_family_registry"],
        ).get_layout_family_registry()
        intent = VisualIntent(
            slide_id=uuid4(),
            communication_goal="open the section",
            audience_takeaway="one memorable idea",
            visual_priority="hero",
            dominant_content_type=VisualContentType.TEXT_ARGUMENT,
            preferred_layout_families=[LayoutFamily.STRATEGY_CARDS],
            hero_asset_id=uuid4(),
        )
        directive = _directive(preferred=[LayoutFamily.HERO])
        directive.transition_mode = "section_break"
        decisions = service._rule_decisions(
            intent,
            asset_count=1,
            candidate_count=3,
            deck_directive=directive,
        )
        assert decisions[0].layout_family == LayoutFamily.HERO.value

    def test_closing_prefers_poster_quote_variant(self) -> None:
        from archium.infrastructure.llm.visual_schemas import LayoutDecisionDraft

        decisions = [
            LayoutDecisionDraft(
                layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                layout_variant="lead_and_points",
            ),
            LayoutDecisionDraft(
                layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                layout_variant="quote_argument",
            ),
        ]
        ordered = LayoutPlanningService._apply_directive_to_decisions(
            decisions,
            _closing_directive(),
            candidate_count=2,
        )
        assert ordered[0].layout_variant == "quote_argument"
