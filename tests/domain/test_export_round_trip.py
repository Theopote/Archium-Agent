"""Tests for export round-trip domain models."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.export_round_trip import (
    ExportRoundTripReport,
    RoundTripStatus,
)


def test_round_trip_report_summary_lines() -> None:
    report = ExportRoundTripReport(
        presentation_id=uuid4(),
        text_match_rate=0.8,
        geometry_match_rate=0.9,
        similarity_score=0.88,
        status=RoundTripStatus.NEEDS_REVIEW,
        drawing_integrity_issues=["plan:fit_mode=cover"],
        blockers=[],
    )
    lines = report.summary_lines_zh()
    assert any("80%" in line for line in lines)
    assert report.qa_status_value() == "needs_review"
