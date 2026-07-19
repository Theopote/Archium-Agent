"""Deterministic wireframe previews for LayoutPlan geometry."""

from __future__ import annotations

from pathlib import Path

from archium.domain.visual.enums import LayoutContentType
from archium.domain.visual.layout import LayoutPlan


def render_layout_preview_png(plan: LayoutPlan, output_path: Path) -> Path:
    """Render element boxes as a wireframe PNG (not a photographic slide)."""
    from PIL import Image, ImageDraw, ImageFont

    scale = 96  # px per inch
    width = max(1, int(plan.page_width * scale))
    height = max(1, int(plan.page_height * scale))
    image = Image.new("RGB", (width, height), color=(248, 248, 246))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default()
    except OSError:
        font = None

    role_colors = {
        "title": (30, 30, 30),
        "hero_visual": (40, 90, 140),
        "supporting_visual": (70, 120, 160),
        "body_text": (60, 60, 60),
        "metric": (120, 70, 40),
        "caption": (90, 90, 90),
        "annotation": (100, 80, 50),
        "lead_statement": (50, 50, 50),
        "source": (110, 110, 110),
        "decoration": (160, 160, 160),
    }

    for element in plan.elements:
        x0 = int(element.x * scale)
        y0 = int(element.y * scale)
        x1 = int((element.x + element.width) * scale)
        y1 = int((element.y + element.height) * scale)
        color = role_colors.get(element.role.value, (80, 80, 80))
        if element.content_type in {
            LayoutContentType.IMAGE,
            LayoutContentType.DRAWING,
            LayoutContentType.CHART,
        }:
            draw.rectangle([x0, y0, x1, y1], outline=color, width=2, fill=(220, 228, 236))
        else:
            draw.rectangle([x0, y0, x1, y1], outline=color, width=2)
        label = element.id
        if font is not None and x1 - x0 > 24 and y1 - y0 > 12:
            draw.text((x0 + 3, y0 + 2), label, fill=color, font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return output_path
