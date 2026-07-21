"""Unit tests for presentation agent helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.agents._helpers import (
    brief_from_draft,
    sanitize_slide_message,
    slides_from_plan,
    storyline_from_draft,
)
from archium.domain.enums import PresentationType, SlideType
from archium.infrastructure.llm.presentation_schemas import (
    BriefDraft,
    SlideDraft,
    SlidePlanDraft,
    StorylineDraft,
)
from sqlalchemy.orm import Session


def test_sanitize_slide_message_truncates_multi_sentence() -> None:
    long_msg = "第一句。第二句。第三句。第四句。"
    result = sanitize_slide_message(long_msg)
    assert result == "第一句。"


def test_sanitize_slide_message_keeps_short_message() -> None:
    msg = "现有交通组织无法满足需求。"
    assert sanitize_slide_message(msg) == msg


def test_brief_from_draft_maps_fields() -> None:
    project_id = uuid4()
    presentation_id = uuid4()
    draft = BriefDraft(
        title="概念汇报",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="甲方",
        purpose="决策",
        core_message="核心信息",
        target_slide_count=10,
    )
    brief = brief_from_draft(
        draft,
        project_id=project_id,
        presentation_id=presentation_id,
        version=2,
    )
    assert brief.title == "概念汇报"
    assert brief.version == 2
    assert brief.presentation_id == presentation_id


def test_storyline_from_draft_maps_chapters() -> None:
    presentation_id = uuid4()
    draft = StorylineDraft.model_validate(
        {
            "thesis": "总体论点",
            "narrative_pattern": "problem_solution",
            "chapters": [
                {
                    "id": "ch1",
                    "title": "现状",
                    "purpose": "问题",
                    "key_message": "痛点",
                    "order": 0,
                    "estimated_slide_count": 3,
                }
            ],
        }
    )
    storyline = storyline_from_draft(draft, presentation_id=presentation_id)
    assert len(storyline.chapters) == 1
    assert storyline.chapters[0].id == "ch1"
    assert storyline.narrative_arc is None


def test_slides_from_plan_sanitizes_messages(db_session: Session) -> None:
    presentation_id = uuid4()
    plan = SlidePlanDraft(
        slides=[
            SlideDraft(
                chapter_id="ch1",
                order=0,
                title="标题",
                message="结论一。结论二。结论三。",
                slide_type=SlideType.CONTENT,
            )
        ]
    )
    slides = slides_from_plan(plan, presentation_id=presentation_id, session=db_session)  # type: ignore[arg-type]
    assert len(slides) == 1
    assert slides[0].message == "结论一。"
