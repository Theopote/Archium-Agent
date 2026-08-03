"""Studio action bar and full export panel for deliver stage."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

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
from archium.ui.error_handlers import report_user_error
from archium.ui.label_map import LAYOUT_GENERATION_ACTION
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.studio.slide_actions import run_studio_replan, show_studio_validation_feedback
from archium.ui.studio_service import (
    StudioPresentationContext,
    export_presentation_from_studio,
    export_presentation_pdf_from_studio,
)
from archium.ui.visual_service import SlideVisualSnapshot
from archium.ui.workflow_progress_panel import render_workflow_progress_panel, set_active_job_id
from archium.application.unit_of_work import UnitOfWork


def _apply_visual_result(result: object) -> None:
    if isinstance(result, VisualWorkflowResult):
        st.session_state.last_visual_workflow_result = result
        st.session_state.visual_workflow_run_id = str(result.workflow_run.id)


def _render_visual_workflow_followup(
    *,
    context: StudioPresentationContext,
) -> None:
    """Keep visual progress and required review actions visible across reruns."""
    active = render_workflow_progress_panel(
        context.project.id,
        scope="visual",
        presentation_id=context.presentation.id,
        result_session_key="last_visual_workflow_result",
        on_complete=_apply_visual_result,
        awaiting_review_message="视觉版式已暂停，请在下方批准视觉方向并继续。",
        success_message="视觉版式已生成，可以检查问题或导出。",
        rerun_on_complete=False,
    )

    result = st.session_state.get("last_visual_workflow_result")
    visual_result = result if isinstance(result, VisualWorkflowResult) else None
    result_matches_context = (
        visual_result is not None
        and visual_result.presentation is not None
        and visual_result.presentation.id == context.presentation.id
    )
    awaiting_art_direction = bool(
        result_matches_context
        and visual_result is not None
        and visual_result.awaiting_review
        and visual_result.review_gate == "art_direction"
        and visual_result.art_direction is not None
    )
    if not active and not awaiting_art_direction:
        return

    if awaiting_art_direction:
        assert visual_result is not None and visual_result.art_direction is not None
        st.warning(
            "视觉生成正在等待确认。批准视觉方向后，工作流才会继续生成版式与 PPTX。",
            icon=":material/rate_review:",
        )
        from archium.ui.art_direction_panel import render_art_direction_panel

        with st.container(border=True):
            st.markdown("#### 确认视觉方向")
            render_art_direction_panel(
                art_direction=visual_result.art_direction,
                workflow_run_id=visual_result.workflow_run.id,
                awaiting_approval=True,
            )


def _render_latest_pptx_download(
    *, context: StudioPresentationContext, key_prefix: str
) -> None:
    """Persist the latest successful PPTX download action across reruns."""
    from pathlib import Path

    raw_path = st.session_state.get("last_studio_pptx_path")
    owner = st.session_state.get("last_studio_pptx_presentation_id")
    if not raw_path or owner != str(context.presentation.id):
        return
    path = Path(str(raw_path))
    if not path.is_file():
        st.warning("最近导出的 PPTX 文件已不存在，请重新导出。")
        return

    with st.container(border=True):
        st.success(f"PPTX 已就绪：{path.name}", icon=":material/check_circle:")
        st.download_button(
            "下载 PPTX",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            icon=":material/download:",
            width="content",
            key=f"{key_prefix}_latest_pptx_download",
        )
        with st.expander("文件位置", expanded=False):
            st.code(str(path), language=None)


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
        require_art_direction_review=True,
        use_llm=False,
        export_pptx=True,
        export_layout_instructions=True,
        candidate_count=3,
        preferences=preferences,
    )
    set_active_job_id(project_id, job.job_id, scope="visual", presentation_id=presentation_id)
    st.info("已在后台生成视觉版式。本页会持续显示进度；如需确认视觉方向，可直接在进度下方处理。")
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


def _export_verdict(*, project_id: UUID, presentation_id: UUID):
    from archium.application.export_gate import resolve_export_verdict_safe

    critique = st.session_state.get("last_presentation_critique")
    return resolve_export_verdict_safe(
        project_id=project_id,
        presentation_id=presentation_id,
        deck_qa_report=_deck_qa_report(),
        presentation_critique=critique if isinstance(critique, dict) else None,
    )


def _assert_export_gate(*, project_id: UUID, presentation_id: UUID, export_format: str) -> None:
    from archium.application.export_gate import assert_formal_export_allowed

    assert_formal_export_allowed(
        _export_verdict(project_id=project_id, presentation_id=presentation_id),
        export_format=export_format,
    )


def _export_pptx(
    *,
    project_id: UUID,
    presentation_id: UUID,
    settings: Settings,
    qa_status: str = "unknown",
    require_formal_gate: bool = True,
) -> None:
    from archium.application.export_policy_service import (
        ExportPolicyService,
        build_pre_export_manifest,
    )
    from archium.ui.delivery.export_policy_panel import get_session_export_policy
    from archium.ui.delivery.fidelity_report_panel import store_manifest

    policy = get_session_export_policy()
    if not require_formal_gate:
        # 非正式（工作稿）目标是“尽可能生成可交付工作版本”，
        # 因此放宽未解析素材/closure 校验等硬门禁，并允许降级到图片式渲染。
        from archium.domain.export_fidelity import ExportFidelityLevel

        policy = policy.model_copy(
            update={
                "required_fidelity": ExportFidelityLevel.RASTER_FALLBACK,
                "allow_slide_level_fallback": True,
                "allow_hybrid_editable": True,
                "allow_text_editable_background": True,
                "allow_raster_fallback": True,
                "fail_on_missing_fonts": False,
                "fail_on_unresolved_assets": False,
                "fail_on_reference_leakage": False,
                "fail_on_drawing_crop": False,
            }
        )
    try:
        if require_formal_gate:
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
            ExportPolicyService().enforce_export_policy(
                manifest,
                policy=policy,
                strict_closure=require_formal_gate,
            )

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

            from archium.domain.export_round_trip import RoundTripStatus

            if rt_report.status == RoundTripStatus.BLOCKED:
                from archium.application.export_round_trip_service import (
                    discard_export_on_round_trip_blocked,
                )

                # QD-005: no .blocked.pptx half-product and no delivery row.
                discard_export_on_round_trip_blocked(file_path)
                st.error(
                    "Round-trip QA 阻塞：导出文件已撤销，请修复阻塞项后重新导出。"
                )
                for line in rt_report.summary_lines_zh():
                    st.caption(line)
                return

            manifest = manifest.model_copy(
                update={
                    "file_uri": str(path),
                    "file_hash": file_hash,
                    "qa_status": qa_status,
                }
            )
            store_manifest(manifest)
            st.session_state.last_studio_pptx_path = str(path)
            st.session_state.last_studio_pptx_presentation_id = str(presentation_id)
            _append_delivery_record(
                "PPTX",
                str(path),
                project_id=project_id,
                presentation_id=presentation_id,
                qa_status="working_draft" if not require_formal_gate else qa_status,
                round_trip_report=round_trip_report,
            )
            if require_formal_gate:
                st.success("PPTX 导出完成。")
            else:
                st.warning("已导出工作稿（非正式交付）。请处理阻塞项后再正式导出。")
            for line in manifest.summary_lines_zh():
                st.caption(line)
            if manifest.fallback_used and manifest.fallback_reason:
                st.warning(f"降级说明：{manifest.fallback_reason}")
            st.code(path, language=None)
        else:
            st.warning("导出完成，但未返回文件路径。")
    except WorkflowError as exc:
        st.error(report_user_error(exc))
    except Exception as exc:
        st.error(report_user_error(exc))


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

        from archium.application.delivery_record_service import DeliveryRecordResult

    logger = logging.getLogger(__name__)
    result = DeliveryRecordResult(file_exported=True, record_persisted=False)
    revision_id = None
    try:
        with get_session() as session:
            from archium.application.evidence_readiness_service import (
                latest_presentation_revision_id,
            )

            revision_id = latest_presentation_revision_id(session, presentation_id)
            record = UnitOfWork.bind(session).api.delivery.record_export(
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
        st.error(report_user_error(exc))
    except Exception as exc:
        st.error(report_user_error(exc))


def _render_quick_export_popover(
    *,
    context: StudioPresentationContext,
    settings: Settings,
    key_prefix: str = "studio",
) -> None:
    """Compact export entry — does not dominate the editing chrome."""
    verdict = _export_verdict(
        project_id=context.project.id,
        presentation_id=context.presentation.id,
    )
    export_disabled = not verdict.allows_formal_export
    with st.popover("导出", width="stretch"):
        st.caption(verdict.partner_summary())
        for line in verdict.partner_lines(limit=4)[1:]:
            st.caption(line)
        if st.button(
            "导出 PPTX",
            width="stretch",
            disabled=export_disabled,
            key=f"{key_prefix}_export_pptx",
        ):
            _export_pptx(
                project_id=context.project.id,
                presentation_id=context.presentation.id,
                settings=settings,
            )
        if export_disabled and verdict.pptx_ready and st.button(
            "导出工作稿",
            width="stretch",
            key=f"{key_prefix}_export_pptx_draft",
            help="版式已齐但正式门禁未通过时，可先导出工作稿（非正式交付）。",
        ):
            _export_pptx(
                project_id=context.project.id,
                presentation_id=context.presentation.id,
                settings=settings,
                require_formal_gate=False,
            )
        if st.button(
            "导出 PDF",
            width="stretch",
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
    st.markdown(f"**{context.project.name}** · {context.presentation.title}")
    st.caption(f"状态：{ready_label}")
    with st.container(horizontal=True, gap="small"):
        if st.button(
            LAYOUT_GENERATION_ACTION,
            type="primary",
            width="content",
            key="studio_generate_layouts",
        ):
            _run_generate_layouts(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
                preferences=preferences,
            )
        replan_disabled = slide_snapshot is None
        if (
            st.button(
                "重新排版",
                width="content",
                disabled=replan_disabled,
                key="studio_top_replan",
            )
            and slide_snapshot is not None
        ):
            run_studio_replan(slide_snapshot.slide.id)
        if st.button("检查问题", width="content", key="studio_top_check_issues"):
            show_studio_validation_feedback(slide_snapshot)
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
    verdict = _export_verdict(project_id=project_id, presentation_id=presentation_id)
    export_disabled = not verdict.allows_formal_export
    preferences = _render_scene_preset_row()

    st.caption(f"{context.project.name} · {context.presentation.title}")
    # Content-width buttons in a tight row — avoid equal stretch columns on wide screens.
    with st.container(horizontal=True, gap="small"):
        if st.button(
            LAYOUT_GENERATION_ACTION,
            type="primary",
            width="content",
            key="deliver_generate_layouts",
        ):
            _run_generate_layouts(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
                preferences=preferences,
            )
        replan_disabled = slide_snapshot is None
        if (
            st.button(
                "重新排版",
                width="content",
                disabled=replan_disabled,
                key="deliver_top_replan",
            )
            and slide_snapshot is not None
        ):
            run_studio_replan(slide_snapshot.slide.id)
        if st.button("检查问题", width="content", key="deliver_top_check_issues"):
            show_studio_validation_feedback(slide_snapshot)
        if st.button(
            "导出 PPTX",
            width="content",
            disabled=export_disabled,
            key="deliver_export_pptx",
        ):
            _export_pptx(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
            )
        if st.button(
            "导出 PDF",
            width="content",
            disabled=export_disabled,
            key="deliver_export_pdf",
        ):
            _export_pdf(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
            )
        if export_disabled and verdict.pptx_ready and st.button(
            "导出工作稿（非正式）",
            width="content",
            key="deliver_export_pptx_draft",
            help="版式已齐但正式门禁未通过时，可先导出工作稿。",
        ):
            _export_pptx(
                project_id=project_id,
                presentation_id=presentation_id,
                settings=settings,
                require_formal_gate=False,
            )

    st.caption(verdict.partner_summary())
    for line in verdict.partner_lines(limit=4)[1:]:
        st.caption(line)
    if verdict.evidence_stacks:
        st.caption("门禁证据栈：" + " · ".join(verdict.evidence_stacks))

    from archium.ui.delivery.export_policy_panel import render_export_policy_panel
    from archium.ui.delivery.fidelity_report_panel import render_fidelity_report_panel

    render_export_policy_panel(key_prefix="deliver")
    render_fidelity_report_panel(key_prefix="deliver")
    _render_visual_workflow_followup(context=context)
    _render_latest_pptx_download(context=context, key_prefix="deliver")
