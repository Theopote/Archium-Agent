"""Storyline-aware left rail for Presentation Studio."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

import streamlit as st

from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Storyline
from archium.infrastructure.database.session import get_session
from archium.ui.page_status_board_panel import status_badge
from archium.ui.studio.slide_navigator import (
    _resolve_selected_index,
    _set_selected_slide,
    _status_by_slide,
    render_slide_navigator,
)
from archium.ui.studio_service import StudioPresentationContext


@dataclass(frozen=True)
class StudioNarrativeBundle:
    outline: OutlinePlan | None
    storyline: Storyline | None
    thesis: str = ""


def load_studio_narrative(presentation_id: UUID) -> StudioNarrativeBundle:
    from archium.application.review_service import PresentationReviewService

    with get_session() as session:
        context = PresentationReviewService(session).get_review_context(presentation_id)
    if context is None:
        return StudioNarrativeBundle(outline=None, storyline=None)
    storyline = context.storyline
    thesis = ""
    if storyline is not None:
        thesis = (storyline.thesis or storyline.narrative_pattern or "").strip()
    elif context.outline is not None:
        thesis = (context.outline.title or "").strip()
    return StudioNarrativeBundle(
        outline=context.outline,
        storyline=storyline,
        thesis=thesis,
    )


def _chapter_meta_map(bundle: StudioNarrativeBundle) -> dict[str, tuple[str, str, str]]:
    """chapter_id → (title, purpose, key_message)."""
    meta: dict[str, tuple[str, str, str]] = {}
    if bundle.storyline is not None:
        for chapter in bundle.storyline.chapters:
            meta[str(chapter.id)] = (
                chapter.title,
                (chapter.purpose or "").strip(),
                (chapter.key_message or "").strip(),
            )
    if bundle.outline is not None:
        for section in bundle.outline.sections:
            meta.setdefault(
                str(section.id),
                (section.title, (getattr(section, "purpose", "") or "").strip(), ""),
            )
    return meta


def _chapter_title_map(bundle: StudioNarrativeBundle) -> dict[str, str]:
    return {cid: title for cid, (title, _, _) in _chapter_meta_map(bundle).items()}


def group_slide_indices_by_chapter(
    context: StudioPresentationContext,
    bundle: StudioNarrativeBundle,
) -> list[tuple[str, str, list[int]]]:
    """Return ordered (chapter_id, chapter_title, slide_indices)."""
    titles = _chapter_title_map(bundle)
    groups: OrderedDict[str, list[int]] = OrderedDict()
    for index, item in enumerate(context.snapshot.slides):
        chapter_id = str(getattr(item.slide, "chapter_id", "") or "ungrouped")
        groups.setdefault(chapter_id, []).append(index)
    result: list[tuple[str, str, list[int]]] = []
    for chapter_id, indices in groups.items():
        title = titles.get(chapter_id) or (
            "未分组" if chapter_id == "ungrouped" else f"章节 {chapter_id[:8]}"
        )
        result.append((chapter_id, title, indices))
    return result


def render_storyline_navigator(
    *,
    context: StudioPresentationContext,
    bundle: StudioNarrativeBundle | None = None,
) -> int:
    """Left rail: storyline chapters → pages (falls back to flat list)."""
    narrative = bundle or load_studio_narrative(context.presentation.id)
    groups = group_slide_indices_by_chapter(context, narrative)
    slides = context.snapshot.slides
    if not slides:
        st.caption("当前汇报还没有页面。")
        return 0

    # If only one ungrouped bucket and no storyline/outline titles, use flat navigator.
    if (
        len(groups) == 1
        and groups[0][0] == "ungrouped"
        and narrative.storyline is None
        and (narrative.outline is None or not narrative.outline.sections)
    ):
        return render_slide_navigator(context=context)

    st.markdown("**故事线**")
    if narrative.thesis:
        st.caption(narrative.thesis[:160])

    try:
        from archium.ui.app_navigation import get_app_page

        st.page_link(
            get_app_page("outline"),
            label="编辑故事线 / 页意图",
            icon=":material/account_tree:",
        )
    except Exception:
        from archium.logging import get_logger

        get_logger(__name__).debug(
            'storyline page link unavailable',
            exc_info=True,
        )

    mode = st.radio(
        "导航",
        options=["按章节", "全部页面"],
        horizontal=True,
        key=f"studio_nav_mode_{context.presentation.id}",
        label_visibility="collapsed",
    )
    if mode == "全部页面":
        return render_slide_navigator(context=context)

    status_map = _status_by_slide(context)
    selected_index = _resolve_selected_index(slides, status_map)
    chapter_meta = _chapter_meta_map(narrative)

    for chapter_id, title, indices in groups:
        purpose, key_message = "", ""
        if chapter_id in chapter_meta:
            _, purpose, key_message = chapter_meta[chapter_id]
        with st.expander(
            f"{title} · {len(indices)} 页",
            expanded=selected_index in indices,
        ):
            if purpose:
                st.caption(f"目的：{purpose[:100]}")
            if key_message:
                st.caption(f"关键信息：{key_message[:100]}")
            for index in indices:
                item = slides[index]
                slide = item.slide
                row = status_map.get(str(slide.id))
                badge = status_badge(row) if row is not None else ""
                role = getattr(slide, "slide_role", None)
                role_bit = ""
                if role is not None:
                    from archium.ui.label_map import slide_role_label

                    role_bit = f" · {slide_role_label(role)}"
                label = f"P{index + 1}  {slide.title or '未命名'}{role_bit}"
                if badge:
                    label = f"{label}  {badge}"
                if st.button(
                    label,
                    key=f"studio_story_page_{context.presentation.id}_{chapter_id}_{index}",
                    use_container_width=True,
                    type="primary" if index == selected_index else "secondary",
                ):
                    _set_selected_slide(index)
                    st.rerun()
    return selected_index
