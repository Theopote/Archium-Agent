"""Streamlit project workspace page."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.config import get_settings
from archium.domain.enums import ProjectType
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.chunk_panel import render_chunk_panel
from archium.ui.components import render_file_downloads
from archium.ui.error_handlers import format_user_error
from archium.ui.review_panel import render_review_panel
from archium.ui.workspace_service import (
    build_presentation_request,
    create_project,
    get_project_overview,
    import_uploaded_file,
    list_project_documents,
    list_project_presentations,
    list_projects,
    run_presentation_workflow,
)

PROJECT_TYPE_LABELS = {
    ProjectType.HEALTHCARE: "医疗建筑",
    ProjectType.URBAN_RENEWAL: "城市更新",
    ProjectType.RESIDENTIAL: "住宅",
    ProjectType.COMMERCIAL: "商业",
    ProjectType.CULTURE: "文化建筑",
    ProjectType.EDUCATION: "教育建筑",
    ProjectType.OTHER: "其他",
}


def _init_session_state() -> None:
    if "selected_project_id" not in st.session_state:
        st.session_state.selected_project_id = None
    if "last_workflow_result" not in st.session_state:
        st.session_state.last_workflow_result = None


def _render_project_selector() -> UUID | None:
    with get_session() as session:
        projects = list_projects(session)

    if not projects:
        st.info("还没有项目。请在下方创建第一个项目。")
        return None

    labels = {
        str(project.id): f"{project.name} · {PROJECT_TYPE_LABELS.get(project.project_type, project.project_type.value)}"
        for project in projects
    }
    options = list(labels.keys())
    default_index = 0
    if st.session_state.selected_project_id in options:
        default_index = options.index(st.session_state.selected_project_id)

    selected = st.selectbox(
        "当前项目",
        options=options,
        index=default_index,
        format_func=lambda value: labels[value],
    )
    st.session_state.selected_project_id = selected
    return UUID(selected)


def _render_create_project() -> None:
    with st.expander("创建新项目", expanded=False), st.form("create_project_form"):
        name = st.text_input("项目名称", placeholder="例如：某医院老院区更新")
        project_type = st.selectbox(
            "项目类型",
            options=list(PROJECT_TYPE_LABELS.keys()),
            format_func=lambda value: PROJECT_TYPE_LABELS[value],
        )
        description = st.text_area("项目说明（可选）", height=80)
        submitted = st.form_submit_button("创建项目", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("请填写项目名称")
                return
            with get_session() as session:
                project = create_project(
                    session,
                    name=name,
                    project_type=project_type,
                    description=description,
                )
            st.session_state.selected_project_id = str(project.id)
            st.success(f"已创建项目：{project.name}")
            st.rerun()


def _render_overview(project_id: UUID) -> None:
    with get_session() as session:
        overview = get_project_overview(session, project_id)
    if overview is None:
        st.warning("项目不存在或已被删除。")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("资料文件", overview.document_count)
    col2.metric("文本片段", overview.chunk_count)
    col3.metric("汇报版本", overview.presentation_count)
    col4.metric("项目类型", PROJECT_TYPE_LABELS.get(overview.project.project_type, "其他"))


def _render_documents(project_id: UUID) -> None:
    st.markdown("#### 项目资料")
    with get_session() as session:
        documents = list_project_documents(session, project_id)

    if documents:
        rows = [
            {
                "文件名": doc.filename,
                "类型": doc.file_type.value,
                "状态": doc.processing_status.value,
                "页数": doc.page_count or "-",
            }
            for doc in documents
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("尚未导入资料。上传任务书、图纸说明或调研文档后再生成汇报。")

    uploads = st.file_uploader(
        "上传项目资料",
        type=["pdf", "docx", "pptx", "xlsx", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"upload_{project_id}",
    )
    if uploads and st.button("开始导入", key=f"import_{project_id}"):
        results = []
        with get_session() as session:
            for upload in uploads:
                results.append(
                    import_uploaded_file(
                        session,
                        project_id,
                        filename=upload.name,
                        data=upload.getvalue(),
                    )
                )
        for result in results:
            if result.error:
                st.error(f"{result.source_path.name}: {result.error}")
            elif result.duplicate:
                st.warning(f"{result.source_path.name}: 已存在相同文件，已跳过")
            else:
                chunk_count = len(result.chunks)
                st.success(f"{result.source_path.name}: 导入成功（{chunk_count} 个片段）")
        st.rerun()


def _render_generation_form(project_id: UUID) -> None:
    st.markdown("#### 生成汇报")
    settings = get_settings()
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请在 `.env` 中设置 `GEMINI_API_KEY` 或 `LLM_API_KEY`。")
        return

    with st.form("presentation_form"):
        title = st.text_input("汇报标题", placeholder="老院区更新概念汇报")
        audience = st.text_input("汇报对象", placeholder="医院管理层")
        purpose = st.text_input("汇报目的", placeholder="确认总体改造方向")
        core_message = st.text_area("核心信息", placeholder="通过交通重组改善院区体验")
        target_slide_count = st.number_input("目标页数", min_value=3, max_value=40, value=12)
        required_sections = st.text_area(
            "必要章节（每行一项，或用顿号分隔）",
            placeholder="现状分析\n改造策略\n实施计划",
        )
        col1, col2, col3 = st.columns(3)
        export_json = col1.checkbox("导出 JSON", value=True)
        export_marp = col2.checkbox("导出 Marp Markdown", value=True)
        export_pptx = col3.checkbox("导出 PPTX（需 Marp CLI）", value=False)
        review_col1, review_col2, review_col3 = st.columns(3)
        require_brief_review = review_col1.checkbox("Brief 生成后暂停审核", value=True)
        require_storyline_review = review_col2.checkbox("Storyline 生成后暂停审核", value=True)
        require_slides_review = review_col3.checkbox("SlideSpec 生成后暂停审核", value=False)
        submitted = st.form_submit_button("运行汇报管线", use_container_width=True)

    if not submitted:
        return

    if not all([title.strip(), audience.strip(), purpose.strip(), core_message.strip()]):
        st.error("请完整填写标题、对象、目的与核心信息。")
        return

    request = build_presentation_request(
        title=title,
        audience=audience,
        purpose=purpose,
        core_message=core_message,
        target_slide_count=int(target_slide_count),
        required_sections_text=required_sections,
    )

    with st.spinner("正在运行 Brief → Storyline → SlideSpec 工作流…"):
        try:
            with get_session() as session:
                result = run_presentation_workflow(
                    session,
                    project_id,
                    request,
                    export_json=export_json,
                    export_marp=export_marp,
                    export_pptx=export_pptx,
                    require_brief_review=require_brief_review,
                    require_storyline_review=require_storyline_review,
                    require_slides_review=require_slides_review,
                )
            st.session_state.last_workflow_result = result
        except WorkflowError as exc:
            st.error(format_user_error(exc))
            return
        except Exception as exc:
            st.error(format_user_error(exc))
            return

    if result.awaiting_review:
        st.warning("工作流已暂停，请在下方审核 Brief / Storyline 后继续。")
    elif result.succeeded:
        st.success(f"汇报已生成，共 {len(result.slides)} 页。")
    else:
        st.error("工作流完成但存在错误。")
        for error in result.errors:
            st.write(f"- {error}")


def _render_review_section(project_id: UUID) -> None:
    st.markdown("#### Brief / Storyline 审核")
    result = st.session_state.get("last_workflow_result")
    presentation_id = result.presentation.id if result is not None else None
    workflow_run_id = result.workflow_run.id if result is not None else None

    if presentation_id is None:
        with get_session() as session:
            presentations = list_project_presentations(session, project_id)
        if not presentations:
            st.caption("生成汇报后，可在此编辑 Brief 与 Storyline。")
            return
        presentation_id = presentations[0].id

    render_review_panel(
        presentation_id=presentation_id,
        workflow_run_id=workflow_run_id,
    )


def _render_last_result() -> None:
    result = st.session_state.get("last_workflow_result")
    if result is None:
        return

    st.markdown("#### 最近生成结果")
    if result.brief:
        st.markdown(f"**Brief：** {result.brief.title}")
        st.caption(
            f"对象：{result.brief.audience} · 目的：{result.brief.purpose} · "
            f"核心信息：{result.brief.core_message}"
        )
    if result.storyline:
        st.caption(f"Storyline 论点：{result.storyline.thesis}")

    if result.presentation is not None:
        with get_session() as session:
            from archium.application.review_service import PresentationReviewService
            from archium.domain.enums import ReviewSeverity, ReviewStatus

            issues = PresentationReviewService(session).list_review_issues(result.presentation.id)
        if issues:
            open_count = sum(1 for issue in issues if issue.status == ReviewStatus.OPEN)
            critical_count = sum(
                1
                for issue in issues
                if issue.severity == ReviewSeverity.CRITICAL and issue.status == ReviewStatus.OPEN
            )
            st.caption(
                f"质量审核：{len(issues)} 条记录，{open_count} 条待处理"
                + (f"，{critical_count} 条严重" if critical_count else "")
                + "。详见「质量审核」标签页。"
            )

    download_paths: list[Path] = []
    if result.json_path:
        download_paths.append(result.json_path)
    if result.marp_md_path:
        download_paths.append(result.marp_md_path)
    if result.marp_pptx_path:
        download_paths.append(result.marp_pptx_path)
    if download_paths:
        render_file_downloads(download_paths, key_prefix="workflow_result")


def _render_history(project_id: UUID) -> None:
    st.markdown("#### 历史汇报")
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)

    if not presentations:
        st.caption("暂无历史汇报。")
        return

    rows = [
        {
            "标题": presentation.title,
            "状态": presentation.status.value,
            "更新时间": presentation.updated_at.strftime("%Y-%m-%d %H:%M"),
        }
        for presentation in presentations
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render() -> None:
    _init_session_state()
    st.markdown("### 项目工作台")
    st.caption("管理项目资料，运行结构化汇报生成管线")

    _render_create_project()
    project_id = _render_project_selector()
    if project_id is None:
        return

    st.divider()
    _render_overview(project_id)
    st.divider()
    _render_documents(project_id)
    st.divider()
    render_chunk_panel(project_id)
    st.divider()
    _render_generation_form(project_id)
    _render_review_section(project_id)
    _render_last_result()
    st.divider()
    _render_history(project_id)
