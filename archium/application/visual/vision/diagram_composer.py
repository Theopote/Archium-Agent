"""Lightweight diagram composition: user base (site plan) + strategy overlays.

Not CAD understanding — deterministic Pillow overlays for Vision Engine v0.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from archium.domain.visual.vision_generation import ArchitectureImageType

if TYPE_CHECKING:
    from PIL.Image import Image as PilImage
    from PIL.ImageDraw import ImageDraw as PilImageDraw


@dataclass(frozen=True)
class DiagramComposeRequest:
    """Inputs for base + overlay composition."""

    base_image_path: str
    width: int
    height: int
    image_type: ArchitectureImageType
    subject: str = ""
    overlay_cues: tuple[str, ...] = ()
    prompt_hash: str = ""
    label: str = "Archium diagram overlay"


_DIAGRAM_TYPES = frozenset(
    {
        ArchitectureImageType.SITE_DIAGRAM,
        ArchitectureImageType.FLOW_DIAGRAM,
    }
)


def supports_diagram_compose(image_type: ArchitectureImageType) -> bool:
    return image_type in _DIAGRAM_TYPES


class VisionDiagramComposer:
    """Composite a desaturated base plan with circulation / strategy overlays."""

    def is_available(self) -> bool:
        try:
            from PIL import Image  # noqa: F401

            return True
        except ImportError:
            return False

    def compose(self, request: DiagramComposeRequest) -> bytes:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFont

        if not self.is_available():
            raise RuntimeError("Pillow unavailable for VisionDiagramComposer")

        base_path = Path(request.base_image_path)
        if not base_path.is_file():
            raise FileNotFoundError(f"base image not found: {base_path}")

        with Image.open(base_path) as opened:
            base = opened.convert("RGB")

        canvas = Image.new("RGB", (request.width, request.height), color=(232, 230, 224))
        fitted = _fit_contain(base, request.width, request.height)
        offset_x = (request.width - fitted.width) // 2
        offset_y = (request.height - fitted.height) // 2
        muted = ImageEnhance.Color(fitted).enhance(0.35)
        muted = ImageEnhance.Brightness(muted).enhance(1.05)
        canvas.paste(muted, (offset_x, offset_y))

        overlay = Image.new("RGBA", (request.width, request.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        margin = max(28, min(request.width, request.height) // 22)
        frame = (
            offset_x + margin // 2,
            offset_y + margin // 2,
            offset_x + fitted.width - margin // 2,
            offset_y + fitted.height - margin // 2,
        )
        draw.rectangle(frame, outline=(50, 60, 70, 200), width=2)

        cues = [cue.strip() for cue in request.overlay_cues if cue.strip()]
        if not cues and request.subject:
            cues = [request.subject[:80]]
        if not cues:
            cues = ["strategy overlay"]

        path_y = offset_y + int(fitted.height * 0.55)
        x0 = offset_x + margin
        x1 = offset_x + fitted.width - margin
        draw.line((x0, path_y, x1, path_y), fill=(196, 78, 52, 220), width=7)
        _draw_arrow_head(draw, x1, path_y, direction="right", color=(196, 78, 52, 230))

        if request.image_type == ArchitectureImageType.FLOW_DIAGRAM:
            secondary_y = path_y - margin * 2
            mid = (x0 + x1) // 2
            draw.line((x0, secondary_y, mid, path_y), fill=(70, 110, 150, 200), width=5)
            _draw_arrow_head(draw, mid, path_y, direction="down", color=(70, 110, 150, 220))
            draw.rectangle(
                (x0 + margin, secondary_y - margin, x1 - margin, secondary_y - margin // 3),
                outline=(90, 120, 140, 210),
                width=3,
            )

        if request.image_type == ArchitectureImageType.SITE_DIAGRAM:
            mid_x = (x0 + x1) // 2 - margin * 2
            zone = (
                mid_x,
                path_y - margin * 3,
                mid_x + margin * 4,
                path_y + margin,
            )
            draw.rectangle(zone, outline=(40, 120, 90, 210), width=3)
            draw.ellipse(
                (zone[0] + 8, zone[1] + 8, zone[0] + 28, zone[1] + 28),
                fill=(40, 120, 90, 180),
            )

        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover
            font = None

        draw.text(
            (margin, margin // 2),
            request.label[:60],
            fill=(35, 35, 35, 230),
            font=font,
        )
        type_label = f"{request.image_type.value} · {request.prompt_hash}".strip(" ·")
        draw.text((margin, margin // 2 + 16), type_label[:70], fill=(70, 70, 70, 220), font=font)

        for index, cue in enumerate(cues[:4]):
            cx = x0 + int((x1 - x0) * ((index + 1) / (min(len(cues), 4) + 1)))
            cy = path_y - margin * 4 - (index % 2) * (margin + 4)
            text = cue[:28]
            chip_w = max(72, min(220, 7 * len(text) + 16))
            chip = (cx - chip_w // 2, cy, cx + chip_w // 2, cy + 18)
            draw.rectangle(chip, fill=(255, 252, 245, 210), outline=(60, 70, 80, 180), width=1)
            draw.text((chip[0] + 6, chip[1] + 3), text, fill=(40, 40, 40, 230), font=font)

        composed = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        buffer = BytesIO()
        composed.save(buffer, format="PNG")
        return buffer.getvalue()


def _fit_contain(image: PilImage, width: int, height: int) -> PilImage:
    from PIL import Image

    assert isinstance(image, Image.Image)
    src_w, src_h = image.size
    scale = min(width / max(src_w, 1), height / max(src_h, 1))
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _draw_arrow_head(
    draw: PilImageDraw,
    x: int,
    y: int,
    *,
    direction: str,
    color: tuple[int, int, int, int],
    size: int = 14,
) -> None:
    if direction == "right":
        points = [(x, y), (x - size, y - size // 2), (x - size, y + size // 2)]
    elif direction == "down":
        points = [(x, y), (x - size // 2, y - size), (x + size // 2, y - size)]
    else:  # pragma: no cover
        points = [(x, y), (x + size, y - size // 2), (x + size, y + size // 2)]
    draw.polygon(points, fill=color)
