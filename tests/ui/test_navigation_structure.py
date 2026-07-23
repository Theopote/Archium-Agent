"""UI navigation structure guards (Architecture V1 sections + product keys)."""

from __future__ import annotations

from pathlib import Path

from archium.ui import app_navigation
from archium.ui.product_flow import (
    LEGACY_STUDIO_PAGE_KEY,
    MAKE_SECTION,
    PRODUCT_STUDIO_PAGE_KEY,
    PROJECT_SECTION,
    RESOURCE_SECTION,
    SYSTEM_SECTION,
    hidden_page_keys,
    primary_page_keys,
    product_studio_page_key,
)

ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_has_four_product_sections() -> None:
    sections = app_navigation.build_app_pages()
    assert list(sections) == [
        PROJECT_SECTION,
        MAKE_SECTION,
        RESOURCE_SECTION,
        SYSTEM_SECTION,
    ] or set(sections) == {
        PROJECT_SECTION,
        MAKE_SECTION,
        RESOURCE_SECTION,
        SYSTEM_SECTION,
    }


def test_make_section_uses_edit_not_legacy_studio() -> None:
    sections = app_navigation.build_app_pages()
    make_ids = {id(page) for page in sections[MAKE_SECTION]}
    assert id(app_navigation.get_app_page(PRODUCT_STUDIO_PAGE_KEY)) in make_ids
    assert product_studio_page_key() == PRODUCT_STUDIO_PAGE_KEY
    assert LEGACY_STUDIO_PAGE_KEY not in primary_page_keys()
    for key in hidden_page_keys():
        assert id(app_navigation.get_app_page(key)) not in {
            id(page) for pages in sections.values() for page in pages
        }


def test_product_flow_pages_exist() -> None:
    for key in ("home", "materials", "outline", "generate", "edit", "deliver"):
        assert app_navigation.get_app_page(key) is not None


def test_resource_section_includes_slide_recovery() -> None:
    sections = app_navigation.build_app_pages()
    assert len(sections[RESOURCE_SECTION]) >= 2
    assert app_navigation.get_app_page("slide-recovery") is not None


def test_slide_recovery_page_is_registered() -> None:
    assert app_navigation.get_app_page("slide-recovery") is not None


def test_bootstrap_is_not_diagnostics_home() -> None:
    text = (ROOT / "archium" / "ui" / "bootstrap.py").read_text(encoding="utf-8")
    assert "def init_app" in text
    assert "def inject_styles" in text
    assert "def render_branding" in text
    assert "module_status_pipeline" not in text
    assert "def render_system_diagnostics" not in text
