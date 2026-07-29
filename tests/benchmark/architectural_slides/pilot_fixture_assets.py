"""Generate presentation-ready benchmark fixtures for the pilot trio cases."""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PILOT_ASSET_IDS: dict[str, tuple[str, str]] = {
    "c0010001-0001-4001-8001-000000000001": ("site_plan", "院区总平面"),
    "c0020001-0001-4001-8001-000000000001": ("photo", "入口混行"),
    "c0020002-0001-4001-8001-000000000002": ("photo", "停车占道"),
    "c0020003-0001-4001-8001-000000000003": ("photo", "景观缺失"),
    "c0020004-0001-4001-8001-000000000004": ("photo", "导向不清"),
    "c0060001-0001-4001-8001-000000000001": ("hero", "内院效果图"),
}


def write_pilot_fixture_asset(output_path: Path, *, asset_id: str) -> Path:
    """Write one pilot fixture PNG with enough visual density for readiness gates."""
    kind, label = PILOT_ASSET_IDS[asset_id]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "site_plan":
        _write_site_plan_fixture(output_path, label=label, seed=11)
    elif kind == "hero":
        _write_photo_fixture(output_path, label=label, seed=99, width=1920, height=1200)
    else:
        _write_photo_fixture(output_path, label=label, seed=hash(asset_id) % 10_000)
    return output_path


def _write_site_plan_fixture(path: Path, *, label: str, seed: int) -> None:
    random.seed(seed)
    width, height = 1920, 1200
    image = Image.new("RGB", (width, height), "#F4F1EA")
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, width - 48, height - 48), outline="#2A2A2A", width=4)
    zones = [
        ("急救", (96, 96, 760, 560), "#B8D4F0"),
        ("门诊", (820, 96, 1820, 560), "#C8E0B0"),
        ("后勤", (96, 620, 760, 1120), "#F0D8B0"),
        ("改造范围", (820, 620, 1820, 1120), "#F0B8B8"),
    ]
    for zone_label, box, color in zones:
        draw.rectangle(box, fill=color, outline="#1A3A6A", width=3)
        draw.text((box[0] + 24, box[1] + 24), zone_label, fill="#111111")
    for x in range(96, width - 48, 48):
        draw.line((x, 96, x, height - 48), fill="#9A9488", width=1)
    for y in range(96, height - 48, 48):
        draw.line((96, y, width - 48, y), fill="#9A9488", width=1)
    draw.line((96, 620, width - 48, 620), fill="#333333", width=6)
    draw.line((820, 96, 820, height - 48), fill="#333333", width=6)
    for _ in range(240):
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
    base = (
        50 + (seed % 40),
        70 + (seed % 30),
        60 + (seed % 35),
    )
    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image)
    for _ in range(360):
        x = random.randint(0, width)
        y = random.randint(0, height)
        radius = random.randint(12, 90)
        color = (
            random.randint(20, 220),
            random.randint(20, 220),
            random.randint(20, 220),
        )
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    for _ in range(120):
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


__all__ = ["PILOT_ASSET_IDS", "write_pilot_fixture_asset"]
