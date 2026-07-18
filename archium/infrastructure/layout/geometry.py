"""Shared geometry helpers for deterministic layout generators."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.design_system import DesignSystem, PageSystem


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle in page units."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return self.width * self.height

    def inset(self, dx: float, dy: float | None = None) -> Rect:
        pad_y = dx if dy is None else dy
        return Rect(
            x=self.x + dx,
            y=self.y + pad_y,
            width=max(0.01, self.width - 2 * dx),
            height=max(0.01, self.height - 2 * pad_y),
        )

    def overlaps(self, other: Rect, *, tolerance: float = 0.0) -> bool:
        return not (
            self.right <= other.x + tolerance
            or other.right <= self.x + tolerance
            or self.bottom <= other.y + tolerance
            or other.bottom <= self.y + tolerance
        )


def page_rect(page: PageSystem) -> Rect:
    return Rect(0.0, 0.0, page.width, page.height)


def safe_area(design_system: DesignSystem) -> Rect:
    """Return the content-safe rectangle from DesignSystem page margins."""
    page = design_system.page
    footer = design_system.footer_style.height if design_system.footer_style.enabled else 0.0
    return Rect(
        x=page.margin_left,
        y=page.margin_top,
        width=page.content_width,
        height=max(0.01, page.content_height - footer),
    )


def column_width(safe: Rect, *, columns: int, gutter: float, span: int = 1) -> float:
    if columns < 1 or span < 1:
        raise ValueError("columns and span must be >= 1")
    total_gutter = gutter * (columns - 1)
    unit = (safe.width - total_gutter) / columns
    return unit * span + gutter * (span - 1)


def grid_column_rect(
    safe: Rect,
    *,
    columns: int,
    gutter: float,
    start_col: int,
    span: int,
    y: float,
    height: float,
) -> Rect:
    """Return a rect spanning ``span`` columns starting at 0-based ``start_col``."""
    unit = column_width(safe, columns=columns, gutter=gutter, span=1)
    x = safe.x + start_col * (unit + gutter)
    width = column_width(safe, columns=columns, gutter=gutter, span=span)
    return Rect(x=x, y=y, width=width, height=height)


def split_horizontal(rect: Rect, *, left_ratio: float, gap: float) -> tuple[Rect, Rect]:
    left_w = max(0.01, (rect.width - gap) * left_ratio)
    right_w = max(0.01, rect.width - gap - left_w)
    left = Rect(rect.x, rect.y, left_w, rect.height)
    right = Rect(rect.x + left_w + gap, rect.y, right_w, rect.height)
    return left, right


def split_vertical(rect: Rect, *, top_ratio: float, gap: float) -> tuple[Rect, Rect]:
    top_h = max(0.01, (rect.height - gap) * top_ratio)
    bottom_h = max(0.01, rect.height - gap - top_h)
    top = Rect(rect.x, rect.y, rect.width, top_h)
    bottom = Rect(rect.x, rect.y + top_h + gap, rect.width, bottom_h)
    return top, bottom


def grid_cells(
    rect: Rect,
    *,
    rows: int,
    cols: int,
    gap_x: float,
    gap_y: float,
) -> list[Rect]:
    """Return row-major grid cells inside ``rect``."""
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")
    cell_w = (rect.width - gap_x * (cols - 1)) / cols
    cell_h = (rect.height - gap_y * (rows - 1)) / rows
    cells: list[Rect] = []
    for row in range(rows):
        for col in range(cols):
            cells.append(
                Rect(
                    x=rect.x + col * (cell_w + gap_x),
                    y=rect.y + row * (cell_h + gap_y),
                    width=cell_w,
                    height=cell_h,
                )
            )
    return cells


def occupied_area(rects: list[Rect]) -> float:
    return sum(rect.area for rect in rects)


def whitespace_ratio(page: PageSystem, occupied: float) -> float:
    total = page.width * page.height
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - occupied / total))
