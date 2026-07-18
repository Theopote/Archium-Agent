"""Unit tests for plan overlay metadata."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.plan_overlay import (
    PLAN_LEGEND_KEY,
    PLAN_NORTH_ARROW_KEY,
    PLAN_SCALE_LABEL_KEY,
    PlanOverlayMetadata,
    plan_overlay_from_asset,
    plan_overlay_to_metadata,
)


def test_plan_overlay_from_asset_empty_metadata() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="plan.png",
        path="/tmp/plan.png",
        asset_type=AssetType.DRAWING,
    )
    overlay = plan_overlay_from_asset(asset)
    assert overlay is not None
    assert overlay.has_any_overlay is False


def test_plan_overlay_from_asset_reads_verified_fields() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="plan.png",
        path="/tmp/plan.png",
        asset_type=AssetType.DRAWING,
        metadata={
            PLAN_NORTH_ARROW_KEY: True,
            PLAN_SCALE_LABEL_KEY: "0 — 100m",
            PLAN_LEGEND_KEY: [{"label": "人行", "color": "#336699"}],
        },
    )
    overlay = plan_overlay_from_asset(asset)
    assert overlay is not None
    assert overlay.show_north_arrow is True
    assert overlay.scale_label == "0 — 100m"
    assert overlay.legend_items[0].label == "人行"


def test_plan_overlay_scale_pending_round_trip() -> None:
    overlay = PlanOverlayMetadata(scale_pending=True)
    meta = plan_overlay_to_metadata(overlay)
    asset = Asset(
        project_id=uuid4(),
        filename="plan.png",
        path="/tmp/plan.png",
        asset_type=AssetType.DRAWING,
        metadata=meta,
    )
    parsed = plan_overlay_from_asset(asset)
    assert parsed is not None
    assert parsed.scale_pending is True
