"""Helpers for visual workflow validation routing."""

from __future__ import annotations

from typing import Any

_BLOCKING = frozenset({"critical", "error"})


def report_has_blocking_issues(report: dict[str, Any]) -> bool:
    """Return True when a validation report payload has ERROR or CRITICAL issues."""
    issues = report.get("issues") or []
    if any(str(issue.get("severity", "")).lower() in _BLOCKING for issue in issues):
        return True
    if report.get("has_critical"):
        return True
    # valid=False with no issue list still blocks (e.g. missing plan).
    return bool(report.get("valid") is False and not issues)


def reports_blocking_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify a list of validation report payloads for workflow routing."""
    blocking_reports = [item for item in reports if report_has_blocking_issues(item)]
    has_soft_issues = any(
        any(
            str(issue.get("severity", "")).lower() in {"warning", "info"}
            for issue in (item.get("issues") or [])
        )
        for item in reports
    )
    return {
        "has_blocking": bool(blocking_reports),
        "blocking_count": len(blocking_reports),
        "warning_only": (not blocking_reports) and has_soft_issues,
        "blocking_plan_ids": [
            str(item.get("layout_plan_id"))
            for item in blocking_reports
            if item.get("layout_plan_id")
        ],
        "blocking_slide_ids": [
            str(item.get("slide_id"))
            for item in blocking_reports
            if item.get("slide_id")
        ],
    }


def format_blocking_warnings(reports: list[dict[str, Any]]) -> list[str]:
    """Human-readable warnings for blocked layout issues."""
    messages: list[str] = []
    for item in reports:
        if not report_has_blocking_issues(item):
            continue
        plan_id = str(item.get("layout_plan_id", "?"))[:8]
        codes = sorted(
            {
                str(issue.get("rule_code"))
                for issue in (item.get("issues") or [])
                if str(issue.get("severity", "")).lower() in _BLOCKING
            }
        )
        messages.append(
            f"LayoutPlan {plan_id}… blocked by {', '.join(codes) or 'ERROR/CRITICAL'}"
        )
    return messages
