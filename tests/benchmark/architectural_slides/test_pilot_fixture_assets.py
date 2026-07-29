"""Tests for pilot trio benchmark fixture assets."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.asset_presentation_readiness_service import (
    evaluate_asset_presentation_readiness,
)
from archium.domain.asset import Asset
from archium.domain.enums import AssetType

from tests.benchmark.architectural_slides.pilot_fixture_assets import (
    PILOT_ASSET_IDS,
    write_pilot_fixture_asset,
)


def test_pilot_fixture_assets_are_presentation_ready(tmp_path: Path) -> None:
    for asset_id, (kind, _label) in PILOT_ASSET_IDS.items():
        path = tmp_path / f"{asset_id}.png"
        write_pilot_fixture_asset(path, asset_id=asset_id)
        asset_type = {
            "site_plan": AssetType.DRAWING,
            "photo": AssetType.PHOTO,
            "hero": AssetType.IMAGE,
        }[kind]
        slot = "hero" if kind in {"site_plan", "hero"} else "evidence"
        asset = Asset(
            project_id=uuid4(),
            filename=path.name,
            path=str(path),
            asset_type=asset_type,
        )
        readiness = evaluate_asset_presentation_readiness(
            asset,
            image_path=path,
            intended_slot=slot,
        )
        assert readiness.pixel_analyzed is True, asset_id
        assert readiness.is_placeholder is False, asset_id
        assert readiness.presentation_ready is True, (asset_id, readiness.reasons)
