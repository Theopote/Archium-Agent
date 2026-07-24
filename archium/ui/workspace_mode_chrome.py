"""Architectural Workspace mode chrome — four-mode posture for the current project."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.workspace_mode_service import (
    WorkspaceModeService,
    profile_for,
    session_mode_override_key,
)
from archium.domain.enums import ArchitecturalWorkspaceMode
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.error_handlers import format_user_error


_MODE_LABELS = {
    ArchitecturalWorkspaceMode.EXISTING_PROJECT: "已有项目",
    ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION: "概念探索",
    ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING: "研究策划",
    ArchitecturalWorkspaceMode.DESIGN_ITERATION: "设计迭代",
}


def resolve_ui_workspace_mode(project_id: UUID) -> ArchitecturalWorkspaceMode:
    key = session_mode_override_key(project_id)
    raw = st.session_state.get(key)
    override = None
    if raw:
        try:
            override = ArchitecturalWorkspaceMode(str(raw))
        except ValueError:
            override = None
    with get_session() as session:
        return WorkspaceModeService(session).resolve_mode(project_id, override=override)


def render_workspace_mode_chrome(project_id: UUID, *, key_prefix: str = "ws_mode") -> None:
    """Show current mode, suggested actions, and optional mode switcher."""
    key = session_mode_override_key(project_id)
    raw = st.session_state.get(key)
    override = None
    if raw:
        try:
            override = ArchitecturalWorkspaceMode(str(raw))
        except ValueError:
            override = None

    try:
        with get_session() as session:
            service = WorkspaceModeService(session)
            profile = service.resolve_profile(project_id, override=override)
            available = service.available_modes(project_id)
    except WorkflowError as exc:
        st.caption(str(exc))
        return
    except Exception as exc:
        st.caption(format_user_error(exc))
        return

    st.info(f"**工作台模式：{profile.title}** — {profile.caption}")
    st.caption(f"当前重心：{profile.focus}")

    cols = st.columns(min(3, max(1, len(profile.suggested_actions))))
    for index, action in enumerate(profile.suggested_actions[:3]):
        cols[index % len(cols)].markdown(f"{index + 1}. {action}")

    if len(available) > 1:
        options = list(available)
        current_index = options.index(profile.mode) if profile.mode in options else 0
        selected = st.selectbox(
            "切换工作台模式",
            options=options,
            index=current_index,
            format_func=lambda item: _MODE_LABELS.get(item, item.value),
            key=f"{key_prefix}_select_{project_id}",
        )
        if selected != profile.mode:
            st.session_state[key] = selected.value
            st.rerun()

    if st.button(
        f"前往：{_primary_label(profile.primary_page_key)}",
        key=f"{key_prefix}_go_{project_id}",
        use_container_width=True,
    ):
        st.switch_page(get_app_page(profile.primary_page_key))


def stage_caption_for_mode(
    stage_id: str,
    mode: ArchitecturalWorkspaceMode | None,
    *,
    default: str,
) -> str:
    if mode is None:
        return default
    return profile_for(mode).stage_captions.get(stage_id, default)


def _primary_label(page_key: str) -> str:
    labels = {
        "materials": "资料",
        "concept-exploration": "概念探索",
        "project-mission": "项目任务",
        "outline": "大纲",
    }
    return labels.get(page_key, page_key)
