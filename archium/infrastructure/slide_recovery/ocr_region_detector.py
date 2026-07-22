"""OCR-based text region detection for slide recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from archium.domain.slide_recovery import NormalizedBox, RecoveredPageRegion

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment,misc]

_OCR_LANG = "chi_sim+eng"
_MIN_CONFIDENCE = 30

try:
    import pytesseract as _pytesseract
except ImportError:  # pragma: no cover
    _pytesseract = None  # type: ignore[assignment]


@dataclass(frozen=True)
class OcrDetectionResult:
    regions: list[RecoveredPageRegion]
    engine: str | None
    char_count: int


def pytesseract_available() -> bool:
    return _pytesseract is not None


def detect_text_regions(
    image_path: Path | str,
    *,
    page_width: float,
    page_height: float,
) -> OcrDetectionResult:
    """Run OCR and return text regions with normalized bounding boxes."""
    path = Path(image_path)
    if Image is None or not path.is_file():
        return OcrDetectionResult(regions=[], engine=None, char_count=0)
    if not pytesseract_available():
        return OcrDetectionResult(regions=[], engine=None, char_count=0)

    assert _pytesseract is not None
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        if width <= 0 or height <= 0:
            return OcrDetectionResult(regions=[], engine=None, char_count=0)
        data = _pytesseract.image_to_data(
            rgb,
            lang=_OCR_LANG,
            output_type=_pytesseract.Output.DICT,
        )

    regions = _regions_from_tesseract_data(
        data,
        image_width=width,
        image_height=height,
        page_width=page_width,
        page_height=page_height,
    )
    char_count = sum(len(region.recovered_text or "") for region in regions)
    return OcrDetectionResult(regions=regions, engine="pytesseract", char_count=char_count)


def _regions_from_tesseract_data(
    data: dict[str, list[object]],
    *,
    image_width: int,
    image_height: int,
    page_width: float,
    page_height: float,
) -> list[RecoveredPageRegion]:
    line_groups: dict[tuple[int, int, int], list[int]] = {}
    count = len(data.get("text", []))
    for index in range(count):
        text = str(data["text"][index] or "").strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < _MIN_CONFIDENCE:
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        line_groups.setdefault(key, []).append(index)

    regions: list[RecoveredPageRegion] = []
    for indices in line_groups.values():
        words = [str(data["text"][index] or "").strip() for index in indices]
        text = " ".join(word for word in words if word)
        if not text:
            continue
        left = min(int(data["left"][index]) for index in indices)
        top = min(int(data["top"][index]) for index in indices)
        right = max(int(data["left"][index]) + int(data["width"][index]) for index in indices)
        bottom = max(int(data["top"][index]) + int(data["height"][index]) for index in indices)
        bbox = _pixel_bbox_to_normalized(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            image_width=image_width,
            image_height=image_height,
        )
        if bbox is None:
            continue
        confidences = []
        for index in indices:
            try:
                confidences.append(float(data["conf"][index]) / 100.0)
            except (TypeError, ValueError):
                continue
        confidence = sum(confidences) / len(confidences) if confidences else 0.75
        regions.append(
            RecoveredPageRegion(
                id=uuid4(),
                bbox=bbox,
                region_type="text",
                semantic_role=_infer_text_semantic_role(text, bbox),
                confidence=min(max(confidence, 0.0), 1.0),
                recovered_text=text,
            )
        )
    return regions


def _pixel_bbox_to_normalized(
    *,
    left: int,
    top: int,
    right: int,
    bottom: int,
    image_width: int,
    image_height: int,
) -> NormalizedBox | None:
    width_px = max(right - left, 1)
    height_px = max(bottom - top, 1)
    x = left / image_width
    y = top / image_height
    width = width_px / image_width
    height = height_px / image_height
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    width = min(width, 1.0 - x)
    height = min(height, 1.0 - y)
    if width <= 0 or height <= 0:
        return None
    return NormalizedBox(x=x, y=y, width=width, height=height)


def _infer_text_semantic_role(text: str, bbox: NormalizedBox) -> str:
    if bbox.y <= 0.2 and len(text) <= 40:
        return "title"
    if bbox.y >= 0.85:
        return "caption"
    if "\t" in text or (text.count(" ") >= 3 and len(text) < 30):
        return "table_cell"
    return "body"
