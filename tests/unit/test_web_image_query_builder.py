"""Tests for web image search query builder."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.images.web_search.query_builder import build_search_query


def test_build_search_query_includes_visual_type_hint() -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="主入口效果图",
        message="展示立面材质",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.RENDERING,
                description="主入口透视",
                required=True,
            )
        ],
    )
    query = build_search_query(slide, slide.visual_requirements[0])
    assert "architecture rendering" in query
    assert "主入口透视" in query
    assert "主入口效果图" in query
