"""Presentation-ready PNG fixtures for architectural benchmark curated assets."""

from __future__ import annotations

import random
from pathlib import Path

from archium.domain.enums import VisualType
from PIL import Image, ImageDraw, ImageFilter

_DRAWING_TYPES = {
    VisualType.SITE_PLAN,
    VisualType.FLOOR_PLAN,
    VisualType.SECTION,
    VisualType.ELEVATION,
    VisualType.MAP,
}
_PHOTO_TYPES = {
    VisualType.SITE_PHOTO,
    VisualType.COMPARISON,
    VisualType.REFERENCE_CASE,
}
_DIAGRAM_TYPES = {
    VisualType.DIAGRAM,
    VisualType.CHART,
    VisualType.TIMELINE,
    VisualType.ICON,
    VisualType.TABLE,
    VisualType.TEXT_ONLY,
}


def fixture_seed(asset_id: str) -> int:
    return abs(hash(asset_id)) % 10_000


def write_benchmark_fixture_asset(
    output_path: Path,
    *,
    asset_id: str,
    visual_type: VisualType,
    label: str,
) -> Path:
    """Write one deterministic fixture PNG that passes presentation readiness gates."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seed = fixture_seed(asset_id)
    if visual_type in _DRAWING_TYPES:
        _write_drawing_fixture(output_path, label=label, seed=seed, visual_type=visual_type)
    elif visual_type == VisualType.RENDERING:
        _write_photo_fixture(output_path, label=label, seed=seed, width=1920, height=1200)
    elif visual_type in _PHOTO_TYPES:
        _write_photo_fixture(output_path, label=label, seed=seed)
    else:
        _write_diagram_fixture(output_path, label=label, seed=seed, visual_type=visual_type)
    return output_path


def _write_drawing_fixture(
    path: Path,
    *,
    label: str,
    seed: int,
    visual_type: VisualType,
) -> None:
    random.seed(seed)
    width, height = 1920, 1200
    image = Image.new("RGB", (width, height), "#F4F1EA")
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, width - 48, height - 48), outline="#2A2A2A", width=4)

    if visual_type == VisualType.SECTION:
        bands = [("#D8E8F8", 120), ("#E8F0D8", 360), ("#F0E0C8", 600), ("#F0D0D0", 840)]
        for color, y in bands:
            draw.rectangle((96, y, width - 96, y + 200), fill=color, outline="#1A3A6A", width=2)
    elif visual_type == VisualType.ELEVATION:
        for index, x in enumerate(range(120, width - 200, 220)):
            h = 400 + (index % 3) * 120
            draw.rectangle((x, height - 160 - h, x + 160, height - 160), fill="#D0D8E8", outline="#333", width=2)
    elif visual_type == VisualType.FLOOR_PLAN:
        rooms = [
            ("诊室", (120, 120, 520, 420)),
            ("候诊", (560, 120, 920, 420)),
            ("护士站", (960, 120, 1320, 420)),
            ("药房", (120, 480, 520, 860)),
            ("检验", (560, 480, 1320, 860)),
        ]
        for room_label, box in rooms:
            draw.rectangle(box, fill="#E8F0FA", outline="#2A5A8A", width=2)
            draw.text((box[0] + 16, box[1] + 16), room_label, fill="#111")
    else:
        zones = [
            ("A区", (96, 96, 760, 560), "#B8D4F0"),
            ("B区", (820, 96, 1820, 560), "#C8E0B0"),
            ("C区", (96, 620, 760, 1120), "#F0D8B0"),
            ("D区", (820, 620, 1820, 1120), "#F0B8B8"),
        ]
        for zone_label, box, color in zones:
            draw.rectangle(box, fill=color, outline="#1A3A6A", width=3)
            draw.text((box[0] + 24, box[1] + 24), zone_label, fill="#111111")

    for x in range(96, width - 48, 48):
        draw.line((x, 96, x, height - 48), fill="#9A9488", width=1)
    for y in range(96, height - 48, 48):
        draw.line((96, y, width - 48, y), fill="#9A9488", width=1)
    for _ in range(140):
        x = random.randint(120, width - 120)
        y = random.randint(120, height - 120)
        draw.line(
            (x, y, x + random.randint(8, 56), y + random.randint(-12, 12)),
            fill="#555555",
            width=2,
        )
    draw.text((72, height - 40), label, fill="#333333")
    image.filter(ImageFilter.SHARPEN).save(path, format="PNG")


def _write_photo_fixture(
    path: Path,
    *,
    label: str,
    seed: int,
    width: int = 1280,
    height: int = 960,
) -> None:
    random.seed(seed)
    base = (50 + (seed % 40), 70 + (seed % 30), 60 + (seed % 35))
    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image)
    for _ in range(180):
        x = random.randint(0, width)
        y = random.randint(0, height)
        radius = random.randint(12, 90)
        color = (
            random.randint(20, 220),
            random.randint(20, 220),
            random.randint(20, 220),
        )
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    for _ in range(50):
        draw.line(
            (
                random.randint(0, width),
                random.randint(0, height),
                random.randint(0, width),
                random.randint(0, height),
            ),
            fill=(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            ),
            width=random.randint(1, 4),
        )
    draw.text((48, height - 56), label, fill="#F2F2F0")
    image.filter(ImageFilter.EDGE_ENHANCE_MORE).filter(ImageFilter.SHARPEN).save(path, format="PNG")


def _write_diagram_fixture(
    path: Path,
    *,
    label: str,
    seed: int,
    visual_type: VisualType,
) -> None:
    random.seed(seed)
    width, height = 1600, 1000
    image = Image.new("RGB", (width, height), "#FAFAF8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, width - 40, height - 40), outline="#444", width=3)

    if visual_type == VisualType.CHART:
        bar_w = 80
        for index, x in enumerate(range(120, width - 200, 140)):
            bar_h = 120 + (index % 5) * 90
            draw.rectangle(
                (x, height - 180 - bar_h, x + bar_w, height - 180),
                fill="#4A6FA5",
                outline="#1A3A6A",
            )
        draw.line((100, height - 180, width - 100, height - 180), fill="#333", width=3)
    elif visual_type == VisualType.TIMELINE:
        y = height // 2
        draw.line((120, y, width - 120, y), fill="#4A6FA5", width=5)
        for index, x in enumerate(range(180, width - 120, 180)):
            draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill="#4A6FA5")
            draw.text((x - 24, y + 24), f"T{index + 1}", fill="#111")
    else:
        nodes = [(200, 200), (width - 280, 220), (width // 2, height - 280), (260, height - 220)]
        for x, y in nodes:
            draw.ellipse((x - 40, y - 40, x + 40, y + 40), fill="#D8E8F8", outline="#2A5A8A", width=2)
        for _ in range(len(nodes) - 1):
            a = random.choice(nodes)
            b = random.choice(nodes)
            draw.line(a + b, fill="#666", width=3)
        for _ in range(80):
            draw.line(
                (
                    random.randint(80, width - 80),
                    random.randint(80, height - 80),
                    random.randint(80, width - 80),
                    random.randint(80, height - 80),
                ),
                fill="#888",
                width=random.randint(1, 3),
            )

    draw.text((72, height - 56), label, fill="#222")
    image.filter(ImageFilter.SHARPEN).save(path, format="PNG")


__all__ = ["fixture_seed", "write_benchmark_fixture_asset"]
