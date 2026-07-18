"""Unit tests for drawing-classifier scoring in asset matching."""

from __future__ import annotations

from uuid import uuid4

from archium.application.asset_matching_service import score_asset_for_requirement
from archium.application.asset_matching_visual import drawing_type_match_adjustment
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import VisualRequirement
from archium.domain.visual_qa import VisualQAReport


def test_drawing_type_match_bonus() -> None:
    requirement = VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图")
    report = VisualQAReport(
        asset_id=uuid4(),
        asset_path="/tmp/plan.png",
        width=1200,
        height=900,
        drawing_type="site_plan",
        drawing_type_confidence=0.9,
    )
    assert drawing_type_match_adjustment(requirement, report) > 0.0


def test_drawing_type_mismatch_penalty() -> None:
    requirement = VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图")
    report = VisualQAReport(
        asset_id=uuid4(),
        asset_path="/tmp/plan.png",
        width=1200,
        height=900,
        drawing_type="floor_plan",
        drawing_type_confidence=0.9,
    )
    assert drawing_type_match_adjustment(requirement, report) < 0.0


def test_site_plan_prefers_matching_drawing_type_over_filename() -> None:
    requirement = VisualRequirement(type=VisualType.SITE_PLAN, description="总平面图")
    site_asset = Asset(
        project_id=uuid4(),
        filename="IMG_0234.jpg",
        path="/tmp/img.jpg",
        asset_type=AssetType.IMAGE,
    )
    floor_asset = Asset(
        project_id=uuid4(),
        filename="site_plan.png",
        path="/tmp/site.png",
        asset_type=AssetType.DRAWING,
        tags=["site_plan"],
    )
    site_report = VisualQAReport(
        asset_id=site_asset.id,
        asset_path=site_asset.path,
        width=1200,
        height=900,
        drawing_type="site_plan",
        drawing_type_confidence=0.9,
    )
    floor_report = VisualQAReport(
        asset_id=floor_asset.id,
        asset_path=floor_asset.path,
        width=1200,
        height=900,
        drawing_type="floor_plan",
        drawing_type_confidence=0.9,
    )
    site_score = score_asset_for_requirement(requirement, site_asset, qa_report=site_report)
    floor_score = score_asset_for_requirement(requirement, floor_asset, qa_report=floor_report)
    assert site_score > floor_score
