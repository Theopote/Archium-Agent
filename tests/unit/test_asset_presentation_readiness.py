"""Tests for Asset Presentation Readiness scoring and hero/evidence gates."""

from __future__ import annotations

from uuid import uuid4

from archium.application.asset_matching_service import score_asset_for_requirement
from archium.application.asset_presentation_readiness_service import (
    evaluate_asset_presentation_readiness,
    is_hero_slot_eligible,
)
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import VisualRequirement


def _asset(**kwargs: object) -> Asset:
    payload = {
        "project_id": uuid4(),
        "filename": "site_plan.png",
        "path": "/tmp/site_plan.png",
        "asset_type": AssetType.DRAWING,
        "width": 2400,
        "height": 1800,
        "quality_score": 0.8,
    }
    payload.update(kwargs)
    return Asset(**payload)  # type: ignore[arg-type]


def test_placeholder_filename_grid_not_presentation_ready() -> None:
    asset = _asset(
        filename="filename_grid_placeholder.png",
        metadata={"is_placeholder": True},
    )
    readiness = evaluate_asset_presentation_readiness(asset, intended_slot="hero")
    assert readiness.is_placeholder is True
    assert readiness.presentation_ready is False
    assert not is_hero_slot_eligible(readiness)


def test_real_drawing_is_hero_eligible() -> None:
    asset = _asset(filename="campus_site_plan.png", description="总平面图", tags=["site_plan"])
    readiness = evaluate_asset_presentation_readiness(asset, intended_slot="hero")
    assert readiness.presentation_ready is True
    assert is_hero_slot_eligible(readiness)


def test_matching_rejects_placeholder_for_site_plan() -> None:
    placeholder = _asset(
        filename="placeholder_site.png",
        tags=["placeholder"],
        metadata={"purpose": "placeholder"},
    )
    real = _asset(filename="real_site_plan.png", tags=["site_plan"], description="总平面")
    requirement = VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图")
    assert score_asset_for_requirement(requirement, placeholder) == 0.0
    assert score_asset_for_requirement(requirement, real) > 0.35
