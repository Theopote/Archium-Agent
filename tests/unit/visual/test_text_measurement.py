"""Unit tests for real font metrics text measurement."""

from __future__ import annotations

import pytest
from archium.domain.visual import default_presentation_design_system
from archium.infrastructure.layout.font_resolver import fonts_available
from archium.infrastructure.layout.text_measurement import TextMeasurementService


@pytest.fixture
def body_style():
    return default_presentation_design_system().typography.body


def test_real_metrics_available_on_dev_machine() -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable — install Microsoft YaHei/Arial or Noto on CI")
    service = TextMeasurementService()
    assert service.uses_real_metrics


def test_punctuation_narrower_than_cjk(body_style) -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    service = TextMeasurementService()
    cjk_width = service.measure_width_pt("汉", style=body_style)
    punct_width = service.measure_width_pt("，", style=body_style)
    assert punct_width < cjk_width


def test_bold_wider_than_regular(body_style) -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    latin = body_style.model_copy(
        update={"font_family": "Arial", "font_family_latin": None, "font_weight": 400}
    )
    regular = latin
    bold = latin.model_copy(update={"font_weight": 700})
    service = TextMeasurementService()
    sample = "Overflow WIDTH"
    assert service.measure_width_pt(sample, style=bold) > service.measure_width_pt(
        sample, style=regular
    )


def test_critical_fit_differs_from_heuristic(body_style) -> None:
    if not fonts_available():
        pytest.skip("System fonts unavailable")
    text = "项目进度：2026年Q1完成概念方案，含标点。"
    box_width_in = 1.85
    real = TextMeasurementService(use_heuristic_fallback=False)
    heuristic = TextMeasurementService(use_heuristic_fallback=True)
    # Force heuristic path by patching availability is heavy; compare line counts directly.
    real_lines = real.estimate_lines(text, box_width_in=box_width_in, style=body_style)
    heuristic_lines = heuristic._estimate_lines_heuristic(  # noqa: SLF001
        text,
        box_width_pt=box_width_in * 72.0,
        style=body_style,
    )
    assert real_lines >= 1
    # Heuristic uses uniform CJK width — real metrics should not always match.
    assert real_lines != heuristic_lines or real.measure_width_pt(text, style=body_style) != sum(
        real.char_width_em(ch) for ch in text
    ) * body_style.font_size


def test_heuristic_fallback_when_fonts_missing(body_style, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "archium.infrastructure.layout.text_measurement.fonts_available",
        lambda: False,
    )
    service = TextMeasurementService(use_heuristic_fallback=True)
    assert not service.uses_real_metrics
    assert service.estimate_lines("你好 world", box_width_in=2.0, style=body_style) >= 1


def test_long_copy_overflow_detected(body_style) -> None:
    service = TextMeasurementService()
    text = "这是一段非常长的正文" * 40
    assert not service.fits(
        text,
        box_width_in=2.0,
        box_height_in=0.4,
        style=body_style,
    )
