"""Unit tests for Presentation Studio label helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.ui.label_map import content_pipeline_chain, entity_label, field_label
from archium.ui.studio_service import StudioPresentationContext, studio_readiness_label
from archium.ui.visual_service import PresentationVisualSnapshot


def test_entity_label_user_mode() -> None:
    assert entity_label("SlideSpec") == "页面内容"
    assert entity_label("LayoutPlan") == "页面版式"


def test_content_pipeline_chain() -> None:
    assert "汇报要求" in content_pipeline_chain()
    assert "Brief" not in content_pipeline_chain()


def test_visual_pipeline_chain() -> None:
    from archium.ui.label_map import visual_pipeline_chain, visual_quality_pair

    assert "视觉方向" in visual_pipeline_chain()
    assert "整套一致性检查" in visual_quality_pair()


def test_entity_label_advanced_mode() -> None:
    assert entity_label("SlideSpec", advanced=True) == "SlideSpec"


def test_field_label_user_mode() -> None:
    assert field_label("title") == "标题"
    assert field_label("layout_family") == "版式类型"


@pytest.mark.parametrize(
    ("slide_count", "layout_ready_count", "ready_for_export", "expected"),
    [
        (0, 0, False, "empty"),
        (3, 0, False, "needs_visual"),
        (3, 2, False, "has_issues"),
        (3, 3, True, "ready"),
    ],
)
def test_studio_readiness_label(
    slide_count: int,
    layout_ready_count: int,
    ready_for_export: bool,
    expected: str,
) -> None:
    from archium.domain.presentation import Presentation
    from archium.domain.project import Project

    project_id = uuid4()
    context = StudioPresentationContext(
        project=Project(name="Demo"),
        presentation=Presentation(project_id=project_id, title="Test Deck"),
        snapshot=PresentationVisualSnapshot(presentation_id=uuid4()),
        ready_for_export=ready_for_export,
        slide_count=slide_count,
        layout_ready_count=layout_ready_count,
        preview_ready_count=0,
    )
    assert studio_readiness_label(context) == expected
