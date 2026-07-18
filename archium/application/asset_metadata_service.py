"""Application service for editable asset metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.asset import Asset
from archium.domain.plan_overlay import (
    PLAN_LEGEND_KEY,
    PLAN_NORTH_ARROW_KEY,
    PLAN_SCALE_LABEL_KEY,
    PLAN_SCALE_PENDING_KEY,
    PlanOverlayMetadata,
    plan_overlay_from_asset,
    plan_overlay_to_metadata,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import AssetRepository

_PLAN_OVERLAY_KEYS = (
    PLAN_NORTH_ARROW_KEY,
    PLAN_SCALE_LABEL_KEY,
    PLAN_SCALE_PENDING_KEY,
    PLAN_LEGEND_KEY,
)


class AssetMetadataService:
    """Update non-file asset metadata such as verified plan overlays."""

    def __init__(self, session: Session) -> None:
        self._assets = AssetRepository(session)

    def list_project_assets(self, project_id: UUID) -> list[Asset]:
        return self._assets.list_by_project(project_id)

    def get_plan_overlay(self, asset_id: UUID) -> PlanOverlayMetadata:
        asset = self._require_asset(asset_id)
        return plan_overlay_from_asset(asset) or PlanOverlayMetadata()

    def save_plan_overlay(self, asset_id: UUID, overlay: PlanOverlayMetadata) -> Asset:
        asset = self._require_asset(asset_id)
        metadata = dict(asset.metadata)
        for key in _PLAN_OVERLAY_KEYS:
            metadata.pop(key, None)
        metadata.update(plan_overlay_to_metadata(overlay))
        updated = asset.model_copy(update={"metadata": metadata})
        return self._assets.update(updated)

    def clear_plan_overlay(self, asset_id: UUID) -> Asset:
        asset = self._require_asset(asset_id)
        metadata = dict(asset.metadata)
        for key in _PLAN_OVERLAY_KEYS:
            metadata.pop(key, None)
        updated = asset.model_copy(update={"metadata": metadata})
        return self._assets.update(updated)

    def _require_asset(self, asset_id: UUID) -> Asset:
        asset = self._assets.get_by_id(asset_id)
        if asset is None:
            raise WorkflowError(f"素材 {asset_id} 不存在。")
        return asset
