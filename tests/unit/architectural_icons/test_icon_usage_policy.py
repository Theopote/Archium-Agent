"""Tests for IconUsagePolicy gating."""

from __future__ import annotations

from archium.application.visual.icon_selection_service import IconSelectionService
from archium.application.visual.icon_usage import (
    filter_icon_refs,
    icons_allowed_for_family,
    max_icons_for_family,
)
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.icon_usage_policy import default_icon_usage_policy
from archium.domain.visual.slide_capacity_budget import CapacityStatus, SlideCapacityBudget


def test_drawing_pages_forbid_icons() -> None:
    assert icons_allowed_for_family(LayoutFamily.DRAWING_FOCUS) is False
    assert icons_allowed_for_family(LayoutFamily.EVIDENCE_BOARD) is False
    assert icons_allowed_for_family(LayoutFamily.METRIC_DASHBOARD) is True
    assert icons_allowed_for_family(LayoutFamily.PROCESS_NARRATIVE) is True


def test_filter_icon_refs_clamps_and_strips() -> None:
    refs = [f"icon:a{i}" for i in range(10)]
    limited = filter_icon_refs(refs, layout_family=LayoutFamily.METRIC_DASHBOARD)
    assert len(limited) <= default_icon_usage_policy().max_icons_metric_dashboard
    assert filter_icon_refs(refs, layout_family=LayoutFamily.DRAWING_FOCUS) == []


def test_filter_removes_when_capacity_overloaded() -> None:
    refs = ["icon:pedestrian_flow", "icon:parking"]
    budget = SlideCapacityBudget(
        usable_width=9.0,
        usable_height=4.5,
        estimated_text_height=5.0,
        image_area_required=0.0,
        annotation_area_required=0.0,
        capacity_ratio=1.4,
        overflow_risk=1.0,
        status=CapacityStatus.OVERLOADED,
        recommended_action="adapt_content",
    )
    assert filter_icon_refs(refs, layout_family=LayoutFamily.METRIC_DASHBOARD, capacity=budget) == []


def test_filter_removes_on_high_density() -> None:
    refs = ["icon:pedestrian_flow"]
    assert (
        filter_icon_refs(
            refs,
            layout_family=LayoutFamily.PROCESS_NARRATIVE,
            expected_density="high",
        )
        == []
    )


def test_selection_respects_drawing_family_ban() -> None:
    result = IconSelectionService().select(
        "pedestrian_flow",
        layout_family=LayoutFamily.DRAWING_FOCUS,
    )
    assert result.match is None
    assert any("forbidden" in note for note in result.notes)


def test_max_icons_by_family() -> None:
    assert max_icons_for_family(LayoutFamily.METRIC_DASHBOARD) <= 4
    assert max_icons_for_family(LayoutFamily.PROCESS_NARRATIVE) <= 5
