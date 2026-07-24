"""Studio action bar and full export panel for deliver stage."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.evidence_readiness_service import (
    DeliveryReadinessReport,
    ProjectEvidenceStatus,
    resolve_delivery_readiness_safe,
)
from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.config.settings import Settings
from archium.domain.render import RenderResult
from archium.domain.visual.preferences import VisualPreferences
from archium.domain.visual.scene_presets import (
    SCENE_PRESET_DESCRIPTIONS,
    SCENE_PRESET_KEYS,
    SCENE_PRESET_LABELS,
    scene_preset_preferences,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.background_workflow_runner import (
    VisualJobAction,
    background_workflows_enabled,
    submit_visual_job,
    warn_background_workflows_required,
)
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.studio.slide_actions import run_studio_replan, show_studio_validation_feedback
from archium.ui.studio_service import (
    StudioPresentationContext,
    export_presentation_from_studio,
    export_presentation_pdf_from_studio,
)
from archium.ui.visual_service import SlideVisualSnapshot
from archium.ui.workflow_progress_panel import render_workflow_progress_panel, set_active_job_id


def _apply_visual_result(result: object) -> None:
    if isinstance(result, VisualWorkflowResult):
        st.session_state.last_visual_workflow_result = result
        st.session_state.visual_workflow_run_id = str(result.workflow_run.id)


def _resolve_scene_preferences() -> VisualPreferences:
    preset_key = str(st.session_state.get("studio_scene_preset") or SCENE_PRESET_KEYS[0])
    if preset_key not in SCENE_PRESET_KEYS:
        preset_key = SCENE_PRESET_KEYS[0]
    return scene_preset_preferences(preset_key)


def _launch_visual_job(
    project_id: UUID,
    presentation_id: UUID,
    *,
    settings: Settings,
    preferences: VisualPreferences | None = None,
) -> bool:
    if not background_workflows_enabled(settings):
        warn_background_workflows_required()
        return False
    job = submit_visual_job(
        project_id,
        presentation_id,
        VisualJobAction.RUN,
        settings=settings,
        require_art_direction_review=False,
        use_llm=False,
        export_pptx=True,
        export_layout_instructions=True,
        candidate_count=3,
        preferences=preferences,
    )
    set_active_job_id(project_id, job.job_id, scope="visual", presentation_id=presentation_id)
    st.info("已在后台生成视觉版式，进度见页面底部。")
    render_workflow_progress_panel(
        project_id,
        scope="visual",
        presentation_id=presentation_id,
        job_id=job.job_id,
        result_session_key="last_visual_workflow_result",
        on_complete=_apply_visual_result,
        success_message="视觉版式已生成。",
    )
    return True


def _render_scene_preset_row() -> VisualPreferences:
    preset_cols = st.columns([1.2, 2.8])
    with preset_cols[0]:
        preset_key = st.selectbox(
            "场景预设",
            options=list(SCENE_PRESET_KEYS),
            format_func=lambda value: SCENE_PRESET_LABELS.get(value, value),
            key="studio_scene_preset",
        )
    with preset_cols[1]:
        st.caption(SCENE_PRESET_DESCRIPTIONS.get(preset_key, ""))
    return _resolve_scene_preferences()


def _run_generate_layouts(
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings,
    preferences: VisualPreferences,
) -> None:
    _launch_visual_job(
        project_id,
        presentation_id,
        settings=settings,
        preferences=preferences,
    )


def _deck_qa_report() -> dict | None:
    result = st.session_state.get("last_visual_workflow_result")
    if isinstance(result, VisualWorkflowResult) and isinstance(result.deck_qa_report, dict):
        return result.deck_qa_report
    return None


def _delivery_readiness(*, project_id: UUID, presentation_id: UUID) -> DeliveryReadinessReport:
    return resolve_delivery_readiness_safe(
        project_id=project_id,
        presentation_id=presentation_id,
        deck_qa_report=_deck_qa_report(),
    )


def _assert_export_gate(*, project_id: UUID, presentation_id: UUID, export_format: str) -> None:
    from archium.application.evidence_readiness_service import assert_formal_export_allowed

    report = _delivery_readiness(project_id=project_id, presentation_id=presentation_id)
    assert_formal_export_allowed(report, export_format=export_format)


def _export_pptx(
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings,
    qa_status: str = "unknown",
) -> None:
    from archium.application.export_policy_service import (
        ExportPolicyService,
        build_pre_export_manifest,
    )
    from archium.ui.delivery.export_policy_panel import get_session_export_policy
    from archium.ui.delivery.fidelity_report_panel import store_manifest

    policy = get_session_export_policy()
    try:
        _assert_export_gate(
            project_id=project_id,
            presentation_id=presentation_id,
            export_format="PPTX",
        )
        with st.spinner("正在评估导出忠实度…"), get_session() as session:
            from archium.application.evidence_readiness_service import (
                latest_presentation_revision_id,
            )

            revision_id = latest_presentation_revision_id(session, presentation_id)
            manifest = build_pre_export_manifest(
                session,
                presentation_id=presentation_id,
                policy=policy,
                export_format="PPTX",
                revision_id=revision_id,
                settings=settings,
            )
            ExportPolicyService().enforce_export_policy(manifest, policy=policy)

        with st.spinner("正在导出 PPTX…"), get_session() as session:
            pptx_export_result: RenderResult = export_presentation_from_studio(
                session,
                presentation_id,
                settings=settings,
                chart_export_mode=policy.chart_export_mode,
            )
        path = pptx_export_result.editable_pptx_path
        if path:
            import hashlib
            from pathlib import Path

            file_hash = ""
            file_path = Path(path)
            if file_path.is_file():
                file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]

            round_trip_report = None
            qa_status = qa_status
            with st.spinner("正在执行 Round-trip QA…"), get_session() as session:
                from archium.application.evidence_readiness_service import (
                    latest_presentation_revision_id,
                )
                from archium.application.export_round_trip_service import (
                    ExportRoundTripService,
                )

                rt_revision_id = latest_presentation_revision_id(session, presentation_id)
                rt_report = ExportRoundTripService(session, settings=settings).validate_pptx_export(
                    presentation_id=presentation_id,
                    pptx_path=file_path,
                    revision_id=rt_revision_id,
                    export_file_hash=file_hash,
                )
                from archium.ui.delivery.fidelity_report_panel import store_round_trip_report

                store_round_trip_report(rt_report)
                round_trip_report = rt_report.model_dump(mode="json")
                qa_status = rt_report.qa_status_value()

            manifest = manifest.model_copy(
                update={
                    "file_uri": str(path),
                    "file_hash": file_hash,
                    "qa_status": qa_status,
                }
            )
            store_manifest(manifest)
            st.session_state.last_studio_pptx_path = str(path)
            _append_delivery_record(
                "PPTX",
                str(path),
                project_id=project_id,
                presentation_id=presentation_id,
                qa_status=qa_status,
                round_trip_report=round_trip_report,
            )
            st.success("PPTX 导出完成。")
            for line in manifest.summary_lines_zh():
                st.caption(line)
            if manifest.fallback_used and manifest.fallback_reason:
                st.warning(f"降级说明：{manifest.fallback_reason}")
            st.code(path, language=None)
        else:
            st.warning("导出完成，但未返回文件路径。")
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _append_delivery_record(
    fmt: str,
    path: str,
    *,
    project_id: UUID,
    presentation_id: UUID,
    qa_status: str = "unknown",
    round_trip_report: dict | None = None,
) -> None:
    import logging
    from datetime import UTC, datetime

    from archium.application.delivery_record_service import (
        DeliveryRecordResult,
        DeliveryRecordService,
    )

    logger = logging.getLogger(__name__)
    result = DeliveryRecordResult(file_exported=True, record_persisted=False)
    revision_id = None
    try:
        with get_session() as session:
            from archium.application.evidence_readiness_service import (
                latest_presentation_revision_id,
            )

            revision_id = latest_presentation_revision_id(session, presentation_id)
            record = DeliveryRecordService(session).record_export(
                project_id=project_id,
                presentation_id=presentation_id,
                format=fmt,
                file_uri=path,
                qa_status=qa_status,
                revision_id=revision_id,
                round_trip_report=round_trip_report,
            )
        result = DeliveryRecordResult(
            file_exported=True,
            record_persisted=True,
            record=record,
        )
    except Exception as exc:
        logger.exception("Failed to persist delivery record for %s", path)
        result = DeliveryRecordResult(
            file_exported=True,
            record_persisted=False,
            error_message=str(exc),
        )
        st.warning("文件已导出，但版本记录保存失败。重新打开应用后可能看不到本条记录。")

    records = list(st.session_state.get("delivery_export_records") or [])
    records.append(
        {
            "format": fmt,
            "path": path,
            "when": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
            "project_id": str(project_id),
            "presentation_id": str(presentation_id),
            "qa_status": qa_status,
            "record_persisted": result.record_persisted,
        }
    )
    st.session_state.delivery_export_records = records[-20:]


def _export_pdf(
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings,
    qa_status: str = "unknown",
) -> None:
    try:
        _assert_export_gate(
            project_id=project_id,
            presentation_id=presentation_id,
            export_format="PDF",
        )
        with st.spinner("正在导出 PDF…"), get_session() as session:
            pdf_export_result: RenderResult = export_presentation_pdf_from_studio(
                session,
                presentation_id,
                settings=settings,
            )
        pdf_path = pdf_export_result.pdf_path
        if pdf_path:
            st.session_state.last_studio_pdf_path = str(pdf_path)
            _append_delivery_record(
                "PDF",
                str(pdf_path),
                project_id=project_id,
                presentation_id=presentation_id,
                qa_status=qa_status,
            )
            st.success("PDF 导出完成。")
            st.code(pdf_path, language=None)
        elif pdf_export_result.editable_pptx_path:
            st.session_state.last_studio_pptx_path = str(pdf_export_result.editable_pptx_path)
            _append_delivery_record(
                "PPTX",
                str(pdf_export_result.editable_pptx_path),
                project_id=project_id,
                presentation_id=presentation_id,
                qa_status=qa_status,
            )
            st.warning("PPTX 已导出，但未检测到 LibreOffice，无法生成 PDF。")
            st.code(pdf_export_result.editable_pptx_path, language=None)
        else:
            st.warning("导出未完成。")
        for warning in pdf_export_result.warnings:
            st.caption(warning)
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _project_evidence_status(project_id: UUID) -> ProjectEvidenceStatus:
    from archium.application.evidence_readiness_service import resolve_project_evidence_safe

    return resolve_project_evidence_safe(project_id)


def _render_quick_export_popover(
    *,
    context: StudioPresentationContext,
    settings: Settings,
    key_prefix: str = "studio",
) -> None:
    """Compact export entry — does not dominate the editing chrome."""
    readiness = _delivery_readiness(
        project_id=context.project.id,
        presentation_id=context.presentation.id,
    )
    export_disabled = not readiness.allows_formal_export
    with st.popover("导出", use_container_width=True):
        st.caption("快速导出当前汇报。完整导出与质量检查请到「交付」。")
        if readiness.evidence.is_unknown:
            st.caption("资料状态无法验证，禁止正式导出。")
        elif readiness.evidence.is_concept_draft:
            st.caption("概念草稿不可正式导出，请先绑定项目资料。")
        elif not readiness.pptx_ready:
            st.caption("导出需先完成全部页面版式。")
        elif readiness.export_blocker_count > 0:
            st.caption("存在阻塞项，正式导出已被阻止。")
        if st.button(
            "导出 PPTX",
            use_container_width=True,
            disabled=export_disabled,
            key=f"{key_prefix}_export_pptx",
        ):
            _export_pptx(
                project_id=context.project.id,
                presentation_id=context.presentation.id,
                settings=settings,
            )
        if st.button(
            "导出 PDF",
            use_container_width=True,
            disabled=export_disabled,
            key=f"{key_prefix}_export_pdf",
        ):
            _export_pdf(
                project_id=context.project.id,
                presentation_id=context.presentation.id,
                settings=settings,
            )
        from archium.ui import icons

        st.page_link(get_app_page("deliver"), label="打开交付页", icon=icons.DELIVER)


def render_studio_toolbar(
    *,
    context: StudioPresentationContext,
    slide_snapshot: SlideVisualSnapshot | None = None,
    show_export: bool = True,
) -> None:
    """Compact Studio chrome: edit actions first; export is a secondary popover."""
    project_id = context.project.id
    presentation_id = context.presentation.id
    settings = get_ui_effective_settings()
    preferences = _render_scene_preset_row()

    ready_label = "可导出" if context.ready_for_export else "版式未齐"
    (
        col_title,
        col_generate,
        col_replan,
        col_check,
        col_export,
    ) = st.columns([2.6, 1, 1, 1, 1])

    with col_title:
        st.markdown(f"**{context.project.name}** · {context.presentation.title}")
        st.caption(f"状态：{ready_label}")

    with col_generate:
        if st.button(
            "生成版式",
            type="primary",
            use_container_width=True,
            key="studio_generate_layouts",
        ):
            _run_generate_layouts(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
                preferences=preferences,
            )

    with col_replan:
        replan_disabled = slide_snapshot is None
        if st.button(
            "重新排版",
            use_container_width=True,
            disabled=replan_disabled,
            key="studio_top_replan",
        ) and slide_snapshot is not None:
            run_studio_replan(slide_snapshot.slide.id)

    with col_check:
        if st.button("检查问题", use_container_width=True, key="studio_top_check_issues"):
            show_studio_validation_feedback(slide_snapshot)

    with col_export:
        if show_export:
            _render_quick_export_popover(context=context, settings=settings)
        else:
            from archium.ui import icons

            st.page_link(get_app_page("deliver"), label="交付 / 导出", icon=icons.EXPORT)


def render_export_panel(
    *,
    context: StudioPresentationContext,
    slide_snapshot: SlideVisualSnapshot | None = None,
) -> None:
    """Full generate / export actions for the「交付」stage."""
    project_id = context.project.id
    presentation_id = context.presentation.id
    settings = get_ui_effective_settings()
    readiness = _delivery_readiness(project_id=project_id, presentation_id=presentation_id)
    export_disabled = not readiness.allows_formal_export
    preferences = _render_scene_preset_row()

    (
        col_title,
        col_generate,
        col_replan,
        col_check,
        col_pptx,
        col_pdf,
    ) = st.columns([2.4, 1, 1, 1, 1, 1])

    with col_title:
        st.markdown("#### 导出与版式")
        st.caption(f"{context.project.name} · {context.presentation.title}")

    with col_generate:
        if st.button(
            "生成版式",
            type="primary",
            use_container_width=True,
            key="deliver_generate_layouts",
        ):
            _run_generate_layouts(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
                preferences=preferences,
            )

    with col_replan:
        replan_disabled = slide_snapshot is None
        if st.button(
            "重新排版",
            use_container_width=True,
            disabled=replan_disabled,
            key="deliver_top_replan",
        ) and slide_snapshot is not None:
            run_studio_replan(slide_snapshot.slide.id)

    with col_check:
        if st.button("检查问题", use_container_width=True, key="deliver_top_check_issues"):
            show_studio_validation_feedback(slide_snapshot)

    with col_pptx:
        if st.button(
            "导出 PPTX",
            use_container_width=True,
            disabled=export_disabled,
            key="deliver_export_pptx",
        ):
            _export_pptx(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
            )

    with col_pdf:
        if st.button(
            "导出 PDF",
            use_container_width=True,
            disabled=export_disabled,
            key="deliver_export_pdf",
        ):
            _export_pdf(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
            )

    if readiness.evidence.is_unknown:
        st.caption("资料状态无法验证，禁止正式导出。")
    elif readiness.evidence.is_concept_draft:
        st.caption("概念草稿不可正式导出，请先绑定项目资料。")
    elif not readiness.pptx_ready:
        st.caption("导出需先完成全部页面版式。")
    elif readiness.export_blocker_count > 0:
        st.caption("存在阻塞项，正式导出已被阻止。")

    from archium.ui.delivery.export_policy_panel import render_export_policy_panel
    from archium.ui.delivery.fidelity_report_panel import render_fidelity_report_panel

    render_export_policy_panel(key_prefix="deliver")
    render_fidelity_report_panel(key_prefix="deliver")
