"""Generate simple schematic PNG fallbacks when project assets are missing."""

from __future__ import annotations

from pathlib import Path

from archium.domain.enums import VisualType

_PLAN_TYPES = {VisualType.SITE_PLAN, VisualType.MAP, VisualType.FLOOR_PLAN}
_TIMELINE_TYPES = {VisualType.TIMELINE}
_DIAGRAM_TYPES = {VisualType.DIAGRAM, VisualType.ICON, VisualType.COMPARISON}

_GENERATABLE_TYPES = _PLAN_TYPES | _TIMELINE_TYPES | _DIAGRAM_TYPES


def can_generate_diagram(visual_type: VisualType) -> bool:
    return visual_type in _GENERATABLE_TYPES


def generate_fallback_diagram(
    output_path: Path,
    *,
    title: str,
    visual_type: VisualType,
    description: str,
    key_points: list[str],
    message: str | None = None,
) -> Path:
    """Render a labeled schematic PNG using Pillow."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for programmatic diagram fallbacks (install archium-agent[documents])"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1280, 800
    image = Image.new("RGB", (width, height), "#F7F6F3")
    draw = ImageDraw.Draw(image)

    _draw_header(draw, width, title, visual_type, description)
    body_top = 120
    if visual_type in _PLAN_TYPES:
        _draw_plan_schematic(draw, width, height, body_top, key_points, message)
    elif visual_type in _TIMELINE_TYPES:
        _draw_timeline_schematic(draw, width, height, body_top, key_points)
    else:
        _draw_bullet_schematic(draw, width, height, body_top, key_points, message)

    image.save(output_path, format="PNG")
    return output_path


def _draw_header(
    draw: object,
    width: int,
    title: str,
    visual_type: VisualType,
    description: str,
) -> None:
    draw.rectangle((0, 0, width, 96), fill="#ECEAE4")  # type: ignore[attr-defined]
    draw.text((48, 24), title[:60], fill="#1A1A1A")  # type: ignore[attr-defined]
    subtitle = f"{visual_type.value} · {description[:80]}"
    draw.text((48, 58), subtitle, fill="#6B675F")  # type: ignore[attr-defined]
    if visual_type in _PLAN_TYPES:
        draw.text(  # type: ignore[attr-defined]
            (48, 78),
            "示意草图 · 非实测图纸 · 待补充正式素材",
            fill="#9A9488",
        )


def _draw_plan_schematic(
    draw: object,
    width: int,
    height: int,
    top: int,
    key_points: list[str],
    message: str | None,
) -> None:
    margin = 80
    box = (margin, top + 20, width - margin, height - 180)
    draw.rectangle(box, outline="#8A8780", width=3, fill="#FFFFFF")  # type: ignore[attr-defined]
    _draw_grid(draw, box)
    labels = key_points[:4] or ([message] if message else ["待补充功能分区"])
    for index, label in enumerate(labels):
        col = index % 2
        row = index // 2
        x = box[0] + 40 + col * ((box[2] - box[0]) // 2 - 20)
        y = box[1] + 40 + row * 120
        block_w = (box[2] - box[0]) // 2 - 60
        block_h = 90
        draw.rectangle(  # type: ignore[attr-defined]
            (x, y, x + block_w, y + block_h),
            outline="#4A6FA5",
            width=2,
            fill="#EEF3FA",
        )
        draw.text((x + 12, y + 30), label[:24], fill="#1A1A1A")  # type: ignore[attr-defined]


def _draw_timeline_schematic(
    draw: object,
    width: int,
    height: int,
    top: int,
    key_points: list[str],
) -> None:
    if not key_points:
        key_points = ["阶段 1", "阶段 2", "阶段 3"]
    y = top + 180
    start_x = 100
    end_x = width - 100
    draw.line((start_x, y, end_x, y), fill="#4A6FA5", width=4)  # type: ignore[attr-defined]
    step = (end_x - start_x) / max(len(key_points), 1)
    for index, point in enumerate(key_points[:6]):
        x = start_x + step * index + step / 2
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="#4A6FA5")  # type: ignore[attr-defined]
        draw.text((x - 40, y + 20), point[:18], fill="#1A1A1A")  # type: ignore[attr-defined]


def _draw_bullet_schematic(
    draw: object,
    width: int,
    height: int,
    top: int,
    key_points: list[str],
    message: str | None,
) -> None:
    y = top + 30
    if message:
        draw.text((80, y), message[:100], fill="#1A1A1A")  # type: ignore[attr-defined]
        y += 40
    points = key_points[:6] or ["待补充图示要点"]
    for point in points:
        draw.ellipse((80, y + 6, 92, y + 18), fill="#4A6FA5")  # type: ignore[attr-defined]
        draw.text((104, y), point[:70], fill="#1A1A1A")  # type: ignore[attr-defined]
        y += 42


def _draw_grid(draw: object, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    for offset in range(0, right - left, 80):
        x = left + offset
        draw.line((x, top, x, bottom), fill="#E8E6E1", width=1)  # type: ignore[attr-defined]
    for offset in range(0, bottom - top, 80):
        y = top + offset
        draw.line((left, y, right, y), fill="#E8E6E1", width=1)  # type: ignore[attr-defined]
