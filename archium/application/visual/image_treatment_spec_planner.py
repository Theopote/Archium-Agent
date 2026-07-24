"""Plan ``ImageTreatmentSpec`` from asset class + DesignSystem (policy only)."""

from __future__ import annotations

from uuid import UUID

from archium.application.visual.image_focus_detector import FocusHint
from archium.application.visual.image_processor import ImageProcessor
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    FocalPoint,
    ImageAssetClass,
    ImageCropStrategy,
    ImageEnhanceParams,
    ImageOverlaySpec,
    ImageSourceKind,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    ImageUnifyParams,
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
    """Build per-asset treatment specs. Policy only — no pixel I/O.

    Heuristic focus enrichment happens later in ``ImageDerivativeService`` via
    ``ImageProcessor.enrich_spec_with_focus``.
    """

    def __init__(self, processor: ImageProcessor | None = None) -> None:
        self._processor = processor or ImageProcessor()

    def plan_for_node(
        self,
        node: ImageNode | DrawingNode,
        *,
        design_system: DesignSystem | None = None,
        asset: Asset | None = None,
        original_asset_id: UUID | None = None,
        source_kind: ImageSourceKind | None = None,
        deck_unify: ImageUnifyParams | None = None,
        focus_hint: FocusHint | None = None,
    ) -> ImageTreatmentSpec | None:
        asset_id = original_asset_id or node.asset_id
        if asset_id is None:
            return None

        asset_class = asset_class_for_node(node, asset=asset)
        resolved_source = source_kind or ImageSourceKind.UNKNOWN
        treatment = PhotoTreatment.NONE
        requested = ImageTreatmentMode.NONE
        if design_system is not None:
            treatment = design_system.image_style.photo_treatment
            requested = photo_treatment_to_mode(treatment)
            if treatment == PhotoTreatment.HISTORICAL:
                resolved_source = (
                    ImageSourceKind.HISTORICAL
                    if resolved_source == ImageSourceKind.UNKNOWN
                    else resolved_source
                )

        requested = self._processor.preferred_mode_for_source(
            resolved_source,
            design_mode=requested,
        )
        if resolved_source == ImageSourceKind.HISTORICAL:
            treatment = PhotoTreatment.HISTORICAL
        elif resolved_source == ImageSourceKind.DOCUMENT_SCAN:
            treatment = PhotoTreatment.DOCUMENT_SCAN

        if isinstance(node, DrawingNode):
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
            rationale = (
                f"design photo_treatment → {mode.value} "
                f"({asset_class.value}; source={resolved_source.value})"
            )

        focal = FocalPoint()
        if isinstance(node, ImageNode) and node.focus_point is not None:
            focal = _focal_from_point(node.focus_point)

        overlay = ImageOverlaySpec()
        unify = ImageUnifyParams()
        enhance = ImageEnhanceParams()
        crop_strategy = ImageCropStrategy.NONE
        auto_subject_crop = False

        if mode == ImageTreatmentMode.PRESENTATION_UNIFY and asset_class not in {
            ImageAssetClass.PROJECT_DRAWING,
            ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
        }:
            overlay = ImageOverlaySpec(kind="soft_vignette", opacity=0.22)
            unify = self._processor.build_unify_params(
                treatment,
                source_kind=resolved_source,
                deck_unify=deck_unify,
            )
            enhance = self._processor.build_enhance_params(
                treatment,
                source_kind=resolved_source,
            )
            if focal.source == "manual" and focal.confidence >= 0.5:
                crop_strategy = ImageCropStrategy.FOCAL
                auto_subject_crop = True
            else:
                tags = list(asset.tags) if asset is not None else []
                hint = focus_hint or self._processor.focus_hint_from_tags(tags)
                role_hint = self._processor.focus_hint_from_semantic_role(
                    getattr(node, "semantic_role", "") or getattr(node, "id", "")
                )
                if role_hint is not None:
                    hint = role_hint
                if hint == "skyline":
                    crop_strategy = ImageCropStrategy.SKYLINE_HEURISTIC
                else:
                    crop_strategy = ImageCropStrategy.SUBJECT_HEURISTIC
                auto_subject_crop = True
                rationale = f"{rationale}; crop={crop_strategy.value}; hint={hint}"
            if deck_unify is not None:
                rationale = f"{rationale}; deck_style_match"
        elif mode == ImageTreatmentMode.DOCUMENT_SCAN:
            enhance = self._processor.build_enhance_params(
                PhotoTreatment.DOCUMENT_SCAN,
                source_kind=resolved_source,
            )
        elif mode == ImageTreatmentMode.SAFE_NORMALIZE:
            # Evidence / clamped path: mild sharpen; source may add denoise.
            enhance = self._processor.build_enhance_params(
                PhotoTreatment.NONE,
                source_kind=resolved_source,
            )
            if not enhance.sharpen and not enhance.denoise:
                enhance = ImageEnhanceParams(sharpen=True)
            # WeChat/phone evidence: denoise helps compression artifacts without recolor.
            if resolved_source in {
                ImageSourceKind.WECHAT_EXPORT,
                ImageSourceKind.PHONE_PHOTO,
                ImageSourceKind.DOCUMENT_SCAN,
            }:
                enhance = ImageEnhanceParams(sharpen=True, denoise=True)

        return ImageTreatmentSpec(
            original_asset_id=asset_id,
            asset_class=asset_class,
            source_kind=resolved_source,
            mode=mode,
            focal_point=focal,
            auto_subject_crop=auto_subject_crop,
            crop_strategy=crop_strategy,
            unify=unify,
            enhance=enhance,
            overlay=overlay,
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
