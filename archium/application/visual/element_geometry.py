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
    margin = min(layout_plan.page_width, layout_plan.page_height) * 0.05
    width = element.width
    height = element.height

    if canonical == "absolute":
        if absolute_x is None or absolute_y is None:
            raise WorkflowError("absolute move requires x and y coordinates")
        x = absolute_x
        y = absolute_y
    elif canonical == "right":
        x = layout_plan.page_width * 0.52
        y = element.y
    elif canonical == "left":
        x = margin
        y = element.y
    elif canonical == "top":
        x = element.x
        y = margin
    elif canonical == "bottom":
        x = element.x
        y = layout_plan.page_height - height - margin
    elif canonical == "center":
        x = (layout_plan.page_width - width) / 2
        y = (layout_plan.page_height - height) / 2
    else:
        raise WorkflowError(f"Unsupported placement: {canonical}")

    if (
        x < 0
        or y < 0
        or x + width > layout_plan.page_width
        or y + height > layout_plan.page_height
    ):
        raise WorkflowError("移动后元素会超出页面边界，无法执行")

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
        limit = max(len(lines[0]) - drop_count * 12, 20)
        candidate = lines[0]
    else:
        candidate = lines[0]

    flattened = candidate.replace("\n", " ").strip()
    shortened, applied, reason = smart_shorten_text(flattened, limit=max(len(flattened) - 8, 24))
    if not applied and len(lines) <= drop_count:
        raise WorkflowError(f"无法安全缩减文字：{reason}")
    return shortened if applied else flattened
