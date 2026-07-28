"""Tests for Beta rehearsal summary script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.summarize_beta_rehearsal import compute_product_kpis, summarize_root


def test_summarize_template_example_rows(tmp_path: Path) -> None:
    session = tmp_path / "demo-session"
    session.mkdir()
    (session / "beta-edit-cost-sheet.csv").write_text(
        (Path(__file__).resolve().parents[2] / "docs/templates/beta-edit-cost-sheet.csv").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (session / "beta-issue-triage.csv").write_text(
        (Path(__file__).resolve().parents[2] / "docs/templates/beta-issue-triage.csv").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    summary = summarize_root(tmp_path)
    assert summary["participants_non_dev"] >= 1
    assert float(summary["total_edit_minutes"]) > 0
    assert summary["open_beta_blocker_count"] >= 1
    assert summary["beta_ready_by_user_data"] is False

    payload = json.loads(json.dumps(summary))
    assert payload["sessions"][0]["minutes_by_category"]["text"] == 3.0
    assert "product_kpis" in payload
    assert "keep_rate" in payload["product_kpis"]
    assert payload["product_kpis"]["kpi_pass"] is False


def test_product_kpis_keep_rate_and_severe_layout() -> None:
    rows = [
        {
            "slide_index": "1",
            "edit_category": "text",
            "minutes_spent": "0",
            "blocking_export": "no",
        },
        {
            "slide_index": "2",
            "edit_category": "text",
            "minutes_spent": "0",
            "blocking_export": "no",
        },
        {
            "slide_index": "3",
            "edit_category": "layout",
            "minutes_spent": "2",
            "blocking_export": "no",
        },
        {
            "slide_index": "4",
            "edit_category": "layout",
            "minutes_spent": "5",
            "blocking_export": "yes",
        },
    ]
    kpis = compute_product_kpis(rows, expected_deck_slides=4)
    assert kpis["keep_slides"] == 2
    assert kpis["keep_rate"] == 0.5
    assert kpis["severe_layout_errors"] == 1
    assert kpis["avg_minutes_per_slide"] == 1.75
    assert kpis["deck_edit_minutes"] == 7.0
    assert kpis["kpi_checks"]["severe_layout_errors"] is False
    assert kpis["kpi_pass"] is False


def test_product_kpis_pass_when_targets_met() -> None:
    rows = [
        {
            "slide_index": str(i),
            "edit_category": "text",
            "minutes_spent": "0" if i <= 12 else "1.5",
            "blocking_export": "no",
        }
        for i in range(1, 21)
    ]
    kpis = compute_product_kpis(rows, expected_deck_slides=20)
    assert kpis["keep_rate"] == 0.6
    assert kpis["avg_minutes_per_slide"] == 0.6
    assert kpis["severe_layout_errors"] == 0
    assert kpis["deck_edit_minutes"] == 12.0
    assert kpis["slide_coverage"] == 1.0
    assert kpis["kpi_pass"] is True


def test_new_beta_session_writes_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.new_beta_session as new_session

    monkeypatch.setattr(new_session, "_SESSIONS_ROOT", tmp_path)
    assert new_session.main(["demo-b10"]) == 0
    meta = json.loads((tmp_path / "demo-b10" / "session-meta.json").read_text(encoding="utf-8"))
    assert meta["session_id"] == "demo-b10"
    assert meta["participants"][0]["is_non_developer"] is True
    assert (tmp_path / "demo-b10" / "beta-edit-cost-sheet.csv").exists()
