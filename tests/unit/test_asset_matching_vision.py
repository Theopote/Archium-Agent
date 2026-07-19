"""Asset matching uses vision caption metadata."""

from __future__ import annotations

from uuid import uuid4

from archium.application.asset_matching_service import score_asset_for_requirement
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import VisualRequirement


def test_score_asset_uses_vision_caption_summary() -> None:
    requirement = VisualRequirement(
        type=VisualType.SITE_PLAN,
        description="总平面图主入口",
        required=True,
    )
    plain = Asset(
        project_id=uuid4(),
        filename="img.png",
        path="/tmp/img.png",
        asset_type=AssetType.IMAGE,
        description="Embedded image from page 1",
    )
    enriched = Asset(
        project_id=plain.project_id,
        filename="site.png",
        path="/tmp/site.png",
        asset_type=AssetType.IMAGE,
        description="site.png 建筑图档",
        metadata={
            "drawing_type": "site_plan",
            "vision_caption": {
                "drawing_type": "site_plan",
                "summary": "总平面图展示主入口广场与门诊楼布局",
                "spatial_elements": ["主入口", "门诊楼"],
                "metrics_visible": [],
            },
        },
        tags=["site_plan", "drawing"],
    )

    plain_score = score_asset_for_requirement(requirement, plain)
    enriched_score = score_asset_for_requirement(requirement, enriched)
    assert enriched_score > plain_score
