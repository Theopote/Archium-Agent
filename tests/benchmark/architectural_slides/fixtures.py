"""Generate placeholder assets for architectural benchmark cases."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.domain.enums import VisualType
from archium.infrastructure.renderers.diagram_generator import generate_fallback_diagram

from tests.benchmark.architectural_slides.case_registry import (
    CASE_001_HERO,
    CASE_002_PHOTOS,
    CASE_003_IMAGES,
    CASE_004_CHART,
)


def ensure_case_assets(case_id: str, assets_dir: Path) -> list[str]:
    """Create deterministic placeholder PNG assets for a benchmark case."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    rel_paths: list[str] = []
    if case_id == "case_001_site_plan":
        rel_paths.append(_write_asset(assets_dir, CASE_001_HERO, VisualType.SITE_PLAN, "院区总平面"))
    elif case_id == "case_002_site_photos":
        labels = ("入口混行", "停车占道", "景观缺失", "导向不清")
        for asset_id, label in zip(CASE_002_PHOTOS, labels, strict=True):
            rel_paths.append(
                _write_asset(assets_dir, asset_id, VisualType.SITE_PHOTO, label)
            )
    elif case_id == "case_003_case_comparison":
        for index, asset_id in enumerate(CASE_003_IMAGES, start=1):
            rel_paths.append(
                _write_asset(
                    assets_dir,
                    asset_id,
                    VisualType.REFERENCE_CASE,
                    f"案例 {index}",
                )
            )
    elif case_id == "case_004_economic_metrics":
        rel_paths.append(
            _write_asset(assets_dir, CASE_004_CHART, VisualType.CHART, "指标趋势")
        )
    return rel_paths


def _write_asset(
    assets_dir: Path,
    asset_id: UUID,
    visual_type: VisualType,
    description: str,
) -> str:
    filename = f"{asset_id}.png"
    output_path = assets_dir / filename
    if not output_path.exists():
        generate_fallback_diagram(
            output_path,
            title=description,
            visual_type=visual_type,
            description=description,
            key_points=[description],
            message=description,
        )
    return f"assets/{filename}"
