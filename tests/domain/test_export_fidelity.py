"""Tests for export fidelity domain types."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.export_fidelity import (
    DeckExportManifest,
    ExportFidelityLevel,
    ExportPolicy,
    SlideExportResult,
    policy_allows_fidelity,
    worst_fidelity,
)


def test_worst_fidelity_picks_most_degraded() -> None:
    levels = [
        ExportFidelityLevel.FULLY_EDITABLE,
        ExportFidelityLevel.HYBRID_EDITABLE,
        ExportFidelityLevel.FULLY_EDITABLE,
    ]
    assert worst_fidelity(levels) == ExportFidelityLevel.HYBRID_EDITABLE


def test_strict_policy_blocks_raster() -> None:
    policy = ExportPolicy()
    assert policy_allows_fidelity(policy, ExportFidelityLevel.FULLY_EDITABLE) is True
    assert policy_allows_fidelity(policy, ExportFidelityLevel.HYBRID_EDITABLE) is True
    assert policy_allows_fidelity(policy, ExportFidelityLevel.RASTER_FALLBACK) is False


def test_manifest_summary_lines_zh() -> None:
    slide_a = SlideExportResult(
        slide_id=uuid4(),
        fidelity_level=ExportFidelityLevel.FULLY_EDITABLE,
    )
    slide_b = SlideExportResult(
        slide_id=uuid4(),
        fidelity_level=ExportFidelityLevel.HYBRID_EDITABLE,
    )
    manifest = DeckExportManifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        requested_policy=ExportPolicy(),
        final_fidelity=ExportFidelityLevel.HYBRID_EDITABLE,
        slides=[slide_a, slide_b],
        fallback_used=True,
        fallback_reason="hybrid_editable×1",
    )
    lines = manifest.summary_lines_zh()
    assert any("支持范围内可编辑" in line and "1" in line for line in lines)
    assert any("混合可编辑" in line for line in lines)
