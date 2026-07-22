"""Prompt users to resolve deferred semantic scene repairs via Proposal."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.scene_repair_service import summarize_deferred_repair
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio.proposal_compare_panel import get_stored_proposal, store_proposal
from archium.ui.studio_service import create_slide_overflow_repair_proposal
from archium.ui.visual_service import SlideVisualSnapshot


def render_deferred_scene_repair_panel(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
) -> None:
    """Surface deferred QA findings as confirmation-required modification suggestions."""
    if slide_snapshot is None or slide_snapshot.render_scene is None:
        return

    slide = slide_snapshot.slide
    if get_stored_proposal(slide.id) is not None:
        return

    deferred = list(slide_snapshot.deferred_scene_repairs or [])
    if not deferred:
        st.caption("当前页没有待确认的 QA 修复建议。")
        return

    overflow_nodes: list[str] = []
    for finding in deferred:
        if finding.check_code == SceneSemanticCheckCode.TEXT_OVERFLOW:
            overflow_nodes.extend(list(finding.evidence_refs or []))

    st.markdown("**修改建议 · QA 修复 · 需确认**")
    st.caption(
        "以下问题不会自动写入正式页面。"
        "安全自动修复仅限越界收拢、明确 contain、缺省值与无损对齐；"
        "其余需生成提案后人工确认。"
    )
    for finding in deferred:
        st.markdown(f"- {summarize_deferred_repair(finding)}")

    if overflow_nodes:
        if st.button(
            "生成溢出修复提案",
            type="secondary",
            use_container_width=True,
            key=f"studio_overflow_repair_proposal_{slide.id}",
        ):
            _create_overflow_proposal(slide.id, overflow_nodes)
    elif any(
        finding.check_code == SceneSemanticCheckCode.FONT_TOO_SMALL
        for finding in deferred
    ):
        st.caption("字体过小：请到 **AI** Tab 描述期望的字号或可读性调整。")


def _create_overflow_proposal(slide_id: UUID, node_ids: list[str]) -> None:
    unique_nodes = list(dict.fromkeys(node_ids))
    try:
        with st.spinner("正在生成溢出修复提案…"), get_session() as session:
            proposal = create_slide_overflow_repair_proposal(
                session,
                slide_id,
                node_ids=unique_nodes or None,
            )
        store_proposal(proposal)
        st.success("溢出修复提案已生成，请到 **AI** Tab 查看对比并确认。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
