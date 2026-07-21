"""Unit tests for reference slide clustering."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.reference_slide_clusterer import ReferenceSlideClusterer
from archium.domain.visual.template_induction import FunctionalSlideType
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_content_pages_form_at_least_three_clusters(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
    )
    classifications = FunctionalSlideClassifier().classify_all(presentation.slides)
    clusters = ReferenceSlideClusterer().cluster(presentation.slides, classifications)
    content_clusters = [
        c for c in clusters if c.functional_type == FunctionalSlideType.CONTENT
    ]
    assert len(content_clusters) >= 3
    for cluster in content_clusters:
        assert cluster.slide_ids
        assert cluster.selection_rationale


def test_clustering_is_stable_across_reruns(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    parser = ReferencePptxParser()
    classifier = FunctionalSlideClassifier()
    clusterer = ReferenceSlideClusterer()

    def run_once():
        presentation = parser.parse(
            pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
        )
        classifications = classifier.classify_all(presentation.slides)
        clusters = clusterer.cluster(presentation.slides, classifications)
        return [
            (
                c.functional_type.value,
                c.content_type.value,
                tuple(c.slide_ids),
            )
            for c in clusters
            if c.functional_type == FunctionalSlideType.CONTENT
        ]

    first = run_once()
    second = run_once()
    assert first == second
