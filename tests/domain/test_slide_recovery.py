"""Tests for slide recovery domain models."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.export_fidelity import ExportFidelityLevel
from archium.domain.slide_recovery import (
    NormalizedBox,
    RecoveredPageRegion,
    SlideRecoveryMetrics,
    SlideRecoveryPageKind,
    infer_reconstruction_fidelity,
)


def test_normalized_box_position_error() -> None:
    a = NormalizedBox(x=0.1, y=0.2, width=0.3, height=0.1)
    b = NormalizedBox(x=0.12, y=0.21, width=0.3, height=0.1)
    assert a.position_error_ratio(b) == pytest.approx(0.02, abs=0.001)


def test_normalized_box_rejects_overflow() -> None:
    with pytest.raises(ValueError, match="bbox must fit"):
        NormalizedBox(x=0.9, y=0.1, width=0.2, height=0.1)


def test_metrics_meets_spike_targets() -> None:
    metrics = SlideRecoveryMetrics(
        text_recall=0.99,
        text_position_error=0.01,
        line_recall=0.95,
        drawing_integrity_ok=True,
        similarity_score=0.93,
        asset_identity_preserved=True,
    )
    assert metrics.meets_spike_targets()
    assert infer_reconstruction_fidelity(metrics) == ExportFidelityLevel.FULLY_EDITABLE


def test_infer_hybrid_when_visual_degraded() -> None:
    metrics = SlideRecoveryMetrics(
        text_recall=0.99,
        text_position_error=0.05,
        line_recall=0.95,
        drawing_integrity_ok=True,
        similarity_score=0.88,
        asset_identity_preserved=True,
    )
    assert infer_reconstruction_fidelity(metrics) == ExportFidelityLevel.HYBRID_EDITABLE


def test_recovered_page_region_fields() -> None:
    region = RecoveredPageRegion(
        id=uuid4(),
        bbox=NormalizedBox(x=0.1, y=0.1, width=0.8, height=0.2),
        region_type="drawing",
        semantic_role="site_plan",
        confidence=0.95,
        source_asset_uri="asset://plan.png",
        keep_whole_drawing=True,
    )
    assert region.keep_whole_drawing is True
    assert region.region_type == "drawing"


def test_page_kind_labels() -> None:
    from archium.domain.slide_recovery import PAGE_KIND_LABELS_ZH

    assert PAGE_KIND_LABELS_ZH[SlideRecoveryPageKind.DRAWING_DOMINANT] == "图纸主导页"
