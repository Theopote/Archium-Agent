"""Genesis starter draft card — outline preview + navigation."""

from __future__ import annotations

import html
from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.genesis_starter_service import GenesisStarterResult
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page


def _load_cover_preview(presentation_id: UUID) -> tuple[str, str] | None:
    with get_session() as session:
        slides = PresentationRepository(session).list_slides(presentation_id)
    if not slides:
        return None
    slide = sorted(slides, key=lambda item: item.order)[0]
    return (slide.title or "封面", (slide.message or "").strip())


def _load_outline_sections(presentation_id: UUID) -> list[tuple[str, str]]:
    with get_session() as session:
        repo = PresentationRepository(session)
        outlines = repo.list_outlines(presentation_id)
        if not outlines:
            return []
        outline = outlines[0]
    sections = sorted(outline.sections, key=lambda item: item.order)
    return [(section.title, section.key_message) for section in sections[:8]]


def _resolve_cover_preview_path(result: GenesisStarterResult) -> str | None:
    if result.cover_preview_path and Path(result.cover_preview_path).is_file():
        return result.cover_preview_path
    if not result.has_cover_layout:
        return None
    from archium.application.genesis_cover_layout_service import cover_wireframe_preview_path

    with get_session() as session:
        return cover_wireframe_preview_path(session, result.presentation_id)


def render_genesis_draft_card(result: GenesisStarterResult, *, compact: bool = False) -> None:
    """Show starter outline summary, wireframe/content preview, and navigation CTAs."""
    st.markdown("**大纲草稿已就绪**")
    st.caption(result.summary)
    if result.slides_ready_count > 0 and result.page_count > 0:
        st.caption(f"内容占位：{result.slides_ready_count}/{result.page_count} 页")

    sections = _load_outline_sections(result.presentation_id)
    if sections:
        chips = " · ".join(html.escape(title) for title, _ in sections[:6])
        if len(sections) > 6:
            chips += f" · +{len(sections) - 6}"
        st.caption(f"结构：{chips}")

    preview_path = _resolve_cover_preview_path(result)
    if preview_path is not None:
        st.image(preview_path, caption="P1 · 版式线框预览", use_container_width=True)
    else:
        preview = _load_cover_preview(result.presentation_id)
        if preview is not None:
            title, message = preview
            st.markdown(
                f'<div style="padding:0.75rem 1rem;border:1px solid #e8e6e1;border-radius:2px;'
                f'background:#faf9f7;margin:0.35rem 0 0.65rem 0;">'
                f'<div style="font-weight:600;font-size:0.95rem;">{html.escape(title)}</div>'
                f'<div style="color:#5a5248;font-size:0.85rem;margin-top:0.35rem;">'
                f"{html.escape(message[:200])}</div>"
                f'<div style="color:#8a8780;font-size:0.72rem;margin-top:0.5rem;">P1 · 内容草稿预览</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    if compact:
        return

    project_id = st.session_state.get("selected_project_id")
    cols = st.columns(3)
    with cols[0]:
        if st.button(
            "进入工作室",
            key=f"genesis_draft_studio_{result.presentation_id}",
            use_container_width=True,
            type="primary",
        ):
            if project_id:
                st.session_state.selected_project_id = str(project_id)
            st.session_state.selected_presentation_id = str(result.presentation_id)
            st.session_state.studio_selected_slide_index = 0
            st.session_state.studio_genesis_welcome = result.summary
            st.switch_page(get_app_page("edit"))
    with cols[1]:
        if st.button(
            "查看大纲",
            key=f"genesis_draft_outline_{result.presentation_id}",
            use_container_width=True,
        ):
            if project_id:
                st.session_state.selected_project_id = str(project_id)
            st.session_state.selected_presentation_id = str(result.presentation_id)
            st.switch_page(get_app_page("outline"))
    with cols[2]:
        if st.button(
            "继续生成",
            key=f"genesis_draft_generate_{result.presentation_id}",
            use_container_width=True,
        ):
            if project_id:
                st.session_state.selected_project_id = str(project_id)
            st.session_state.selected_presentation_id = str(result.presentation_id)
            st.switch_page(get_app_page("generate"))
