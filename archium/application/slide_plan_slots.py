"""Derive ordered slide slots before per-page SlideSpec generation."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline


@dataclass(frozen=True)
class SlidePlanSlot:
    """One planned page position before LLM fills SlideSpec content."""

    chapter_id: str
    order: int
    section_title: str
    page_intent: str
    deck_position: int
    deck_total: int


def build_slide_plan_slots(
    brief: PresentationBrief,
    storyline: Storyline,
    *,
    outline: OutlinePlan | None = None,
) -> list[SlidePlanSlot]:
    """Expand outline/storyline into one slot per page (bounded deck size)."""
    slots: list[SlidePlanSlot] = []
    order = 0

    if outline is not None and outline.sections:
        for section in sorted(outline.sections, key=lambda item: item.order):
            if not section.expanded:
                continue
            page_count = section.estimated_slide_count
            if section.required and page_count < 1:
                page_count = 1
            if page_count <= 0:
                continue
            for page_index in range(page_count):
                intent = section.key_message
                if page_index > 0:
                    intent = f"{section.key_message}（第 {page_index + 1} 页补充）"
                slots.append(
                    SlidePlanSlot(
                        chapter_id=section.id,
                        order=order,
                        section_title=section.title,
                        page_intent=intent,
                        deck_position=len(slots),
                        deck_total=0,
                    )
                )
                order += 1
    elif storyline.chapters:
        remaining = brief.target_slide_count
        chapters = sorted(storyline.chapters, key=lambda item: item.order)
        for chapter in chapters:
            if remaining <= 0:
                break
            count = min(max(chapter.estimated_slide_count, 1), remaining)
            for page_index in range(count):
                intent = chapter.key_message
                if page_index > 0:
                    intent = f"{chapter.key_message}（第 {page_index + 1} 页补充）"
                slots.append(
                    SlidePlanSlot(
                        chapter_id=chapter.id,
                        order=order,
                        section_title=chapter.title,
                        page_intent=intent,
                        deck_position=len(slots),
                        deck_total=0,
                    )
                )
                order += 1
                remaining -= 1

    if not slots:
        for index in range(brief.target_slide_count):
            slots.append(
                SlidePlanSlot(
                    chapter_id="ch1",
                    order=index,
                    section_title=brief.title,
                    page_intent=brief.core_message,
                    deck_position=index,
                    deck_total=0,
                )
            )

    # Trim or pad to target_slide_count
    target = brief.target_slide_count
    if len(slots) > target:
        slots = slots[:target]
    elif len(slots) < target:
        last = slots[-1] if slots else None
        for index in range(len(slots), target):
            slots.append(
                SlidePlanSlot(
                    chapter_id=last.chapter_id if last else "ch1",
                    order=index,
                    section_title=last.section_title if last else brief.title,
                    page_intent=brief.core_message,
                    deck_position=index,
                    deck_total=0,
                )
            )

    total = len(slots)
    return [
        SlidePlanSlot(
            chapter_id=slot.chapter_id,
            order=slot.order,
            section_title=slot.section_title,
            page_intent=slot.page_intent,
            deck_position=index,
            deck_total=total,
        )
        for index, slot in enumerate(slots)
    ]
