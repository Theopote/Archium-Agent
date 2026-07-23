"""Outline page — per-page design brief review and approval."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.review_models import SlideDesignBriefUpdate
from archium.application.slide_design_brief_service import (
    SlideDesignBriefService,
    design_briefs_ready,
    summarize_design_briefs,
)
from archium.domain.outline import OutlinePlan
from archium.domain.enums import ApprovalStatus
from archium.application.slide_design_brief_heuristics import format_design_brief_card
from archium.domain.slide_design_brief import (
    BRIEF_STATUS_LABELS_ZH,
    SlideDesignBrief,
    index_design_briefs,
)
from archium.domain.slide_intent import SlideIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error

_PRIMARY_VISUAL_OPTIONS = [
    ("drawing", "建筑图纸"),
    ("photo", "现场照片"),
    ("metric", "数据指标"),
    ("comparison", "对比分析"),
    ("title", "封面标题"),
    ("content", "正文内容"),
]

_DENSITY_OPTIONS = ["low", "medium", "high"]
_DENSITY_LABELS = {"low": "低", "medium": "中", "high": "高"}


def render_design_brief_panel(
    *,
    outline: OutlinePlan,
    intents: list[SlideIntent],
    selected_page: int,
) -> None:
    """Render design brief column for one selected page."""
    st.markdown("**页面设计摘要**")
    if not intents:
        st.info("请先生成并保存页面意图。")
        return

    summary = summarize_design_briefs(outline)
    ready, missing = design_briefs_ready(outline)
    metric_cols = st.columns(4)
    metric_cols[0].metric("总页数", summary.total)
    metric_cols[1].metric("已批准", summary.approved)
    metric_cols[2].metric("待确认", summary.pending)
    metric_cols[3].metric("草稿", summary.draft)

    if not outline.page_design_briefs:
        st.caption("尚未生成设计摘要。可从页面意图自动生成。")
        if st.button("生成全部设计摘要", type="primary", key="brief_generate_all"):
            try:
                with get_session() as session:
                    SlideDesignBriefService(session).generate_all(outline.id)
                st.success("已生成全部页面设计摘要。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
        return

    briefs = index_design_briefs(outline.page_design_briefs)
    page_order = intents[selected_page].order
    brief = briefs.get(page_order)
    if brief is None:
        st.warning(f"第 {selected_page + 1} 页尚无设计摘要。")
        if st.button("生成本页设计摘要", key=f"brief_regen_{page_order}"):
            try:
                with get_session() as session:
                    SlideDesignBriefService(session).regenerate_page(outline.id, page_order)
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
        return

    status_label = BRIEF_STATUS_LABELS_ZH.get(brief.status, brief.status.value)
    st.caption(f"状态：**{status_label}**")

    mode = st.radio(
        "摘要模式",
        options=["查看", "编辑"],
        horizontal=True,
        key=f"brief_mode_{outline.id}_{page_order}",
    )

    if mode == "查看":
        st.text(format_design_brief_card(brief))
    else:
        brief = _render_brief_editor(outline.id, brief)

    action_cols = st.columns(4)
    with action_cols[0]:
        if st.button("批准本页", key=f"brief_approve_{page_order}", use_container_width=True):
            try:
                with get_session() as session:
                    SlideDesignBriefService(session).approve_page(
                        outline.id,
                        page_order,
                        expected_version=outline.version,
                    )
                st.success(f"第 {page_order + 1} 页设计摘要已批准。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
    with action_cols[1]:
        if st.button("重生成摘要", key=f"brief_regen_{page_order}", use_container_width=True):
            try:
                with get_session() as session:
                    SlideDesignBriefService(session).regenerate_page(outline.id, page_order)
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
    with action_cols[2]:
        if st.button("批量批准", key="brief_approve_all", use_container_width=True):
            try:
                with get_session() as session:
                    SlideDesignBriefService(session).approve_all(
                        outline.id,
                        expected_version=outline.version,
                    )
                st.success("全部页面设计摘要已批准。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
    with action_cols[3]:
        if st.button("重新生成全部", key="brief_regen_all", use_container_width=True):
            try:
                with get_session() as session:
                    SlideDesignBriefService(session).generate_all(outline.id)
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))

    if ready:
        st.success("全部页面设计摘要已批准，可进入正式批量生成。")
    elif missing:
        st.caption("进入生成前需完成：" + "；".join(missing))


def _render_brief_editor(outline_id: UUID, brief: SlideDesignBrief) -> SlideDesignBrief:

    visual_options = [key for key, _ in _PRIMARY_VISUAL_OPTIONS]
    visual_labels = {key: label for key, label in _PRIMARY_VISUAL_OPTIONS}
    current_visual = brief.primary_visual_type if brief.primary_visual_type in visual_options else "content"

    with st.container(border=True):
        page_task = st.text_area(
            "页面任务",
            value=brief.page_task,
            key=f"brief_task_{outline_id}_{brief.page_order}",
        )
        central_claim = st.text_area(
            "中心结论",
            value=brief.central_claim,
            key=f"brief_claim_{outline_id}_{brief.page_order}",
        )
        primary_visual = st.selectbox(
            "中心视觉类型",
            options=visual_options,
            index=visual_options.index(current_visual),
            format_func=lambda value: visual_labels.get(value, value),
            key=f"brief_visual_{outline_id}_{brief.page_order}",
        )
        layout_family = st.text_input(
            "构图 / 布局族",
            value=brief.layout_family.value if brief.layout_family else "",
            key=f"brief_layout_{outline_id}_{brief.page_order}",
        )
        density = st.selectbox(
            "页面密度",
            options=_DENSITY_OPTIONS,
            index=_DENSITY_OPTIONS.index(brief.expected_density)
            if brief.expected_density in _DENSITY_OPTIONS
            else 1,
            format_func=lambda value: _DENSITY_LABELS.get(value, value),
            key=f"brief_density_{outline_id}_{brief.page_order}",
        )
        forbidden = st.text_area(
            "禁止内容（每行一条）",
            value="\n".join(brief.forbidden_content),
            key=f"brief_forbidden_{outline_id}_{brief.page_order}",
        )
        protection = st.text_area(
            "保护规则（每行一条）",
            value="\n".join(brief.protection_rules),
            key=f"brief_protection_{outline_id}_{brief.page_order}",
        )

    if st.button("保存设计摘要", type="primary", key=f"brief_save_{brief.page_order}"):
        update = SlideDesignBriefUpdate(
            page_order=brief.page_order,
            page_task=page_task.strip(),
            central_claim=central_claim.strip(),
            primary_visual_type=primary_visual,
            primary_asset_ids=list(brief.primary_asset_ids),
            supporting_asset_ids=list(brief.supporting_asset_ids),
            evidence_ids=list(brief.evidence_ids),
            layout_family=layout_family.strip(),
            expected_density=density,
            drawing_policy=brief.drawing_policy.model_dump(mode="json")
            if brief.drawing_policy
            else None,
            image_policy=brief.image_policy.model_dump(mode="json") if brief.image_policy else None,
            required_content=list(brief.required_content),
            forbidden_content=[line.strip() for line in forbidden.splitlines() if line.strip()],
            protection_rules=[line.strip() for line in protection.splitlines() if line.strip()],
            status=brief.status.value,
        )
        try:
            with get_session() as session:
                saved = SlideDesignBriefService(session).update_brief(outline_id, update)
            st.success("设计摘要已保存。")
            if saved.status == ApprovalStatus.CHANGES_PENDING:
                st.warning("已批准页面被修改，状态变为「待重新确认」。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))

    return brief
