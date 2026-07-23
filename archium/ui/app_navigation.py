"""Shared Streamlit pages for ``st.navigation`` and ``st.page_link``.

Studio page-key contract (see ``product_flow``):
- Primary flow uses ``edit`` (制作 → 工作室).
- ``studio`` remains a hidden deep-link / workbench module entry only.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from archium.ui import icons
from archium.ui.product_flow import (
    LEGACY_STUDIO_PAGE_KEY,
    MAKE_SECTION,
    PRODUCT_STUDIO_PAGE_KEY,
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
        slide_recovery,
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
        PRODUCT_STUDIO_PAGE_KEY: st.Page(
            edit.render,
            title=stages[3].title,
            icon=stages[3].icon,
            url_path=PRODUCT_STUDIO_PAGE_KEY,
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
        icon=icons.HOME,
        url_path="home",
        default=True,
    )
    project_page = st.Page(
        project_management.render,
        title="项目",
        icon=icons.PROJECT,
        url_path="project-management",
    )
    template_library_page = st.Page(
        template_library.render,
        title="模板库",
        icon=icons.TEMPLATE_LIBRARY,
        url_path="template-library",
    )
    slide_recovery_page = st.Page(
        slide_recovery.render,
        title="页面复活",
        icon=icons.SLIDE_RECOVERY,
        url_path="slide-recovery",
    )
    settings_page = st.Page(
        settings.render, title="设置", icon=icons.SETTINGS, url_path="settings"
    )

    # Hidden from sidebar but kept for deep links / st.page_link / st.switch_page.
    # LEGACY_STUDIO_PAGE_KEY registers the raw workbench for bookmarks only —
    # product navigation must use PRODUCT_STUDIO_PAGE_KEY (edit).
    hidden_pages = {
        "project-mission": st.Page(
            project_mission.render,
            title="项目任务",
            icon=icons.PROJECT_MISSION,
            url_path="project-mission",
        ),
        LEGACY_STUDIO_PAGE_KEY: st.Page(
            studio.render,
            title="工作室",
            icon=icons.STUDIO,
            url_path=LEGACY_STUDIO_PAGE_KEY,
        ),
        "template-studio": st.Page(
            template_studio.render,
            title="模板工作室",
            icon=icons.TEMPLATE_STUDIO,
            url_path="template-studio",
        ),
        "template-induction": st.Page(
            template_induction.render,
            title="模板归纳",
            icon=icons.TEMPLATE_INDUCTION,
            url_path="template-induction",
        ),
        "workspace": st.Page(
            workspace.render,
            title="项目工作台",
            icon=icons.WORKSPACE,
            url_path="workspace",
        ),
        "visual-design": st.Page(
            visual_design.render,
            title="视觉设计",
            icon=icons.VISUAL_DESIGN,
            url_path="visual-design",
        ),
        "command-center": st.Page(
            command_center.render,
            title="指令中心",
            icon=icons.COMMAND_CENTER,
            url_path="command-center",
        ),
    }

    _PAGES.clear()
    _PAGES.update({"home": home_page})
    _PAGES.update({"project-management": project_page})
    _PAGES.update(stage_pages)
    _PAGES.update({"template-library": template_library_page})
    _PAGES.update({"slide-recovery": slide_recovery_page})
    _PAGES.update({"settings": settings_page})
    _PAGES.update(hidden_pages)
    # Keep legacy deep-link key resolvable; do not put it in sidebar sections.
    _PAGES[LEGACY_STUDIO_PAGE_KEY] = hidden_pages[LEGACY_STUDIO_PAGE_KEY]
    _PAGES.setdefault(PRODUCT_STUDIO_PAGE_KEY, stage_pages[PRODUCT_STUDIO_PAGE_KEY])

    return {
        PROJECT_SECTION: [home_page, project_page],
        MAKE_SECTION: [
            stage_pages["materials"],
            stage_pages["outline"],
            stage_pages["generate"],
            stage_pages[PRODUCT_STUDIO_PAGE_KEY],
            stage_pages["deliver"],
        ],
        RESOURCE_SECTION: [template_library_page, slide_recovery_page],
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
