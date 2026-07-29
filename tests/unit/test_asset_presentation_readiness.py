"""Tests for Asset Presentation Readiness scoring and hero/evidence gates."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from archium.application.asset_matching_service import AssetMatchingService
from archium.application.asset_matching_service import score_asset_for_requirement
from archium.application.asset_presentation_readiness_service import (
    PRESENTATION_READINESS_UNKNOWN,
    analyze_and_cache_asset_presentation_readiness,
    evaluate_asset_presentation_readiness,
    has_pixel_verified_readiness,
    is_hero_slot_eligible,
)
from archium.config.settings import get_settings
from archium.domain.asset import Asset
from archium.domain.asset_presentation_readiness import (
    ASSET_PRESENTATION_READINESS_KEY,
    AssetPresentationRole,
)
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import VisualRequirement

pytest.importorskip("PIL")


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


def _pixel_verified_asset(**kwargs: object) -> Asset:
    asset = _asset(**kwargs)
    readiness = evaluate_asset_presentation_readiness(
        asset,
        image_path=kwargs.get("path"),
        intended_slot="hero",
    )
    readiness = readiness.model_copy(
        update={
            "pixel_analyzed": True,
            "presentation_ready": True,
            "recommended_role": AssetPresentationRole.HERO_DRAWING,
            "visual_information_density": 0.8,
            "readable_at_slide_scale": True,
            "reasons": [],
        }
    )
    metadata = dict(asset.metadata or {})
    metadata[ASSET_PRESENTATION_READINESS_KEY] = readiness.to_metadata()
    return asset.model_copy(update={"metadata": metadata})


def test_placeholder_filename_grid_not_presentation_ready() -> None:
    asset = _asset(
        filename="filename_grid_placeholder.png",
        metadata={"is_placeholder": True},
    )
    readiness = evaluate_asset_presentation_readiness(asset, intended_slot="hero")
    assert readiness.is_placeholder is True
    assert readiness.presentation_ready is False
    assert not is_hero_slot_eligible(readiness)


def test_real_drawing_requires_pixel_verified_readiness() -> None:
    asset = _asset(filename="campus_site_plan.png", description="总平面图", tags=["site_plan"])
    readiness = evaluate_asset_presentation_readiness(asset, intended_slot="hero")
    assert not has_pixel_verified_readiness(readiness)
    assert PRESENTATION_READINESS_UNKNOWN in readiness.reasons
    assert readiness.presentation_ready is False
    assert not is_hero_slot_eligible(readiness)

    verified = _pixel_verified_asset(
        filename="campus_site_plan.png",
        description="总平面图",
        tags=["site_plan"],
    )
    cached = evaluate_asset_presentation_readiness(verified, intended_slot="hero")
    assert has_pixel_verified_readiness(cached)
    assert is_hero_slot_eligible(cached)


def test_blank_image_detected_as_placeholder(tmp_path: Path) -> None:
    from PIL import Image

    blank = tmp_path / "blank.png"
    Image.new("RGB", (2000, 1500), color=(250, 250, 250)).save(blank)
    asset = _asset(filename="site_plan.png", path=str(blank))
    readiness = evaluate_asset_presentation_readiness(asset, image_path=blank, intended_slot="hero")
    assert readiness.pixel_analyzed is True
    assert readiness.is_placeholder is True
    assert readiness.presentation_ready is False


def test_busy_image_passes_pixel_analysis(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    busy = tmp_path / "drawing.png"
    image = Image.new("RGB", (2000, 1500), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    for x in range(0, 2000, 40):
        draw.line([(x, 0), (x, 1500)], fill=(0, 0, 0), width=2)
    for y in range(0, 1500, 40):
        draw.line([(0, y), (2000, y)], fill=(0, 0, 0), width=2)
    image.save(busy)

    asset = _asset(filename="campus_site_plan.png", path=str(busy))
    analyzed = analyze_and_cache_asset_presentation_readiness(asset, project_storage_root=tmp_path)
    readiness = evaluate_asset_presentation_readiness(analyzed, intended_slot="hero")
    assert readiness.pixel_analyzed is True
    assert readiness.presentation_ready is True
    assert is_hero_slot_eligible(readiness)


def test_matching_rejects_placeholder_for_site_plan() -> None:
    placeholder = _asset(
        filename="placeholder_site.png",
        tags=["placeholder"],
        metadata={"purpose": "placeholder"},
    )
    real = _pixel_verified_asset(filename="real_site_plan.png", tags=["site_plan"], description="总平面")
    requirement = VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图")
    assert score_asset_for_requirement(requirement, placeholder) == 0.0
    assert score_asset_for_requirement(requirement, real) > 0.35


def test_matching_rejects_unverified_readiness_for_site_plan() -> None:
    unverified = _asset(filename="maybe_site_plan.png", tags=["site_plan"], description="总平面")
    requirement = VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图")
    assert score_asset_for_requirement(requirement, unverified) == 0.0


def test_matching_service_backfills_pixel_readiness_before_scoring(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    storage_root = tmp_path / "projects"
    asset_rel = Path("assets") / "drawing.png"
    project_id = uuid4()
    abs_path = storage_root / str(project_id) / asset_rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (2000, 1500), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    for x in range(0, 2000, 30):
        draw.line([(x, 0), (x, 1500)], fill=(0, 0, 0), width=2)
    for y in range(0, 1500, 30):
        draw.line([(0, y), (2000, y)], fill=(0, 0, 0), width=2)
    image.save(abs_path)

    asset = _asset(
        project_id=project_id,
        filename="drawing.png",
        path=str(asset_rel).replace("\\", "/"),
        width=None,
        height=None,
        quality_score=None,
    )
    settings = get_settings().model_copy(update={"project_storage_path": storage_root})
    service = AssetMatchingService(MagicMock(), settings=settings)
    service._assets = MagicMock()
    service._assets.update.side_effect = lambda updated: updated

    prepared = service._ensure_assets_have_cached_readiness([asset])

    assert len(prepared) == 1
    readiness = evaluate_asset_presentation_readiness(prepared[0], intended_slot="hero")
    assert readiness.pixel_analyzed is True
    assert prepared[0].width == 2000
    assert prepared[0].height == 1500
    service._assets.update.assert_called_once()
