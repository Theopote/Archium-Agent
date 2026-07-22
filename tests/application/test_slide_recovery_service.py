"""Tests for SlideRecoveryService."""

from __future__ import annotations

import pytest

from archium.application.slide_recovery_service import (
    SlideRecoveryRequest,
    SlideRecoveryService,
    evaluate_recovery_metrics,
)
from archium.domain.export_fidelity import ExportFidelityLevel
from archium.domain.slide_recovery import SlideRecoveryPageKind
from archium.infrastructure.slide_recovery.scene_region_adapter import regions_from_render_scene
from tests.spike.slide_recovery_fixtures import SPIKE_SCENES


@pytest.fixture
def service() -> SlideRecoveryService:
    return SlideRecoveryService(session=None)


@pytest.mark.parametrize(
    ("page_kind", "expected_fidelity"),
    [
        (SlideRecoveryPageKind.TITLE, ExportFidelityLevel.FULLY_EDITABLE),
        (SlideRecoveryPageKind.IMAGE_TEXT, ExportFidelityLevel.FULLY_EDITABLE),
        (SlideRecoveryPageKind.TABLE, ExportFidelityLevel.FULLY_EDITABLE),
        (SlideRecoveryPageKind.PHOTO, ExportFidelityLevel.FULLY_EDITABLE),
        (SlideRecoveryPageKind.DRAWING_DOMINANT, ExportFidelityLevel.FULLY_EDITABLE),
    ],
)
def test_recover_page_meets_spike_targets(
    service: SlideRecoveryService,
    page_kind: SlideRecoveryPageKind,
    expected_fidelity: ExportFidelityLevel,
) -> None:
    source = SPIKE_SCENES[page_kind]
    result = service.recover_page(
        SlideRecoveryRequest(
            source_page_id=f"spike_{page_kind.value}",
            source_scene=source,
            page_kind=page_kind,
        )
    )
    assert result.recovered_scene_id is not None
    assert result.hybrid_scene is not None
    assert result.metrics is not None
    assert result.metrics.meets_spike_targets()
    assert result.reconstruction_fidelity == expected_fidelity
    assert not result.blockers


def test_drawing_kept_whole(service: SlideRecoveryService) -> None:
    source = SPIKE_SCENES[SlideRecoveryPageKind.DRAWING_DOMINANT]
    result = service.recover_page(
        SlideRecoveryRequest(
            source_page_id="drawing",
            source_scene=source,
            page_kind=SlideRecoveryPageKind.DRAWING_DOMINANT,
        )
    )
    assert result.metrics is not None
    assert result.metrics.drawing_integrity_ok
    drawing_regions = [r for r in result.visual_regions if r.region_type == "drawing"]
    assert len(drawing_regions) == 1
    assert drawing_regions[0].keep_whole_drawing is True


def test_degradation_marks_hybrid(service: SlideRecoveryService) -> None:
    source = SPIKE_SCENES[SlideRecoveryPageKind.IMAGE_TEXT]
    result = service.recover_page(
        SlideRecoveryRequest(
            source_page_id="degraded",
            source_scene=source,
            page_kind=SlideRecoveryPageKind.IMAGE_TEXT,
            position_noise=0.03,
            drop_text_ratio=0.5,
        )
    )
    assert result.metrics is not None
    assert not result.metrics.meets_spike_targets()
    assert result.reconstruction_fidelity != ExportFidelityLevel.FULLY_EDITABLE
    assert result.warnings or result.blockers


def test_table_bitmap_fallback(service: SlideRecoveryService) -> None:
    source = SPIKE_SCENES[SlideRecoveryPageKind.TABLE]
    result = service.recover_page(
        SlideRecoveryRequest(
            source_page_id="table_bitmap",
            source_scene=source,
            page_kind=SlideRecoveryPageKind.TABLE,
            force_table_bitmap=True,
        )
    )
    assert result.reconstruction_fidelity == ExportFidelityLevel.HYBRID_EDITABLE
    assert any("混合可编辑" in warning for warning in result.warnings)
    table_regions = [r for r in result.visual_regions if r.region_type == "table"]
    assert len(table_regions) == 1
    assert table_regions[0].bitmap_fallback is True


def test_regions_partition_counts() -> None:
    source = SPIKE_SCENES[SlideRecoveryPageKind.DRAWING_DOMINANT]
    regions = regions_from_render_scene(source)
    assert any(region.region_type == "text" for region in regions)
    assert any(region.region_type == "drawing" for region in regions)
    assert any(region.region_type == "line" for region in regions)


def test_evaluate_metrics_identity() -> None:
    source = SPIKE_SCENES[SlideRecoveryPageKind.TITLE]
    regions = regions_from_render_scene(source)
    metrics = evaluate_recovery_metrics(source, source, regions)
    assert metrics.text_recall == 1.0
    assert metrics.text_position_error == 0.0
