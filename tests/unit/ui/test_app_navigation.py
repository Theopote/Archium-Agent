"""Unit tests for shared Streamlit navigation page registry and product flow."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.ui import app_navigation
from archium.ui.product_flow import (
    LEGACY_STUDIO_PAGE_KEY,
    MAKE_SECTION,
    PRODUCT_STUDIO_PAGE_KEY,
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
    product_studio_page_key,
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
    assert len(sections[PROJECT_SECTION]) == 3
    assert len(sections[MAKE_SECTION]) == 5
    assert len(sections[RESOURCE_SECTION]) == 2
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
    assert app_navigation.get_app_page("project-genesis") is not None
    assert app_navigation.get_app_page("concept-exploration") is not None
    assert "concept-exploration" in hidden_page_keys()

    # Hidden tools must stay out of the visible sidebar sections.
    visible_pages = {id(page) for pages in sections.values() for page in pages}
    for key in hidden_page_keys():
        assert id(app_navigation.get_app_page(key)) not in visible_pages


def test_edit_is_product_studio_key_studio_is_legacy_hidden_only() -> None:
    """edit = formal 工作室 stage; studio = deep-link only (not sidebar)."""
    assert product_studio_page_key() == PRODUCT_STUDIO_PAGE_KEY == "edit"
    assert LEGACY_STUDIO_PAGE_KEY == "studio"
    assert PRODUCT_STUDIO_PAGE_KEY in primary_page_keys()
    assert LEGACY_STUDIO_PAGE_KEY in hidden_page_keys()
    assert LEGACY_STUDIO_PAGE_KEY not in primary_page_keys()

    sections = app_navigation.build_app_pages()
    make_ids = {id(page) for page in sections[MAKE_SECTION]}
    assert id(app_navigation.get_app_page(PRODUCT_STUDIO_PAGE_KEY)) in make_ids
    assert id(app_navigation.get_app_page(LEGACY_STUDIO_PAGE_KEY)) not in make_ids


def test_product_ui_does_not_navigate_to_legacy_studio_page_key() -> None:
    """Guardrail: product chrome must open 工作室 via ``edit``, not ``studio``."""
    import re

    root = Path(__file__).resolve().parents[3] / "archium" / "ui"
    pattern = re.compile(
        r"""get_app_page\(\s*['"]studio['"]\s*\)"""
        r"""|switch_page\(\s*['"]studio['"]\s*\)"""
        r"""|page_link\(\s*['"]studio['"]"""
    )
    # Registration / docs only — not product navigation targets.
    allow = {
        root / "app_navigation.py",
        root / "product_flow.py",
        root / "pages" / "studio.py",
    }
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path in allow:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path.relative_to(root.parent.parent)))
    assert offenders == [], (
        "Product navigation must use page key 'edit' "
        f"(product_studio_page_key), not legacy 'studio': {offenders}"
    )


def test_home_is_project_cockpit_not_welcome_wall() -> None:
    home_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    )
    text = home_src.read_text(encoding="utf-8")
    assert "9 步" not in text
    assert "欢迎使用 Archium" not in text
    assert "继续工作" in text
    assert "汇报任务" in text
    assert "当前阶段" in text
    assert "总体进度" in text
    assert "待处理问题" in text
    assert "最近版本" in text
    assert "五阶段说明（首次使用）" in text
    assert "list_recent_project_snapshots" in text
    assert "_render_project_cockpit" in text


def test_sidebar_uses_project_progress_not_module_status() -> None:
    boot_src = Path(__file__).resolve().parents[3] / "archium" / "bootstrap.py"
    settings_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "settings.py"
    )
    boot_text = boot_src.read_text(encoding="utf-8")
    settings_text = settings_src.read_text(encoding="utf-8")
    assert "render_project_progress_card" in boot_text
    assert "render_module_status" not in boot_text
    assert "render_version_footer" in boot_text
    assert "建筑 · 归档 · 智能" not in boot_text
    assert "_render_system_diagnostics" in settings_text
    assert "render_system_diagnostics" in settings_text
    assert "_render_about" in settings_text


def test_branding_avoids_museum_subtitle() -> None:
    from archium.ui import icons
    from archium.ui.branding import BRAND_SUBTITLE, DISPLAY_VERSION, SIDEBAR_VALUE_HINT
    from archium.ui.product_flow import get_stage

    assert "Museum" not in BRAND_SUBTITLE
    assert "建筑汇报智能工作台" in BRAND_SUBTITLE
    assert DISPLAY_VERSION == "v0.2 Alpha"
    assert SIDEBAR_VALUE_HINT == "本地项目 · 自动保存"
    assert get_stage("materials").icon == icons.MATERIALS
    assert get_stage("edit").icon == icons.STUDIO
    assert icons.HOME.startswith(":material/")


def test_materials_stage_uses_four_tabs() -> None:
    workspace_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "workspace.py"
    )
    text = workspace_src.read_text(encoding="utf-8")
    assert '["文件", "事实", "素材", "缺口"]' in text
    assert "load_materials_summary" in text
    assert "更多工具" in text
    assert "上传资料" in text
    assert "个文件" in text
    assert "条事实" in text
    assert "项素材" in text
    assert "个待确认问题" in text


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
    assert "页面意图卡" in text
    assert "章节与页面树" in text
    assert "叙事弧线" in text
    assert "页面标题" in text
    assert "确认大纲" in text
    assert "直接前往生成" not in text
    assert "OutlineApprovalService" in text
    assert "include_next=False" in text
    assert "保存当前页" in text
    assert "outline_intent_mode" in text
    assert "outline_sec_toggle_" in text
    assert "outline_narrow_layout" in text
    assert "page_picker" in text
    # Wide layout uses the tree; selectbox is gated behind narrow / no-tree.
    assert 'key="outline_card_select"' in text
    assert "page_picker:" in text or "page_picker =" in text or "if page_picker" in text


def test_generate_stage_shows_page_queue() -> None:
    generate_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "generate.py"
    )
    text = generate_src.read_text(encoding="utf-8")
    assert "逐页队列" in text
    assert "处理问题页" in text
    assert "进入工作室" in text
    assert "render_generate_stage" in text


def test_deliver_stage_is_export_focused() -> None:
    deliver_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "deliver.py"
    )
    text = deliver_src.read_text(encoding="utf-8")
    assert "准备度" in text
    assert "版本记录" in text
    assert "render_export_panel" in text
    assert "render_benchmark" not in text
    assert "render_studio_selection" not in text
    assert "_resolve_deliver_context" in text
    assert "切换汇报版本" in text


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
    assert "show_progress=True" in edit_text
    assert "show_header: bool | None = None" in studio_text
    assert "render_page_header" in studio_text
    assert '"工作室"' in studio_text
    assert "_render_studio_info_menus" in studio_text
    assert "_render_deck_issue_list" in studio_text
    assert "_render_bottom_dock" not in studio_text
    assert 'st.popover("活动中心"' in studio_text
    assert 'st.popover("问题"' not in studio_text


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


def test_studio_inspector_uses_lazy_tabs_with_ai_workspace() -> None:
    studio_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "studio.py"
    )
    text = studio_src.read_text(encoding="utf-8")
    assert "_INSPECTOR_TABS" in text
    assert '("属性", "布局", "内容", "AI", "评论", "风格", "检查")' in text
    assert "def _render_inspector_tabs" in text
    assert "_select_inspector_tab" in text
    assert "st.tabs(" not in text
    assert "_render_view_controls" in text
    assert 'st.popover("视图"' in text
    assert 'st.popover("活动中心"' in text
    assert "render_ai_workspace" in text
    assert "_render_bottom_dock" not in text
    assert "_render_studio_info_menus" in text
    # Lazy panels: AI and check are gated, not both under st.tabs contexts.
    assert 'if active == "AI":' in text
    assert "render_deferred_scene_repair_panel" in text
    assert "render_human_review_panel" in text
    info_start = text.index("def _render_studio_info_menus")
    info_block = text[info_start : text.index("def render(", info_start)]
    assert "render_deferred_scene_repair_panel" not in info_block
    assert "render_human_review_panel" not in info_block
    assert 'st.popover("状态"' not in info_block
    assert 'st.popover("问题"' not in info_block
    assert 'st.popover("历史"' not in info_block
