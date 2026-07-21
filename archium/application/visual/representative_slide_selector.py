"""Select representative slides for each reference cluster.

Editability scoring (V1.5) is still a **heuristic**, not a full PPTX editability
audit. It rewards replaceable top-level slots (placeholders / text / content
images) and penalizes groups, master-like chrome, full-page backgrounds,
SmartArt/OLE/media tags, lock flags, and parse failures. It does not prove that
a slot can be safely rewritten in an edit-based generator.
"""

from __future__ import annotations

import math

from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ReferenceSlideCluster,
    RepresentativeSlideScore,
)

_FULL_PAGE_AREA_RATIO = 0.85
_CONTENT_IMAGE_TYPES = {
    ReferenceElementType.IMAGE,
    ReferenceElementType.DRAWING,
}


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


def _is_full_page(element: ReferenceElement, *, page_area: float) -> bool:
    return element.width * element.height >= page_area * _FULL_PAGE_AREA_RATIO


def _hard_edit_tags(element: ReferenceElement) -> set[str]:
    tags = {
        note
        for note in element.style_notes
        if isinstance(note, str) and note.startswith("hard_edit:")
    }
    if not element.parse_ok or element.parse_warning:
        tags.add("hard_edit:parse_failed")
    if element.element_type == ReferenceElementType.GROUP:
        tags.add("hard_edit:group")
    return tags


def compute_editability(slide: ReferenceSlideSnapshot) -> tuple[float, list[str]]:
    """Heuristic editability in ``[0, 1]`` plus short rationale fragments."""
    rationale: list[str] = []
    page_area = max(slide.width * slide.height, 0.01)
    top_level = list(slide.elements)
    flat = list(slide.iter_elements())

    placeholder_slots = sum(
        1 for e in top_level if e.element_type == ReferenceElementType.PLACEHOLDER
    )
    replaceable_text = sum(
        1
        for e in top_level
        if e.element_type == ReferenceElementType.TEXT
        and not e.repeats_across_pages
        and not e.likely_background_or_decoration
    )
    replaceable_images = sum(
        1
        for e in top_level
        if e.element_type in _CONTENT_IMAGE_TYPES
        and not e.likely_background_or_decoration
        and not e.repeats_across_pages
        and not _is_full_page(e, page_area=page_area)
    )
    # Nested text/images inside groups are weaker slots (harder to target).
    grouped_slots = sum(
        1
        for e in flat
        if e not in top_level
        and e.element_type
        in {
            ReferenceElementType.TEXT,
            ReferenceElementType.IMAGE,
            ReferenceElementType.DRAWING,
            ReferenceElementType.PLACEHOLDER,
        }
    )

    score = 0.18
    score += 0.14 * min(placeholder_slots, 4)
    score += 0.10 * min(replaceable_text, 4)
    score += 0.12 * min(replaceable_images, 3)
    score += 0.04 * min(grouped_slots, 3)  # weak credit only

    if placeholder_slots:
        rationale.append(f"placeholders={placeholder_slots}")
    if replaceable_text:
        rationale.append(f"top_text_slots={replaceable_text}")
    if replaceable_images:
        rationale.append(f"top_image_slots={replaceable_images}")

    group_roots = sum(1 for e in top_level if e.element_type == ReferenceElementType.GROUP)
    if group_roots:
        score -= 0.08 * min(group_roots, 3)
        rationale.append(f"grouped_shapes={group_roots}")

    master_like = sum(1 for e in flat if e.repeats_across_pages)
    if master_like >= 2:
        score -= min(0.18, 0.06 * master_like)
        rationale.append(f"master_like_chrome={master_like}")

    full_page_bg = any(
        (
            e.element_type
            in {
                ReferenceElementType.IMAGE,
                ReferenceElementType.DRAWING,
                ReferenceElementType.DECORATION,
            }
            or "hard_edit:full_page_background" in e.style_notes
        )
        and _is_full_page(e, page_area=page_area)
        for e in flat
    )
    if full_page_bg:
        score -= 0.12
        rationale.append("full_page_background")

    hard_tags: set[str] = set()
    for element in flat:
        hard_tags |= _hard_edit_tags(element)
    # Group / full-page already scored above — avoid double-counting those tags.
    scored_elsewhere = {"hard_edit:group", "hard_edit:full_page_background"}
    remaining_hard = sorted(hard_tags - scored_elsewhere)
    if remaining_hard:
        score -= 0.10 * min(len(remaining_hard), 4)
        rationale.extend(remaining_hard[:4])

    if placeholder_slots + replaceable_text + replaceable_images == 0:
        score *= 0.45
        rationale.append("no_clear_replaceable_slots")

    if slide.parse_warnings:
        score *= 0.55
        rationale.append("slide_parse_warnings")

    return max(0.0, min(1.0, score)), rationale


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

        editability, edit_notes = compute_editability(slide)

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
            *edit_notes,
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
