"""Tests for asset provenance labels."""

from __future__ import annotations

from uuid import uuid4

from archium.application.asset_provenance import (
    format_asset_option_label,
    format_asset_provenance,
    is_web_import_asset,
)
from archium.domain.asset import Asset


def test_web_import_provenance_label() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="web_001.jpg",
        path="web_imports/web_001.jpg",
        tags=["web_import", "pexels"],
        metadata={
            "provider": "pexels",
            "attribution": "Photo by Alex on Pexels",
        },
    )
    assert is_web_import_asset(asset)
    label = format_asset_provenance(asset)
    assert label is not None
    assert "网络搜图" in label
    assert "pexels" in label
    assert "Alex" in label
    assert format_asset_option_label(asset) == "web_001.jpg · 网络/pexels"
