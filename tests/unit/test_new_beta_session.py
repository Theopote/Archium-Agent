"""Tests for Beta session scaffolding script."""

from __future__ import annotations

from pathlib import Path

from scripts.new_beta_session import main


def test_new_beta_session_creates_csv_templates(tmp_path: Path, monkeypatch: object) -> None:
    import scripts.new_beta_session as mod

    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(mod, "_SESSIONS_ROOT", sessions_root)
    monkeypatch.setattr(mod, "_TEMPLATES", Path(__file__).resolve().parents[2] / "docs" / "templates")

    assert main(["test-session-001"]) == 0
    session = sessions_root / "test-session-001"
    assert (session / "beta-edit-cost-sheet.csv").exists()
    assert (session / "beta-issue-triage.csv").exists()
    assert (session / "README.txt").exists()
