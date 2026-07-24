"""Vision Engine input/output evaluator — reuses photo QA heuristics (v0.3)."""

from __future__ import annotations

from pathlib import Path

from archium.domain.visual.vision_generation import VisionInputEvaluation


class VisionImageEvaluator:
    """Evaluate base photos before conditioned edit; never promotes to evidence."""

    def evaluate_base_image(self, path: str | Path) -> VisionInputEvaluation:
        target = Path(path)
        if not target.is_file():
            return VisionInputEvaluation(
                warnings=[f"base image missing: {target}"],
                blocking=True,
            )

        try:
            from PIL import Image

            from archium.infrastructure.vision.analyzer import (
                check_photo_exposure,
                check_photo_sharpness,
            )
        except ImportError:
            return VisionInputEvaluation(
                warnings=["Pillow unavailable — skipped base photo QA"],
                blocking=False,
            )

        with Image.open(target) as opened:
            image = opened.convert("RGB")

        sharpness = check_photo_sharpness(image)
        exposure = check_photo_exposure(image)
        warnings: list[str] = []
        if not sharpness.passed:
            warnings.append(sharpness.summary)
        if not exposure.passed:
            warnings.append(exposure.summary)

        # Soft gate: warn but do not block conditioned edit — architects often
        # only have WeChat exports. Still refuse empty/tiny images.
        width, height = image.size
        blocking = width < 64 or height < 64
        if blocking:
            warnings.append("base image too small for conditioned edit")

        return VisionInputEvaluation(
            sharpness_passed=sharpness.passed,
            exposure_passed=exposure.passed,
            warnings=warnings,
            blocking=blocking,
            checks=[
                sharpness.model_dump(mode="json"),
                exposure.model_dump(mode="json"),
            ],
        )
