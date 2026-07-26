"""Unit tests for case_ref normalization helpers."""

from __future__ import annotations

from archium.domain.case_ref import (
    case_id_from_ref,
    normalize_case_id,
    normalize_case_id_list,
    normalize_precedent_ref,
)
from archium.domain.design_knowledge import DesignKnowledge


def test_normalize_case_id_accepts_bare_and_prefixed() -> None:
    assert normalize_case_id("ningbo_museum") == "ningbo_museum"
    assert normalize_case_id("case:ningbo_museum") == "ningbo_museum"
    assert normalize_case_id("CASE:therme_vals") == "therme_vals"
    assert normalize_case_id("") is None
    assert normalize_case_id("宁波博物馆") is None
    assert normalize_precedent_ref("ningbo_museum") == "case:ningbo_museum"
    assert case_id_from_ref("case:ningbo_museum") == "ningbo_museum"


def test_normalize_case_id_list_dedupes() -> None:
    assert normalize_case_id_list(
        ["case:a", "a", "b", "bad id", ""]
    ) == ["a", "b"]


def test_design_knowledge_precedent_ref_validator() -> None:
    knowledge = DesignKnowledge(precedent_ref="ningbo_museum")
    assert knowledge.precedent_ref == "case:ningbo_museum"
    empty = DesignKnowledge(precedent_ref="")
    assert empty.precedent_ref is None
