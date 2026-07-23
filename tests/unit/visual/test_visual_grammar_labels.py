"""Unit tests for Visual Grammar UI labels / evidence merge helpers."""

from __future__ import annotations

from archium.application.visual.visual_grammar_labels import (
    archetype_label,
    coerce_archetype_selection,
    grammar_evidence_hints,
    merge_grammar_evidence,
    selection_value_for_intent,
)
from archium.domain.visual.visual_grammar import PageArchetype


def test_archetype_label_auto_and_named() -> None:
    assert archetype_label(None) == "自动识别"
    assert archetype_label("auto") == "自动识别"
    assert archetype_label(PageArchetype.NARRATIVE_OPENING) == "叙事开篇"
    assert archetype_label("site_problem_diagnosis") == "现状问题"


def test_coerce_selection_round_trip() -> None:
    assert coerce_archetype_selection("auto") is None
    assert coerce_archetype_selection("narrative_opening") == PageArchetype.NARRATIVE_OPENING
    assert selection_value_for_intent(None) == "auto"
    assert (
        selection_value_for_intent(PageArchetype.SITE_CONTEXT_ANALYSIS)
        == "site_context_analysis"
    )


def test_merge_grammar_evidence_appends_missing_slots() -> None:
    existing = ["用户自定义证据"]
    merged = merge_grammar_evidence(existing, PageArchetype.NARRATIVE_OPENING)
    assert "用户自定义证据" in merged
    assert any("historic_or_context_photo" in item for item in merged)
    assert any("renewal_goal" in item for item in merged)
    # Idempotent when hints already present.
    again = merge_grammar_evidence(merged, PageArchetype.NARRATIVE_OPENING)
    assert again == merged


def test_grammar_hints_empty_for_auto() -> None:
    assert grammar_evidence_hints(None) == []
    assert grammar_evidence_hints(PageArchetype.GENERIC) == []
