"""Top export/action bar for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.config.settings import Settings
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.background_workflow_runner import (
    VisualJobAction,
    background_workflows_enabled,
    submit_visual_job,
)
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.studio_service import StudioPresentationContext, export_presentation_from_studio
from archium.ui.visual_service import run_visual_workflow
from archium.ui.workflow_progress_panel import render_workflow_progress_panel, set_active_job_id


def _apply_visual_result(result: object) -> None:
    if isinstance(result, VisualWorkflowResult):
        st.session_state.last_visual_workflow_result = result
        st.session_state.visual_workflow_run_id = str(result.workflow_run.id)


def _launch_visual_job(
    project_id: UUID,
    presentation_id: UUID,
    *,
    settings: Settings,
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


def render_export_panel(*, context: StudioPresentationContext) -> None:
    """Render generate / save / export actions."""
    project_id = context.project.id
    presentation_id = context.presentation.id
    settings = get_ui_effective_settings()

    col_title, col_generate, col_save, col_export = st.columns([3, 1, 1, 1])
    with col_title:
        st.markdown("#### 操作")
        st.caption(f"{context.project.name} · {context.presentation.title}")
    with col_generate:
        if st.button("生成版式", type="primary", use_container_width=True, key="studio_generate_layouts"):
            if _launch_visual_job(project_id, presentation_id, settings=settings):
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
    with col_save:
        st.button("保存", use_container_width=True, disabled=True, key="studio_save_stub")
        st.caption("自动保存")
    with col_export:
        export_disabled = not context.ready_for_export
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
                    st.success("导出完成。")
                    st.code(path, language=None)
                else:
                    st.warning("导出完成，但未返回文件路径。")
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))
        if export_disabled:
            st.caption("需先完成全部页面版式")
