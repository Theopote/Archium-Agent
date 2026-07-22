"""Merge structural PPTX regions with perceptual OCR/VLM supplements."""

from __future__ import annotations

from archium.domain.slide_recovery import RecoveredPageRegion

_OVERLAP_IOU_THRESHOLD = 0.40


def merge_structural_and_perceptual(
    structural: list[RecoveredPageRegion],
    perceptual: list[RecoveredPageRegion],
) -> list[RecoveredPageRegion]:
    """Keep structural nodes; add non-overlapping OCR/VLM discoveries."""
    merged = list(structural)
    for candidate in perceptual:
        if candidate.region_type == "text":
            if _text_already_covered(candidate, structural):
                continue
            if _overlaps_regions(candidate, structural, region_types={"text"}):
                continue
        elif _overlaps_regions(candidate, structural):
            continue
        merged.append(candidate)
    return merged


def _text_already_covered(
    candidate: RecoveredPageRegion,
    structural: list[RecoveredPageRegion],
) -> bool:
    text = (candidate.recovered_text or "").strip()
    if not text:
        return True
    for region in structural:
        if region.region_type != "text":
            continue
        existing = (region.recovered_text or "").strip()
        if not existing:
            continue
        if text in existing or existing in text:
            return True
    return False


def _overlaps_regions(
    candidate: RecoveredPageRegion,
    regions: list[RecoveredPageRegion],
    *,
    region_types: set[str] | None = None,
) -> bool:
    for region in regions:
        if region_types is not None and region.region_type not in region_types:
            continue
        if _iou(candidate.bbox, region.bbox) >= _OVERLAP_IOU_THRESHOLD:
            return True
    return False


def _iou(a: object, b: object) -> float:
    ax1, ay1 = a.x, a.y  # type: ignore[attr-defined]
    ax2, ay2 = ax1 + a.width, ay1 + a.height  # type: ignore[attr-defined]
    bx1, by1 = b.x, b.y  # type: ignore[attr-defined]
    bx2, by2 = bx1 + b.width, by1 + b.height  # type: ignore[attr-defined]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0
