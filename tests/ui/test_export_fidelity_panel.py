"""UI source tests for export fidelity panels."""

from __future__ import annotations

from pathlib import Path


def test_export_policy_panel_source() -> None:
    source = Path("archium/ui/delivery/export_policy_panel.py").read_text(encoding="utf-8")
    assert "strict_native" in source
    assert "allow_raster" in source
    assert "get_session_export_policy" in source


def test_fidelity_report_panel_discloses_fallback() -> None:
    source = Path("archium/ui/delivery/fidelity_report_panel.py").read_text(encoding="utf-8")
    assert "fallback_used" in source
    assert "summary_lines_zh" in source


def test_export_panel_integrates_policy_before_export() -> None:
    source = Path("archium/ui/studio/export_panel.py").read_text(encoding="utf-8")
    assert "build_pre_export_manifest" in source
    assert "enforce_export_policy" in source
    assert "render_export_policy_panel" in source
    assert "ExportRoundTripService" in source


def test_fidelity_panel_shows_round_trip() -> None:
    source = Path("archium/ui/delivery/fidelity_report_panel.py").read_text(encoding="utf-8")
    assert "render_round_trip_report_panel" in source
    assert "Round-trip QA" in source
