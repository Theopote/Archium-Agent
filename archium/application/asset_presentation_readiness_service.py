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

_PIXEL_ANALYZABLE_TYPES = {
    AssetType.IMAGE,
    AssetType.PHOTO,
    AssetType.DRAWING,
    AssetType.DIAGRAM,
    AssetType.CHART,
}

PRESENTATION_READINESS_UNKNOWN = "presentation_readiness_unknown"


def resolve_asset_runtime_image_path(
    asset: Asset,
    *,
    project_storage_root: Path | str | None = None,
) -> Path | None:
    """Resolve ``asset.path`` to a readable filesystem path when possible."""
    raw = Path(asset.path)
    if raw.is_file():
        return raw
    if project_storage_root is not None and not raw.is_absolute():
        candidate = Path(project_storage_root) / str(asset.project_id) / raw
        if candidate.is_file():
            return candidate
    return None


def is_pixel_analyzable_asset(asset: Asset) -> bool:
    return asset.asset_type in _PIXEL_ANALYZABLE_TYPES


def analyze_and_cache_asset_presentation_readiness(
    asset: Asset,
    *,
    project_storage_root: Path | str | None = None,
    intended_slot: str | None = None,
) -> Asset:
    """Run pixel-based readiness analysis and persist the result on the asset."""
    if not is_pixel_analyzable_asset(asset):
        return asset
    image_path = resolve_asset_runtime_image_path(
        asset,
        project_storage_root=project_storage_root,
    )
    readiness = evaluate_asset_presentation_readiness(
        asset,
        image_path=image_path,
        intended_slot=intended_slot,
    )
    updated = cache_readiness_on_asset(asset, readiness)
    if image_path is not None and readiness.pixel_analyzed:
        measured = _measure_image_metrics(image_path)
        if measured is not None:
            _density, width, height = measured
            updates: dict[str, object] = {}
            if updated.width is None:
                updates["width"] = width
            if updated.height is None:
                updates["height"] = height
            if updates:
                updated = updated.model_copy(update=updates)
    return updated


def evaluate_asset_presentation_readiness(
    asset: Asset,
    *,
    image_path: Path | str | None = None,
    intended_slot: str | None = None,
) -> AssetPresentationReadiness:
    """Score visual fitness without requiring a full Visual QA pass.

    Uses filename/metadata heuristics always; opens the image when
    ``image_path`` is provided and Pillow is available. Hero / evidence
    matching requires a cached result with ``pixel_analyzed=True``.
    """
    reasons: list[str] = []
    cached = _cached_readiness(asset)
    if cached is not None and image_path is None:
        return cached

    is_placeholder = _detect_placeholder(asset)
    if is_placeholder:
        reasons.append("filename_or_metadata_marks_placeholder")

    density = _density_from_metadata(asset)
    pixel_analyzed = False
    width = asset.width
    height = asset.height

    path = Path(image_path) if image_path else None
    if path is not None and path.is_file():
        measured = _measure_image_metrics(path)
        if measured is not None:
            density, measured_width, measured_height = measured
            pixel_analyzed = True
            width = width or measured_width
            height = height or measured_height
            if density < 0.12:
                is_placeholder = True
                reasons.append("image_nearly_blank_or_flat")
            elif _detect_synthetic_visual_stub(path):
                is_placeholder = True
                reasons.append("synthetic_filename_grid_or_color_bar")
            elif density < _MIN_DENSITY_READY:
                reasons.append("low_visual_information_density")
    elif is_pixel_analyzable_asset(asset):
        reasons.append(PRESENTATION_READINESS_UNKNOWN)

    readable = _readable_at_slide_scale(width, height, intended_slot=intended_slot)
    if not readable:
        reasons.append("insufficient_resolution_for_slide_scale")

    role = _recommend_role(
        asset,
        is_placeholder=is_placeholder,
        density=density,
        readable=readable,
        pixel_analyzed=pixel_analyzed,
    )
    min_area = _min_display_area(role)
    ready = (
        pixel_analyzed
        and not is_placeholder
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
        pixel_analyzed=pixel_analyzed,
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


def has_pixel_verified_readiness(readiness: AssetPresentationReadiness) -> bool:
    """Return True when readiness was produced from actual pixel measurement."""
    return readiness.pixel_analyzed


def is_hero_slot_eligible(readiness: AssetPresentationReadiness) -> bool:
    """Hero / drawing_focus primary slot requires presentation-ready content."""
    if not has_pixel_verified_readiness(readiness):
        return False
    if not readiness.presentation_ready:
        return False
    return readiness.recommended_role in {
        AssetPresentationRole.HERO_DRAWING,
        AssetPresentationRole.HERO_PHOTO,
        AssetPresentationRole.EVIDENCE_PRIMARY,
    }


def is_evidence_slot_eligible(readiness: AssetPresentationReadiness) -> bool:
    if not has_pixel_verified_readiness(readiness):
        return False
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
    return bool(
        _PLACEHOLDER_NAME_RE.search(blob) or _FILENAME_GRID_HINT_RE.search(blob)
    )


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


def _measure_image_metrics(path: Path) -> tuple[float, int, int] | None:
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat
    except ImportError:  # pragma: no cover
        return None
    try:
        with Image.open(path) as opened:
            rgb = opened.convert("RGB")
            width, height = rgb.size
            gray = ImageOps.grayscale(rgb)
            gray = gray.resize((160, 90))
    except OSError:
        return None
    stats = ImageStat.Stat(gray)
    stdev = float(stats.stddev[0]) if stats.stddev else 0.0
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
    density = min(1.0, (stdev / 64.0) * 0.55 + (edge_mean / 40.0) * 0.45)
    return density, width, height


def _measure_image_density(path: Path) -> float | None:
    measured = _measure_image_metrics(path)
    if measured is None:
        return None
    return measured[0]


def _detect_synthetic_visual_stub(path: Path) -> bool:
    """Detect benchmark-style stubs: solid photo bars or filename-grid diagrams."""
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat
    except ImportError:  # pragma: no cover
        return False
    try:
        with Image.open(path) as opened:
            gray = ImageOps.grayscale(opened.convert("RGB"))
    except OSError:
        return False

    width, height = gray.size
    if width < 64 or height < 64:
        return False

    top = gray.crop((0, 0, width, int(height * 0.78)))
    bottom = gray.crop((0, int(height * 0.82), width, height))
    top_stdev = float(ImageStat.Stat(top).stddev[0] or 0)
    bottom_edges = bottom.filter(ImageFilter.FIND_EDGES)
    top_edges = top.filter(ImageFilter.FIND_EDGES)
    bottom_edge_mean = float(ImageStat.Stat(bottom_edges).mean[0] or 0)
    top_edge_mean = float(ImageStat.Stat(top_edges).mean[0] or 0)
    if top_stdev < 8 and bottom_edge_mean > max(3.0, top_edge_mean * 2.0):
        return True

    density = _measure_image_density(path)
    stats = ImageStat.Stat(gray)
    stdev = float(stats.stddev[0] or 0)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mean = float(ImageStat.Stat(edges).mean[0] or 0)
    if density is not None and density < 0.38 and 12 <= stdev <= 48 and edge_mean < 22:
        sample = gray.resize((48, 27))
        cell_stdevs: list[float] = []
        for row in range(3):
            for col in range(3):
                x0 = col * 48 // 3
                y0 = row * 27 // 3
                x1 = (col + 1) * 48 // 3
                y1 = (row + 1) * 27 // 3
                cell = sample.crop((x0, y0, x1, y1))
                cell_stdevs.append(float(ImageStat.Stat(cell).stddev[0] or 0))
        if cell_stdevs and max(cell_stdevs) - min(cell_stdevs) < 18:
            return True
    return False


def _readable_at_slide_scale(
    width: int | None,
    height: int | None,
    *,
    intended_slot: str | None,
) -> bool:
    if width is None or height is None:
        return False
    edge = min(width, height)
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
    pixel_analyzed: bool,
) -> AssetPresentationRole:
    if not pixel_analyzed:
        return AssetPresentationRole.UNSUITABLE
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
