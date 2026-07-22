"""Shared Streamlit pages for ``st.navigation`` and ``st.page_link``."""

from __future__ import annotations

from typing import Any

import streamlit as st

from archium.ui.product_flow import (
    MAKE_SECTION,
    PROJECT_SECTION,
    RESOURCE_SECTION,
    SYSTEM_SECTION,
    primary_stages,
)

_PAGES: dict[str, Any] = {}


def build_app_pages() -> dict[str, list[Any]]:
    """Create navigation sections (项目 / 制作 / 资源 / 系统) and cache pages for links."""
    from archium.ui.pages import (
        command_center,
        home,
        project_management,
        project_mission,
        settings,
        studio,
        template_induction,
        template_library,
        template_studio,
        visual_design,
        workspace,
    )
    from archium.ui.pages.flow import (
        deliver,
        edit,
        generate,
        materials,
        outline,
    )

    stages = primary_stages()
    stage_pages = {
        "materials": st.Page(
            materials.render,
            title=stages[0].title,
            icon=stages[0].icon,
            url_path="materials",
        ),
        "outline": st.Page(
            outline.render,
            title=stages[1].title,
            icon=stages[1].icon,
            url_path="outline",
        ),
        "generate": st.Page(
            generate.render,
            title=stages[2].title,
            icon=stages[2].icon,
            url_path="generate",
        ),
        "edit": st.Page(
            edit.render,
            title=stages[3].title,
            icon=stages[3].icon,
            url_path="edit",
        ),
        "deliver": st.Page(
            deliver.render,
            title=stages[4].title,
            icon=stages[4].icon,
            url_path="deliver",
        ),
    }

    home_page = st.Page(
        home.render,
        title="概览",
        icon="🏛️",
        url_path="home",
        default=True,
    )
    project_page = st.Page(
        project_management.render,
        title="项目",
        icon="📁",
        url_path="project-management",
    )
    template_library_page = st.Page(
        template_library.render,
        title="模板库",
        icon="🧩",
        url_path="template-library",
    )
    settings_page = st.Page(settings.render, title="设置", icon="⚙️", url_path="settings")

    # Hidden from sidebar but kept for deep links / st.page_link / st.switch_page.
    hidden_pages = {
        "project-mission": st.Page(
            project_mission.render,
            title="项目任务",
            icon="🧭",
            url_path="project-mission",
        ),
        "studio": st.Page(studio.render, title="工作室", icon="🎬", url_path="studio"),
        "template-studio": st.Page(
            template_studio.render,
            title="模板工作室",
            icon="🧩",
            url_path="template-studio",
        ),
        "template-induction": st.Page(
            template_induction.render,
            title="模板归纳",
            icon="🔬",
            url_path="template-induction",
        ),
        "workspace": st.Page(workspace.render, title="项目工作台", icon="📂", url_path="workspace"),
        "visual-design": st.Page(
            visual_design.render,
            title="视觉设计",
            icon="🎨",
            url_path="visual-design",
        ),
        "command-center": st.Page(
            command_center.render,
            title="指令中心",
            icon="💬",
            url_path="command-center",
        ),
    }

    _PAGES.clear()
    _PAGES.update({"home": home_page})
    _PAGES.update({"project-management": project_page})
    _PAGES.update(stage_pages)
    _PAGES.update({"template-library": template_library_page})
    _PAGES.update({"settings": settings_page})
    _PAGES.update(hidden_pages)
    # Aliases so older links keep working while primary flow uses stage keys.
    _PAGES["studio"] = hidden_pages["studio"]
    _PAGES.setdefault("edit", stage_pages["edit"])

    return {
        PROJECT_SECTION: [home_page, project_page],
        MAKE_SECTION: [
            stage_pages["materials"],
            stage_pages["outline"],
            stage_pages["generate"],
            stage_pages["edit"],
            stage_pages["deliver"],
        ],
        RESOURCE_SECTION: [template_library_page],
        SYSTEM_SECTION: [settings_page],
    }


def get_app_page(key: str) -> Any:
    """Return a registered ``st.Page`` object for ``st.page_link``."""
    if not _PAGES:
        # Sidebar / early chrome may link before ``st.navigation(build_app_pages())``.
        build_app_pages()
    page = _PAGES.get(key)
    if page is None:
        msg = f"Unknown app page: {key}"
        raise KeyError(msg)
    return page
