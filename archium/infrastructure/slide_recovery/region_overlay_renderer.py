"""Draw recovered region bounding boxes on a source page raster preview."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.domain.slide_recovery import REGION_TYPE_LABELS_ZH, RecoveredPageRegion

_REGION_COLORS: dict[str, str] = {
    "text": "#2563EB",
    "image": "#7C3AED",
    "drawing": "#DC2626",
    "table": "#059669",
    "chart": "#D97706",
    "line": "#64748B",
    "shape": "#0891B2",
    "background": "#94A3B8",
    "unknown": "#6B7280",
}


def render_region_overlay(
    source_image_path: Path,
    regions: list[RecoveredPageRegion],
    output_path: Path,
    *,
    highlight_region_id: UUID | None = None,
) -> Path:
    """Annotate *source_image_path* with region boxes and write *output_path*."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(source_image_path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size

    try:
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.truetype(
            "arial.ttf", max(12, width // 80)
        )
    except OSError:
        font = ImageFont.load_default()

    for index, region in enumerate(regions):
        color = _REGION_COLORS.get(region.region_type, "#6B7280")
        is_highlight = highlight_region_id is not None and region.id == highlight_region_id
        line_width = 4 if is_highlight else 2
        alpha = 220 if is_highlight else 160
        rgb = _hex_to_rgb(color)

        x0 = int(region.bbox.x * width)
        y0 = int(region.bbox.y * height)
        x1 = int((region.bbox.x + region.bbox.width) * width)
        y1 = int((region.bbox.y + region.bbox.height) * height)

        for offset in range(line_width):
            draw.rectangle(
                (x0 - offset, y0 - offset, x1 + offset, y1 + offset),
                outline=(*rgb, alpha),
            )

        label = _region_label(index, region)
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        label_y = max(0, y0 - text_h - 4)
        draw.rectangle(
            (x0, label_y, x0 + text_w + 8, label_y + text_h + 4),
            fill=(*rgb, 200),
        )
        draw.text((x0 + 4, label_y + 2), label, fill=(255, 255, 255, 255), font=font)

    composed = Image.alpha_composite(image, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(output_path)
    return output_path


def _region_label(index: int, region: RecoveredPageRegion) -> str:
    kind = REGION_TYPE_LABELS_ZH.get(region.region_type, region.region_type)
    role = region.semantic_role or "—"
    if region.region_type == "text" and region.recovered_text:
        snippet = region.recovered_text.strip().replace("\n", " ")
        if len(snippet) > 12:
            snippet = snippet[:12] + "…"
        return f"#{index + 1} {kind} · {snippet}"
    return f"#{index + 1} {kind} · {role}"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
