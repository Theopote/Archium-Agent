"""Select representative slides for each reference cluster."""

from __future__ import annotations

import math

from archium.domain.visual.reference_slide import ReferenceElementType, ReferenceSlideSnapshot
from archium.domain.visual.template_induction import (
    ReferenceSlideCluster,
    RepresentativeSlideScore,
)


def _euclidean(a: list[float], b: list[float]) -> float:
    n = max(len(a), len(b))
    total = 0.0
    for i in range(n):
        av = a[i] if i < len(a) else 0.0
        bv = b[i] if i < len(b) else 0.0
        total += (av - bv) ** 2
    return math.sqrt(total)


def _centroid(slides: list[ReferenceSlideSnapshot]) -> list[float]:
    vectors = [s.visual_embedding or [] for s in slides if s.visual_embedding]
    if not vectors:
        return []
    dim = max(len(v) for v in vectors)
    acc = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            acc[i] += vec[i] if i < len(vec) else 0.0
    return [v / len(vectors) for v in acc]


class RepresentativeSlideSelector:
    """Score candidates; never pick by shape count alone."""

    def select_for_clusters(
        self,
        clusters: list[ReferenceSlideCluster],
        slides: list[ReferenceSlideSnapshot],
    ) -> tuple[list[ReferenceSlideCluster], list[RepresentativeSlideScore]]:
        by_id = {s.slide_id: s for s in slides}
        all_scores: list[RepresentativeSlideScore] = []
        updated: list[ReferenceSlideCluster] = []

        for cluster in clusters:
            members = [by_id[sid] for sid in cluster.slide_ids if sid in by_id]
            if not members:
                updated.append(cluster)
                continue
            scores = [self.score(slide, cluster=cluster, members=members) for slide in members]
            scores.sort(key=lambda s: (-s.total_score, s.slide_id))
            best = scores[0]
            cluster.representative_slide_id = best.slide_id
            cluster.selection_rationale = list(best.rationale)
            all_scores.extend(scores)
            updated.append(cluster)
        return updated, all_scores

    def score(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        cluster: ReferenceSlideCluster,
        members: list[ReferenceSlideSnapshot],
    ) -> RepresentativeSlideScore:
        centroid = _centroid(members)
        vec = slide.visual_embedding or []
        if centroid and vec:
            dist = _euclidean(vec, centroid)
            centrality = max(0.0, 1.0 - dist)
        else:
            centrality = 0.5

        roles = {e.semantic_role for e in slide.elements}
        has_title = "title" in roles
        has_body_or_visual = bool(
            roles & {"body", "hero_image", "supporting_image", "drawing", "metric"}
        )
        structural = 0.35 * float(has_title) + 0.35 * float(has_body_or_visual)
        structural += 0.15 if slide.layout_name else 0.0
        structural += 0.15 if not slide.parse_warnings else 0.0
        structural = min(1.0, structural)

        # Editability: replaceable text/image slots, not locked weirdness.
        text_slots = sum(1 for e in slide.elements if e.element_type == ReferenceElementType.TEXT)
        image_slots = slide.image_count
        editability = min(1.0, 0.25 + 0.15 * min(text_slots, 4) + 0.2 * min(image_slots, 3))
        if slide.parse_warnings:
            editability *= 0.5

        # Visual clarity: dominant element + not empty.
        areas = [e.width * e.height for e in slide.elements]
        page_area = max(slide.width * slide.height, 0.01)
        max_frac = (max(areas) / page_area) if areas else 0.0
        visual_clarity = min(1.0, 0.3 + max_frac)
        if slide.image_path:
            visual_clarity = min(1.0, visual_clarity + 0.15)

        # Reuse potential: frequency of content signature in cluster.
        sig_count = sum(1 for m in members if m.content_signature == slide.content_signature)
        reuse = min(1.0, sig_count / max(len(members), 1))

        # Anomaly: unique signature, parse failure, extreme density.
        anomaly = 0.0
        rationale: list[str] = []
        if slide.parse_warnings:
            anomaly += 0.35
            rationale.append("parse warnings")
        if sig_count == 1 and len(members) >= 3:
            anomaly += 0.25
            rationale.append("unique signature in large cluster")
        if len(slide.elements) <= 1:
            anomaly += 0.2
            rationale.append("too few elements")

        complexity_penalty = 0.0
        if len(slide.elements) > 18:
            complexity_penalty += 0.25
            rationale.append("excessive element count")
        if slide.text_length > 900:
            complexity_penalty += 0.15
            rationale.append("excessive text length")

        # Explicitly do NOT reward raw shape count.
        total = (
            centrality
            + structural
            + editability
            + visual_clarity
            + reuse
            - anomaly
            - complexity_penalty
        )
        rationale = [
            f"centrality={centrality:.2f}",
            f"structural={structural:.2f}",
            f"editability={editability:.2f}",
            f"clarity={visual_clarity:.2f}",
            f"reuse={reuse:.2f}",
            *rationale,
        ]

        return RepresentativeSlideScore(
            slide_id=slide.slide_id,
            cluster_id=cluster.id,
            cluster_centrality=round(centrality, 3),
            structural_completeness=round(structural, 3),
            editability=round(editability, 3),
            visual_clarity=round(visual_clarity, 3),
            reuse_potential=round(reuse, 3),
            anomaly_penalty=round(anomaly, 3),
            excessive_complexity_penalty=round(complexity_penalty, 3),
            total_score=round(total, 3),
            rationale=rationale,
        )
