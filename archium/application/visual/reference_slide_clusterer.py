"""Cluster content reference slides by structure + visual signature."""

from __future__ import annotations

import math
from collections import defaultdict

from archium.domain.visual.reference_slide import ReferenceSlideSnapshot
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideClassification,
    FunctionalSlideType,
    ReferenceSlideCluster,
)

_DEFAULT_DISTANCE_THRESHOLD = 0.42


def _euclidean(a: list[float], b: list[float]) -> float:
    n = max(len(a), len(b))
    total = 0.0
    for i in range(n):
        av = a[i] if i < len(a) else 0.0
        bv = b[i] if i < len(b) else 0.0
        total += (av - bv) ** 2
    return math.sqrt(total)


def _mean_embedding(slides: list[ReferenceSlideSnapshot]) -> list[float]:
    vectors = [s.visual_embedding or [] for s in slides if s.visual_embedding]
    if not vectors:
        return []
    dim = max(len(v) for v in vectors)
    acc = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            acc[i] += vec[i] if i < len(vec) else 0.0
    return [v / len(vectors) for v in acc]


class ReferenceSlideClusterer:
    """Deterministic clustering of CONTENT pages (functional pages stay singleton)."""

    def __init__(self, *, distance_threshold: float = _DEFAULT_DISTANCE_THRESHOLD) -> None:
        self._threshold = distance_threshold

    def cluster(
        self,
        slides: list[ReferenceSlideSnapshot],
        classifications: list[FunctionalSlideClassification],
    ) -> list[ReferenceSlideCluster]:
        by_id = {s.slide_id: s for s in slides}
        class_by_id = {c.slide_id: c for c in classifications}
        clusters: list[ReferenceSlideCluster] = []

        # Non-content functional pages: one cluster each (still selectable as representative).
        for slide in slides:
            clf = class_by_id.get(slide.slide_id)
            if clf is None:
                continue
            if clf.functional_type != FunctionalSlideType.CONTENT:
                clusters.append(
                    ReferenceSlideCluster(
                        functional_type=clf.functional_type,
                        content_type=clf.content_type,
                        slide_ids=[slide.slide_id],
                        representative_slide_id=slide.slide_id,
                        visual_similarity=1.0,
                        structural_similarity=1.0,
                        semantic_similarity=1.0,
                        confidence=clf.confidence,
                        selection_rationale=["singleton functional page"],
                        needs_review=clf.needs_review,
                    )
                )

        content_slides = [
            s
            for s in slides
            if class_by_id.get(s.slide_id)
            and class_by_id[s.slide_id].functional_type == FunctionalSlideType.CONTENT
        ]

        # First bucket by content_type + layout_name for stability.
        buckets: dict[tuple[str, str], list[ReferenceSlideSnapshot]] = defaultdict(list)
        for slide in content_slides:
            clf = class_by_id[slide.slide_id]
            key = (clf.content_type.value, slide.layout_name or "")
            buckets[key].append(slide)

        for (content_type_value, _layout), bucket in sorted(buckets.items()):
            groups = self._group_by_distance(bucket)
            for group in groups:
                content_type = ArchitecturalContentType(content_type_value)
                embeddings = [s.visual_embedding or [] for s in group]
                centroid = _mean_embedding(group)
                if len(group) == 1 or not centroid:
                    visual_sim = 1.0
                else:
                    dists = [_euclidean(e, centroid) for e in embeddings if e]
                    mean_d = sum(dists) / max(len(dists), 1)
                    visual_sim = max(0.0, 1.0 - mean_d)
                signatures = {s.content_signature for s in group}
                structural_sim = 1.0 if len(signatures) == 1 else max(0.4, 1.0 - 0.15 * (len(signatures) - 1))
                semantic_sim = 1.0  # same content_type bucket
                conf = sum(class_by_id[s.slide_id].confidence for s in group) / len(group)
                clusters.append(
                    ReferenceSlideCluster(
                        functional_type=FunctionalSlideType.CONTENT,
                        content_type=content_type,
                        slide_ids=[s.slide_id for s in group],
                        representative_slide_id="",  # filled by selector
                        visual_similarity=round(visual_sim, 3),
                        structural_similarity=round(structural_sim, 3),
                        semantic_similarity=round(semantic_sim, 3),
                        confidence=round(conf, 3),
                        selection_rationale=[
                            f"content_type={content_type.value}",
                            f"size={len(group)}",
                            f"visual_sim={visual_sim:.2f}",
                        ],
                        needs_review=any(class_by_id[s.slide_id].needs_review for s in group)
                        or conf < 0.55,
                    )
                )

        # Stable order by first slide index.
        def sort_key(cluster: ReferenceSlideCluster) -> int:
            ids = cluster.slide_ids
            if not ids:
                return 10_000
            return by_id[ids[0]].slide_index if ids[0] in by_id else 10_000

        return sorted(clusters, key=sort_key)

    def _group_by_distance(
        self,
        slides: list[ReferenceSlideSnapshot],
    ) -> list[list[ReferenceSlideSnapshot]]:
        remaining = list(sorted(slides, key=lambda s: s.slide_index))
        groups: list[list[ReferenceSlideSnapshot]] = []
        while remaining:
            seed = remaining.pop(0)
            seed_vec = seed.visual_embedding or []
            group = [seed]
            kept: list[ReferenceSlideSnapshot] = []
            for candidate in remaining:
                cand_vec = candidate.visual_embedding or []
                same_sig = candidate.content_signature == seed.content_signature
                dist = _euclidean(seed_vec, cand_vec) if seed_vec and cand_vec else 99.0
                if same_sig or dist <= self._threshold:
                    group.append(candidate)
                else:
                    kept.append(candidate)
            remaining = kept
            groups.append(group)
        return groups
