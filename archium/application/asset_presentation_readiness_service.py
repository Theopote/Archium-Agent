"""Evaluate whether an asset is presentation-ready for hero / evidence slots."""

from __future__ import annotations

import re
from pathlib import Path

from archium.domain.asset import Asset
from archium.domain.asset_presentation_readiness import (
    ASSET_PRESENTATION_READINESS_KEY,
    AssetPresentationReadiness,
    AssetPresentationRole,
)
from archium.domain.enums import AssetType

_PLACEHOLDER_NAME_RE = re.compile(
    r"(placeholder|占位|filename.?grid|file.?name.?grid|dummy|lorem|sample.?image|"
    r"missing.?image|no.?image|untitled|image.?not.?found|素材缺失|待补)",
    re.IGNORECASE,
)
_FILENAME_GRID_HINT_RE = re.compile(
    r"(grid.?of.?names|name.?strip|file.?list|文件名)",
    re.IGNORECASE,
)

# Minimum pixel edge for hero / drawing readability on a 16:9 slide.
_HERO_MIN_EDGE_PX = 900
_EVIDENCE_MIN_EDGE_PX = 640
_MIN_DENSITY_READY = 0.35


def evaluate_asset_presentation_readiness(
    asset: Asset,
    *,
    image_path: Path | str | None = None,
    intended_slot: str | None = None,
) -> AssetPresentationReadiness:
    """Score visual fitness without requiring a full Visual QA pass.

    Uses filename/metadata heuristics always; opens the image when
    ``image_path`` is provided and Pillow is available.
    """
    reasons: list[str] = []
    cached = _cached_readiness(asset)
    if cached is not None and image_path is None:
        return cached

    is_placeholder = _detect_placeholder(asset)
    if is_placeholder:
        reasons.append("filename_or_metadata_marks_placeholder")

    density = _density_from_metadata(asset)
    path = Path(image_path) if image_path else None
    if path is not None and path.is_file():
        measured = _measure_image_density(path)
        if measured is not None:
            density = measured
            if density < 0.12:
                is_placeholder = True
                reasons.append("image_nearly_blank_or_flat")
            elif density < _MIN_DENSITY_READY:
                reasons.append("low_visual_information_density")

    if density <= 0.0:
        # Unknown content — provisional mid density so catalog matching still works;
        # image measurement / placeholder flags remain the hard gates.
        if asset.width and asset.height:
            density = 0.45 if not asset.is_low_resolution else 0.2
        else:
            density = 0.55
            reasons.append("unknown_dimensions_provisional_density")

    readable = _readable_at_slide_scale(asset, intended_slot=intended_slot)
    if not readable:
        reasons.append("insufficient_resolution_for_slide_scale")

    role = _recommend_role(asset, is_placeholder=is_placeholder, density=density, readable=readable)
    min_area = _min_display_area(role)
    ready = (
        not is_placeholder
        and density >= _MIN_DENSITY_READY
        and readable
        and role != AssetPresentationRole.UNSUITABLE
    )
    if not ready and not reasons:
        reasons.append("not_presentation_ready")

    return AssetPresentationReadiness(
        is_placeholder=is_placeholder,
        visual_information_density=round(min(1.0, max(0.0, density)), 3),
        readable_at_slide_scale=readable,
        recommended_role=role,
        min_display_area_ratio=min_area,
        presentation_ready=ready,
        reasons=reasons,
    )


def cache_readiness_on_asset(asset: Asset, readiness: AssetPresentationReadiness) -> Asset:
    """Return a copy of ``asset`` with readiness stored in metadata."""
    metadata = dict(asset.metadata or {})
    metadata[ASSET_PRESENTATION_READINESS_KEY] = readiness.to_metadata()
    quality = asset.quality_score
    if readiness.presentation_ready:
        quality = max(quality or 0.0, readiness.visual_information_density)
    elif quality is None or quality > 0.25:
        quality = min(quality or 0.25, 0.2)
    return asset.model_copy(update={"metadata": metadata, "quality_score": quality})


def is_hero_slot_eligible(readiness: AssetPresentationReadiness) -> bool:
    """Hero / drawing_focus primary slot requires presentation-ready content."""
    if not readiness.presentation_ready:
        return False
    return readiness.recommended_role in {
        AssetPresentationRole.HERO_DRAWING,
        AssetPresentationRole.HERO_PHOTO,
        AssetPresentationRole.EVIDENCE_PRIMARY,
    }


def is_evidence_slot_eligible(readiness: AssetPresentationReadiness) -> bool:
    if not readiness.presentation_ready:
        return False
    return readiness.recommended_role in {
        AssetPresentationRole.EVIDENCE_PRIMARY,
        AssetPresentationRole.EVIDENCE_SUPPORTING,
        AssetPresentationRole.HERO_PHOTO,
        AssetPresentationRole.HERO_DRAWING,
    }


def _cached_readiness(asset: Asset) -> AssetPresentationReadiness | None:
    raw = (asset.metadata or {}).get(ASSET_PRESENTATION_READINESS_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return AssetPresentationReadiness.model_validate(raw)
    except Exception:
        return None


def _detect_placeholder(asset: Asset) -> bool:
    meta = asset.metadata or {}
    if meta.get("is_placeholder") is True or meta.get("placeholder") is True:
        return True
    if meta.get("synthetic_filename_grid") is True or meta.get("filename_grid") is True:
        return True
    purpose = meta.get("purpose") or meta.get("document_purpose")
    if isinstance(purpose, str) and purpose.strip().lower() in {
        "placeholder",
        "filename_grid",
        "synthetic",
    }:
        return True
    tags = {tag.strip().lower() for tag in (asset.tags or []) if tag.strip()}
    if tags & {"placeholder", "filename_grid", "synthetic", "dummy"}:
        return True
    blob = " ".join(
        part
        for part in (
            asset.filename,
            asset.description or "",
            str(meta.get("vision_caption") or ""),
        )
        if part
    )
    if _PLACEHOLDER_NAME_RE.search(blob) or _FILENAME_GRID_HINT_RE.search(blob):
        return True
    return False


def _density_from_metadata(asset: Asset) -> float:
    meta = asset.metadata or {}
    raw = meta.get("visual_information_density")
    if isinstance(raw, (int, float)):
        return float(raw)
    readiness = meta.get(ASSET_PRESENTATION_READINESS_KEY)
    if isinstance(readiness, dict):
        value = readiness.get("visual_information_density")
        if isinstance(value, (int, float)):
            return float(value)
    if asset.quality_score is not None:
        return float(asset.quality_score)
    return 0.0


def _measure_image_density(path: Path) -> float | None:
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat
    except ImportError:  # pragma: no cover
        return None
    try:
        with Image.open(path) as opened:
            gray = ImageOps.grayscale(opened.convert("RGB"))
            # Downsample for speed.
            gray = gray.resize((160, 90))
    except OSError:
        return None
    stats = ImageStat.Stat(gray)
    stdev = float(stats.stddev[0]) if stats.stddev else 0.0
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
    # Map stdev/edges into 0–1 density (blank ~0, busy drawing/photo ~0.7+).
    density = min(1.0, (stdev / 64.0) * 0.55 + (edge_mean / 40.0) * 0.45)
    return density


def _readable_at_slide_scale(asset: Asset, *, intended_slot: str | None) -> bool:
    if asset.width is None or asset.height is None:
        # Unknown size: allow matching; delivery gates still require real pixels.
        return True
    edge = min(asset.width, asset.height)
    if intended_slot in {"hero", "hero_drawing", "drawing", "site_plan"}:
        return edge >= _HERO_MIN_EDGE_PX
    if intended_slot in {"evidence", "photo"}:
        return edge >= _EVIDENCE_MIN_EDGE_PX
    return edge >= _EVIDENCE_MIN_EDGE_PX


def _recommend_role(
    asset: Asset,
    *,
    is_placeholder: bool,
    density: float,
    readable: bool,
) -> AssetPresentationRole:
    if is_placeholder or density < 0.12:
        return AssetPresentationRole.UNSUITABLE
    meta = asset.metadata or {}
    origin = str(meta.get("asset_origin") or meta.get("origin") or "").lower()
    tags = {tag.strip().lower() for tag in (asset.tags or []) if tag.strip()}
    if origin == "reference_case" or tags & {"reference", "reference_case"}:
        return AssetPresentationRole.REFERENCE_ONLY

    if asset.asset_type in {AssetType.DRAWING, AssetType.DIAGRAM}:
        if density >= _MIN_DENSITY_READY:
            return (
                AssetPresentationRole.HERO_DRAWING
                if readable
                else AssetPresentationRole.EVIDENCE_SUPPORTING
            )
        return AssetPresentationRole.UNSUITABLE

    if asset.asset_type in {AssetType.PHOTO, AssetType.IMAGE}:
        if readable and density >= 0.5:
            return AssetPresentationRole.HERO_PHOTO
        if density >= _MIN_DENSITY_READY:
            return (
                AssetPresentationRole.EVIDENCE_PRIMARY
                if readable
                else AssetPresentationRole.EVIDENCE_SUPPORTING
            )
        return AssetPresentationRole.UNSUITABLE

    return AssetPresentationRole.UNSUITABLE


def _min_display_area(role: AssetPresentationRole) -> float:
    if role == AssetPresentationRole.HERO_DRAWING:
        return 0.65
    if role == AssetPresentationRole.HERO_PHOTO:
        return 0.55
    if role == AssetPresentationRole.EVIDENCE_PRIMARY:
        return 0.35
    if role == AssetPresentationRole.EVIDENCE_SUPPORTING:
        return 0.18
    return 0.35
