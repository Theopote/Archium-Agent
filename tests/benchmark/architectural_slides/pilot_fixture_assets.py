"""Generate presentation-ready benchmark fixtures for the pilot trio cases."""

from __future__ import annotations

from pathlib import Path

from archium.domain.enums import VisualType

from tests.benchmark.architectural_slides.benchmark_fixture_assets import (
    write_benchmark_fixture_asset,
)

PILOT_ASSET_IDS: dict[str, tuple[str, str]] = {
    "c0010001-0001-4001-8001-000000000001": ("site_plan", "院区总平面"),
    "c0020001-0001-4001-8001-000000000001": ("photo", "入口混行"),
    "c0020002-0001-4001-8001-000000000002": ("photo", "停车占道"),
    "c0020003-0001-4001-8001-000000000003": ("photo", "景观缺失"),
    "c0020004-0001-4001-8001-000000000004": ("photo", "导向不清"),
    "c0060001-0001-4001-8001-000000000001": ("hero", "内院效果图"),
}

_KIND_TO_VISUAL = {
    "site_plan": VisualType.SITE_PLAN,
    "photo": VisualType.SITE_PHOTO,
    "hero": VisualType.RENDERING,
}


def write_pilot_fixture_asset(output_path: Path, *, asset_id: str) -> Path:
    """Write one pilot fixture PNG with enough visual density for readiness gates."""
    kind, label = PILOT_ASSET_IDS[asset_id]
    return write_benchmark_fixture_asset(
        output_path,
        asset_id=asset_id,
        visual_type=_KIND_TO_VISUAL[kind],
        label=label,
    )


__all__ = ["PILOT_ASSET_IDS", "write_pilot_fixture_asset"]
