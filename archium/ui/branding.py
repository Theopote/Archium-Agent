"""Product branding and version display strings."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PRODUCT_NAME = "Archium"
PRODUCT_NAME_CN = "阿基姆"
# Avoid “Museum” — Archium is not museum-architecture-specific.
BRAND_SUBTITLE_EN = "Architecture × Intelligence"
BRAND_SUBTITLE_CN = "建筑汇报智能工作台"
BRAND_SUBTITLE = f"{BRAND_SUBTITLE_EN} · {BRAND_SUBTITLE_CN}"

# Sidebar footer: short productized line; details live in Settings → About.
DISPLAY_VERSION = "v0.2 Alpha"
SIDEBAR_VALUE_HINT = "本地项目 · 自动保存"


def package_version() -> str:
    """Installed package version (fallback matches pyproject)."""
    try:
        return version("archium-agent")
    except PackageNotFoundError:
        return "0.2.0a5"


FULL_VERSION_LABEL = package_version()


def render_version_footer() -> None:
    """Compact productized version line for the sidebar."""
    import streamlit as st

    st.markdown(
        '<div style="margin-top:2rem;font-size:0.72rem;color:#bbb9b2;line-height:1.6;">'
        f"{DISPLAY_VERSION}<br>{SIDEBAR_VALUE_HINT}"
        "</div>",
        unsafe_allow_html=True,
    )
