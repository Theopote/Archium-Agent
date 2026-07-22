"""Presentation Technology Radar — external AI PPT systems catalog."""

from __future__ import annotations

import streamlit as st
from typing import cast

from archium.application.presentation_technology_radar_service import (
    PresentationTechnologyRadarService,
    RadarFilter,
)
from archium.domain.external_presentation_system import (
    ArchiumRelevance,
    CATEGORY_LABELS_ZH,
    RELEVANCE_LABELS_ZH,
    SystemCategory,
)


def _render_summary(service: PresentationTechnologyRadarService) -> None:
    summary = service.summary()
    cols = st.columns(4)
    cols[0].metric("系统总数", summary.total)
    cols[1].metric("采纳", summary.adopt_count)
    cols[2].metric("试验", summary.trial_count)
    cols[3].metric("评估/暂缓", summary.by_relevance.get("assess", 0) + summary.by_relevance.get("hold", 0))


def _render_filters() -> RadarFilter:
    col1, col2, col3 = st.columns(3)
    with col1:
        relevance_raw = st.selectbox(
            "Archium 相关性",
            options=["全部", *list(RELEVANCE_LABELS_ZH.keys())],
            format_func=lambda value: "全部" if value == "全部" else RELEVANCE_LABELS_ZH[value],
            key="radar_filter_relevance",
        )
    with col2:
        category_raw = st.selectbox(
            "类别",
            options=["全部", *list(CATEGORY_LABELS_ZH.keys())],
            format_func=lambda value: "全部" if value == "全部" else CATEGORY_LABELS_ZH[value],
            key="radar_filter_category",
        )
    with col3:
        query = st.text_input("搜索", placeholder="名称、概念、页面模型…", key="radar_filter_query")

    flags = st.columns(2)
    editable_only = flags[0].checkbox("仅原生可编辑 PPTX", key="radar_filter_editable")
    local_llm_only = flags[1].checkbox("仅支持本地 LLM", key="radar_filter_local_llm")

    return RadarFilter(
        relevance=None if relevance_raw == "全部" else cast(ArchiumRelevance, relevance_raw),
        category=None if category_raw == "全部" else cast(SystemCategory, category_raw),
        query=query or None,
        editable_pptx_only=editable_only,
        local_llm_only=local_llm_only,
    )


def _render_system_card(item: object) -> None:
    from archium.domain.external_presentation_system import ExternalPresentationSystem

    assert isinstance(item, ExternalPresentationSystem)
    title = f"{item.name} · {item.relevance_label_zh()}"
    with st.expander(title, expanded=False):
        for line in item.summary_lines_zh()[1:]:
            st.caption(line)

        if item.repository_url:
            st.markdown(f"仓库：[{item.repository_url}]({item.repository_url})")
        if item.product_url:
            st.markdown(f"产品：[{item.product_url}]({item.product_url})")

        model_cols = st.columns(2)
        with model_cols[0]:
            if item.page_model:
                st.write(f"**页面模型：** {item.page_model}")
            if item.layout_engine:
                st.write(f"**布局引擎：** {item.layout_engine}")
            if item.template_system:
                st.write(f"**模板系统：** {item.template_system}")
        with model_cols[1]:
            if item.edit_model:
                st.write(f"**编辑模型：** {item.edit_model}")
            if item.qa_model:
                st.write(f"**QA 模型：** {item.qa_model}")

        if item.concepts_to_adopt:
            st.markdown("**可采纳概念**")
            for concept in item.concepts_to_adopt:
                st.write(f"- {concept}")
        if item.concepts_to_avoid:
            st.markdown("**应避免概念**")
            for concept in item.concepts_to_avoid:
                st.write(f"- {concept}")
        if item.notes:
            st.info(item.notes)

        st.caption(f"最近评审：{item.last_reviewed_at.strftime('%Y-%m-%d')}")


def render() -> None:
    st.title("演示技术雷达")
    st.caption(
        "外部 AI PPT / 演示系统的观察档案。"
        "用于记录可采纳概念与应避免路径，避免每次临时分析后失去记录。"
    )

    service = PresentationTechnologyRadarService()
    _render_summary(service)
    radar_filter = _render_filters()
    systems = service.list_systems(radar_filter)

    st.markdown(f"#### 匹配 **{len(systems)}** 个系统")
    for item in systems:
        _render_system_card(item)

    stale = service.list_stale(days=180)
    if stale:
        with st.expander(f"超过 180 天未复审（{len(stale)}）", expanded=False):
            for item in stale:
                st.write(f"- {item.name}")
