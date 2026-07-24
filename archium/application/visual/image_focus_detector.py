"""Pillow heuristic focus / subject detection for smart crop (no OpenCV)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from archium.domain.visual.image_derivative import FocalPoint, ImageCropBox, ImageCropStrategy
from archium.logging import get_logger

logger = get_logger(__name__, operation="image_focus_detector")

MIN_CROP_CONFIDENCE = 0.35
_ANALYSIS_EDGE = 64


FocusHint = Literal["auto", "subject", "skyline", "people"]


@dataclass(frozen=True)
class FocusDetectionResult:
    focal_point: FocalPoint
    crop: ImageCropBox | None = None
    strategy_used: ImageCropStrategy = ImageCropStrategy.SUBJECT_HEURISTIC


class ImageFocusDetector:
    """Edge-energy heuristics for building subject / skyline / weak people cues."""

    def detect(
        self,
        path: Path,
        *,
        hint: FocusHint = "auto",
        strategy: ImageCropStrategy = ImageCropStrategy.SUBJECT_HEURISTIC,
    ) -> FocusDetectionResult | None:
        if not path.is_file():
            return None
        try:
            from PIL import Image
        except ImportError:
            return None

        try:
            with Image.open(path) as opened:
                gray = opened.convert("L")
                gray.thumbnail((_ANALYSIS_EDGE, _ANALYSIS_EDGE), Image.Resampling.BILINEAR)
                energy = _edge_energy(gray)
        except OSError as exc:
            logger.info("Focus detect failed for %s: %s", path, exc)
            return None

        w, h = energy.size
        if w < 4 or h < 4:
            return None

        resolved = strategy
        if strategy == ImageCropStrategy.SKYLINE_HEURISTIC or hint == "skyline":
            focal = _skyline_focal(energy)
            resolved = ImageCropStrategy.SKYLINE_HEURISTIC
        elif hint == "people":
            focal = _people_focal(energy)
            if focal.confidence < MIN_CROP_CONFIDENCE:
                focal = _subject_focal(energy)
            resolved = ImageCropStrategy.SUBJECT_HEURISTIC
        else:
            focal = _subject_focal(energy)
            resolved = ImageCropStrategy.SUBJECT_HEURISTIC

        if focal.confidence < MIN_CROP_CONFIDENCE:
            return FocusDetectionResult(
                focal_point=FocalPoint(source="heuristic", confidence=focal.confidence),
                crop=None,
                strategy_used=resolved,
            )

        keep = 0.85
        crop = ImageCropBox(
            x=max(0.0, min(1.0 - keep, focal.x - keep / 2)),
            y=max(0.0, min(1.0 - keep, focal.y - keep / 2)),
            width=keep,
            height=keep,
        )
        return FocusDetectionResult(
            focal_point=focal,
            crop=crop,
            strategy_used=resolved,
        )


def _edge_energy(gray: object) -> object:
    """Return L-mode image with simple |∇| energy (Pillow only)."""
    from PIL import ImageChops, ImageFilter

    image = gray.filter(ImageFilter.SMOOTH)
    left = ImageChops.offset(image, 1, 0)
    up = ImageChops.offset(image, 0, 1)
    dx = ImageChops.difference(image, left)
    dy = ImageChops.difference(image, up)
    return ImageChops.add(dx, dy, scale=1.0, offset=0)


def _pixels(energy: object) -> list[int]:
    # Pillow 14 deprecates getdata; prefer get_flattened_data when present.
    flattened = getattr(energy, "get_flattened_data", None)
    if callable(flattened):
        return list(flattened())
    return list(energy.getdata())  # type: ignore[attr-defined]


def _subject_focal(energy: object) -> FocalPoint:
    """Building-ish subject: energy centroid in mid/lower band (avoid sky)."""
    w, h = energy.size  # type: ignore[attr-defined]
    data = _pixels(energy)
    total = 0.0
    sx = 0.0
    sy = 0.0
    peak = 0
    for y in range(h):
        # Weight sky band (top 20%) down; boost lower 60%.
        if y < h * 0.2:
            row_w = 0.25
        elif y > h * 0.4:
            row_w = 1.35
        else:
            row_w = 1.0
        for x in range(w):
            v = data[y * w + x] * row_w
            if v <= 0:
                continue
            total += v
            sx += x * v
            sy += y * v
            peak = max(peak, int(v))
    if total <= 1e-6:
        return FocalPoint(source="heuristic", confidence=0.0)
    fx = (sx / total) / max(w - 1, 1)
    fy = (sy / total) / max(h - 1, 1)
    # Confidence: how far from dead center + how peaked vs mean.
    mean = total / (w * h)
    peaked = min(1.0, (peak / max(mean, 1.0)) / 8.0)
    offset = ((fx - 0.5) ** 2 + (fy - 0.5) ** 2) ** 0.5
    confidence = min(1.0, 0.25 + peaked * 0.45 + offset * 0.9)
    return FocalPoint(
        x=max(0.0, min(1.0, fx)),
        y=max(0.0, min(1.0, fy)),
        confidence=confidence,
        source="heuristic",
    )


def _skyline_focal(energy: object) -> FocalPoint:
    """Prefer upper third where horizontal structure (skyline) is strong."""
    w, h = energy.size  # type: ignore[attr-defined]
    data = _pixels(energy)
    band = max(1, int(h * 0.34))
    total = 0.0
    sx = 0.0
    sy = 0.0
    for y in range(band):
        for x in range(w):
            v = float(data[y * w + x])
            total += v
            sx += x * v
            sy += y * v
    if total <= 1e-6:
        return FocalPoint(x=0.5, y=0.28, confidence=0.2, source="heuristic")
    fx = (sx / total) / max(w - 1, 1)
    fy = (sy / total) / max(h - 1, 1)
    # Bias slightly upward for skyline compositions.
    fy = min(fy, 0.4)
    confidence = min(1.0, 0.4 + (total / (band * w * 40.0)))
    return FocalPoint(
        x=max(0.0, min(1.0, fx)),
        y=max(0.0, min(1.0, fy)),
        confidence=confidence,
        source="heuristic",
    )


def _people_focal(energy: object) -> FocalPoint:
    """Weak people cue: vertical mid-band energy centroid."""
    w, h = energy.size  # type: ignore[attr-defined]
    data = _pixels(energy)
    x0, x1 = int(w * 0.25), int(w * 0.75)
    y0, y1 = int(h * 0.15), int(h * 0.85)
    total = 0.0
    sx = 0.0
    sy = 0.0
    for y in range(y0, max(y0 + 1, y1)):
        for x in range(x0, max(x0 + 1, x1)):
            v = float(data[y * w + x])
            total += v
            sx += x * v
            sy += y * v
    if total <= 1e-6:
        return FocalPoint(source="heuristic", confidence=0.15)
    fx = (sx / total) / max(w - 1, 1)
    fy = (sy / total) / max(h - 1, 1)
    # People heuristic is weak — cap confidence.
    confidence = min(0.55, 0.2 + (total / ((x1 - x0) * (y1 - y0) * 50.0)))
    return FocalPoint(
        x=max(0.0, min(1.0, fx)),
        y=max(0.0, min(1.0, fy)),
        confidence=confidence,
        source="heuristic",
    )
