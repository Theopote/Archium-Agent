"""Unit tests for SlideRecoveryDeliveryService helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from archium.application.slide_recovery_delivery_service import SlideRecoveryDeliveryService


def test_resolve_source_preview_path_prefers_preview_image(tmp_path: Path) -> None:
    preview = tmp_path / "preview.png"
    preview.write_bytes(b"png")
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")

    service = SlideRecoveryDeliveryService.__new__(SlideRecoveryDeliveryService)
    result = SimpleNamespace(
        workflow_run=SimpleNamespace(
            state={
                "preview_image_path": str(preview),
                "source_path": str(source),
            }
        )
    )
    assert service.resolve_source_preview_path(result) == preview


def test_resolve_source_preview_path_ignores_non_image_source(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("notes")

    service = SlideRecoveryDeliveryService.__new__(SlideRecoveryDeliveryService)
    result = SimpleNamespace(
        workflow_run=SimpleNamespace(state={"source_path": str(notes)})
    )
    assert service.resolve_source_preview_path(result) is None
