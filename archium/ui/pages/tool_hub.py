"""单项工具台 — 不强迫走完整主链的独立能力入口。"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from archium.ui import icons
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import render_page_header


@dataclass(frozen=True, slots=True)
class ToolHubEntry:
    title: str
    caption: str
    page_key: str | None
    icon: str
    available: bool
    via_hint: str = ""


def tool_hub_entries() -> list[ToolHubEntry]:
    """Catalog for the tool hub. Unavailable items stay honest placeholders."""
    return [
        ToolHubEntry(
            title="页面复活",
            caption="从旧 PPT / 扫描页恢复一页可继续编辑的内容。",
            page_key="slide-recovery",
            icon=icons.SLIDE_RECOVERY,
            available=True,
        ),
        ToolHubEntry(
            title="模板库",
            caption="浏览与套用已有版式模板。",
            page_key="template-library",
            icon=icons.TEMPLATE_LIBRARY,
            available=True,
        ),
        ToolHubEntry(
            title="从 PDF 提取指标",
            caption="解析技术经济指标与关键面积数据。",
            page_key=None,
            icon=icons.MATERIALS,
            available=False,
            via_hint="请在「资料」阶段上传 PDF，系统会提取事实与指标。",
        ),
        ToolHubEntry(
            title="识别扫描图",
            caption="识别图纸/扫描件中的空间与图面信息。",
            page_key=None,
            icon=":material/document_scanner:",
            available=False,
            via_hint="请在「资料」上传扫描图；视觉资料会进入证据库。",
        ),
        ToolHubEntry(
            title="生成汇报大纲",
            caption="只组织故事线，不立即跑完整生成。",
            page_key="outline",
            icon=icons.OUTLINE,
            available=True,
        ),
        ToolHubEntry(
            title="优化一页 PPT",
            caption="进入工作室，针对单页做版式与文案打磨。",
            page_key="edit",
            icon=icons.STUDIO,
            available=True,
        ),
        ToolHubEntry(
            title="草图变分析图",
            caption="将概念草图整理为可进汇报的分析图。",
            page_key=None,
            icon=":material/draw:",
            available=False,
            via_hint="即将接入；当前可先把草图作为资料上传。",
        ),
        ToolHubEntry(
            title="检查汇报事实",
            caption="核对事实台账中的冲突与待确认项。",
            page_key="materials",
            icon=":material/fact_check:",
            available=True,
        ),
        ToolHubEntry(
            title="已有资料整理成汇报",
            caption="从资料出发进入大纲与生成。",
            page_key="materials",
            icon=icons.MATERIALS,
            available=True,
        ),
    ]


def render() -> None:
    render_page_header(
        "单项工具",
        "只做一件事，不必创建完整 Mission 或跑通五阶段。可用工具直接进入；其余标明接入路径。",
    )
    available = [item for item in tool_hub_entries() if item.available]
    upcoming = [item for item in tool_hub_entries() if not item.available]

    st.markdown("**可用**")
    cols = st.columns(2)
    for index, entry in enumerate(available):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{entry.title}**")
                st.caption(entry.caption)
                if entry.page_key:
                    st.page_link(
                        get_app_page(entry.page_key),
                        label=f"打开 · {entry.title}",
                        icon=entry.icon,
                    )

    if upcoming:
        st.markdown("**即将接入**")
        for entry in upcoming:
            with st.container(border=True):
                st.markdown(f"**{entry.title}**")
                st.caption(entry.caption)
                st.caption(entry.via_hint or "即将接入，暂无独立入口。")
