"""Unit tests for deck repair suggestion mapping."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.deck_repair_service import DeckRepairService
from archium.domain.visual.deck_qa import (
    DECK_COMPOSITION_FAMILY_DEVIATION,
    DECK_REPEATED_LAYOUT_FAMILY,
    DECK_WEAK_SECTION_TRANSITION,
    DeckQAFinding,
)
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutFamily, LayoutIssueSeverity


def _finding(*, rule_code: str, slide_ids: list[str], evidence: dict | None = None) -> DeckQAFinding:
    return DeckQAFinding(
        rule_code=rule_code,
        severity=LayoutIssueSeverity.WARNING,
        message="test finding",
        slide_ids=slide_ids,
        evidence=evidence or {},
        suggestion="fix it",
    )


class TestDeckRepairService:
    def test_repeated_layout_family_suggests_change_layout(self) -> None:
        slide_id = uuid4()
        report = {
            "findings": [
                _finding(
                    rule_code=DECK_REPEATED_LAYOUT_FAMILY,
                    slide_ids=[str(slide_id)],
                    evidence={"family": LayoutFamily.HERO.value},
                ).model_dump(mode="json")
            ]
        }
        suggestions = DeckRepairService().suggest_from_report(report)
        assert len(suggestions) == 1
        assert suggestions[0].slide_id == slide_id
        assert suggestions[0].intent == VisualEditIntent.CHANGE_LAYOUT.value
        assert suggestions[0].params.get("layout_family") == LayoutFamily.DRAWING_FOCUS

    def test_composition_deviation_uses_expected_family(self) -> None:
        slide_id = uuid4()
        report = {
            "findings": [
                _finding(
                    rule_code=DECK_COMPOSITION_FAMILY_DEVIATION,
                    slide_ids=[str(slide_id)],
                    evidence={"expected_family": LayoutFamily.STRATEGY_CARDS.value},
                ).model_dump(mode="json")
            ]
        }
        suggestions = DeckRepairService().suggest_from_report(report)
        assert len(suggestions) == 1
        assert suggestions[0].params.get("layout_family") == LayoutFamily.STRATEGY_CARDS

    def test_section_transition_suggests_increase_whitespace(self) -> None:
        slide_id = uuid4()
        report = {
            "findings": [
                _finding(
                    rule_code=DECK_WEAK_SECTION_TRANSITION,
                    slide_ids=[str(slide_id)],
                ).model_dump(mode="json")
            ]
        }
        suggestions = DeckRepairService().suggest_from_report(report)
        assert len(suggestions) == 1
        assert suggestions[0].intent == VisualEditIntent.INCREASE_WHITESPACE.value

    def test_deduplicates_same_slide_and_intent(self) -> None:
        slide_id = uuid4()
        duplicate = _finding(
            rule_code=DECK_WEAK_SECTION_TRANSITION,
            slide_ids=[str(slide_id)],
        ).model_dump(mode="json")
        report = {"findings": [duplicate, duplicate]}
        suggestions = DeckRepairService().suggest_from_report(report)
        assert len(suggestions) == 1
