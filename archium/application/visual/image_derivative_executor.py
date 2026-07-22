"""Execute ``ImageTreatmentSpec`` → ``ImageDerivative`` (Pillow; not PptxGen filters).

Original assets are never overwritten. Derivatives land under
``data/projects/<id>/cache/derivatives/``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from archium.application.visual.asset_path_resolver import storage_asset_uri
from archium.domain.visual.image_derivative import ImageDerivative, ImageTreatmentSpec
from archium.infrastructure.storage.local_storage import LocalProjectStorage, compute_file_hash
from archium.logging import get_logger

logger = get_logger(__name__, operation="image_derivative")


class ImageDerivativeNotImplementedError(NotImplementedError):
    """Reserved for modes that still require Sharp/Node (e.g. advanced subject crop)."""


class ImageDerivativeExecutor:
    """Pillow executor for SAFE_NORMALIZE / PRESENTATION_UNIFY / DOCUMENT_SCAN.

    ``auto_subject_crop`` and non-none overlays are not implemented yet — those
    modes fall back to normalize-only or raise when strictly required later.
    """

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
            "focal": spec.focal_point.model_dump(mode="json"),
            "crop": spec.crop.model_dump(mode="json") if spec.crop else None,
            "auto_subject_crop": spec.auto_subject_crop,
            "overlay": spec.overlay.model_dump(mode="json"),
            "target_max_edge_px": spec.target_max_edge_px,
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
        if spec.mode.value == "none":
            return None
        if not self.is_available():
            logger.info("Pillow unavailable — skipping image derivative")
            return None
        if not original_path.is_file():
            logger.info("Original asset missing for derivative: %s", original_path)
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
) -> tuple[object, int, int] | None:
    from PIL import Image, ImageEnhance, ImageOps

    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened)
            image = image.convert("RGB")
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
        image = ImageEnhance.Color(image).enhance(0.92)
        image = ImageEnhance.Contrast(image).enhance(1.06)
        image = ImageEnhance.Brightness(image).enhance(1.02)

    if spec.crop is not None:
        image = _apply_norm_crop(image, spec.crop)
    elif spec.auto_subject_crop:
        # Subject crop requires a dedicated detector — not implemented; skip.
        pass

    if spec.target_max_edge_px:
        image.thumbnail(
            (spec.target_max_edge_px, spec.target_max_edge_px),
            Image.Resampling.LANCZOS,
        )

    width, height = image.size
    return image, width, height


def _apply_norm_crop(image: object, crop: object) -> object:
    from PIL import Image

    assert isinstance(image, Image.Image)
    w, h = image.size
    left = int(max(0.0, min(1.0, float(crop.x))) * w)
    top = int(max(0.0, min(1.0, float(crop.y))) * h)
    right = int(max(0.0, min(1.0, float(crop.x) + float(crop.width))) * w)
    bottom = int(max(0.0, min(1.0, float(crop.y) + float(crop.height))) * h)
    if right <= left or bottom <= top:
        return image
    return image.crop((left, top, right, bottom))
