"""Recolor bundled architectural icon SVG strokes to match DesignSystem tokens."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PACK_DEFAULT_STROKE = "#1A1A1A"
_TRANSPARENT_STROKES = frozenset({"none", "transparent"})


def is_architectural_icon_ref(content_ref: str | None) -> bool:
    return bool(content_ref and str(content_ref).startswith("icon:"))


def normalize_icon_stroke_color(value: str) -> str:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) not in {3, 6, 8}:
        raise ValueError(f"invalid icon stroke color: {value}")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    return f"#{cleaned.upper()}"


def recolor_icon_svg_text(svg_text: str, stroke_color: str) -> str:
    """Return SVG markup with monochrome stroke colors remapped to ``stroke_color``."""
    target = normalize_icon_stroke_color(stroke_color)
    root = ET.fromstring(svg_text)
    pack_default = PACK_DEFAULT_STROKE.lower()

    def should_remap(raw: str | None) -> bool:
        if raw is None:
            return False
        text = raw.strip()
        if not text or text.lower() in _TRANSPARENT_STROKES:
            return False
        return text.lower() in {pack_default, "currentcolor"}

    if should_remap(root.attrib.get("stroke")) or root.attrib.get("fill", "").lower() == "none":
        root.set("stroke", target)

    for elem in root.iter():
        stroke = elem.attrib.get("stroke")
        if should_remap(stroke):
            elem.set("stroke", target)

    xml = ET.tostring(root, encoding="unicode")
    if not xml.startswith("<?xml"):
        return xml
    return re.sub(r"^\<\?xml[^?]*\?\>\s*", "", xml)


def materialize_recolored_icon(
    source_path: Path,
    stroke_color: str,
    *,
    cache_dir: Path | None = None,
) -> Path:
    """Write a cached recolored SVG and return its path (idempotent per source+color).

    Missing sources are returned unchanged without ``Path.resolve()`` so Windows-style
    absolute paths (``C:/…``) are not rewritten into cwd-relative paths on Linux.
    """
    if not source_path.is_file():
        return source_path

    resolved = source_path.resolve()
    target = normalize_icon_stroke_color(stroke_color)
    if target.upper() == PACK_DEFAULT_STROKE:
        return resolved

    digest = hashlib.sha256(f"{resolved}:{target}".encode()).hexdigest()[:16]
    out_dir = cache_dir or Path.cwd() / ".data" / "icon_recolor_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{resolved.stem}_{digest}.svg"
    if out_path.is_file():
        return out_path

    text = recolor_icon_svg_text(resolved.read_text(encoding="utf-8"), target)
    out_path.write_text(text, encoding="utf-8")
    return out_path

