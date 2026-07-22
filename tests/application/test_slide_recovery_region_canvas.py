"""Tests for slide recovery region canvas, merge, and split."""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.application.slide_recovery_region_canvas import (
    apply_canvas_move,
    apply_canvas_resize,
    layout_plan_from_regions,
    merge_regions,
    split_region,
)
from archium.application.slide_recovery_region_edit_service import normalize_bbox
from archium.domain.slide_recovery import NormalizedBox, RecoveredPageRegion
from archium.exceptions import WorkflowError


def _text_region(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    role: str = "body",
) -> RecoveredPageRegion:
    return RecoveredPageRegion(
        id=uuid4(),
        bbox=NormalizedBox(x=x, y=y, width=width, height=height),
        region_type="text",
        semantic_role=role,
        recovered_text=text,
    )


def test_layout_plan_from_regions_maps_normalized_boxes() -> None:
    regions = [
        _text_region(x=0.1, y=0.2, width=0.3, height=0.1, text="标题", role="title"),
    ]
    plan = layout_plan_from_regions(regions)
    element = plan.elements[0]
    assert element.x == pytest.approx(1.0)
    assert element.y == pytest.approx(1.125)
    assert element.width == pytest.approx(3.0)
    assert element.height == pytest.approx(0.5625)


def test_apply_canvas_move_updates_region_bbox() -> None:
    region = _text_region(x=0.1, y=0.2, width=0.3, height=0.1, text="A")
    plan = layout_plan_from_regions([region])
    moved = apply_canvas_move(region, plan, x_percent=20.0, y_percent=30.0)
    assert moved.bbox.x == pytest.approx(0.2)
    assert moved.bbox.y == pytest.approx(0.3)
    assert moved.bbox.width == pytest.approx(0.3)


def test_apply_canvas_resize_updates_region_bbox() -> None:
    region = _text_region(x=0.1, y=0.2, width=0.3, height=0.1, text="A")
    plan = layout_plan_from_regions([region])
    resized = apply_canvas_resize(
        region,
        plan,
        x_percent=10.0,
        y_percent=20.0,
        width_percent=40.0,
        height_percent=15.0,
    )
    assert resized.bbox.x == pytest.approx(0.1)
    assert resized.bbox.y == pytest.approx(0.2)
    assert resized.bbox.width == pytest.approx(0.4)
    assert resized.bbox.height == pytest.approx(0.15)


def test_merge_regions_builds_union_bbox_and_joins_text() -> None:
    first = _text_region(x=0.1, y=0.1, width=0.2, height=0.1, text="左")
    second = _text_region(x=0.35, y=0.15, width=0.2, height=0.1, text="右")
    merged = merge_regions([first, second], [first.id, second.id])
    assert len(merged) == 1
    region = merged[0]
    assert region.bbox.x == pytest.approx(0.1)
    assert region.bbox.y == pytest.approx(0.1)
    assert region.bbox.width == pytest.approx(0.45)
    assert region.bbox.height == pytest.approx(0.15)
    assert region.recovered_text == "左\n右"


def test_merge_regions_requires_two_ids() -> None:
    region = _text_region(x=0.1, y=0.1, width=0.2, height=0.1, text="单")
    with pytest.raises(WorkflowError, match="两个"):
        merge_regions([region], [region.id])


def test_split_region_vertical_and_horizontal() -> None:
    region = _text_region(x=0.2, y=0.2, width=0.6, height=0.4, text="左右拆分测试")
    left, right = split_region(region, axis="vertical", ratio=0.5)
    assert left.bbox.width == pytest.approx(0.3)
    assert right.bbox.x == pytest.approx(0.5)
    assert right.bbox.width == pytest.approx(0.3)

    top, bottom = split_region(region, axis="horizontal", ratio=0.4)
    assert top.bbox.height == pytest.approx(0.16)
    assert bottom.bbox.y == pytest.approx(0.36)
    assert bottom.bbox.height == pytest.approx(0.24)


def test_split_region_splits_text_near_boundary() -> None:
    region = _text_region(
        x=0.1,
        y=0.1,
        width=0.8,
        height=0.2,
        text="第一段，第二段",
    )
    left, right = split_region(region, axis="vertical", ratio=0.5)
    assert left.recovered_text == "第一段"
    assert right.recovered_text == "第二段"
