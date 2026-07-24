"""Execute ``ImageTreatmentSpec`` → ``ImageDerivative`` (Pillow; not PptxGen filters).

Original assets are never overwritten. Derivatives land under
``data/projects/<id>/cache/derivatives/``.

Pipeline steps (in order):
1. EXIF orientation + convert toward sRGB/RGB
2. Mode normalize / tunable unify (temperature, sat, contrast, brightness)
3. Mild enhance (sharpen / denoise / historical_restore)
4. Explicit crop or focal-centered crop (when requested)
5. Soft overlay (vignette) when allowed for asset class
6. Max-edge downscale
"""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import UUID

if TYPE_CHECKING:
    from PIL import Image as PILImage

from archium.application.visual.asset_path_resolver import storage_asset_uri
from archium.domain.visual.image_derivative import (
    FocalPoint,
    ImageAssetClass,
    ImageCropBox,
    ImageDerivative,
    ImageEnhanceParams,
    ImageTreatmentSpec,
    ImageUnifyParams,
    mode_allowed_for_asset_class,
)
from archium.infrastructure.storage.local_storage import LocalProjectStorage, compute_file_hash
from archium.logging import get_logger

logger = get_logger(__name__, operation="image_derivative")

PIPELINE_VERSION = "exif_srgb_v4_source_style"


class ImageDerivativeNotImplementedError(NotImplementedError):
    """Reserved for Sharp/Node advanced subject detection."""


class ImageDerivativeExecutor:
    """Pillow executor for SAFE_NORMALIZE / PRESENTATION_UNIFY / DOCUMENT_SCAN."""

    def __init__(self, storage: LocalProjectStorage | None = None) -> None:
        self._storage = storage or LocalProjectStorage()

    def is_available(self) -> bool:
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            return False
        return True

    def compute_params_hash(
        self,
        spec: ImageTreatmentSpec,
        *,
        original_file_hash: str,
    ) -> str:
        payload = {
            "mode": spec.mode.value,
            "asset_class": spec.asset_class.value,
            "source_kind": spec.source_kind.value,
            "focal": spec.focal_point.model_dump(mode="json"),
            "crop": spec.crop.model_dump(mode="json") if spec.crop else None,
            "auto_subject_crop": spec.auto_subject_crop,
            "crop_strategy": spec.crop_strategy.value,
            "unify": spec.unify.model_dump(mode="json"),
            "enhance": spec.enhance.model_dump(mode="json"),
            "overlay": spec.overlay.model_dump(mode="json"),
            "target_max_edge_px": spec.target_max_edge_px,
            "pipeline": PIPELINE_VERSION,
            "original_file_hash": original_file_hash,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def execute(
        self,
        spec: ImageTreatmentSpec,
        *,
        project_id: UUID,
        original_path: Path,
    ) -> ImageDerivative | None:
        """Return a derivative, or None when mode is NONE / pass-through."""
        if spec.mode.value == "none" and not _has_geometry_ops(spec) and not _has_enhance_ops(spec):
            return None
        if not self.is_available():
            logger.info("Pillow unavailable — skipping image derivative")
            return None
        if not original_path.is_file():
            logger.info("Original asset missing for derivative: %s", original_path)
            return None
        # Evidence/drawing: refuse expressive overlays even if spec asks.
        if not mode_allowed_for_asset_class(spec.asset_class, spec.mode):
            logger.info(
                "Refusing mode %s for asset_class %s",
                spec.mode.value,
                spec.asset_class.value,
            )
            return None

        file_hash = compute_file_hash(original_path)
        params_hash = self.compute_params_hash(spec, original_file_hash=file_hash)
        layout = self._storage.ensure_project_layout(project_id)
        out_dir = layout["cache"] / "derivatives" / str(spec.original_asset_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{params_hash}.jpg"
        rel = out_path.relative_to(layout["root"]).as_posix()
        uri = storage_asset_uri(project_id, rel)

        if out_path.is_file():
            width, height = _image_size(out_path)
            return ImageDerivative(
                original_asset_id=spec.original_asset_id,
                treatment_spec_id=spec.id,
                storage_uri=uri,
                params_hash=params_hash,
                width_px=width,
                height_px=height,
                mime_type="image/jpeg",
                executor="pillow",
            )

        processed = _process_image(original_path, spec)
        if processed is None:
            return None
        image, width, height = processed
        image.save(out_path, format="JPEG", quality=88, optimize=True)
        return ImageDerivative(
            original_asset_id=spec.original_asset_id,
            treatment_spec_id=spec.id,
            storage_uri=uri,
            params_hash=params_hash,
            width_px=width,
            height_px=height,
            mime_type="image/jpeg",
            executor="pillow",
        )


def _has_geometry_ops(spec: ImageTreatmentSpec) -> bool:
    return bool(
        spec.crop is not None
        or spec.auto_subject_crop
        or (spec.overlay.kind != "none" and spec.overlay.opacity > 0)
    )


def _has_enhance_ops(spec: ImageTreatmentSpec) -> bool:
    e = spec.enhance
    return bool(e.sharpen or e.denoise or e.historical_restore)


def _image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except OSError:
        return None, None


def _process_image(
    path: Path,
    spec: ImageTreatmentSpec,
) -> tuple[PILImage.Image, int, int] | None:
    from PIL import Image, ImageOps

    try:
        with Image.open(path) as opened:
            image = _load_oriented_srgb(opened)
    except OSError as exc:
        logger.info("Failed to open image for derivative: %s (%s)", path, exc)
        return None

    mode = spec.mode.value
    if mode in {"safe_normalize", "presentation_unify", "document_scan"}:
        image = ImageOps.autocontrast(image, cutoff=1.0)

    if mode == "document_scan":
        image = ImageOps.grayscale(image).convert("RGB")
        image = ImageOps.autocontrast(image, cutoff=2.0)
    elif mode == "presentation_unify":
        image = _apply_unify(image, spec.unify)

    image = _apply_enhance(image, spec.enhance, mode=mode)

    if spec.crop is not None:
        image = _apply_norm_crop(image, spec.crop)
    elif spec.auto_subject_crop or (
        spec.focal_point.source in {"manual", "heuristic", "model"}
        and spec.focal_point.confidence >= 0.5
        and mode == "presentation_unify"
    ):
        image = _focal_center_crop(image, spec.focal_point, keep_ratio=0.85)

    # Overlays only on non-evidence presentation photos.
    if (
        spec.overlay.kind == "soft_vignette"
        and spec.overlay.opacity > 0
        and spec.asset_class
        not in {ImageAssetClass.PROJECT_DRAWING, ImageAssetClass.PROJECT_EVIDENCE_PHOTO}
    ):
        image = _apply_soft_vignette(image, opacity=spec.overlay.opacity)

    if spec.target_max_edge_px:
        image.thumbnail(
            (spec.target_max_edge_px, spec.target_max_edge_px),
            Image.Resampling.LANCZOS,
        )

    width, height = image.size
    return image, width, height


def _apply_unify(image: PILImage.Image, unify: ImageUnifyParams) -> PILImage.Image:
    from PIL import ImageEnhance

    image = _apply_temperature(image, unify.temperature)
    image = ImageEnhance.Color(image).enhance(unify.saturation)
    image = ImageEnhance.Contrast(image).enhance(unify.contrast)
    image = ImageEnhance.Brightness(image).enhance(unify.brightness)
    return image


def _apply_temperature(image: PILImage.Image, temperature: float) -> PILImage.Image:
    """Linear RGB gain: warm = +R/−B, cool = −R/+B."""
    from PIL import Image

    t = max(-0.35, min(0.35, float(temperature)))
    if abs(t) < 1e-6:
        return image
    r_gain = 1.0 + t
    b_gain = 1.0 - t
    # split → scale → merge keeps Pillow-only path
    r, g, b = image.split()
    r = r.point(lambda p: max(0, min(255, int(p * r_gain))))
    b = b.point(lambda p: max(0, min(255, int(p * b_gain))))
    return Image.merge("RGB", (r, g, b))


def _apply_enhance(
    image: PILImage.Image,
    enhance: ImageEnhanceParams,
    *,
    mode: str,
) -> PILImage.Image:
    from PIL import ImageEnhance, ImageFilter

    if enhance.historical_restore:
        # Mild "album" restore — not generative inpainting.
        image = image.filter(ImageFilter.MedianFilter(size=3))
        image = ImageEnhance.Color(image).enhance(0.9)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = image.filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3)
        )
        return image

    if enhance.denoise:
        image = image.filter(ImageFilter.MedianFilter(size=3))
    if enhance.sharpen:
        # Safer on SAFE_NORMALIZE evidence: gentler unsharp.
        percent = 90 if mode == "safe_normalize" else 120
        image = image.filter(
            ImageFilter.UnsharpMask(radius=1.4, percent=percent, threshold=2)
        )
    return image


def _load_oriented_srgb(opened: PILImage.Image) -> PILImage.Image:
    """EXIF-orient and convert to RGB (sRGB working space for JPEG pipeline)."""
    from PIL import Image, ImageCms, ImageOps

    image = ImageOps.exif_transpose(opened)
    # Prefer ICC → sRGB when profile present; fall back to plain RGB.
    try:
        icc = image.info.get("icc_profile")
        if icc and image.mode in {"RGB", "RGBA", "L", "CMYK"}:
            src = ImageCms.ImageCmsProfile(BytesIO(bytes(icc)))
            dst = ImageCms.createProfile("sRGB")
            image = cast(PILImage.Image, ImageCms.profileToProfile(image, src, dst, outputMode="RGB"))
            return image
    except Exception:  # noqa: BLE001 — ICC optional
        pass
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def _apply_norm_crop(image: PILImage.Image, crop: ImageCropBox) -> PILImage.Image:
    w, h = image.size
    left = int(max(0.0, min(1.0, float(crop.x))) * w)
    top = int(max(0.0, min(1.0, float(crop.y))) * h)
    right = int(max(0.0, min(1.0, float(crop.x) + float(crop.width))) * w)
    bottom = int(max(0.0, min(1.0, float(crop.y) + float(crop.height))) * h)
    if right <= left or bottom <= top:
        return image
    return image.crop((left, top, right, bottom))


def _focal_center_crop(
    image: PILImage.Image,
    focal: FocalPoint,
    *,
    keep_ratio: float = 0.85,
) -> PILImage.Image:
    """Crop around focal point, keeping ``keep_ratio`` of the shorter side."""
    keep_ratio = max(0.5, min(1.0, keep_ratio))
    w, h = image.size
    crop_w = int(w * keep_ratio)
    crop_h = int(h * keep_ratio)
    cx = int(focal.x * w)
    cy = int(focal.y * h)
    left = max(0, min(w - crop_w, cx - crop_w // 2))
    top = max(0, min(h - crop_h, cy - crop_h // 2))
    return image.crop((left, top, left + crop_w, top + crop_h))


def _apply_soft_vignette(image: PILImage.Image, *, opacity: float) -> PILImage.Image:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    opacity = max(0.0, min(1.0, opacity))
    if opacity <= 1e-6:
        return image
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    inset = int(min(w, h) * 0.08)
    draw.ellipse((inset, inset, w - inset, h - inset), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(8, min(w, h) // 12)))
    darkened = ImageEnhance.Brightness(image).enhance(1.0 - 0.35 * opacity)
    return Image.composite(image, darkened, mask)
