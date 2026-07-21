"""Unit tests for functional slide classification."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
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
    assert any(r.functional_type == FunctionalSlideType.AGENDA for r in results)
    assert any(r.functional_type == FunctionalSlideType.CONTENT for r in results)
    assert any(r.functional_type == FunctionalSlideType.CLOSING for r in results)
    assert any(r.functional_type == FunctionalSlideType.SECTION_DIVIDER for r in results)


def test_low_confidence_needs_review(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
    )
    # Force a broken slide signature.
    presentation.slides[5].parse_warnings = ["synthetic"]
    results = FunctionalSlideClassifier().classify_all(presentation.slides)
    assert results[5].needs_review is True
    assert results[5].confidence < 0.55
