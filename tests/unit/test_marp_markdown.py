"""Unit tests for Marp Markdown generation."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from archium.agents._helpers import brief_from_draft, slides_from_plan, storyline_from_draft
from archium.infrastructure.llm.presentation_schemas import (
    BriefDraft,
    SlidePlanDraft,
    StorylineDraft,
)
from archium.infrastructure.renderers.marp_markdown import build_marp_markdown

from tests.fixtures.mock_presentation_responses import BRIEF_JSON, SLIDE_PLAN_JSON, STORYLINE_JSON


def test_build_marp_markdown_includes_front_matter_and_slides(db_session: Session) -> None:
    project_id = uuid4()
    presentation_id = uuid4()
    brief = brief_from_draft(
        BriefDraft.model_validate_json(BRIEF_JSON),
        project_id=project_id,
        presentation_id=presentation_id,
    )
    storyline = storyline_from_draft(
        StorylineDraft.model_validate_json(STORYLINE_JSON),
        presentation_id=presentation_id,
    )
    slides = slides_from_plan(
        SlidePlanDraft.model_validate_json(SLIDE_PLAN_JSON),
        presentation_id=presentation_id,
        session=db_session,
    )

    markdown = build_marp_markdown(brief, storyline, slides)

    assert markdown.startswith("---\nmarp: true\n")
    assert "老院区更新概念汇报" in markdown
    assert "总体论点" in markdown
    assert "院区现状" in markdown
    assert markdown.count("\n---\n") >= len(slides) + 1
    assert "来源：" in markdown
    assert "视觉需求：" in markdown


def test_build_marp_markdown_preserves_slide_order(db_session: Session) -> None:
    presentation_id = uuid4()
    brief = brief_from_draft(
        BriefDraft.model_validate_json(BRIEF_JSON),
        project_id=uuid4(),
        presentation_id=presentation_id,
    )
    storyline = storyline_from_draft(
        StorylineDraft.model_validate_json(STORYLINE_JSON),
        presentation_id=presentation_id,
    )
    slides = slides_from_plan(
        SlidePlanDraft.model_validate_json(SLIDE_PLAN_JSON),
        presentation_id=presentation_id,
        session=db_session,
    )

    markdown = build_marp_markdown(brief, storyline, slides)
    first_index = markdown.index("院区现状")
    second_index = markdown.index("核心问题")
    assert first_index < second_index
