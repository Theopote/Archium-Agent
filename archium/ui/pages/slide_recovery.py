"""Slide Recovery — independent external page reconstruction tool."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import streamlit as st

from archium.application.slide_recovery_workflow_service import (
    SlideRecoveryWorkflowRequest,
    SlideRecoveryWorkflowResult,
)
from archium.config.settings import Settings
from archium.domain.enums import WorkflowStatus
from archium.domain.slide_recovery import PAGE_KIND_LABELS_ZH, SlideRecoveryPageKind
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.background_workflow_runner import (
    SlideRecoveryJobAction,
    background_workflows_enabled,
    submit_slide_recovery_job,
)
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.slide_recovery_panel import render_slide_recovery_result_panel
from archium.ui.workflow_progress_panel import (
    render_workflow_progress_panel,
    set_active_job_id,
)
from archium.ui.workspace_service import list_projects


def _init_session_state() -> None:
    defaults = {
        "slide_recovery_project_id": None,
        "last_slide_recovery_result": None,
        "slide_recovery_upload_path": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_project_selector() -> UUID | None:
    with get_session() as session:
        projects = list_projects(session)
    if not projects:
        st.info("请先创建项目，以便记录页面复活工作流。")
        return None

    labels = {str(project.id): project.name for project in projects}
    options = list(labels.keys())
    default_index = 0
    if st.session_state.slide_recovery_project_id in options:
        default_index = options.index(st.session_state.slide_recovery_project_id)

    selected = st.selectbox(
        "关联项目",
        options=options,
        index=default_index,
        format_func=lambda value: labels[value],
        key="slide_recovery_project_select",
    )
    st.session_state.slide_recovery_project_id = selected
    return UUID(selected)


def _save_uploaded_file(uploaded_file: object) -> Path:
    suffix = Path(str(getattr(uploaded_file, "name", "page.png"))).suffix or ".png"
    workspace = Path(tempfile.gettempdir()) / "archium-slide-recovery" / "uploads"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / f"{uuid4().hex}{suffix.lower()}"
    target.write_bytes(uploaded_file.getvalue())  # type: ignore[union-attr]
    st.session_state.slide_recovery_upload_path = str(target)
    return target


def _launch_recovery_job(
    project_id: UUID,
    *,
    source_path: Path,
    slide_index: int,
    page_kind: SlideRecoveryPageKind | None,
    force_table_bitmap: bool,
    settings: Settings,
) -> None:
    workspace_dir = source_path.parent / "workspace"
    request = SlideRecoveryWorkflowRequest(
        source_path=source_path,
        slide_index=slide_index,
        page_kind=page_kind,
        force_table_bitmap=force_table_bitmap,
        workspace_dir=workspace_dir,
    )

    if background_workflows_enabled(settings):
        job = submit_slide_recovery_job(
            project_id,
            SlideRecoveryJobAction.RUN,
            request=request,
            settings=settings,
        )
        set_active_job_id(project_id, job.job_id, scope="slide_recovery")
        render_workflow_progress_panel(
            project_id,
            scope="slide_recovery",
            job_id=job.job_id,
            result_session_key="last_slide_recovery_result",
            awaiting_review_message="页面复活已完成初步恢复，请复核指标与混合降级说明。",
            success_message="页面复活工作流已完成。",
        )
        return

    with st.spinner("正在恢复页面…"):
        with get_session() as session:
            from archium.application.slide_recovery_workflow_service import (
                SlideRecoveryWorkflowService,
            )

            service = SlideRecoveryWorkflowService(session, settings=settings)
            result = service.run(project_id, request)
    st.session_state.last_slide_recovery_result = result
    if result.awaiting_review:
        st.warning("恢复结果需人工复核。")
    elif result.succeeded:
        st.success("页面复活完成。")
    else:
        st.error("；".join(result.errors) or "页面复活失败。")


def _render_review_actions(result: SlideRecoveryWorkflowResult, settings: Settings) -> None:
    run = result.workflow_run
    if run.status != WorkflowStatus.AWAITING_REVIEW:
        return

    st.markdown("#### 人工复核")
    st.caption("接受后将写入完成状态；拒绝会取消本次恢复。")
    notes = st.text_input("复核备注（可选）", key="slide_recovery_review_notes")
    col_accept, col_reject = st.columns(2)
    project_id = run.project_id

    with col_accept:
        if st.button("接受恢复结果", key="slide_recovery_accept", type="primary"):
            if background_workflows_enabled(settings):
                job = submit_slide_recovery_job(
                    project_id,
                    SlideRecoveryJobAction.CONTINUE_REVIEW,
                    request=SlideRecoveryWorkflowRequest(source_path=Path(".")),
                    settings=settings,
                    workflow_run_id=run.id,
                    review_accepted=True,
                    review_notes=notes or None,
                )
                set_active_job_id(project_id, job.job_id, scope="slide_recovery")
                st.rerun()
            else:
                with get_session() as session:
                    from archium.application.slide_recovery_workflow_service import (
                        SlideRecoveryWorkflowService,
                    )

                    service = SlideRecoveryWorkflowService(session, settings=settings)
                    finalized = service.continue_after_review(
                        run.id,
                        accepted=True,
                        notes=notes or None,
                    )
                st.session_state.last_slide_recovery_result = finalized
                st.success("已接受恢复结果。")
                st.rerun()

    with col_reject:
        if st.button("拒绝", key="slide_recovery_reject"):
            if background_workflows_enabled(settings):
                job = submit_slide_recovery_job(
                    project_id,
                    SlideRecoveryJobAction.CONTINUE_REVIEW,
                    request=SlideRecoveryWorkflowRequest(source_path=Path(".")),
                    settings=settings,
                    workflow_run_id=run.id,
                    review_accepted=False,
                    review_notes=notes or None,
                )
                set_active_job_id(project_id, job.job_id, scope="slide_recovery")
                st.rerun()
            else:
                with get_session() as session:
                    from archium.application.slide_recovery_workflow_service import (
                        SlideRecoveryWorkflowService,
                    )

                    service = SlideRecoveryWorkflowService(session, settings=settings)
                    finalized = service.continue_after_review(
                        run.id,
                        accepted=False,
                        notes=notes or None,
                    )
                st.session_state.last_slide_recovery_result = finalized
                st.warning("已拒绝本次恢复结果。")
                st.rerun()


def render() -> None:
    st.title("页面复活")
    st.caption(
        "将外部 PNG/JPG 或图片式 PPTX 页面恢复为 Hybrid RenderScene。"
        "本工具独立于主生成链，仅用于技术验证与导入辅助。"
    )
    _init_session_state()
    settings = get_ui_effective_settings()

    project_id = _render_project_selector()
    if project_id is None:
        return

    uploaded = st.file_uploader(
        "上传源页面",
        type=["png", "jpg", "jpeg", "webp", "pptx"],
        key="slide_recovery_upload",
    )

    col1, col2 = st.columns(2)
    with col1:
        slide_index = st.number_input(
            "PPTX 页码（从 1 开始）",
            min_value=1,
            value=1,
            step=1,
            key="slide_recovery_slide_index",
        )
    with col2:
        kind_options = ["自动识别", *list(SlideRecoveryPageKind)]
        kind_choice = st.selectbox(
            "页面类型",
            options=kind_options,
            format_func=lambda value: (
                "自动识别"
                if value == "自动识别"
                else PAGE_KIND_LABELS_ZH.get(value, value.value)
            ),
            key="slide_recovery_page_kind",
        )
    force_table_bitmap = st.checkbox(
        "表格区域使用 Bitmap 降级",
        value=False,
        help="复杂表格保持为图片对象，仅保留标题等文字可编辑。",
    )

    active_result = st.session_state.get("last_slide_recovery_result")
    if active_result is not None:
        render_workflow_progress_panel(
            project_id,
            scope="slide_recovery",
            result_session_key="last_slide_recovery_result",
            awaiting_review_message="页面复活等待复核。",
        )
        if isinstance(active_result, SlideRecoveryWorkflowResult):
            render_slide_recovery_result_panel(active_result)
            _render_review_actions(active_result, settings)

    if st.button("开始页面复活", type="primary", key="slide_recovery_start"):
        if uploaded is None and not st.session_state.slide_recovery_upload_path:
            st.error("请先上传源页面文件。")
            return
        try:
            source_path = (
                _save_uploaded_file(uploaded)
                if uploaded is not None
                else Path(st.session_state.slide_recovery_upload_path)
            )
            page_kind = (
                None
                if kind_choice == "自动识别"
                else SlideRecoveryPageKind(kind_choice)
            )
            _launch_recovery_job(
                project_id,
                source_path=source_path,
                slide_index=int(slide_index) - 1,
                page_kind=page_kind,
                force_table_bitmap=force_table_bitmap,
                settings=settings,
            )
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))
