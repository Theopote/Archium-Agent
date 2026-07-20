"""Geometry helpers for transactional layout element edits."""

from __future__ import annotations

from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.exceptions import WorkflowError

_POSITION_ALIASES: dict[str, str] = {
    "right": "right",
    "右边": "right",
    "右侧": "right",
    "left": "left",
    "左边": "left",
    "左侧": "left",
    "top": "top",
    "上方": "top",
    "上面": "top",
    "bottom": "bottom",
    "下方": "bottom",
    "下面": "bottom",
    "center": "center",
    "中间": "center",
    "居中": "center",
}


def normalize_position(position: str) -> str:
    """Map natural-language position hints to canonical placement names."""
    normalized = position.strip().lower()
    if normalized == "absolute":
        return "absolute"
    if normalized in _POSITION_ALIASES:
        return _POSITION_ALIASES[normalized]
    if normalized.startswith("position_of_") or normalized == "temp":
        raise WorkflowError("元素交换（swap）暂未支持，请分步移动元素。")
    raise WorkflowError(f"无法识别目标位置：{position}")


def _content_safe_rect(layout_plan: LayoutPlan) -> tuple[float, float, float, float]:
    """Approximate the presentation safe area using standard 16:9 margins."""
    margin_x = layout_plan.page_width * 0.07
    margin_y = layout_plan.page_height * 0.08
    return margin_x, margin_y, layout_plan.page_width - (2 * margin_x), layout_plan.page_height - (2 * margin_y)


def _assert_within_safe_area(
    layout_plan: LayoutPlan,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    safe_x, safe_y, safe_w, safe_h = _content_safe_rect(layout_plan)
    if (
        x < safe_x
        or y < safe_y
        or x + width > safe_x + safe_w
        or y + height > safe_y + safe_h
    ):
        raise WorkflowError("移动后元素会超出安全区域，无法执行")


def layout_bounds_from_percent(
    layout_plan: LayoutPlan,
    *,
    x_percent: float,
    y_percent: float,
    width_percent: float,
    height_percent: float,
) -> tuple[float, float, float, float]:
    """Convert canvas overlay percentages to layout-plan bounds."""
    page_width = float(layout_plan.page_width or 10.0)
    page_height = float(layout_plan.page_height or 5.625)
    return (
        (x_percent / 100.0) * page_width,
        (y_percent / 100.0) * page_height,
        (width_percent / 100.0) * page_width,
        (height_percent / 100.0) * page_height,
    )


def layout_coords_from_percent(
    layout_plan: LayoutPlan,
    *,
    x_percent: float,
    y_percent: float,
) -> tuple[float, float]:
    """Convert canvas overlay percentages to layout-plan coordinates."""
    page_width = float(layout_plan.page_width or 10.0)
    page_height = float(layout_plan.page_height or 5.625)
    return (x_percent / 100.0) * page_width, (y_percent / 100.0) * page_height


def compute_element_placement(
    element: LayoutElement,
    layout_plan: LayoutPlan,
    position: str,
    *,
    absolute_x: float | None = None,
    absolute_y: float | None = None,
) -> tuple[float, float, float, float]:
    """Return x, y, width, height for moving an element to a page region."""
    canonical = normalize_position(position)
    width = element.width
    height = element.height
    safe_x, safe_y, safe_w, safe_h = _content_safe_rect(layout_plan)
    min(layout_plan.page_width, layout_plan.page_height) * 0.05

    if canonical == "absolute":
        if absolute_x is None or absolute_y is None:
            raise WorkflowError("absolute move requires x and y coordinates")
        x = absolute_x
        y = absolute_y
    elif canonical == "right":
        x = safe_x + safe_w - width
        y = element.y
    elif canonical == "left":
        x = safe_x
        y = element.y
    elif canonical == "top":
        x = element.x
        y = safe_y
    elif canonical == "bottom":
        x = element.x
        y = safe_y + safe_h - height
    elif canonical == "center":
        x = safe_x + (safe_w - width) / 2
        y = safe_y + (safe_h - height) / 2
    else:
        raise WorkflowError(f"Unsupported placement: {canonical}")

    if (
        x < 0
        or y < 0
        or x + width > layout_plan.page_width
        or y + height > layout_plan.page_height
    ):
        raise WorkflowError("移动后元素会超出页面边界，无法执行")

    _assert_within_safe_area(
        layout_plan,
        x=x,
        y=y,
        width=width,
        height=height,
    )

    return x, y, width, height


def reduce_text_content(text: str, *, reduce_lines: int | None = None) -> str:
    """Shorten element text by removing trailing lines and compressing wording."""
    from archium.application.slide_repair_policy import smart_shorten_text

    stripped = text.strip()
    if not stripped:
        raise WorkflowError("目标元素没有可缩减的文字内容")

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        lines = [stripped]

    drop_count = max(int(reduce_lines or 1), 1)
    if len(lines) > drop_count:
        candidate = "\n".join(lines[:-drop_count])
    elif len(lines) == 1:
        max(len(lines[0]) - drop_count * 12, 20)
        candidate = lines[0]
    else:
        candidate = lines[0]

    flattened = candidate.replace("\n", " ").strip()
    shortened, applied, reason = smart_shorten_text(flattened, limit=max(len(flattened) - 8, 24))
    if not applied and len(lines) <= drop_count:
        raise WorkflowError(f"无法安全缩减文字：{reason}")
    return shortened if applied else flattened
