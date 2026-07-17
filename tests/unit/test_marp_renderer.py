"""Unit tests for MarpPresentationRenderer."""

from __future__ import annotations

from uuid import uuid4

from archium.agents._helpers import brief_from_draft, slides_from_plan, storyline_from_draft
from archium.infrastructure.llm.presentation_schemas import (
    BriefDraft,
    SlidePlanDraft,
    StorylineDraft,
)
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer
from sqlalchemy.orm import Session

from tests.fixtures.mock_presentation_responses import BRIEF_JSON, SLIDE_PLAN_JSON, STORYLINE_JSON


def test_marp_renderer_writes_markdown_file(test_settings: object, db_session: Session) -> None:
    presentation_id = uuid4()
    project_id = uuid4()
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

    renderer = MarpPresentationRenderer(test_settings)  # type: ignore[arg-type]
    markdown_path = renderer.render(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=slides,
    )

    assert markdown_path.name == "presentation.md"
    assert markdown_path.exists()
    content = markdown_path.read_text(encoding="utf-8")
    assert "marp: true" in content
    assert "老院区更新概念汇报" in content
