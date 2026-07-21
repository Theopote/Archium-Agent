"""Manual cluster move / merge / split for template induction review (Phase 3.5)."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideClassification,
    FunctionalSlideType,
    ReferenceSlideCluster,
)

ClusterLayout = dict[str, list[str]]


def layout_from_clusters(clusters: list[ReferenceSlideCluster]) -> ClusterLayout:
    return {cluster.id: list(cluster.slide_ids) for cluster in clusters}


def move_slide(
    layout: ClusterLayout,
    slide_id: str,
    target_cluster_id: str,
) -> ClusterLayout:
    """Move one slide into ``target_cluster_id`` (creating the bucket if needed)."""
    result: ClusterLayout = {}
    for cluster_id, slide_ids in layout.items():
        kept = [sid for sid in slide_ids if sid != slide_id]
        if kept:
            result[cluster_id] = kept
    bucket = list(result.get(target_cluster_id, []))
    if slide_id not in bucket:
        bucket.append(slide_id)
    result[target_cluster_id] = bucket
    return result


def merge_clusters(
    layout: ClusterLayout,
    source_cluster_id: str,
    target_cluster_id: str,
) -> ClusterLayout:
    """Merge ``source_cluster_id`` into ``target_cluster_id`` (source removed)."""
    if source_cluster_id == target_cluster_id:
        return layout
    source_slides = list(layout.get(source_cluster_id, []))
    target_slides = list(layout.get(target_cluster_id, []))
    merged = target_slides + [s for s in source_slides if s not in target_slides]
    result = {
        cid: slides
        for cid, slides in layout.items()
        if cid not in {source_cluster_id, target_cluster_id} and slides
    }
    if merged:
        result[target_cluster_id] = merged
    return result


def split_slide(layout: ClusterLayout, slide_id: str) -> tuple[ClusterLayout, str]:
    """Move ``slide_id`` into a freshly allocated cluster id."""
    new_cluster_id = str(uuid4())
    return move_slide(layout, slide_id, new_cluster_id), new_cluster_id


def rebuild_clusters(
    layout: ClusterLayout,
    existing: list[ReferenceSlideCluster],
    classifications: list[FunctionalSlideClassification],
) -> list[ReferenceSlideCluster]:
    """Materialize ``ReferenceSlideCluster`` rows from a manual layout."""
    old_by_id = {cluster.id: cluster for cluster in existing}
    class_by_id = {item.slide_id: item for item in classifications}

    def cluster_sort_key(item: tuple[str, list[str]]) -> tuple[int, str]:
        cluster_id, slide_ids = item
        indices = [
            class_by_id[sid].slide_index
            for sid in slide_ids
            if sid in class_by_id
        ]
        return (min(indices) if indices else 10_000, cluster_id)

    clusters: list[ReferenceSlideCluster] = []
    for cluster_id, slide_ids in sorted(layout.items(), key=cluster_sort_key):
        if not slide_ids:
            continue
        prior = old_by_id.get(cluster_id)
        sample = next(
            (class_by_id[sid] for sid in slide_ids if sid in class_by_id),
            None,
        )
        functional = (
            prior.functional_type
            if prior is not None
            else (sample.functional_type if sample else FunctionalSlideType.CONTENT)
        )
        content = (
            prior.content_type
            if prior is not None
            else (sample.content_type if sample else ArchitecturalContentType.UNKNOWN)
        )
        rep = ""
        if prior is not None and prior.representative_slide_id in slide_ids:
            rep = prior.representative_slide_id
        rationale = (
            ["human cluster edit"]
            if prior is None
            else [*prior.selection_rationale, "human cluster edit"]
        )
        clusters.append(
            ReferenceSlideCluster(
                id=cluster_id,
                functional_type=functional,
                content_type=content,
                slide_ids=slide_ids,
                representative_slide_id=rep,
                visual_similarity=prior.visual_similarity if prior else 1.0,
                structural_similarity=prior.structural_similarity if prior else 1.0,
                semantic_similarity=prior.semantic_similarity if prior else 1.0,
                confidence=prior.confidence if prior else 0.55,
                selection_rationale=rationale,
                needs_review=True,
            )
        )
    return clusters


def layout_changed(original: ClusterLayout, updated: ClusterLayout) -> bool:
    if set(original.keys()) != set(updated.keys()):
        return True
    for cluster_id, slide_ids in original.items():
        if slide_ids != updated.get(cluster_id, []):
            return True
    return False
