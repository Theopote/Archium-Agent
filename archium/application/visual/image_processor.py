"""ImageProcessor facade — detect / unify knobs for the derivative pipeline.

Not an Agent. Pixel work stays in ``ImageDerivativeExecutor``.
"""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.image_focus_detector import (
    FocusDetectionResult,
    FocusHint,
    ImageFocusDetector,
    MIN_CROP_CONFIDENCE,
)
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    ImageCropStrategy,
    ImageEnhanceParams,
    ImageTreatmentSpec,
    ImageUnifyParams,
    default_historical_unify_params,
    default_presentation_unify_params,
)


class ImageProcessor:
    """Facade: focus analysis + deck unify/enhance defaults. Not an Agent."""

    def __init__(self, detector: ImageFocusDetector | None = None) -> None:
        self._detector = detector or ImageFocusDetector()

    def analyze_focus(
        self,
        path: Path,
        *,
        hint: FocusHint = "auto",
        strategy: ImageCropStrategy = ImageCropStrategy.SUBJECT_HEURISTIC,
    ) -> FocusDetectionResult | None:
        return self._detector.detect(path, hint=hint, strategy=strategy)

    def build_unify_params(self, treatment: PhotoTreatment) -> ImageUnifyParams:
        if treatment == PhotoTreatment.HISTORICAL:
            return default_historical_unify_params()
        if treatment == PhotoTreatment.SUBTLE_UNIFY:
            return default_presentation_unify_params()
        return ImageUnifyParams()

    def build_enhance_params(self, treatment: PhotoTreatment) -> ImageEnhanceParams:
        if treatment == PhotoTreatment.HISTORICAL:
            return ImageEnhanceParams(
                sharpen=True,
                denoise=True,
                historical_restore=True,
            )
        if treatment == PhotoTreatment.SUBTLE_UNIFY:
            return ImageEnhanceParams(sharpen=True, denoise=False, historical_restore=False)
        if treatment == PhotoTreatment.DOCUMENT_SCAN:
            return ImageEnhanceParams(sharpen=True, denoise=True, historical_restore=False)
        return ImageEnhanceParams()

    def enrich_spec_with_focus(
        self,
        spec: ImageTreatmentSpec,
        path: Path,
        *,
        hint: FocusHint = "auto",
    ) -> ImageTreatmentSpec:
        """Fill heuristic focal/crop when strategy asks and no manual focus."""
        if spec.focal_point.source == "manual" and spec.focal_point.confidence >= 0.5:
            return spec
        strategy = spec.crop_strategy
        if strategy in {ImageCropStrategy.NONE, ImageCropStrategy.FOCAL}:
            if not spec.auto_subject_crop:
                return spec
            strategy = ImageCropStrategy.SUBJECT_HEURISTIC

        result = self.analyze_focus(path, hint=hint, strategy=strategy)
        if result is None:
            return spec
        focal = result.focal_point
        if focal.confidence < MIN_CROP_CONFIDENCE:
            return spec.model_copy(
                update={
                    "focal_point": focal,
                    "auto_subject_crop": False,
                    "crop": None,
                }
            )
        return spec.model_copy(
            update={
                "focal_point": focal,
                "auto_subject_crop": True,
                "crop": result.crop,
                "crop_strategy": result.strategy_used,
            }
        )

    def focus_hint_from_tags(self, tags: list[str] | None) -> FocusHint:
        lowered = {t.lower() for t in (tags or [])}
        if "skyline" in lowered or "天际线" in lowered or "sky" in lowered:
            return "skyline"
        if "people" in lowered or "人物" in lowered or "portrait" in lowered:
            return "people"
        if "building" in lowered or "建筑" in lowered or "site_photo" in lowered:
            return "subject"
        return "auto"
