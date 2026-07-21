"""Rule-driven visual layout pattern classification (PPTAgent visual layer, V1).

Uses structural embedding features and element geometry — not screenshot CNN/VLM.
Screenshot paths remain available for a future optional embedding pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.reference_slide import ReferenceElementType, ReferenceSlideSnapshot
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideClassification,
    FunctionalSlideType,
    VisualLayoutPattern,
)

_LOW_CONFIDENCE = 0.45


@dataclass(frozen=True)
class VisualLayoutFeatures:
    covered: float
    top_heavy: float
    left_heavy: float
    max_element: float
    image_count: int
    drawing_count: int
    text_length: int
    element_count: int
    metric_like_text: int


def extract_visual_layout_features(slide: ReferenceSlideSnapshot) -> VisualLayoutFeatures:
    emb = slide.visual_embedding or []
    flat = slide.iter_elements()
    area = max(slide.width * slide.height, 0.01)
    max_frac = max((e.width * e.height / area for e in flat), default=0.0)
    drawing_count = sum(1 for e in flat if e.element_type == ReferenceElementType.DRAWING)
    metric_like = sum(
        1
        for e in flat
        if e.element_type == ReferenceElementType.TEXT
        and e.semantic_role == "metric"
    )
    if metric_like == 0:
        metric_like = sum(
            1
            for text in slide.text_content
            if any(token in text for token in ("㎡", "%", "万", "指标"))
        )

    return VisualLayoutFeatures(
        covered=emb[0] if emb else 0.0,
        top_heavy=emb[1] if len(emb) > 1 else 0.0,
        left_heavy=emb[2] if len(emb) > 2 else 0.0,
        max_element=emb[3] if len(emb) > 3 else max_frac,
        image_count=slide.image_count,
        drawing_count=drawing_count,
        text_length=slide.text_length,
        element_count=len(flat),
        metric_like_text=metric_like,
    )


class VisualLayoutPatternClassifier:
    """Infer visual composition pattern from parsed reference slide structure."""

    def classify_all(
        self,
        slides: list[ReferenceSlideSnapshot],
        classifications: list[FunctionalSlideClassification],
    ) -> list[FunctionalSlideClassification]:
        by_id = {item.slide_id: item for item in classifications}
        updated: list[FunctionalSlideClassification] = []
        for slide in slides:
            base = by_id.get(slide.slide_id)
            if base is None:
                continue
            pattern, confidence, evidence = self.classify(
                slide,
                functional_type=base.functional_type,
                content_type=base.content_type,
            )
            extra_evidence = list(base.evidence)
            extra_evidence.extend(evidence[:3])
            needs_review = base.needs_review or confidence < _LOW_CONFIDENCE
            updated.append(
                base.model_copy(
                    update={
                        "visual_layout_pattern": pattern,
                        "confidence": round(min(1.0, (base.confidence + confidence) / 2), 3)
                        if base.confidence > 0
                        else round(confidence, 3),
                        "evidence": extra_evidence,
                        "needs_review": needs_review,
                    }
                )
            )
        return updated

    def classify(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        functional_type: FunctionalSlideType,
        content_type: ArchitecturalContentType,
    ) -> tuple[VisualLayoutPattern, float, list[str]]:
        features = extract_visual_layout_features(slide)
        evidence: list[str] = []

        if functional_type in {
            FunctionalSlideType.SECTION_DIVIDER,
            FunctionalSlideType.COVER,
        } and features.text_length < 80 and features.image_count <= 1:
            if features.max_element >= 0.4:
                return VisualLayoutPattern.HERO_IMAGE, 0.72, ["functional sparse + dominant visual"]
            return VisualLayoutPattern.SECTION_SPLASH, 0.7, ["functional section/cover splash"]

        if (
            features.drawing_count >= 1
            and features.max_element >= 0.42
        ) or content_type == ArchitecturalContentType.DRAWING_FOCUS and features.max_element >= 0.35:
            evidence.append(f"max_element={features.max_element:.2f}")
            evidence.append(f"drawings={features.drawing_count}")
            return VisualLayoutPattern.FULL_BLEED_DRAWING, 0.82, evidence

        if features.image_count >= 3 or (
            features.image_count >= 2 and features.max_element < 0.28
        ):
            evidence.append(f"images={features.image_count}")
            return VisualLayoutPattern.IMAGE_GRID, 0.78, evidence

        if (
            features.metric_like_text >= 2
            or content_type == ArchitecturalContentType.METRIC_SUMMARY
        ) and features.element_count >= 3:
            evidence.append(f"metric_blocks={features.metric_like_text}")
            return VisualLayoutPattern.METRIC_CARDS, 0.76, evidence

        if features.max_element >= 0.55 and features.text_length > 60:
            evidence.append("large visual + overlay text")
            return VisualLayoutPattern.TEXT_OVERLAY, 0.74, evidence

        if (
            features.left_heavy >= 0.28
            and features.image_count >= 1
            and features.max_element < 0.45
        ):
            evidence.append(f"left_heavy={features.left_heavy:.2f}")
            return VisualLayoutPattern.TWO_COLUMN, 0.75, evidence

        if (
            features.image_count >= 1
            and features.max_element >= 0.32
            and features.image_count <= 2
            and features.left_heavy < 0.32
        ):
            evidence.append(f"hero_frac={features.max_element:.2f}")
            return VisualLayoutPattern.HERO_IMAGE, 0.77, evidence

        if features.element_count >= 5 and features.covered >= 0.35 and features.max_element < 0.32:
            evidence.append(f"elements={features.element_count}")
            return VisualLayoutPattern.CARD_LAYOUT, 0.68, evidence

        if features.text_length >= 120 and features.image_count == 0 and features.drawing_count == 0:
            evidence.append("text-dominant column")
            return VisualLayoutPattern.TEXT_COLUMN, 0.66, evidence

        if features.covered < 0.22 and features.text_length < 50 and features.image_count == 0:
            return VisualLayoutPattern.MINIMAL, 0.62, ["sparse layout"]

        if content_type == ArchitecturalContentType.BEFORE_AFTER and features.image_count >= 2:
            return VisualLayoutPattern.TWO_COLUMN, 0.7, ["before/after split"]

        return VisualLayoutPattern.UNKNOWN, 0.35, ["no strong visual pattern"]


def dominant_visual_layout_pattern(
    patterns: list[VisualLayoutPattern],
) -> VisualLayoutPattern:
    if not patterns:
        return VisualLayoutPattern.UNKNOWN
    counts: dict[VisualLayoutPattern, int] = {}
    for pattern in patterns:
        counts[pattern] = counts.get(pattern, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].value))
    winner, top = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == top:
        return VisualLayoutPattern.UNKNOWN
    return winner
