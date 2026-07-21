"""Derive ordered slide slots before per-page SlideSpec generation."""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide_asset_binding import (
    SlideAssetBinding,
    format_page_asset_bindings_block,
    index_page_asset_bindings,
)
from archium.domain.slide_intent import SlideIntent, format_slide_intent_card, index_slide_intents


@dataclass(frozen=True)
class SlidePlanSlot:
    """One planned page position before LLM fills SlideSpec content."""

    chapter_id: str
    order: int
    section_title: str
    page_intent: str
    deck_position: int
    deck_total: int
    slide_intent: SlideIntent | None = None
    asset_bindings: tuple[SlideAssetBinding, ...] = field(default_factory=tuple)

    @property
    def intent_card_text(self) -> str:
        if self.slide_intent is None:
            return ""
        return format_slide_intent_card(self.slide_intent)

    @property
    def asset_bindings_text(self) -> str:
        return format_page_asset_bindings_block(list(self.asset_bindings))


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

    intent_by_order = index_slide_intents(outline.page_intents if outline is not None else [])
    bindings_by_order = index_page_asset_bindings(
        outline.page_asset_bindings if outline is not None else []
    )
    total = len(slots)
    return [
        _slot_with_page_controls(
            slot,
            index=index,
            total=total,
            intent=intent_by_order.get(index),
            bindings=tuple(bindings_by_order.get(index, [])),
        )
        for index, slot in enumerate(slots)
    ]


def _slot_with_page_controls(
    slot: SlidePlanSlot,
    *,
    index: int,
    total: int,
    intent: SlideIntent | None,
    bindings: tuple[SlideAssetBinding, ...],
) -> SlidePlanSlot:
    page_intent = intent.effective_page_intent() if intent is not None else slot.page_intent
    chapter_id = slot.chapter_id
    if intent is not None and intent.chapter_id.strip():
        chapter_id = intent.chapter_id.strip()
    return SlidePlanSlot(
        chapter_id=chapter_id,
        order=index,
        section_title=slot.section_title,
        page_intent=page_intent,
        deck_position=index,
        deck_total=total,
        slide_intent=intent,
        asset_bindings=bindings,
    )
