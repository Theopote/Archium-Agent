"""Preview and adopt web images from the Asset Board."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.image_search_settings_service import ImageSearchSettingsService
from archium.application.web_image_preview_service import WebImagePreviewService
from archium.config.settings import get_settings
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.image_search_settings import session_pexels_api_key, session_unsplash_api_key


def render_web_image_preview_panel(
    *,
    project_id: UUID,
    presentation_id: UUID,
    slide: SlideSpec,
    requirement: VisualRequirement,
    requirement_index: int,
    web_search_eligible: bool,
) -> None:
    if not web_search_eligible:
        return

    st.markdown("**网络搜图预览**")
    st.caption("先预览授权图候选，确认后再写入素材库并绑定到本页视觉需求。")

    preview_key = f"web_preview_{presentation_id}_{slide.id}_{requirement_index}"
    cache_key = f"{preview_key}_result"

    with get_session() as session:
        preferences = ImageSearchSettingsService(session).get_preferences(
            base_settings=get_settings(),
        )
        preview_service = WebImagePreviewService(
            session,
            pexels_session_api_key=session_pexels_api_key(),
            unsplash_session_api_key=session_unsplash_api_key(),
            image_search_preferences=preferences,
        )
        configured = preview_service.configured

    if not configured:
        st.info("请先在 **设置 → 网络搜图** 配置 Pexels 或 Unsplash API Key。")
        return

    if st.button("检索预览", key=f"{preview_key}_search", use_container_width=True):
        with get_session() as session:
            service = WebImagePreviewService(
                session,
                pexels_session_api_key=session_pexels_api_key(),
                unsplash_session_api_key=session_unsplash_api_key(),
                image_search_preferences=ImageSearchSettingsService(session).get_preferences(
                    base_settings=get_settings(),
                ),
            )
            result = service.preview_requirement(slide, requirement)
        if result is None or not result.items:
            st.warning("未找到合适的授权配图，请调整页面标题/需求描述后重试。")
            st.session_state.pop(cache_key, None)
        else:
            st.session_state[cache_key] = result
            st.success(f"已检索到 {len(result.items)} 张候选图（关键词：{result.query}）")

    result = st.session_state.get(cache_key)
    if result is None:
        return

    st.caption(f"检索关键词：`{result.query}`")
    columns = st.columns(min(len(result.items), 3))
    for index, item in enumerate(result.items):
        column = columns[index % len(columns)]
        with column:
            st.image(
                item.candidate.download_url,
                caption=f"{item.provider} · {item.candidate.attribution}",
                use_container_width=True,
            )
            if st.button(
                "采用此图",
                key=f"{preview_key}_adopt_{index}",
                use_container_width=True,
            ):
                try:
                    with get_session() as session:
                        service = WebImagePreviewService(
                            session,
                            pexels_session_api_key=session_pexels_api_key(),
                            unsplash_session_api_key=session_unsplash_api_key(),
                            image_search_preferences=ImageSearchSettingsService(session).get_preferences(
                                base_settings=get_settings(),
                            ),
                        )
                        service.adopt_candidate(
                            project_id,
                            slide.id,
                            requirement_index,
                            item=item,
                            search_query=result.query,
                            confirm=True,
                        )
                    st.session_state.pop(cache_key, None)
                    st.success("已采用配图并确认匹配。")
                    st.rerun()
                except (WorkflowError, ValueError) as exc:
                    st.error(str(exc))
