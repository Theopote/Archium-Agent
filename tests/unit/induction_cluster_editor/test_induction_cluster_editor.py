"""Unit tests for manual induction cluster editing (Phase 3.5)."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.induction_cluster_editor import (
    layout_from_clusters,
    merge_clusters,
    move_slide,
    rebuild_clusters,
    split_slide,
)
from archium.application.visual.reference_slide_clusterer import ReferenceSlideClusterer
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    InductionReviewOverride,
    ReferenceSlideCluster,
)
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser

from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_move_slide_between_clusters() -> None:
    layout = {"c1": ["a", "b"], "c2": ["c"]}
    moved = move_slide(layout, "b", "c2")
    assert moved["c1"] == ["a"]
    assert set(moved["c2"]) == {"b", "c"}


def test_merge_clusters_combines_members() -> None:
    layout = {"c1": ["a", "b"], "c2": ["c"]}
    merged = merge_clusters(layout, "c2", "c1")
    assert "c2" not in merged
    assert set(merged["c1"]) == {"a", "b", "c"}


def test_split_slide_creates_new_cluster() -> None:
    layout = {"c1": ["a", "b", "c"]}
    split_layout, new_id = split_slide(layout, "b")
    assert split_layout["c1"] == ["a", "c"]
    assert split_layout[new_id] == ["b"]


def test_apply_overrides_preserves_manual_cluster_layout(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    run = service.induce(pptx, capture_screenshots=False)
    presentation = run.presentation
    induction = run.induction

    content_clusters = [
        c
        for c in induction.clusters
        if c.functional_type == FunctionalSlideType.CONTENT and len(c.slide_ids) >= 2
    ]
    assert content_clusters, "need a multi-member content cluster"
    donor = content_clusters[0]
    slide_to_move = donor.slide_ids[0]
    receiver = content_clusters[1]

    layout = layout_from_clusters(induction.clusters)
    layout = move_slide(layout, slide_to_move, receiver.id)

    updated = service.apply_overrides(
        induction,
        presentation,
        overrides=[],
        cluster_layout=layout,
    )
    receiver_after = next(c for c in updated.clusters if c.id == receiver.id)
    assert slide_to_move in receiver_after.slide_ids
    assert slide_to_move not in next(
        c for c in updated.clusters if c.id == donor.id
    ).slide_ids


def test_manual_layout_not_wiped_by_type_only_override(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    parser = ReferencePptxParser()
    presentation = parser.parse(pptx, workspace_dir=tmp_path / "ws", capture_screenshots=False)
    classifications = FunctionalSlideClassifier().classify_all(presentation.slides)
    clusters = ReferenceSlideClusterer().cluster(presentation.slides, classifications)
    content = [c for c in clusters if c.functional_type == FunctionalSlideType.CONTENT]
    assert len(content) >= 2

    from archium.domain.visual.template_induction import TemplateInductionResult

    induction = TemplateInductionResult(
        name="test",
        slide_count=len(presentation.slides),
        classifications=classifications,
        clusters=clusters,
    )
    layout = layout_from_clusters(clusters)
    moved = move_slide(layout, content[0].slide_ids[0], content[1].id)

    service = TemplateInductionService()
    first = service.apply_overrides(induction, presentation, [], cluster_layout=moved)
    layout_after = layout_from_clusters(first.clusters)
    assert layout_after == moved

    # Type-only override on unrelated slide should not auto re-cluster away manual layout.
    other = next(c for c in classifications if c.slide_id != content[0].slide_ids[0])
    second = service.apply_overrides(
        first,
        presentation,
        [
            InductionReviewOverride(
                slide_id=other.slide_id,
                content_type=ArchitecturalContentType.STRATEGY,
            )
        ],
        cluster_layout=moved,
    )
    assert layout_from_clusters(second.clusters) == moved


def test_rebuild_clusters_marks_human_edit() -> None:
    cluster = ReferenceSlideCluster(
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.TEXT_ARGUMENT,
        slide_ids=["slide_001", "slide_002"],
        representative_slide_id="slide_001",
    )
    rebuilt = rebuild_clusters(
        {cluster.id: ["slide_001", "slide_002", "slide_003"]},
        [cluster],
        [],
    )
    assert len(rebuilt) == 1
    assert "human cluster edit" in rebuilt[0].selection_rationale[-1]
