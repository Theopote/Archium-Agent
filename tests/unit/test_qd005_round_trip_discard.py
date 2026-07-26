"""QD-005 — Round-trip BLOCKED must not leave delivery PPTX residue."""

from __future__ import annotations

from pathlib import Path

from archium.application.export_round_trip_service import (
    discard_export_on_round_trip_blocked,
)


def test_discard_export_removes_primary_and_legacy_blocked(tmp_path: Path) -> None:
    pptx = tmp_path / "presentation.pptx"
    blocked = tmp_path / "presentation.blocked.pptx"
    pptx.write_bytes(b"PK-fake")
    blocked.write_bytes(b"PK-fake-blocked")

    removed = discard_export_on_round_trip_blocked(pptx)

    assert not pptx.exists()
    assert not blocked.exists()
    assert pptx in removed or any(p.name == "presentation.pptx" for p in removed)
    assert any(p.name.endswith(".blocked.pptx") for p in removed)


def test_discard_export_noop_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "presentation.pptx"
    assert discard_export_on_round_trip_blocked(missing) == []


def test_export_panel_does_not_keep_blocked_half_product() -> None:
    source = Path("archium/ui/studio/export_panel.py").read_text(encoding="utf-8")
    assert "discard_export_on_round_trip_blocked" in source
    assert ".blocked.pptx" not in source or "撤销" in source
    # Must not rename-to-.blocked as the BLOCKED success path
    assert "file_path.replace(blocked_path)" not in source
    assert 'qa_status="blocked"' not in source.split("if rt_report.status == RoundTripStatus.BLOCKED")[1].split(
        "manifest = manifest.model_copy"
    )[0]
