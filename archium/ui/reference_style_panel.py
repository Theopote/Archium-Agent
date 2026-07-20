"""Streamlit panel for reference style profiles."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.reference_style_service import (
    has_reference_style_documents,
    validate_reference_style_profile,
)
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.database.session import get_session


def render_reference_style_panel(project_id: UUID) -> None:
    st.markdown("#### 参考风格提炼")
    st.caption("从标记为「参考风格」的资料中提炼视觉语言，供 ArtDirection 借鉴（非项目事实）。")

    with get_session() as session:
        projects = ProjectRepository(session)
        project = projects.get_by_id(project_id)
        profiles = projects.list_reference_style_profiles(project_id)
        has_style_docs = has_reference_style_documents(session, project_id)

    if project is None:
        st.warning("项目不存在")
        return

    if not has_style_docs and not profiles:
        return

    if not profiles:
        st.info("已标记参考风格文件，运行汇报生成后将自动提炼视觉语言。")
        return

    profile = profiles[0]
    st.markdown(f"**风格名称：** {profile.style_name}")
    if profile.mood_keywords:
        st.markdown("**语气关键词：** " + " · ".join(profile.mood_keywords))

    cols = st.columns(3)
    cols[0].metric("色彩线索", len(profile.color_cues))
    cols[1].metric("排版线索", len(profile.typography_cues))
    cols[2].metric("版式线索", len(profile.layout_cues))

    issues = validate_reference_style_profile(profile)
    if issues:
        with st.expander(f"质量提示（{len(issues)}）", expanded=True):
            for issue in issues[:10]:
                st.markdown(f"- {issue}")

    if profile.do_rules:
        with st.expander("建议遵循"):
            for rule in profile.do_rules:
                st.markdown(f"- {rule}")

    if profile.dont_rules:
        with st.expander("建议避免"):
            for rule in profile.dont_rules:
                st.markdown(f"- {rule}")

    if profile.adaptation_notes:
        with st.expander("借鉴说明"):
            for note in profile.adaptation_notes:
                st.markdown(f"- {note}")

    st.caption(f"版本 v{profile.version} · 关联文件 {len(profile.source_document_ids)} 个")
