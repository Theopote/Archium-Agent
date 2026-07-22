"""Deck export fidelity manifest display for deliver stage."""

from __future__ import annotations

import streamlit as st

from archium.domain.export_fidelity import (
    DeckExportManifest,
    ExportFidelityLevel,
    FIDELITY_LABELS_ZH,
)

MANIFEST_SESSION_KEY = "last_deck_export_manifest"


def store_manifest(manifest: DeckExportManifest) -> None:
    st.session_state[MANIFEST_SESSION_KEY] = manifest.model_dump(mode="json")


def get_stored_manifest() -> DeckExportManifest | None:
    raw = st.session_state.get(MANIFEST_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return DeckExportManifest.model_validate(raw)
    except Exception:
        return None


def render_fidelity_report_panel(
    manifest: DeckExportManifest | None = None,
    *,
    key_prefix: str = "deliver",
) -> None:
    """Show per-level slide counts and fallback disclosure."""
    resolved = manifest or get_stored_manifest()
    if resolved is None:
        return

    st.markdown("#### 导出忠实度")
    summary_lines = resolved.summary_lines_zh()
    if summary_lines:
        for line in summary_lines:
            st.write(line)
    else:
        st.caption("暂无页面忠实度数据。")

    final_label = FIDELITY_LABELS_ZH.get(
        resolved.final_fidelity,
        resolved.final_fidelity.value,
    )
    st.caption(f"整套最终忠实度：**{final_label}** · QA：{resolved.qa_status}")

    if resolved.fallback_used:
        st.warning(
            f"本次导出使用了降级策略。"
            + (f" 原因：{resolved.fallback_reason}" if resolved.fallback_reason else "")
        )
    elif resolved.final_fidelity == ExportFidelityLevel.FULLY_EDITABLE:
        st.success("全部页面均为原生可编辑，未发生静默降级。")

    with st.expander("逐页详情", expanded=False):
        for slide in resolved.slides:
            label = FIDELITY_LABELS_ZH.get(slide.fidelity_level, slide.fidelity_level.value)
            detail = (
                f"页 {str(slide.slide_id)[:8]}… · {label} · "
                f"文字 {slide.native_text_count} · 形状 {slide.native_shape_count} · "
                f"位图 {slide.bitmap_asset_count}"
            )
            if slide.blockers:
                detail += f" · 阻塞：{'; '.join(slide.blockers)}"
            st.caption(detail)

    if resolved.file_uri:
        st.caption(f"文件：{resolved.file_uri}")
    if resolved.file_hash:
        st.caption(f"哈希：{resolved.file_hash}")
