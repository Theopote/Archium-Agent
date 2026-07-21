"""Unit tests for reference slide clustering."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.reference_slide_clusterer import (
    _LAYOUT_MISMATCH_PENALTY,
    ReferenceSlideClusterer,
)
from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideClassification,
    FunctionalSlideType,
)
from archium.infrastructure.template.reference_pptx_parser import (
    ReferencePptxParser,
    _axis_aligned_union_area,
    _content_signature,
    _visual_embedding,
)

from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def _content_clf(slide_id: str, index: int) -> FunctionalSlideClassification:
    return FunctionalSlideClassification(
        slide_id=slide_id,
        slide_index=index,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.STRATEGY,
        confidence=0.7,
    )


def _slide(
    *,
    index: int,
    layout_name: str,
    embedding: list[float],
    signature: str = "sig-same",
) -> ReferenceSlideSnapshot:
    return ReferenceSlideSnapshot(
        slide_index=index,
        slide_id=f"slide_{index + 1:03d}",
        layout_name=layout_name,
        visual_embedding=embedding,
        content_signature=signature,
        text_content=["策略要点"],
    )


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


def test_different_layout_names_can_merge_when_structure_matches() -> None:
    """layout_name is soft — identical structure must not be hard-split."""
    emb = [0.2, 0.1, 0.1, 0.15, 0.1, 0.2, 0.0, 0.0, 0.2, 0.0, 0.0, 0.3]
    slides = [
        _slide(index=0, layout_name="Layout A", embedding=emb, signature="shared"),
        _slide(index=1, layout_name="Layout B", embedding=emb, signature="shared"),
        _slide(index=2, layout_name="标题页", embedding=emb, signature="shared"),
    ]
    classifications = [_content_clf(s.slide_id, s.slide_index) for s in slides]
    clusters = ReferenceSlideClusterer().cluster(slides, classifications)
    content = [c for c in clusters if c.functional_type == FunctionalSlideType.CONTENT]
    assert len(content) == 1
    assert set(content[0].slide_ids) == {s.slide_id for s in slides}
    assert any("layout_name soft-merged" in r for r in content[0].selection_rationale)


def test_content_signature_ignores_layout_name() -> None:
    a = _content_signature(
        element_types=["text", "image"],
        image_count=1,
        text_length=40,
        chart_count=0,
        table_count=0,
    )
    b = _content_signature(
        element_types=["text", "image"],
        image_count=1,
        text_length=40,
        chart_count=0,
        table_count=0,
    )
    assert a == b


def test_connected_components_are_transitive() -> None:
    """A~B and B~C must keep C with A even if A–C is slightly above threshold."""
    # Embeddings live in 1D for clarity; threshold default is 0.42.
    # A–B = 0.30, B–C = 0.30, A–C = 0.60 (> threshold) — seed-only would split C.
    a = _slide(index=0, layout_name="X", embedding=[0.0] * 12, signature="a")
    b = _slide(index=1, layout_name="X", embedding=[0.30] + [0.0] * 11, signature="b")
    c = _slide(index=2, layout_name="X", embedding=[0.60] + [0.0] * 11, signature="c")
    slides = [a, b, c]
    classifications = [_content_clf(s.slide_id, s.slide_index) for s in slides]
    clusters = ReferenceSlideClusterer(distance_threshold=0.42).cluster(
        slides, classifications
    )
    content = [cl for cl in clusters if cl.functional_type == FunctionalSlideType.CONTENT]
    assert len(content) == 1
    assert set(content[0].slide_ids) == {"slide_001", "slide_002", "slide_003"}
    assert any("connected_components" in r for r in content[0].selection_rationale)


def test_layout_mismatch_adds_soft_penalty_only() -> None:
    clusterer = ReferenceSlideClusterer(distance_threshold=0.42)
    left = _slide(index=0, layout_name="A", embedding=[0.0] * 12, signature="x")
    right = _slide(index=1, layout_name="B", embedding=[0.30] + [0.0] * 11, signature="y")
    dist = clusterer._pair_distance(left, right)
    assert abs(dist - (0.30 + _LAYOUT_MISMATCH_PENALTY)) < 1e-9
    assert clusterer._are_similar(left, right)


def test_union_area_does_not_double_count_overlaps() -> None:
    # Two 2x2 squares overlapping in a 1x1 square on a 10x10 page.
    rects = [(0.0, 0.0, 2.0, 2.0), (1.0, 1.0, 2.0, 2.0)]
    union = _axis_aligned_union_area(rects, page_width=10.0, page_height=10.0)
    assert abs(union - 7.0) < 1e-9  # 4 + 4 - 1


def test_visual_embedding_covered_uses_union_not_sum() -> None:
    page_w, page_h = 10.0, 10.0
    elements = [
        ReferenceElement(
            id="bg",
            element_type=ReferenceElementType.DECORATION,
            x=0.0,
            y=0.0,
            width=10.0,
            height=10.0,
        ),
        ReferenceElement(
            id="overlay",
            element_type=ReferenceElementType.SHAPE,
            x=1.0,
            y=1.0,
            width=5.0,
            height=5.0,
        ),
    ]
    emb = _visual_embedding(
        width=page_w,
        height=page_h,
        elements=elements,
        image_count=0,
        text_length=0,
        chart_count=0,
        table_count=0,
    )
    covered = emb[0]
    # Full-page background already covers 1.0; overlay must not push above 1.0.
    assert covered == 1.0
    # Summed areas would be (100+25)/100 = 1.25 before the old clamp-to-2.
    assert covered <= 1.0
