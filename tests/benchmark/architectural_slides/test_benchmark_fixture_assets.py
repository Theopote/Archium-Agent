"""Tests for presentation-ready benchmark fixture asset generation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.asset_presentation_readiness_service import (
    evaluate_asset_presentation_readiness,
)
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType

from tests.benchmark.architectural_slides.benchmark_fixture_assets import (
    write_benchmark_fixture_asset,
)
from tests.benchmark.architectural_slides.case_catalog import CASE_CATALOG


def _asset_type_for(visual_type: VisualType) -> AssetType:
    if visual_type in {
        VisualType.SITE_PLAN,
        VisualType.FLOOR_PLAN,
        VisualType.SECTION,
        VisualType.ELEVATION,
        VisualType.MAP,
    }:
        return AssetType.DRAWING
    if visual_type == VisualType.SITE_PHOTO:
        return AssetType.PHOTO
    return AssetType.IMAGE


def test_all_catalog_assets_generate_presentation_ready_fixtures(tmp_path: Path) -> None:
    seen: set[str] = set()
    for entry in CASE_CATALOG:
        for spec in entry.assets:
            asset_id = str(spec.asset_id)
            if asset_id in seen:
                continue
            seen.add(asset_id)
            path = tmp_path / f"{asset_id}.png"
            write_benchmark_fixture_asset(
                path,
                asset_id=asset_id,
                visual_type=spec.visual_type,
                label=spec.description,
            )
            slot = (
                "hero"
                if spec.visual_type
                in {
                    VisualType.SITE_PLAN,
                    VisualType.FLOOR_PLAN,
                    VisualType.RENDERING,
                }
                else "evidence"
            )
            asset = Asset(
                project_id=uuid4(),
                filename=path.name,
                path=str(path),
                asset_type=_asset_type_for(spec.visual_type),
            )
            readiness = evaluate_asset_presentation_readiness(
                asset,
                image_path=path,
                intended_slot=slot,
            )
            assert readiness.pixel_analyzed is True, asset_id
            assert readiness.is_placeholder is False, (asset_id, readiness.reasons)
            assert readiness.presentation_ready is True, (asset_id, readiness.reasons)
