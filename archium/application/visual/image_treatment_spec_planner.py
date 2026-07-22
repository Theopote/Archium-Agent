"""Plan ``ImageTreatmentSpec`` from asset class + DesignSystem (no pixels)."""

from __future__ import annotations

from uuid import UUID

from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    FocalPoint,
    ImageAssetClass,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    mode_allowed_for_asset_class,
)
from archium.domain.visual.render_scene import DrawingNode, ImageNode, Point


def asset_class_for_node(
    node: ImageNode | DrawingNode,
    *,
    asset: Asset | None = None,
) -> ImageAssetClass:
    if isinstance(node, DrawingNode):
        return ImageAssetClass.PROJECT_DRAWING
    if asset is not None and asset.asset_type in {AssetType.DRAWING, AssetType.DIAGRAM}:
        return ImageAssetClass.PROJECT_DRAWING
    origin = getattr(node, "asset_origin", "project_upload")
    if origin == "reference_case":
        return ImageAssetClass.REFERENCE_CASE
    tags = {tag.lower() for tag in (asset.tags if asset is not None else [])}
    if "evidence" in tags or "site_photo" in tags or "现场" in tags:
        return ImageAssetClass.PROJECT_EVIDENCE_PHOTO
    if asset is not None and asset.asset_type == AssetType.PHOTO:
        return ImageAssetClass.PRESENTATION
    if origin in {"public_research", "stock_image", "ai_generated"}:
        return ImageAssetClass.PRESENTATION
    return ImageAssetClass.PRESENTATION


def photo_treatment_to_mode(treatment: PhotoTreatment) -> ImageTreatmentMode:
    mapping = {
        PhotoTreatment.NONE: ImageTreatmentMode.NONE,
        PhotoTreatment.SUBTLE_UNIFY: ImageTreatmentMode.PRESENTATION_UNIFY,
        PhotoTreatment.DOCUMENT_SCAN: ImageTreatmentMode.DOCUMENT_SCAN,
        PhotoTreatment.HISTORICAL: ImageTreatmentMode.PRESENTATION_UNIFY,
    }
    return mapping.get(treatment, ImageTreatmentMode.NONE)


class ImageTreatmentSpecPlanner:
    """Build per-asset treatment specs. Policy only — no pixel I/O."""

    def plan_for_node(
        self,
        node: ImageNode | DrawingNode,
        *,
        design_system: DesignSystem | None = None,
        asset: Asset | None = None,
        original_asset_id: UUID | None = None,
    ) -> ImageTreatmentSpec | None:
        asset_id = original_asset_id or node.asset_id
        if asset_id is None:
            return None

        asset_class = asset_class_for_node(node, asset=asset)
        requested = ImageTreatmentMode.NONE
        if design_system is not None:
            requested = photo_treatment_to_mode(design_system.image_style.photo_treatment)

        if isinstance(node, DrawingNode):
            # Drawings: never expressive unify; optional safe normalize later.
            mode = ImageTreatmentMode.NONE
            rationale = "drawing node: pixel treatment disabled (preserve technical truth)"
        elif not mode_allowed_for_asset_class(asset_class, requested):
            mode = (
                ImageTreatmentMode.SAFE_NORMALIZE
                if mode_allowed_for_asset_class(
                    asset_class, ImageTreatmentMode.SAFE_NORMALIZE
                )
                else ImageTreatmentMode.NONE
            )
            rationale = (
                f"clamped {requested.value} → {mode.value} for asset_class={asset_class.value}"
            )
        else:
            mode = requested
            rationale = f"design photo_treatment → {mode.value} ({asset_class.value})"

        focal = FocalPoint()
        if isinstance(node, ImageNode) and node.focus_point is not None:
            focal = _focal_from_point(node.focus_point)

        return ImageTreatmentSpec(
            original_asset_id=asset_id,
            asset_class=asset_class,
            mode=mode,
            focal_point=focal,
            target_max_edge_px=2400 if mode != ImageTreatmentMode.NONE else None,
            rationale=rationale,
        )


def _focal_from_point(point: Point) -> FocalPoint:
    return FocalPoint(
        x=max(0.0, min(1.0, float(point.x))),
        y=max(0.0, min(1.0, float(point.y))),
        confidence=1.0,
        source="manual",
    )
