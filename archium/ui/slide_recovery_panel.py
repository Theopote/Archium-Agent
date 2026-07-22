"""Slide Recovery result panel — metrics, fidelity, and review actions."""

from __future__ import annotations

import streamlit as st

from archium.application.slide_recovery_workflow_service import SlideRecoveryWorkflowResult
from archium.domain.export_fidelity import FIDELITY_LABELS_ZH
from archium.domain.slide_recovery import PAGE_KIND_LABELS_ZH


def render_slide_recovery_result_panel(
    result: SlideRecoveryWorkflowResult | None,
    *,
    key_prefix: str = "slide_recovery",
) -> None:
    if result is None:
        return

    recovery = result.recovery_result
    hybrid = result.hybrid_scene or (recovery.hybrid_scene if recovery else None)
    if recovery is None and hybrid is None:
        st.info("恢复结果尚未生成。")
        return

    st.markdown("#### 恢复结果")
    if hybrid is not None:
        st.caption(
            f"页面类型：{PAGE_KIND_LABELS_ZH.get(hybrid.page_kind, hybrid.page_kind.value)} · "
            f"可编辑级别：{hybrid.fidelity_label_zh()}"
        )

    if recovery is not None:
        for line in recovery.summary_lines_zh():
            st.write(line)

    metrics = recovery.metrics if recovery is not None else hybrid.metrics if hybrid else None
    if metrics is not None:
        cols = st.columns(3)
        cols[0].metric("文本召回率", f"{metrics.text_recall:.0%}")
        cols[1].metric("位置误差", f"{metrics.text_position_error:.1%}")
        cols[2].metric("视觉相似度", f"{metrics.similarity_score:.0%}")

        with st.expander("完整指标", expanded=False):
            for line in metrics.summary_lines_zh():
                st.write(line)

    fidelity = (
        recovery.reconstruction_fidelity
        if recovery is not None
        else hybrid.reconstruction_fidelity if hybrid else None
    )
    if fidelity is not None:
        st.caption(f"导出保真度：{FIDELITY_LABELS_ZH.get(fidelity, fidelity.value)}")

    warnings = list(result.warnings)
    if recovery is not None:
        warnings.extend(recovery.warnings)
    if warnings:
        st.warning("；".join(warnings))

    if result.errors:
        st.error("；".join(result.errors))

    if hybrid is not None and hybrid.hybrid_bitmap_region_ids:
        st.caption(
            f"混合 Bitmap 区域：{len(hybrid.hybrid_bitmap_region_ids)} 个 "
            "（复杂视觉保持为图片对象）"
        )

    if hybrid is not None and hybrid.scene.nodes:
        with st.expander("Hybrid RenderScene 节点", expanded=False):
            for node in hybrid.scene.sorted_nodes():
                st.write(f"- `{node.id}` · {node.node_type} · {node.semantic_role or '—'}")
