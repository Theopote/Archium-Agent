"""Unit tests for deterministic text emphasis runs."""

from __future__ import annotations

from archium.application.visual.text_emphasis import build_emphasis_text_runs
from archium.domain.visual.defaults import default_presentation_design_system


def test_emphasis_marks_bullet_prefix_and_metric() -> None:
    runs = build_emphasis_text_runs(
        "01. 容积率控制在 2.5 以内",
        base_color="#132533",
        accent_color="#C45C26",
    )
    assert len(runs) >= 3
    assert runs[0].text.startswith("01.")
    assert runs[0].font_weight == 700
    assert runs[0].color == "#C45C26"
    metric = next(run for run in runs if "2.5" in run.text)
    assert metric.color == "#C45C26"
    assert metric.font_weight == 700


def test_emphasis_marks_keywords_and_lead_clause() -> None:
    runs = build_emphasis_text_runs(
        "核心策略：以南沙蓝绿骨架重建港产城关系。",
        base_color="#132533",
        accent_color="#C45C26",
        emphasize_lead_clause=True,
    )
    texts = "".join(run.text for run in runs)
    assert "核心策略" in texts
    accented = [run for run in runs if run.color == "#C45C26"]
    assert accented
    assert any("核心" in run.text or "策略" in run.text for run in accented)


def test_default_design_system_is_tinted_not_office_white() -> None:
    design = default_presentation_design_system()
    bg = design.colors.background.upper()
    assert bg not in {"#FFFFFF", "#FFF", "FFFFFF"}
    # Cool board tint — visibly off-white.
    assert bg.startswith("#D") or bg.startswith("#C") or bg.startswith("#E")
    assert design.typography.title.font_size <= 22
    assert design.typography.display.font_size <= 30
    assert design.typography.body.font_size == 14
    assert design.colors.accent.upper() != design.colors.primary_text.upper()
