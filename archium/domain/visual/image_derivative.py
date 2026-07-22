"""Image derivative pipeline domain contract (Sprint 3).

Pipeline:

    OriginalAsset
      → ImageTreatmentSpec (plan: mode, focal point, crops, overlays)
      → ImageDerivative (immutable processed bytes + params_hash)
      → RenderScene asset reference (storage_uri of derivative)

Execution: Pillow via ``ImageDerivativeExecutor`` (SAFE_NORMALIZE /
PRESENTATION_UNIFY / DOCUMENT_SCAN). Auto subject crop / Sharp advanced ops
remain deferred. Do **not** add filters inside PptxGenJS.

Related (not this pipeline):
- ``ImageTreatmentPlanningService`` — layout fit/policy only
- Page-revival OCR/VLM — not photo harmonization
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel


class ImageTreatmentMode(StrEnum):
    """Harmonization intensity — evidence assets must stay at NONE or SAFE_NORMALIZE."""

    NONE = "none"
    SAFE_NORMALIZE = "safe_normalize"
    PRESENTATION_UNIFY = "presentation_unify"
    DOCUMENT_SCAN = "document_scan"


class ImageAssetClass(StrEnum):
    """Evidence policy class — drives which modes are legal."""

    PROJECT_DRAWING = "project_drawing"
    PROJECT_EVIDENCE_PHOTO = "project_evidence_photo"
    REFERENCE_CASE = "reference_case"
    PRESENTATION = "presentation"
    UNKNOWN = "unknown"


class FocalPoint(DomainModel):
    """Normalized focal point in the original image (0–1)."""

    x: float = Field(ge=0.0, le=1.0, default=0.5)
    y: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source: Literal["manual", "heuristic", "model", "unset"] = "unset"


class ImageCropBox(DomainModel):
    """Normalized crop rectangle in original image space (0–1)."""

    x: float = Field(ge=0.0, le=1.0, default=0.0)
    y: float = Field(ge=0.0, le=1.0, default=0.0)
    width: float = Field(gt=0.0, le=1.0, default=1.0)
    height: float = Field(gt=0.0, le=1.0, default=1.0)


class ImageOverlaySpec(DomainModel):
    """Optional non-destructive overlay (legend frame, vignette, etc.)."""

    kind: Literal["none", "soft_vignette", "caption_bar", "legend_frame"] = "none"
    opacity: float = Field(ge=0.0, le=1.0, default=0.0)


class ImageTreatmentSpec(DomainModel):
    """Declarative treatment plan for one original asset (no pixels)."""

    id: UUID = Field(default_factory=uuid4)
    original_asset_id: UUID
    asset_class: ImageAssetClass = ImageAssetClass.UNKNOWN
    mode: ImageTreatmentMode = ImageTreatmentMode.NONE
    focal_point: FocalPoint = Field(default_factory=FocalPoint)
    crop: ImageCropBox | None = None
    auto_subject_crop: bool = False
    overlay: ImageOverlaySpec = Field(default_factory=ImageOverlaySpec)
    target_max_edge_px: int | None = Field(default=None, gt=0)
    rationale: str = ""


class ImageDerivative(DomainModel):
    """Immutable processed derivative of an original asset.

    ``storage_uri`` points at derivative bytes; ``original_asset_id`` is never
    overwritten. ``params_hash`` binds the treatment spec for cache reuse.
    """

    id: UUID = Field(default_factory=uuid4)
    original_asset_id: UUID
    treatment_spec_id: UUID
    storage_uri: str = ""
    params_hash: str = ""
    width_px: int | None = Field(default=None, gt=0)
    height_px: int | None = Field(default=None, gt=0)
    mime_type: str = "image/png"
    executor: Literal["none", "sharp", "pillow", "other"] = "none"


def mode_allowed_for_asset_class(
    asset_class: ImageAssetClass,
    mode: ImageTreatmentMode,
) -> bool:
    """Evidence / drawing assets cannot use expressive unify modes."""
    if mode == ImageTreatmentMode.NONE:
        return True
    if asset_class in {
        ImageAssetClass.PROJECT_DRAWING,
        ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
    }:
        return mode == ImageTreatmentMode.SAFE_NORMALIZE
    return True
