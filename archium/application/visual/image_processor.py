"""ImageProcessor facade — detect / unify knobs for the derivative pipeline.

Not an Agent. Pixel work stays in ``ImageDerivativeExecutor``.
"""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.image_focus_detector import (
    MIN_CROP_CONFIDENCE,
    FocusDetectionResult,
    FocusHint,
    ImageFocusDetector,
)
from archium.application.visual.image_source_classifier import (
    ImageSourceClassification,
    ImageSourceClassifier,
)
from archium.domain.asset import Asset
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    ImageCropStrategy,
    ImageEnhanceParams,
    ImageSourceKind,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    ImageUnifyParams,
    default_historical_unify_params,
    default_presentation_unify_params,
)


class ImageProcessor:
    """Facade: focus analysis + deck unify/enhance defaults. Not an Agent."""

    def __init__(
        self,
        detector: ImageFocusDetector | None = None,
        source_classifier: ImageSourceClassifier | None = None,
    ) -> None:
        self._detector = detector or ImageFocusDetector()
        self._sources = source_classifier or ImageSourceClassifier()

    def classify_source(
        self,
        *,
        path: Path | None = None,
        asset: Asset | None = None,
        filename: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> ImageSourceClassification:
        return self._sources.classify(
            path=path,
            asset=asset,
            filename=filename,
            tags=tags,
            description=description,
        )

    def analyze_focus(
        self,
        path: Path,
        *,
        hint: FocusHint = "auto",
        strategy: ImageCropStrategy = ImageCropStrategy.SUBJECT_HEURISTIC,
    ) -> FocusDetectionResult | None:
        return self._detector.detect(path, hint=hint, strategy=strategy)

    def build_unify_params(
        self,
        treatment: PhotoTreatment,
        *,
        source_kind: ImageSourceKind | None = None,
        deck_unify: ImageUnifyParams | None = None,
    ) -> ImageUnifyParams:
        if deck_unify is not None and treatment == PhotoTreatment.SUBTLE_UNIFY:
            return deck_unify
        if treatment == PhotoTreatment.HISTORICAL or source_kind == ImageSourceKind.HISTORICAL:
            return default_historical_unify_params()
        if treatment == PhotoTreatment.SUBTLE_UNIFY:
            return default_presentation_unify_params()
        if source_kind == ImageSourceKind.WECHAT_EXPORT:
            # WeChat exports are often warm + oversaturated.
            return ImageUnifyParams(
                temperature=-0.06,
                saturation=0.88,
                contrast=1.05,
                brightness=1.03,
            )
        if source_kind == ImageSourceKind.PHONE_PHOTO:
            return default_presentation_unify_params()
        return ImageUnifyParams()

    def build_enhance_params(
        self,
        treatment: PhotoTreatment,
        *,
        source_kind: ImageSourceKind | None = None,
    ) -> ImageEnhanceParams:
        if treatment == PhotoTreatment.HISTORICAL or source_kind == ImageSourceKind.HISTORICAL:
            return ImageEnhanceParams(
                sharpen=True,
                denoise=True,
                historical_restore=True,
            )
        if treatment == PhotoTreatment.DOCUMENT_SCAN or source_kind == ImageSourceKind.DOCUMENT_SCAN:
            return ImageEnhanceParams(sharpen=True, denoise=True, historical_restore=False)
        if source_kind == ImageSourceKind.WECHAT_EXPORT:
            return ImageEnhanceParams(sharpen=True, denoise=True, historical_restore=False)
        if treatment == PhotoTreatment.SUBTLE_UNIFY:
            return ImageEnhanceParams(sharpen=True, denoise=False, historical_restore=False)
        return ImageEnhanceParams()

    def preferred_mode_for_source(
        self,
        source_kind: ImageSourceKind,
        *,
        design_mode: ImageTreatmentMode,
    ) -> ImageTreatmentMode:
        """Override design mode when source strongly suggests scan/historical."""
        if source_kind == ImageSourceKind.DOCUMENT_SCAN:
            return ImageTreatmentMode.DOCUMENT_SCAN
        if source_kind == ImageSourceKind.HISTORICAL and design_mode in {
            ImageTreatmentMode.PRESENTATION_UNIFY,
            ImageTreatmentMode.NONE,
            ImageTreatmentMode.SAFE_NORMALIZE,
        }:
            # Historical still uses presentation_unify path with historical knobs
            # when expressive modes are allowed; clamp happens in planner.
            if design_mode == ImageTreatmentMode.NONE:
                return ImageTreatmentMode.PRESENTATION_UNIFY
            return design_mode
        return design_mode

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
        if "people" in lowered or "人物" in lowered or "portrait" in lowered or "人流" in lowered:
            return "people"
        if "road" in lowered or "道路" in lowered or "traffic" in lowered or "车流" in lowered:
            return "subject"
        if "building" in lowered or "建筑" in lowered or "site_photo" in lowered:
            return "subject"
        return "auto"

    def focus_hint_from_semantic_role(self, semantic_role: str | None) -> FocusHint | None:
        """Map layout / grammar element ids or roles onto crop hints."""
        role = (semantic_role or "").strip().casefold()
        if not role:
            return None
        if any(token in role for token in ("skyline", "天际", "horizon")):
            return "skyline"
        if any(token in role for token in ("people", "crowd", "人流", "portrait")):
            return "people"
        if any(
            token in role
            for token in (
                "historic",
                "hero",
                "building",
                "site",
                "map",
                "photo",
                "evidence",
                "before",
                "after",
            )
        ):
            return "subject"
        return None
