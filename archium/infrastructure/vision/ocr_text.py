"""Shared OCR text extraction for document ingest (Topic 05 / KN-005).

Reuses pytesseract when available; slide recovery keeps its own region detector.
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

try:
    import pytesseract as _pytesseract
except ImportError:  # pragma: no cover
    _pytesseract = None

_OCR_LANG = "chi_sim+eng"
_MIN_CHARS = 8


def pytesseract_available() -> bool:
    return _pytesseract is not None and Image is not None


def extract_text_from_image(image_path: Path | str, *, lang: str = _OCR_LANG) -> str:
    """Return OCR plain text for an image path, or empty string if unavailable."""
    path = Path(image_path)
    if not pytesseract_available() or not path.is_file():
        return ""
    assert Image is not None and _pytesseract is not None
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            text = _pytesseract.image_to_string(rgb, lang=lang) or ""
    except Exception:
        return ""
    return " ".join(text.split()).strip()


def is_meaningful_ocr_text(text: str, *, min_chars: int = _MIN_CHARS) -> bool:
    return len((text or "").strip()) >= min_chars
