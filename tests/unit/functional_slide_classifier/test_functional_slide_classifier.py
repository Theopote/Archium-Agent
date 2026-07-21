"""Unit tests for functional slide classification."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import FunctionalSlideType
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_functional_classification_cover_agenda_content_closing(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
    )
    results = FunctionalSlideClassifier().classify_all(presentation.slides)
    by_index = {r.slide_index: r for r in results}
    assert by_index[0].functional_type == FunctionalSlideType.COVER
    assert "first-page prior" in by_index[0].evidence
    assert any(r.functional_type == FunctionalSlideType.AGENDA for r in results)
    assert any(r.functional_type == FunctionalSlideType.CONTENT for r in results)
    assert any(r.functional_type == FunctionalSlideType.CLOSING for r in results)
    assert any(r.functional_type == FunctionalSlideType.SECTION_DIVIDER for r in results)
    assert any(
        any("rule_driven_structural_v1" in item for item in r.evidence) for r in results
    )


def test_first_page_disclaimer_overrides_cover_prior() -> None:
    slide = ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_001",
        text_content=["免责声明", "本材料仅供内部评审，不得外传。"],
        elements=[
            ReferenceElement(
                id="t1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.5,
                width=8.0,
                height=2.0,
                text="免责声明",
                semantic_role="title",
                font_size_pt=28,
            )
        ],
    )
    result = FunctionalSlideClassifier().classify(slide, deck_size=10)
    assert result.functional_type != FunctionalSlideType.COVER
    assert result.needs_review is True
    assert any("disclaimer" in e for e in result.evidence)


def test_first_page_agenda_not_forced_cover() -> None:
    slide = ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_001",
        text_content=["目录", "01 现状 02 策略 03 实施"],
        elements=[],
    )
    result = FunctionalSlideClassifier().classify(slide, deck_size=8)
    assert result.functional_type == FunctionalSlideType.AGENDA


def test_sparse_section_always_needs_review() -> None:
    slide = ReferenceSlideSnapshot(
        slide_index=4,
        slide_id="slide_005",
        text_content=["二、空间策略"],
        elements=[
            ReferenceElement(
                id="t1",
                element_type=ReferenceElementType.TEXT,
                x=1.5,
                y=2.2,
                width=7.0,
                height=1.0,
                text="二、空间策略",
                semantic_role="title",
                font_size_pt=30,
            )
        ],
    )
    prev = ReferenceSlideSnapshot(
        slide_index=3,
        slide_id="slide_004",
        text_content=["现状问题分析正文" * 5],
        elements=[],
    )
    nxt = ReferenceSlideSnapshot(
        slide_index=5,
        slide_id="slide_006",
        text_content=["策略细则说明" * 5],
        elements=[],
    )
    result = FunctionalSlideClassifier().classify(
        slide, deck_size=10, previous_slide=prev, next_slide=nxt
    )
    assert result.functional_type == FunctionalSlideType.SECTION_DIVIDER
    assert result.confidence <= 0.55
    assert result.needs_review is True
    assert any("sparse section candidate" in e for e in result.evidence)


def test_sparse_large_visual_prefers_content_with_review() -> None:
    slide = ReferenceSlideSnapshot(
        slide_index=2,
        slide_id="slide_003",
        text_content=["现场全景"],
        elements=[
            ReferenceElement(
                id="img",
                element_type=ReferenceElementType.IMAGE,
                x=0.5,
                y=0.8,
                width=9.0,
                height=4.2,
                semantic_role="hero_image",
            ),
            ReferenceElement(
                id="t",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.2,
                width=4.0,
                height=0.4,
                text="现场全景",
                semantic_role="title",
            ),
        ],
    )
    result = FunctionalSlideClassifier().classify(slide, deck_size=6)
    assert result.functional_type == FunctionalSlideType.CONTENT
    assert result.needs_review is True
    assert result.confidence <= 0.54
    assert any("large visual" in e for e in result.evidence)


def test_low_confidence_needs_review(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
    )
    presentation.slides[5].parse_warnings = ["synthetic"]
    results = FunctionalSlideClassifier().classify_all(presentation.slides)
    assert results[5].needs_review is True
    assert results[5].confidence < 0.55
