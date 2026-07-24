"""DOM-006: LayoutFamily controlled vocabulary."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.slide_design_brief import SlideDesignBrief
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.layout_family_normalize import (
    coerce_layout_family,
    layout_family_value,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene
from pydantic import ValidationError


def test_coerce_aliases_and_unset() -> None:
    assert coerce_layout_family("") is None
    assert coerce_layout_family(None) is None
    assert coerce_layout_family("photo_evidence_grid") == LayoutFamily.EVIDENCE_BOARD
    assert coerce_layout_family("HERO") == LayoutFamily.HERO
    assert layout_family_value(LayoutFamily.HERO) == "hero"
    assert layout_family_value(None) == ""


def test_coerce_rejects_illegal_family() -> None:
    with pytest.raises(ValueError, match="unknown layout_family"):
        coerce_layout_family("not_a_real_family")


def test_brief_rejects_illegal_layout_family() -> None:
    with pytest.raises(ValidationError):
        SlideDesignBrief(
            page_order=0,
            page_task="任务",
            layout_family="not_a_real_family",
        )


def test_brief_coerces_alias_and_blank() -> None:
    aliased = SlideDesignBrief(
        page_order=0,
        page_task="任务",
        layout_family="photo_evidence_grid",
    )
    assert aliased.layout_family == LayoutFamily.EVIDENCE_BOARD
    blank = SlideDesignBrief(page_order=1, page_task="任务", layout_family="")
    assert blank.layout_family is None


def test_render_scene_source_layout_family_typed() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=13.333,
        page_height=7.5,
        background=BackgroundStyle(color="#FFFFFF"),
        source_layout_family="drawing_focus",
    )
    assert scene.source_layout_family == LayoutFamily.DRAWING_FOCUS
    with pytest.raises(ValidationError):
        RenderScene(
            slide_id=uuid4(),
            layout_plan_id=uuid4(),
            page_width=13.333,
            page_height=7.5,
            background=BackgroundStyle(color="#FFFFFF"),
            source_layout_family="template-layout-name",
        )
