"""Conditioned photo/drawing edit — illustrative variants (Vision Engine v0.3).

Offline Pillow path when API image-edit is unavailable. Never claims to be
site evidence; output is always illustrative concept / mood transfer.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from archium.domain.visual.vision_generation import VisionGenerationMode, VisionStylePreset

if TYPE_CHECKING:
    from PIL.Image import Image as PilImage


@dataclass(frozen=True)
class ConditionedEditRequest:
    base_image_path: str
    width: int
    height: int
    subject: str
    mode: VisionGenerationMode = VisionGenerationMode.EDIT_FROM_PHOTO
    style: str = VisionStylePreset.COMPETITION_CONCEPT_SKETCH.value
    prompt_hash: str = ""
    overlay_cues: tuple[str, ...] = ()


class VisionConditionedEditor:
    """Deterministic base→illustrative edit for offline / stub backends."""

    provider = "conditioned_editor"
    model = "pillow_edit_v03"

    def is_available(self) -> bool:
        try:
            from PIL import Image  # noqa: F401

            return True
        except ImportError:
            return False

    def edit(self, request: ConditionedEditRequest) -> bytes:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

        if not self.is_available():
            raise RuntimeError("Pillow unavailable for VisionConditionedEditor")

        base_path = Path(request.base_image_path)
        if not base_path.is_file():
            raise FileNotFoundError(f"base image not found: {base_path}")

        with Image.open(base_path) as opened:
            base = ImageOps.exif_transpose(opened).convert("RGB")

        canvas = Image.new("RGB", (request.width, request.height), color=(236, 232, 224))
        fitted = _fit_cover(base, request.width, request.height)
        # Soften photo toward concept / sketch feel.
        muted = ImageEnhance.Color(fitted).enhance(0.55)
        muted = ImageEnhance.Contrast(muted).enhance(0.92)
        muted = muted.filter(ImageFilter.SMOOTH_MORE)
        canvas.paste(muted, (0, 0))

        wash = Image.new("RGBA", (request.width, request.height), (245, 238, 220, 70))
        composed = Image.alpha_composite(canvas.convert("RGBA"), wash)

        overlay = Image.new("RGBA", (request.width, request.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        margin = max(28, min(request.width, request.height) // 20)
        draw.rectangle(
            (margin, margin, request.width - margin, request.height - margin),
            outline=(70, 80, 90, 180),
            width=2,
        )

        # Suggestive "intervention" stroke — not a measured CAD edit.
        y = int(request.height * 0.62)
        draw.line(
            (margin * 2, y, request.width - margin * 2, y - margin),
            fill=(180, 90, 60, 200),
            width=5,
        )
        draw.rectangle(
            (
                int(request.width * 0.35),
                int(request.height * 0.35),
                int(request.width * 0.72),
                int(request.height * 0.58),
            ),
            outline=(60, 110, 140, 190),
            width=3,
        )

        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover
            font = None

        title = "Archium Vision · photo edit (illustrative only)"
        if request.mode == VisionGenerationMode.EDIT_FROM_DRAWING:
            title = "Archium Vision · drawing edit (illustrative only)"
        draw.text((margin + 4, margin + 4), title[:70], fill=(35, 35, 35, 230), font=font)
        draw.text(
            (margin + 4, margin + 22),
            f"{request.style} · {request.prompt_hash}"[:70],
            fill=(70, 70, 70, 220),
            font=font,
        )
        subject = (request.subject or "")[:90]
        if subject:
            draw.text(
                (margin + 4, request.height - margin * 2),
                subject,
                fill=(50, 50, 50, 230),
                font=font,
            )
        for index, cue in enumerate(list(request.overlay_cues)[:3]):
            cy = margin + 48 + index * 22
            text = str(cue)[:32]
            draw.rectangle(
                (margin + 4, cy, margin + 8 + max(80, 7 * len(text)), cy + 16),
                fill=(255, 252, 245, 200),
                outline=(80, 80, 80, 160),
                width=1,
            )
            draw.text((margin + 10, cy + 2), text, fill=(40, 40, 40, 230), font=font)

        out = Image.alpha_composite(composed, overlay).convert("RGB")
        buffer = BytesIO()
        out.save(buffer, format="PNG")
        return buffer.getvalue()


def soft_harmonize_png(data: bytes) -> bytes:
    """Presentation-soft unify aligned with ImageDerivative spirit (not evidence)."""
    from io import BytesIO

    from PIL import Image, ImageEnhance

    with Image.open(BytesIO(data)) as opened:
        image = opened.convert("RGB")
    image = ImageEnhance.Color(image).enhance(0.92)
    image = ImageEnhance.Contrast(image).enhance(1.06)
    image = ImageEnhance.Brightness(image).enhance(1.02)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _fit_cover(image: PilImage, width: int, height: int) -> PilImage:
    from PIL import Image

    assert isinstance(image, Image.Image)
    src_w, src_h = image.size
    scale = max(width / max(src_w, 1), height / max(src_h, 1))
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))
