"""Shared Streamlit pages for ``st.navigation`` and ``st.page_link``."""

from __future__ import annotations

from typing import Any

import streamlit as st

_PAGES: dict[str, Any] = {}


def build_app_pages() -> list[Any]:
    """Create navigation pages once and cache them for cross-page links."""
    from archium.ui.pages import (
        command_center,
        home,
        project_mission,
        settings,
        studio,
        visual_design,
        workspace,
    )

    pages = [
        st.Page(home.render, title="首页", icon="🏛️", url_path="home", default=True),
        st.Page(
            project_mission.render,
            title="项目任务",
            icon="🧭",
            url_path="project-mission",
        ),
        st.Page(studio.render, title="汇报工作室", icon="🎬", url_path="studio"),
        st.Page(workspace.render, title="项目工作台", icon="📁", url_path="workspace"),
        st.Page(
            visual_design.render,
            title="视觉设计",
            icon="🎨",
            url_path="visual-design",
        ),
        st.Page(settings.render, title="设置", icon="⚙️", url_path="settings"),
        st.Page(
            command_center.render,
            title="指令中心",
            icon="💬",
            url_path="command-center",
        ),
    ]
    _PAGES.clear()
    _PAGES.update(
        {
            "home": pages[0],
            "project-mission": pages[1],
            "studio": pages[2],
            "workspace": pages[3],
            "visual-design": pages[4],
            "settings": pages[5],
            "command-center": pages[6],
        }
    )
    return pages


def get_app_page(key: str) -> Any:
    """Return a registered ``st.Page`` object for ``st.page_link``."""
    page = _PAGES.get(key)
    if page is None:
        msg = f"Unknown app page: {key}"
        raise KeyError(msg)
    return page
