"""Unit tests for slide plan slot expansion."""

from __future__ import annotations

from uuid import uuid4

from archium.application.slide_plan_slots import build_slide_plan_slots
from archium.domain.enums import PresentationType
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Chapter, PresentationBrief, Storyline


def _brief(target_slide_count: int = 4) -> PresentationBrief:
    presentation_id = uuid4()
    return PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="老院区更新",
        audience="院领导",
        purpose="决策",
        core_message="改善交通",
        target_slide_count=target_slide_count,
        presentation_type=PresentationType.CLIENT_REVIEW,
    )


def _storyline(presentation_id) -> Storyline:
    return Storyline(
        presentation_id=presentation_id,
        thesis="交通重组",
        chapters=[
            Chapter(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="人车混行",
                order=0,
                estimated_slide_count=2,
            ),
            Chapter(
                id="ch2",
                title="策略",
                purpose="方案",
                key_message="环形车道",
                order=1,
                estimated_slide_count=2,
            ),
        ],
    )


def test_slots_follow_outline_section_counts() -> None:
    brief = _brief(target_slide_count=4)
    storyline = _storyline(brief.presentation_id)
    outline = OutlinePlan(
        presentation_id=brief.presentation_id,
        title=brief.title,
        thesis="交通重组",
        audience=brief.audience,
        purpose=brief.purpose,
        sections=[
            OutlineSection(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="人车混行",
                order=0,
                estimated_slide_count=2,
            ),
            OutlineSection(
                id="ch2",
                title="策略",
                purpose="方案",
                key_message="环形车道",
                order=1,
                estimated_slide_count=2,
            ),
        ],
    )

    slots = build_slide_plan_slots(brief, storyline, outline=outline)

    assert len(slots) == 4
    assert slots[0].chapter_id == "ch1"
    assert slots[0].order == 0
    assert slots[-1].deck_total == 4


def test_slots_trim_to_target_slide_count() -> None:
    brief = _brief(target_slide_count=3)
    storyline = _storyline(brief.presentation_id)
    slots = build_slide_plan_slots(brief, storyline)
    assert len(slots) == 3
    assert all(slot.deck_total == 3 for slot in slots)
