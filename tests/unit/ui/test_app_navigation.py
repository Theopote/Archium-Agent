"""Unit tests for shared Streamlit navigation page registry and product flow."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.ui import app_navigation
from archium.ui.product_flow import (
    MAKE_SECTION,
    PROJECT_SECTION,
    RESOURCE_SECTION,
    SYSTEM_SECTION,
    get_stage,
    hidden_page_keys,
    next_stage,
    previous_stage,
    primary_page_keys,
    primary_stage_ids,
    product_flow_chain,
    product_flow_home_steps,
)


def test_get_app_page_unknown_raises() -> None:
    app_navigation._PAGES.clear()
    with pytest.raises(KeyError, match="Unknown app page"):
        app_navigation.get_app_page("missing")


def test_product_flow_has_five_ordered_stages() -> None:
    assert primary_stage_ids() == (
        "materials",
        "outline",
        "generate",
        "edit",
        "deliver",
    )
    assert primary_page_keys() == primary_stage_ids()
    assert product_flow_chain() == "资料 → 大纲 → 生成 → 工作室 → 交付"
    assert "编辑" not in product_flow_chain()
    assert len(product_flow_home_steps()) == 5
    assert get_stage("materials").title == "资料"
    assert get_stage("edit").title == "工作室"
    assert previous_stage("materials") is None
    assert next_stage("deliver") is None
    assert next_stage("materials").id == "outline"
    assert previous_stage("deliver").id == "edit"


def test_build_app_pages_registers_four_sections_and_hidden_keys() -> None:
    sections = app_navigation.build_app_pages()
    assert set(sections) == {
        PROJECT_SECTION,
        MAKE_SECTION,
        RESOURCE_SECTION,
        SYSTEM_SECTION,
    }
    assert len(sections[PROJECT_SECTION]) == 2
    assert len(sections[MAKE_SECTION]) == 5
    assert len(sections[RESOURCE_SECTION]) == 1
    assert len(sections[SYSTEM_SECTION]) == 1

    # Stage titles come from product_flow (st.Page.title needs ScriptRunContext).
    assert [get_stage(key).title for key in primary_page_keys()] == [
        "资料",
        "大纲",
        "生成",
        "工作室",
        "交付",
    ]

    for key in primary_page_keys():
        assert app_navigation.get_app_page(key) is not None
    for key in hidden_page_keys():
        assert app_navigation.get_app_page(key) is not None
    assert app_navigation.get_app_page("template-library") is not None
    assert app_navigation.get_app_page("studio") is not None
    assert app_navigation.get_app_page("workspace") is not None
    assert app_navigation.get_app_page("home") is not None
    assert app_navigation.get_app_page("settings") is not None
    assert app_navigation.get_app_page("project-management") is not None

    # Hidden tools must stay out of the visible sidebar sections.
    visible_pages = {id(page) for pages in sections.values() for page in pages}
    for key in hidden_page_keys():
        assert id(app_navigation.get_app_page(key)) not in visible_pages


def test_home_is_project_cockpit_not_welcome_wall() -> None:
    home_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    )
    text = home_src.read_text(encoding="utf-8")
    assert "9 步" not in text
    assert "继续处理哪个项目" in text
    assert "最近项目" in text
    assert "当前任务" in text
    assert "快捷入口" in text
    assert "五阶段说明（首次使用）" in text
    assert "阶段说明" not in text or "五阶段说明" in text
    assert "list_recent_project_snapshots" in text
    assert "欢迎使用 Archium" not in text


def test_sidebar_uses_project_progress_not_module_status() -> None:
    app_src = Path(__file__).resolve().parents[3] / "app.py"
    settings_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "settings.py"
    )
    app_text = app_src.read_text(encoding="utf-8")
    settings_text = settings_src.read_text(encoding="utf-8")
    assert "render_project_progress_card" in app_text
    assert "render_module_status" not in app_text
    assert "_render_system_diagnostics" in settings_text
    assert "render_system_diagnostics" in settings_text


def test_outline_default_does_not_embed_mission_unconditionally() -> None:
    outline_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "outline.py"
    )
    text = outline_src.read_text(encoding="utf-8")
    assert "高级任务规划" in text
    assert "project_mission.render(embedded=True)" in text
    assert "outline_advanced_planning" in text
    assert "def _render_default_outline" in text


def test_edit_stage_embeds_studio_without_inner_header() -> None:
    edit_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "edit.py"
    )
    studio_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "studio.py"
    )
    edit_text = edit_src.read_text(encoding="utf-8")
    studio_text = studio_src.read_text(encoding="utf-8")
    assert "studio.render(" in edit_text
    assert "embedded=True" in edit_text
    assert "show_header=False" in edit_text
    assert "show_export=False" in edit_text
    assert "show_progress=False" in edit_text
    assert "show_header: bool | None = None" in studio_text
    assert 'st.markdown("### 工作室")' in studio_text


def test_studio_export_is_popover_not_top_panel() -> None:
    studio_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "studio.py"
    )
    export_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "studio"
        / "export_panel.py"
    )
    studio_text = studio_src.read_text(encoding="utf-8")
    export_text = export_src.read_text(encoding="utf-8")
    assert "render_studio_toolbar" in studio_text
    assert "render_export_panel(" not in studio_text
    assert "def render_studio_toolbar" in export_text
    assert 'st.popover("导出"' in export_text
    assert "打开交付页" in export_text


def test_studio_inspector_uses_five_tabs_with_ai_and_proposal_together() -> None:
    studio_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "studio.py"
    )
    text = studio_src.read_text(encoding="utf-8")
    assert '["属性", "布局", "内容", "AI", "检查"]' in text
    assert "def _render_inspector_tabs" in text
    ai_block_start = text.index("with tab_ai:")
    check_block_start = text.index("with tab_check:")
    ai_block = text[ai_block_start:check_block_start]
    assert "render_ai_edit_panel" in ai_block
    assert "render_proposal_compare_panel" in ai_block
    assert "render_human_review_panel" not in ai_block
    assert "render_deferred_scene_repair_panel" in text[check_block_start:]
    assert "render_human_review_panel" in text[check_block_start:]
