"""Asset matching uses vision caption metadata."""

from __future__ import annotations

from uuid import uuid4

from archium.application.asset_matching_service import score_asset_for_requirement
from archium.domain.asset import Asset
from archium.domain.asset_presentation_readiness import (
    ASSET_PRESENTATION_READINESS_KEY,
    AssetPresentationReadiness,
    AssetPresentationRole,
)
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import VisualRequirement


def _with_pixel_readiness(asset: Asset, *, role: AssetPresentationRole = AssetPresentationRole.HERO_DRAWING) -> Asset:
    readiness = AssetPresentationReadiness(
        pixel_analyzed=True,
        presentation_ready=True,
        visual_information_density=0.8,
        readable_at_slide_scale=True,
        recommended_role=role,
    )
    metadata = dict(asset.metadata or {})
    metadata[ASSET_PRESENTATION_READINESS_KEY] = readiness.to_metadata()
    return asset.model_copy(
        update={
            "metadata": metadata,
            "width": asset.width or 2000,
            "height": asset.height or 1500,
        }
    )


def test_score_asset_uses_vision_caption_summary() -> None:
    requirement = VisualRequirement(
        type=VisualType.SITE_PLAN,
        description="总平面图主入口",
        required=True,
    )
    plain = _with_pixel_readiness(
        Asset(
            project_id=uuid4(),
            filename="img.png",
            path="/tmp/img.png",
            asset_type=AssetType.IMAGE,
            description="Embedded image from page 1",
        ),
        role=AssetPresentationRole.EVIDENCE_SUPPORTING,
    )
    enriched = _with_pixel_readiness(
        Asset(
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
    )

    plain_score = score_asset_for_requirement(requirement, plain)
    enriched_score = score_asset_for_requirement(requirement, enriched)
    assert enriched_score > plain_score
