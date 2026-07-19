"""Unit tests for derived real-project acceptance human metrics."""

from __future__ import annotations

from archium.application.project_acceptance_metrics import derive_acceptance_human_metrics


def test_derive_metrics_from_clean_deck() -> None:
    derived = derive_acceptance_human_metrics(
        slide_count=20,
        critical_layout_page_count=0,
        error_layout_page_count=0,
        validation_reports=[{"score": 1.0, "issues": []} for _ in range(20)],
        first_generation_seconds=12.0,
    )
    assert derived["major_edit_page_ratio"] == 0.0
    assert derived["exported_page_ratio"] == 1.0
    assert derived["average_human_visual_score"] >= 3.5
    assert derived["user_edit_minutes"] >= 2.0


def test_derive_metrics_counts_major_and_minor_pages() -> None:
    reports = [
        {"score": 0.4, "issues": [{"severity": "error", "rule_code": "LAYOUT.TEXT_OVERFLOW"}]},
        {"score": 0.9, "issues": [{"severity": "warning", "rule_code": "LAYOUT.WHITESPACE_LOW"}]},
        {"score": 1.0, "issues": []},
    ]
    derived = derive_acceptance_human_metrics(
        slide_count=3,
        critical_layout_page_count=0,
        error_layout_page_count=1,
        validation_reports=reports,
        first_generation_seconds=5.0,
    )
    assert derived["major_edit_page_ratio"] == round(1 / 3, 3)
    assert derived["minor_edit_page_ratio"] == round(1 / 3, 3)
    assert derived["exported_page_ratio"] == round(2 / 3, 3)
