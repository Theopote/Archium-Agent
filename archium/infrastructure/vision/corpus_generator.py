"""Generate synthetic labeled images for Visual QA calibration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.application.visual_qa_calibration import CORPUS_CATEGORY_TARGETS

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]

_PLAN_CATEGORIES = frozenset({"site_plan", "floor_plan"})
_DRAWING_CATEGORIES = frozenset({"site_plan", "floor_plan", "section", "elevation", "diagram"})


@dataclass(frozen=True)
class GeneratedSample:
    sample_id: str
    relative_path: str
    category: str
    labels: dict[str, object]
    notes: str


def category_image_size(category: str) -> tuple[int, int]:
    if category == "section":
        return (900, 1200)
    if category == "elevation":
        return (1400, 1000)
    if category == "site_plan":
        return (1200, 1000)
    if category == "floor_plan":
        return (1000, 1000)
    if category == "diagram":
        return (1200, 800)
    return (1280, 720)


def generate_corpus(
    corpus_root: Path,
    *,
    category_targets: dict[str, int] | None = None,
    overwrite_images: bool = False,
) -> list[GeneratedSample]:
    """Write synthetic PNGs and return sample metadata (does not update manifest)."""
    _require_pillow()
    targets = category_targets or dict(CORPUS_CATEGORY_TARGETS)
    images_dir = corpus_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    generated: list[GeneratedSample] = []
    for category, count in targets.items():
        for index in range(count):
            sample_id = f"{category}_{index + 1:03d}"
            relative_path = f"images/{sample_id}.png"
            output_path = corpus_root / relative_path
            variant = index % 10
            if output_path.exists() and not overwrite_images:
                labels, notes = _labels_for_variant(category, variant)
            else:
                labels, notes = _render_variant(category, variant, output_path)
            generated.append(
                GeneratedSample(
                    sample_id=sample_id,
                    relative_path=relative_path,
                    category=category,
                    labels=labels,
                    notes=notes,
                )
            )
    return generated


def _require_pillow() -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required to generate the Visual QA calibration corpus")


def _labels_for_variant(category: str, variant: int) -> tuple[dict[str, object], str]:
    labels: dict[str, object] = {
        "drawing_type": category,
        "has_north_arrow": None,
        "has_legend": None,
        "is_low_resolution": False,
        "is_clipped": False,
        "excessive_margins": False,
        "high_text_density": False,
        "low_contrast": False,
    }
    notes = "合成标定样本"

    if variant == 1:
        labels["is_low_resolution"] = True
        notes = "低分辨率合成样本"
    elif variant == 2 and category in _PLAN_CATEGORIES:
        labels["has_north_arrow"] = True
        notes = "含指北针的合成总图/平面图"
    elif variant == 3 and category in _PLAN_CATEGORIES:
        labels["has_north_arrow"] = False
        notes = "缺少指北针的合成总图/平面图"
    elif variant == 4:
        labels["has_legend"] = True
        notes = "含图例色块的合成样本"
    elif variant == 5:
        labels["excessive_margins"] = True
        notes = "有效图面偏小的合成样本"
    elif variant == 6:
        labels["is_clipped"] = True
        notes = "内容贴边的合成样本"
    elif variant == 7:
        labels["low_contrast"] = True
        notes = "低对比度合成样本"
    elif variant == 8:
        labels["high_text_density"] = True
        notes = "高边缘密度/文字拥挤合成样本"
    elif variant == 9 and category in _DRAWING_CATEGORIES:
        labels["has_legend"] = False
        notes = "缺少图例的合成图纸"

    if category == "photo":
        labels["has_north_arrow"] = None
        labels["has_legend"] = None

    return labels, notes


def _render_variant(category: str, variant: int, output_path: Path) -> tuple[dict[str, object], str]:
    labels, notes = _labels_for_variant(category, variant)
    size = category_image_size(category)
    if labels.get("is_low_resolution"):
        size = (640, 480)

    image = Image.new("RGB", size, color=(245, 245, 242))
    draw = ImageDraw.Draw(image)

    if category == "photo":
        _draw_photo(image, draw, variant)
    elif category == "section":
        _draw_section(draw, size, variant)
    elif category == "elevation":
        _draw_elevation(draw, size, variant)
    elif category == "diagram":
        _draw_diagram(draw, size, variant)
    elif category == "floor_plan":
        _draw_floor_plan(draw, size, variant)
    else:
        _draw_site_plan(draw, size, variant)

    if labels.get("has_north_arrow") is True:
        _draw_north_arrow(draw, size)
    if labels.get("has_legend") is True:
        _draw_legend(draw, size)
    if labels.get("excessive_margins") is True:
        _apply_excessive_margins(image)
    if labels.get("is_clipped") is True:
        _apply_clipping(draw, size)
    if labels.get("low_contrast") is True:
        _apply_low_contrast(image)
    if labels.get("high_text_density") is True:
        _apply_high_text_density(draw, size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return labels, notes


def _draw_site_plan(draw: ImageDraw.ImageDraw, size: tuple[int, int], variant: int) -> None:
    width, height = size
    margin = 80
    draw.rectangle(
        (margin, margin, width - margin, height - margin),
        outline=(30, 30, 30),
        width=3,
    )
    draw.line((margin, height // 2, width - margin, height // 2), fill=(180, 180, 180), width=2)
    draw.line((width // 2, margin, width // 2, height - margin), fill=(180, 180, 180), width=2)
    for index in range(4):
        x = margin + 60 + index * 120
        y = margin + 60
        draw.rectangle((x, y, x + 80, y + 60), outline=(90, 90, 90), width=2)


def _draw_floor_plan(draw: ImageDraw.ImageDraw, size: tuple[int, int], variant: int) -> None:
    width, height = size
    margin = 70
    cell_w = (width - margin * 2) // 4
    cell_h = (height - margin * 2) // 3
    for row in range(3):
        for col in range(4):
            x0 = margin + col * cell_w
            y0 = margin + row * cell_h
            draw.rectangle((x0, y0, x0 + cell_w - 8, y0 + cell_h - 8), outline=(40, 40, 40), width=2)


def _draw_section(draw: ImageDraw.ImageDraw, size: tuple[int, int], variant: int) -> None:
    width, height = size
    base_y = height - 120
    draw.line((80, base_y, width - 80, base_y), fill=(20, 20, 20), width=4)
    points = [(120, base_y), (220, base_y - 280), (420, base_y - 180), (560, base_y - 360), (760, base_y)]
    draw.line(points, fill=(30, 30, 30), width=3)
    draw.line((760, base_y, 760, base_y - 360), fill=(120, 120, 120), width=2)


def _draw_elevation(draw: ImageDraw.ImageDraw, size: tuple[int, int], variant: int) -> None:
    width, height = size
    base_y = height - 100
    draw.rectangle((180, base_y - 420, 520, base_y), outline=(25, 25, 25), width=3)
    draw.rectangle((560, base_y - 320, 820, base_y), outline=(25, 25, 25), width=3)
    for x in range(220, 500, 60):
        draw.rectangle((x, base_y - 380, x + 30, base_y - 260), fill=(180, 210, 230))
    for x in range(600, 780, 55):
        draw.rectangle((x, base_y - 280, x + 28, base_y - 160), fill=(180, 210, 230))


def _draw_diagram(draw: ImageDraw.ImageDraw, size: tuple[int, int], variant: int) -> None:
    width, height = size
    left = 120
    top = 140
    for index, label in enumerate(["研究", "概念", "方案", "深化"]):
        x = left + index * 180
        draw.ellipse((x, top, x + 90, top + 90), outline=(50, 90, 140), width=3)
        draw.text((x + 18, top + 34), label, fill=(30, 30, 30))
        if index < 3:
            draw.line((x + 95, top + 45, x + 170, top + 45), fill=(80, 80, 80), width=2)


def _draw_photo(image: Image.Image, draw: ImageDraw.ImageDraw, variant: int) -> None:
    width, height = image.size
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = (
            int(120 + 80 * ratio),
            int(160 + 40 * ratio),
            int(210 - 40 * ratio),
        )
        draw.line((0, y, width, y), fill=color)
    draw.rectangle((width // 4, height // 2, width * 3 // 4, height - 80), fill=(70, 75, 82))
    draw.polygon(
        [
            (width // 4, height // 2),
            (width // 2, height // 3),
            (width * 3 // 4, height // 2),
        ],
        fill=(45, 45, 48),
    )


def _draw_north_arrow(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    width, _height = size
    corner = width - 80
    draw.polygon([(corner + 40, 10), (corner + 10, 85), (corner + 70, 85)], fill=(10, 10, 10))
    draw.text((corner + 28, 88), "N", fill=(10, 10, 10))


def _draw_legend(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    width, height = size
    base_y = height - 70
    colors = [(220, 30, 30), (30, 120, 220), (40, 180, 80), (240, 180, 40)]
    for index, color in enumerate(colors):
        x = 40 + index * 90
        draw.rectangle((x, base_y, x + 50, base_y + 20), fill=color)
        draw.text((x + 56, base_y + 2), f"L{index + 1}", fill=(20, 20, 20))


def _apply_excessive_margins(image: Image.Image) -> None:
    width, height = image.size
    small = image.copy()
    small.thumbnail((int(width * 0.45), int(height * 0.45)))
    canvas = Image.new("RGB", (width, height), color=(250, 250, 248))
    offset = ((width - small.width) // 2, (height - small.height) // 2)
    canvas.paste(small, offset)
    image.paste(canvas)


def _apply_clipping(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    width, height = size
    draw.rectangle((0, 0, width, 12), fill=(20, 20, 20))
    draw.rectangle((0, height - 12, width, height), fill=(20, 20, 20))
    draw.rectangle((0, 0, 12, height), fill=(20, 20, 20))
    draw.rectangle((width - 12, 0, width, height), fill=(20, 20, 20))


def _apply_low_contrast(image: Image.Image) -> None:
    gray = Image.new("RGB", image.size, color=(190, 190, 188))
    gray.paste(image)
    blended = Image.blend(gray, image, alpha=0.25)
    image.paste(blended)


def _apply_high_text_density(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    width, height = size
    for x in range(40, width - 40, 12):
        draw.line((x, 100, x, height - 100), fill=(60, 60, 60), width=1)
    for y in range(120, height - 120, 14):
        draw.line((60, y, width - 60, y), fill=(80, 80, 80), width=1)


def samples_to_manifest_entries(samples: list[GeneratedSample]) -> list[dict[str, object]]:
    return [
        {
            "id": sample.sample_id,
            "path": sample.relative_path,
            "category": sample.category,
            "labels": sample.labels,
            "notes": sample.notes,
            "source": "synthetic_bootstrap",
        }
        for sample in samples
    ]
