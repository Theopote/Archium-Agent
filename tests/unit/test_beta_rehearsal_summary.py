"""Tests for Beta rehearsal summary script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.summarize_beta_rehearsal import summarize_root


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


def test_new_beta_session_writes_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.new_beta_session as new_session

    monkeypatch.setattr(new_session, "_SESSIONS_ROOT", tmp_path)
    assert new_session.main(["demo-b10"]) == 0
    meta = json.loads((tmp_path / "demo-b10" / "session-meta.json").read_text(encoding="utf-8"))
    assert meta["session_id"] == "demo-b10"
    assert meta["participants"][0]["is_non_developer"] is True
    assert (tmp_path / "demo-b10" / "beta-edit-cost-sheet.csv").exists()
