"""Unit tests for visual validation routing (P0: no silent invalid export)."""

from __future__ import annotations

from archium.workflow.visual_graph import _route_after_validation
from archium.workflow.visual_validation_routing import (
    report_has_blocking_issues,
    reports_blocking_summary,
)


def test_blocking_issue_detection() -> None:
    assert report_has_blocking_issues(
        {
            "valid": False,
            "issues": [{"severity": "error", "rule_code": "LAYOUT.ELEMENT_OVERLAP"}],
        }
    )
    assert report_has_blocking_issues(
        {
            "valid": False,
            "issues": [{"severity": "critical", "rule_code": "LAYOUT.ELEMENT_OUTSIDE_PAGE"}],
        }
    )
    assert not report_has_blocking_issues(
        {
            "valid": True,
            "issues": [{"severity": "warning", "rule_code": "LAYOUT.HERO_NOT_DOMINANT"}],
        }
    )


def test_route_after_validation_repairs_then_fallback_then_review() -> None:
    blocking_reports = [
        {
            "layout_plan_id": "p1",
            "slide_id": "s1",
            "valid": False,
            "issues": [{"severity": "error", "rule_code": "LAYOUT.TEXT_OVERFLOW"}],
        }
    ]
    assert (
        _route_after_validation(
            {
                "validation_reports": blocking_reports,
                "repair_round": 0,
                "max_repair_rounds": 1,
                "fallback_applied": False,
            }
        )
        == "repair"
    )
    assert (
        _route_after_validation(
            {
                "validation_reports": blocking_reports,
                "repair_round": 1,
                "max_repair_rounds": 1,
                "fallback_applied": False,
            }
        )
        == "fallback"
    )
    assert (
        _route_after_validation(
            {
                "validation_reports": blocking_reports,
                "repair_round": 1,
                "max_repair_rounds": 1,
                "fallback_applied": True,
            }
        )
        == "await_review"
    )


def test_route_after_validation_allows_warning_only_render() -> None:
    reports = [
        {
            "layout_plan_id": "p1",
            "valid": True,
            "issues": [{"severity": "warning", "rule_code": "LAYOUT.HERO_NOT_DOMINANT"}],
        }
    ]
    summary = reports_blocking_summary(reports)
    assert not summary["has_blocking"]
    assert summary["warning_only"]
    assert (
        _route_after_validation(
            {
                "validation_reports": reports,
                "repair_round": 0,
                "max_repair_rounds": 1,
                "fallback_applied": False,
            }
        )
        == "render"
    )


def test_route_after_validation_valid_renders() -> None:
    assert (
        _route_after_validation(
            {
                "validation_reports": [{"valid": True, "issues": []}],
                "repair_round": 0,
                "max_repair_rounds": 1,
                "fallback_applied": False,
            }
        )
        == "render"
    )
