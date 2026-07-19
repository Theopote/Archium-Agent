"""Top export/action bar for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.config.settings import Settings
from archium.domain.visual.preferences import VisualPreferences
from archium.domain.visual.scene_presets import (
    SCENE_PRESET_DESCRIPTIONS,
    SCENE_PRESET_KEYS,
    SCENE_PRESET_LABELS,
    scene_preset_preferences,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.background_workflow_runner import (
    VisualJobAction,
    background_workflows_enabled,
    submit_visual_job,
)
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.studio.slide_actions import run_studio_replan, show_studio_validation_feedback
from archium.ui.studio_service import (
    StudioPresentationContext,
    export_presentation_from_studio,
    export_presentation_pdf_from_studio,
)
from archium.ui.visual_service import SlideVisualSnapshot, run_visual_workflow
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


def render_export_panel(
    *,
    context: StudioPresentationContext,
    slide_snapshot: SlideVisualSnapshot | None = None,
) -> None:
    """Render generate / replan / check / export actions."""
    project_id = context.project.id
    presentation_id = context.presentation.id
    settings = get_ui_effective_settings()
    export_disabled = not context.ready_for_export
    preferences = _resolve_scene_preferences()

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

    (
        col_title,
        col_generate,
        col_replan,
        col_check,
        col_pptx,
        col_pdf,
    ) = st.columns([2.4, 1, 1, 1, 1, 1])

    with col_title:
        st.markdown("#### 操作")
        st.caption(f"{context.project.name} · {context.presentation.title}")

    with col_generate:
        if st.button("生成版式", type="primary", use_container_width=True, key="studio_generate_layouts"):
            if _launch_visual_job(
                project_id,
                presentation_id,
                settings=settings,
                preferences=preferences,
            ):
                return
            try:
                with st.spinner("正在生成视觉版式…"), get_session() as session:
                    result = run_visual_workflow(
                        session,
                        project_id,
                        presentation_id,
                        require_art_direction_review=False,
                        use_llm=False,
                        export_pptx=True,
                        candidate_count=3,
                        preferences=preferences,
                    )
                _apply_visual_result(result)
                if result.succeeded:
                    st.success("视觉版式已生成。")
                else:
                    detail = "；".join(result.errors) if result.errors else "未知错误"
                    st.error(f"生成未完成：{detail}")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

    with col_replan:
        replan_disabled = slide_snapshot is None
        if st.button(
            "重新排版",
            use_container_width=True,
            disabled=replan_disabled,
            key="studio_top_replan",
        ):
            if slide_snapshot is not None:
                run_studio_replan(slide_snapshot.slide.id)

    with col_check:
        if st.button("检查问题", use_container_width=True, key="studio_top_check_issues"):
            show_studio_validation_feedback(slide_snapshot)

    with col_pptx:
        if st.button(
            "导出 PPTX",
            use_container_width=True,
            disabled=export_disabled,
            key="studio_export_pptx",
        ):
            try:
                with st.spinner("正在导出 PPTX…"), get_session() as session:
                    result = export_presentation_from_studio(
                        session,
                        presentation_id,
                        settings=settings,
                    )
                path = result.editable_pptx_path
                if path:
                    st.success("PPTX 导出完成。")
                    st.code(path, language=None)
                else:
                    st.warning("导出完成，但未返回文件路径。")
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

    with col_pdf:
        if st.button(
            "导出 PDF",
            use_container_width=True,
            disabled=export_disabled,
            key="studio_export_pdf",
        ):
            try:
                with st.spinner("正在导出 PDF…"), get_session() as session:
                    result = export_presentation_pdf_from_studio(
                        session,
                        presentation_id,
                        settings=settings,
                    )
                pdf_path = result.pdf_path
                if pdf_path:
                    st.success("PDF 导出完成。")
                    st.code(pdf_path, language=None)
                elif result.editable_pptx_path:
                    st.warning("PPTX 已导出，但未检测到 LibreOffice，无法生成 PDF。")
                    st.code(result.editable_pptx_path, language=None)
                else:
                    st.warning("导出未完成。")
                for warning in result.warnings:
                    st.caption(warning)
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

    if export_disabled:
        st.caption("导出需先完成全部页面版式。")
