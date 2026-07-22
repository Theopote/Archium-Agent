"""Main-chain adopt concept landing panel."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.main_chain_adopt_service import MainChainAdoptService
from archium.domain.main_chain_adopt import (
    STAGE_LABELS_ZH,
    AdoptLandingStatus,
    MainChainAdoptCheckpoint,
    MainChainAdoptReport,
    MainChainStage,
)
from archium.infrastructure.database.session import get_session

_STATUS_LABELS_ZH = {
    AdoptLandingStatus.LANDED: "已落地",
    AdoptLandingStatus.PLATFORM: "平台内置",
    AdoptLandingStatus.PARTIAL: "部分落地",
    AdoptLandingStatus.GAP: "待补齐",
}


def load_main_chain_adopt_report(
    project_id: UUID,
    *,
    presentation_id: UUID | None = None,
) -> MainChainAdoptReport:
    with get_session() as session:
        return MainChainAdoptService(session).evaluate(
            project_id,
            presentation_id=presentation_id,
        )


def _status_icon(status: AdoptLandingStatus) -> str:
    return {
        AdoptLandingStatus.LANDED: "✓",
        AdoptLandingStatus.PLATFORM: "●",
        AdoptLandingStatus.PARTIAL: "◐",
        AdoptLandingStatus.GAP: "○",
    }.get(status, "○")


def _render_checkpoint_row(item: MainChainAdoptCheckpoint) -> None:
    status = _STATUS_LABELS_ZH.get(item.status, item.status.value)
    icon = _status_icon(item.status)
    st.markdown(f"{icon} **{item.binding.label_zh}** · {status}")
    if item.detail_zh:
        st.caption(item.detail_zh)


def render_main_chain_adopt_panel(
    project_id: UUID,
    *,
    presentation_id: UUID | None = None,
    stage_id: MainChainStage | None = None,
    key_prefix: str = "adopt",
    expanded: bool = False,
) -> MainChainAdoptReport:
    report = load_main_chain_adopt_report(project_id, presentation_id=presentation_id)
    title = "主链采纳概念"
    if stage_id is not None:
        title = f"{title} · {STAGE_LABELS_ZH.get(stage_id, stage_id)}"

    with st.expander(title, expanded=expanded):
        st.caption(
            f"已落地 {report.landed_count()}/{len(report.checkpoints)} · "
            f"待补齐 {report.gap_count()}"
        )
        items = report.for_stage(stage_id) if stage_id else report.checkpoints
        if not items:
            st.info("当前阶段无 adopt 概念检查项。")
            return report
        for item in items:
            _render_checkpoint_row(item)
    return report
