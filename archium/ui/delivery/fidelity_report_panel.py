"""Deck export fidelity manifest display for deliver stage."""

from __future__ import annotations

import streamlit as st

from archium.domain.export_fidelity import (
    FIDELITY_LABELS_ZH,
    DeckExportManifest,
    ExportFidelityLevel,
)
from archium.domain.export_round_trip import (
    ROUND_TRIP_STATUS_LABELS_ZH,
    ExportRoundTripReport,
    RoundTripStatus,
)

MANIFEST_SESSION_KEY = "last_deck_export_manifest"
ROUND_TRIP_SESSION_KEY = "last_export_round_trip_report"


def store_manifest(manifest: DeckExportManifest) -> None:
    st.session_state[MANIFEST_SESSION_KEY] = manifest.model_dump(mode="json")


def store_round_trip_report(report: ExportRoundTripReport) -> None:
    st.session_state[ROUND_TRIP_SESSION_KEY] = report.model_dump(mode="json")


def get_stored_manifest() -> DeckExportManifest | None:
    raw = st.session_state.get(MANIFEST_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return DeckExportManifest.model_validate(raw)
    except Exception:
        return None


def get_stored_round_trip_report() -> ExportRoundTripReport | None:
    raw = st.session_state.get(ROUND_TRIP_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return ExportRoundTripReport.model_validate(raw)
    except Exception:
        return None


def load_persisted_round_trip_report(
    presentation_id,
    session=None,
) -> ExportRoundTripReport | None:
    """Reload Round-trip QA from the latest PPTX delivery record after restart."""
    from uuid import UUID

    from archium.application.delivery_record_service import DeliveryRecordService
    from archium.application.unit_of_work import session_of, unit_of_work

    pid = presentation_id if isinstance(presentation_id, UUID) else UUID(str(presentation_id))

    def _from_session(active_session) -> ExportRoundTripReport | None:
        records = DeliveryRecordService(active_session).list_for_presentation(pid, limit=12)
        for record in records:
            raw = record.round_trip_report_json
            if not isinstance(raw, dict):
                continue
            try:
                return ExportRoundTripReport.model_validate(raw)
            except Exception:
                continue
        return None

    if session is not None:
        return _from_session(session_of(session))
    with unit_of_work() as uow:
        return _from_session(uow)


def resolve_round_trip_report(
    *,
    presentation_id=None,
    report: ExportRoundTripReport | None = None,
) -> ExportRoundTripReport | None:
    """Prefer live session, then explicit report, then delivery-record persistence."""
    if report is not None:
        return report
    stored = get_stored_round_trip_report()
    if stored is not None:
        return stored
    if presentation_id is None:
        return None
    persisted = load_persisted_round_trip_report(presentation_id)
    if persisted is not None:
        try:
            store_round_trip_report(persisted)
        except Exception:
            pass
    return persisted


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
            "本次导出使用了降级策略。"
            + (f" 原因：{resolved.fallback_reason}" if resolved.fallback_reason else "")
        )
    elif resolved.final_fidelity == ExportFidelityLevel.FULLY_EDITABLE:
        st.success("全部页面均在支持范围内可编辑，未发生静默降级。")

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
        from pathlib import Path

        st.caption(f"文件：{Path(resolved.file_uri).name}")
        with st.expander("完整路径", expanded=False):
            st.code(resolved.file_uri, language=None)
    if resolved.file_hash:
        st.caption(f"哈希：{resolved.file_hash}")

    presentation_id = None
    if resolved.presentation_id is not None:
        presentation_id = resolved.presentation_id
    render_round_trip_report_panel(
        key_prefix=key_prefix,
        presentation_id=presentation_id,
    )


def render_round_trip_report_panel(
    report: ExportRoundTripReport | None = None,
    *,
    key_prefix: str = "deliver",
    presentation_id=None,
) -> None:
    """Show export round-trip QA metrics after PPTX export."""
    resolved = resolve_round_trip_report(
        presentation_id=presentation_id,
        report=report,
    )
    if resolved is None:
        return

    st.markdown("#### Round-trip QA")
    status_label = ROUND_TRIP_STATUS_LABELS_ZH.get(resolved.status, resolved.status.value)
    for line in resolved.summary_lines_zh():
        st.write(line)

    if resolved.status == RoundTripStatus.PASS:
        st.success(f"导出回环验证：{status_label}")
    elif resolved.status == RoundTripStatus.PASS_WITH_WARNINGS:
        st.warning(f"导出回环验证：{status_label}")
    elif resolved.status == RoundTripStatus.NEEDS_REVIEW:
        st.warning(f"导出回环验证：{status_label} — 建议人工复核")
    else:
        st.error(f"导出回环验证：{status_label}")

    if resolved.blockers:
        for blocker in resolved.blockers[:8]:
            st.caption(f"阻塞：{blocker}")
    if resolved.font_substitutions:
        st.caption("字体替代：" + "；".join(resolved.font_substitutions[:6]))

    with st.expander("Round-trip 逐页详情", expanded=False):
        for slide in resolved.slides:
            sim = (
                f" · 相似度 {slide.similarity_score:.0%}"
                if slide.similarity_score >= 0
                else ""
            )
            st.caption(
                f"第 {slide.slide_order + 1} 页 · 文本 {slide.text_match_rate:.0%}"
                f" · 几何 {slide.geometry_match_rate:.0%}{sim}"
            )
            if slide.missing_text_nodes:
                st.caption("  缺失文本：" + "；".join(slide.missing_text_nodes[:3]))
            if slide.drawing_integrity_issues:
                st.caption("  图纸：" + "；".join(slide.drawing_integrity_issues[:3]))
