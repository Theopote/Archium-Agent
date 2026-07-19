"""Unit tests for planned-vs-available UI labeling helpers."""

from __future__ import annotations

from archium.domain.visual.enums import LayoutFamily
from archium.ui import layout_family_ui
from archium.ui.availability_labels import (
    COMING_SOON_SUFFIX,
    append_coming_soon_suffix,
    format_availability_suffix,
)
from archium.ui.layout_family_ui import (
    format_layout_family_label,
    layout_family_availability_status,
)


def test_append_coming_soon_suffix_is_idempotent() -> None:
    base = "混合画布"
    once = append_coming_soon_suffix(base)
    twice = append_coming_soon_suffix(once)
    assert once.endswith(COMING_SOON_SUFFIX)
    assert once == twice


def test_format_availability_suffix() -> None:
    assert format_availability_suffix(available=True, available_label="可自动生成") == " · 可自动生成"
    assert format_availability_suffix(available=False) == " · 即将支持"


def test_format_layout_family_label_marks_planned(monkeypatch) -> None:
    monkeypatch.setattr(
        layout_family_ui,
        "layout_family_implemented",
        lambda family: family != LayoutFamily.HYBRID_CANVAS,
    )
    assert "即将支持" not in format_layout_family_label(LayoutFamily.HERO)
    assert "即将支持" in format_layout_family_label(LayoutFamily.HYBRID_CANVAS)


def test_layout_family_availability_status(monkeypatch) -> None:
    monkeypatch.setattr(
        layout_family_ui,
        "layout_family_implemented",
        lambda family: family == LayoutFamily.HERO,
    )
    assert layout_family_availability_status(LayoutFamily.HERO) == "可用"
    assert layout_family_availability_status(LayoutFamily.EVIDENCE_BOARD) == "即将支持"


def test_all_registered_families_are_implemented_for_now() -> None:
    assert not layout_family_ui.planned_layout_family_definitions()
    assert len(layout_family_ui.implemented_layout_family_definitions()) == len(LayoutFamily)
