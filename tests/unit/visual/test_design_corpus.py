"""Design Corpus + page grammar catalog growth tests."""

from __future__ import annotations

from archium.application.visual.design_corpus_service import DesignCorpusService
from archium.domain.visual.page_visual_grammar import (
    PageGrammarId,
    list_page_formulas,
    select_page_formula,
)


def test_page_grammar_catalog_reaches_twenty() -> None:
    formulas = list_page_formulas()
    assert len(formulas) == 20
    ids = {f.id for f in formulas}
    assert PageGrammarId.AXONOMETRIC_CALLOUT in ids
    assert PageGrammarId.MASTERPLAN_FOCUS in ids
    assert PageGrammarId.PROGRAM_STACK in ids
    assert PageGrammarId.QUOTE_CITATION in ids


def test_new_formula_title_selection() -> None:
    assert select_page_formula(emotion="calm", title="总平面").id == (
        PageGrammarId.MASTERPLAN_FOCUS
    )
    assert select_page_formula(emotion="strategy", title="轴测分析").id == (
        PageGrammarId.AXONOMETRIC_CALLOUT
    )
    assert select_page_formula(emotion="strategy", title="功能构成").id == (
        PageGrammarId.PROGRAM_STACK
    )
    assert select_page_formula(emotion="calm", title="设计语录").id == (
        PageGrammarId.QUOTE_CITATION
    )


def test_design_corpus_meets_v1_target() -> None:
    service = DesignCorpusService()
    progress = service.progress()
    assert progress["total"] >= 50
    assert progress["meets_v1_target"] is True
    assert progress["formula_coverage"] == 20
    assert progress["by_source"]["formula_exemplar"] == 40  # 20 × 2 styles
    assert progress["by_source"]["case_001_hospital"] == 20


def test_design_corpus_match_by_formula() -> None:
    service = DesignCorpusService()
    hits = service.match(formula_id="path_experience", limit=3)
    assert hits
    assert all(h.formula_id == "path_experience" for h in hits)
    assert any(h.source == "case_001_hospital" for h in service.match(
        formula_id="path_experience", limit=10
    ))
