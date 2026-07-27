"""Unit tests for deck content placeholder cards."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole
from archium.ui.studio.deck_content_placeholder import content_placeholder_html


def test_content_placeholder_html_includes_title_and_role() -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="problem",
        order=2,
        title="问题与机遇",
        message="人车混行是基地核心矛盾",
        slide_role=SlideRole.PROBLEM_ANALYSIS,
    )
    html_out = content_placeholder_html(index=2, slide=slide, accent_color="#d92d20")
    assert "问题与机遇" in html_out
    assert "问题分析" in html_out
    assert "P3" in html_out
    assert "人车混行" in html_out
