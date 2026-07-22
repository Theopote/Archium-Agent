"""Golden calibration for TextMeasurementService real font metrics."""

from __future__ import annotations

import pytest
from archium.domain.visual import default_presentation_design_system
from archium.infrastructure.layout.font_resolver import fonts_available
from archium.infrastructure.layout.text_measurement import TextMeasurementService

_GOLDEN_SAMPLE = "项目进度：2026年Q1完成概念方案，含标点。"
_GOLDEN_BOX_WIDTH_IN = 1.85
_GOLDEN_FONT_SIZE_PT = 12.0


@pytest.mark.unit
def test_measure_width_pt_without_style_uses_real_metrics() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    service = TextMeasurementService()
    with_style = service.measure_width_pt(_GOLDEN_SAMPLE, font_size_pt=_GOLDEN_FONT_SIZE_PT)
    body = default_presentation_design_system().typography.body.model_copy(
        update={"font_size": _GOLDEN_FONT_SIZE_PT}
    )
    styled = service.measure_width_pt(_GOLDEN_SAMPLE, style=body)
    assert with_style == pytest.approx(styled, rel=0.01)
    assert service.uses_real_metrics
    assert with_style > 0


@pytest.mark.unit
def test_golden_line_count_calibration() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    body = default_presentation_design_system().typography.body.model_copy(
        update={"font_size": _GOLDEN_FONT_SIZE_PT}
    )
    service = TextMeasurementService()
    lines = service.estimate_lines(
        _GOLDEN_SAMPLE,
        box_width_in=_GOLDEN_BOX_WIDTH_IN,
        style=body,
    )
    assert 2 <= lines <= 4
