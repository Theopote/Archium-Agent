"""Image derivative execution — **NOT IMPLEMENTED**.

Sharp / Node (or Pillow) must only execute an ``ImageTreatmentSpec``. Do not add
ad-hoc color filters inside PptxGenJS. Page-revival OCR/VLM is a separate
capability and must not be wired here as a substitute.
"""

from __future__ import annotations

from archium.domain.visual.image_derivative import ImageDerivative, ImageTreatmentSpec


class ImageDerivativeNotImplementedError(NotImplementedError):
    """Raised until Sprint 3 executor (Sharp/Node) is wired."""


class ImageDerivativeExecutor:
    """Execute ``ImageTreatmentSpec`` → ``ImageDerivative``.

    Status: NOT IMPLEMENTED. Callers must treat missing derivatives as
    pass-through to the original asset URI.
    """

    def execute(self, spec: ImageTreatmentSpec) -> ImageDerivative:
        raise ImageDerivativeNotImplementedError(
            "ImageDerivative pipeline is NOT IMPLEMENTED. "
            "Establish OriginalAsset → ImageTreatmentSpec → ImageDerivative → "
            "RenderScene reference before adding Sharp; do not add PptxGen filters. "
            f"(spec_id={spec.id}, original_asset_id={spec.original_asset_id}, "
            f"mode={spec.mode.value})"
        )

    def is_available(self) -> bool:
        return False
