"""Unit tests for representative slide selection."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.reference_slide_clusterer import ReferenceSlideClusterer
from archium.application.visual.representative_slide_selector import RepresentativeSlideSelector
from archium.domain.visual.template_induction import FunctionalSlideType
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_each_cluster_gets_representative(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
    )
    classifications = FunctionalSlideClassifier().classify_all(presentation.slides)
    clusters = ReferenceSlideClusterer().cluster(presentation.slides, classifications)
    clusters, scores = RepresentativeSlideSelector().select_for_clusters(
        clusters, presentation.slides
    )
    for cluster in clusters:
        assert cluster.representative_slide_id
        assert cluster.representative_slide_id in cluster.slide_ids
    assert scores


def test_anomalous_dense_page_not_preferred(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False
    )
    # Identify the anomalous last dense page (most elements).
    anomalous = max(presentation.slides, key=lambda s: len(s.elements))
    classifications = FunctionalSlideClassifier().classify_all(presentation.slides)
    # Force anomalous into a multi-member content cluster with a normal page.
    content = [
        s
        for s in presentation.slides
        if s.slide_id != anomalous.slide_id and len(s.elements) < 12
    ][:2]
    from archium.domain.visual.template_induction import (
        ArchitecturalContentType,
        ReferenceSlideCluster,
    )

    cluster = ReferenceSlideCluster(
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.TEXT_ARGUMENT,
        slide_ids=[content[0].slide_id, content[1].slide_id, anomalous.slide_id],
    )
    members = [content[0], content[1], anomalous]
    selector = RepresentativeSlideSelector()
    scores = [selector.score(s, cluster=cluster, members=members) for s in members]
    scores.sort(key=lambda s: (-s.total_score, s.slide_id))
    assert scores[0].slide_id != anomalous.slide_id
    anomalous_score = next(s for s in scores if s.slide_id == anomalous.slide_id)
    assert anomalous_score.excessive_complexity_penalty > 0
