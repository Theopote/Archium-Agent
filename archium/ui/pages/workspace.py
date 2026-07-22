"""Streamlit project workspace page."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.workflow_models import WorkflowRunResult
from archium.domain.enums import ProjectType
from archium.domain.render import RenderResult
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.asset_metadata_panel import render_asset_metadata_panel
from archium.ui.background_workflow_runner import (
    background_workflows_enabled,
    submit_presentation_workflow,
)
from archium.ui.chunk_panel import render_chunk_panel
from archium.ui.components import render_file_downloads
from archium.ui.cultural_narrative_panel import render_cultural_narrative_panel
from archium.ui.error_handlers import format_user_error
from archium.ui.fact_ledger_panel import render_fact_ledger_panel
from archium.ui.knowledge_panel import render_knowledge_panel
from archium.ui.label_map import (
    brief_storyline_pair,
    content_pipeline_chain,
    entity_label,
)
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.rag_preview_panel import render_rag_preview_panel
from archium.ui.reference_style_panel import render_reference_style_panel
from archium.ui.renovation_issue_panel import render_renovation_issue_panel
from archium.ui.review_analytics_panel import render_project_review_quality_dashboard
from archium.ui.review_panel import render_review_panel
from archium.ui.visual_service import (
    export_presentation_pptx_from_layout_plans,
    generate_visual_and_export_pptx,
    presentation_has_visual_layout,
)
from archium.ui.workflow_progress_panel import (
    render_workflow_progress_panel,
    set_active_job_id,
)
from archium.ui.workspace_service import (
    backfill_project_asset_vision,
    build_presentation_request,
    create_project,
    export_presentation_pptx_legacy,
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
    if "last_pptx_export_result" not in st.session_state:
        st.session_state.last_pptx_export_result = None


def _resolve_active_presentation_id(project_id: UUID) -> UUID | None:
    result: WorkflowRunResult | None = st.session_state.get("last_workflow_result")
    if result is not None and result.presentation is not None:
        return result.presentation.id
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)
    return presentations[0].id if presentations else None


def _pptx_export_prompt_key(presentation_id: UUID) -> str:
    return f"pptx_export_prompt_{presentation_id}"


def _store_pptx_export_result(result: RenderResult) -> None:
    st.session_state.last_pptx_export_result = result


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
        "上传资料",
        type=["pdf", "docx", "pptx", "xlsx", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"upload_{project_id}",
    )
    if uploads and st.button("上传资料", type="primary", key=f"import_{project_id}"):
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
                asset_captions = sum(
                    1 for chunk in result.chunks if chunk.content_type == "asset_caption"
                )
                detail = f"{chunk_count} 个片段"
                if asset_captions:
                    detail += f"（含 {asset_captions} 个图档语义索引）"
                st.success(f"{result.source_path.name}: 导入成功（{detail}）")
        st.rerun()

    settings = get_ui_effective_settings()
    if settings.asset_vision_rag_enabled:
        st.caption(
            "图档语义索引：导入时会为图纸/大图生成可检索描述并写入向量库。"
            "历史项目可点击下方按钮补建。"
        )
        if st.button("补建图档语义索引", key=f"backfill_vision_{project_id}"):
            try:
                with get_session() as session:
                    backfill_result = backfill_project_asset_vision(
                        session, project_id, settings=settings
                    )
                if backfill_result.chunks_created:
                    st.success(
                        f"已补建 {backfill_result.chunks_created} 个图档语义片段"
                        f"（处理 {backfill_result.assets_processed} 个素材）。"
                    )
                else:
                    st.info("没有需要补建的图档素材，或功能已关闭。")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_generation_form(project_id: UUID) -> None:
    st.markdown("#### 生成汇报")
    settings = get_ui_effective_settings()
    if render_workflow_progress_panel(project_id):
        return

    st.caption(
        f"生成{entity_label('SlideSpec')}后，可直接在本页「导出 PPTX」。"
        "若尚未运行视觉编排，导出时会提示是否先生成版式。"
    )
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往 **设置 → AI 服务** 配置，或在 `.env` 中设置 `GEMINI_API_KEY`。")
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
        with st.expander("高级选项", expanded=False):
            st.caption("导出格式与分阶段审核暂停。默认即可生成；需要时再展开调整。")
            col1, col2, col3, col4 = st.columns(4)
            export_json = col1.checkbox("导出 JSON", value=True)
            export_marp = col2.checkbox("导出 Marp Markdown", value=True)
            export_pptx = col3.checkbox("导出 PPTX（Marp CLI）", value=False)
            export_pdf = col4.checkbox("导出 PDF（Marp CLI）", value=False)
            spec_col1, spec_col2 = st.columns(2)
            export_presentation_spec = spec_col1.checkbox(
                "导出 PresentationSpec JSON",
                value=False,
                help="生成 presentation.spec.json，供 PptxGenJS 或其它渲染器使用。",
            )
            export_editable_pptx = spec_col2.checkbox(
                "导出可编辑 PPTX（PptxGenJS）",
                value=False,
                help="需 Node.js，并在 archium/infrastructure/renderers/pptxgen 目录运行 npm install。",
            )
            export_preview_images = st.checkbox(
                "生成幻灯片预览图 PNG（需 Marp CLI）",
                value=export_marp,
                help="导出 Marp Markdown 后，通过 marp --images 生成逐页 PNG 预览。",
            )
            review_col1, review_col2, review_col3, review_col4 = st.columns(4)
            require_brief_review = review_col1.checkbox(
                f"{entity_label('PresentationBrief')} 生成后暂停审核",
                value=True,
            )
            require_storyline_review = review_col2.checkbox(
                f"{entity_label('Storyline')} 生成后暂停审核",
                value=True,
            )
            require_outline_review = review_col3.checkbox(
                f"{entity_label('OutlinePlan')} 生成后暂停审核",
                value=True,
            )
            require_slides_review = review_col4.checkbox(
                f"{entity_label('SlideSpec')} 生成后暂停审核",
                value=False,
            )
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

    export_kwargs = {
        "export_json": export_json,
        "export_marp": export_marp,
        "export_presentation_spec": export_presentation_spec or export_editable_pptx,
        "export_editable_pptx": export_editable_pptx,
        "export_pptx": export_pptx,
        "export_pdf": export_pdf,
        "export_preview_images": export_preview_images and export_marp,
        "require_brief_review": require_brief_review,
        "require_storyline_review": require_storyline_review,
        "require_outline_review": require_outline_review,
        "require_slides_review": require_slides_review,
    }

    if background_workflows_enabled(settings):
        job = submit_presentation_workflow(
            project_id,
            request,
            settings=settings,
            **export_kwargs,
        )
        set_active_job_id(project_id, job.job_id)
        st.info("已在后台启动汇报管线，下方将实时显示进度。")
        render_workflow_progress_panel(project_id, job_id=job.job_id)
        return

    with st.spinner(f"正在运行 {content_pipeline_chain()} 工作流…"):
        try:
            with get_session() as session:
                result = run_presentation_workflow(
                    session,
                    project_id,
                    request,
                    settings=settings,
                    **export_kwargs,
                )
            st.session_state.last_workflow_result = result
        except WorkflowError as exc:
            st.error(format_user_error(exc))
            return
        except Exception as exc:
            st.error(format_user_error(exc))
            return

    if result.awaiting_review:
        st.warning(
            f"工作流已暂停，请切换到「审核」标签页继续处理 {brief_storyline_pair()}。"
        )
    elif result.succeeded:
        st.success(f"汇报已生成，共 {len(result.slides)} 页。")
    else:
        st.error("工作流完成但存在错误。")
        for error in result.errors:
            st.write(f"- {error}")


def _render_review_section(project_id: UUID) -> None:
    st.markdown(f"#### {brief_storyline_pair()} 审核")
    result = st.session_state.get("last_workflow_result")
    presentation_id = result.presentation.id if result is not None else None
    workflow_run_id = result.workflow_run.id if result is not None else None

    if presentation_id is None:
        with get_session() as session:
            presentations = list_project_presentations(session, project_id)
        if not presentations:
            st.caption(
                f"生成汇报后，可在此编辑{entity_label('PresentationBrief')}与"
                f"{entity_label('Storyline')}。"
            )
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
        st.markdown(f"**{entity_label('PresentationBrief')}：** {result.brief.title}")
        st.caption(
            f"对象：{result.brief.audience} · 目的：{result.brief.purpose} · "
            f"核心信息：{result.brief.core_message}"
        )
    if result.storyline:
        st.caption(f"{entity_label('Storyline')} 论点：{result.storyline.thesis}")

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
                + "。详见「审核」标签页。"
            )

    if result.errors:
        st.error("工作流未完成：" + "；".join(result.errors))
        workflow_run_id = result.workflow_run.id
        if st.button("重试工作流导出", key=f"retry_export_{workflow_run_id}"):
            from archium.ui.workspace_service import resume_workflow

            try:
                retried = resume_workflow(workflow_run_id)
                st.session_state.last_workflow_result = retried
                if retried.succeeded:
                    st.success("导出已完成。")
                else:
                    st.warning("仍有错误，请检查质量审核或继续编辑内容。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

    download_paths: list[Path] = list(result.render.output_paths())
    if result.render.warnings:
        for warning in result.render.warnings:
            st.warning(warning)
    if result.render.preview_images:
        st.markdown("**幻灯片预览**")
        preview_cols = st.columns(min(3, len(result.render.preview_images)))
        for index, image_path in enumerate(result.render.preview_images):
            with preview_cols[index % len(preview_cols)]:
                st.image(str(image_path), caption=f"第 {index + 1} 页", use_container_width=True)
    if download_paths:
        render_file_downloads(download_paths, key_prefix="workflow_result")


def _render_pptx_export_section(project_id: UUID) -> None:
    presentation_id = _resolve_active_presentation_id(project_id)
    if presentation_id is None:
        st.caption("生成汇报后可在此导出 PPTX。")
        return

    st.markdown("#### 导出 PPTX")
    st.caption(
        f"推荐路径：先完成视觉编排，再按{entity_label('LayoutPlan')}坐标导出可编辑 PPTX。"
        "也可跳过视觉编排，直接使用旧版 PresentationSpec 模板。"
    )

    with get_session() as session:
        has_visual_layout = presentation_has_visual_layout(session, presentation_id)

    prompt_key = _pptx_export_prompt_key(presentation_id)
    show_prompt = bool(st.session_state.get(prompt_key))

    if st.button(
        "导出 PPTX",
        type="primary",
        use_container_width=True,
        key=f"export_pptx_main_{presentation_id}",
    ):
        if has_visual_layout:
            st.session_state.pop(prompt_key, None)
            try:
                with (
                    st.spinner(f"正在按{entity_label('LayoutPlan')}导出 PPTX…"),
                    get_session() as session,
                ):
                    export_result = export_presentation_pptx_from_layout_plans(
                        session,
                        presentation_id,
                    )
                _store_pptx_export_result(export_result)
                st.success("PPTX 已导出（视觉版式）。")
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))
        else:
            st.session_state[prompt_key] = True
            st.rerun()

    if show_prompt:
        st.warning(
            "检测到尚未生成视觉版式。"
            f"推荐现在生成{entity_label('ArtDirection')}与{entity_label('LayoutPlan')}后再导出；"
            "也可直接使用旧版模板导出（质量较低）。"
        )
        col_recommended, col_legacy = st.columns(2)
        if col_recommended.button(
            "现在生成（推荐）",
            type="primary",
            use_container_width=True,
            key=f"export_pptx_generate_{presentation_id}",
        ):
            st.session_state.pop(prompt_key, None)
            try:
                with (
                    st.spinner("正在生成视觉编排并导出 PPTX…"),
                    get_session() as session,
                ):
                    visual_result = generate_visual_and_export_pptx(
                        session,
                        project_id,
                        presentation_id,
                    )
                st.session_state.last_visual_workflow_result = visual_result
                if visual_result.awaiting_review:
                    if visual_result.review_gate == "layout_review":
                        st.warning(
                            "版式仍有 ERROR/CRITICAL 问题，已暂停 PPTX 导出。"
                            "请前往「视觉设计 → 单页视觉」调整后继续，"
                            "或使用旧版模板导出。"
                        )
                    else:
                        st.info("已生成视觉方向，等待批准。请前往「视觉设计」继续。")
                elif visual_result.succeeded:
                    pptx_paths = [
                        Path(path)
                        for path in visual_result.render_paths
                        if path.lower().endswith(".pptx")
                    ]
                    if pptx_paths:
                        _store_pptx_export_result(
                            RenderResult(
                                editable_pptx_path=pptx_paths[-1],
                                warnings=list(visual_result.warnings),
                            )
                        )
                        st.success("视觉编排完成，PPTX 已导出。")
                    else:
                        with get_session() as session:
                            export_result = export_presentation_pptx_from_layout_plans(
                                session,
                                presentation_id,
                            )
                        _store_pptx_export_result(export_result)
                        st.success("视觉编排完成，PPTX 已导出。")
                else:
                    detail = (
                        "；".join(visual_result.errors)
                        if visual_result.errors
                        else "未知错误"
                    )
                    st.error(f"视觉编排未完成：{detail}")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

        if col_legacy.button(
            "直接用旧版模板导出",
            use_container_width=True,
            key=f"export_pptx_legacy_{presentation_id}",
        ):
            st.session_state.pop(prompt_key, None)
            try:
                with (
                    st.spinner("正在使用旧版模板导出 PPTX…"),
                    get_session() as session,
                ):
                    export_result = export_presentation_pptx_legacy(
                        session,
                        presentation_id,
                    )
                _store_pptx_export_result(export_result)
                st.success("PPTX 已导出（旧版模板）。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))
    elif has_visual_layout:
        st.caption(
            f"当前汇报已具备视觉版式，点击上方按钮将按{entity_label('LayoutPlan')}导出。"
        )

    cached_export_result: RenderResult | None = st.session_state.get("last_pptx_export_result")
    if cached_export_result is not None:
        download_paths = list(cached_export_result.output_paths())
        if cached_export_result.warnings:
            for warning in cached_export_result.warnings:
                st.warning(warning)
        if download_paths:
            st.markdown("**PPTX 下载**")
            render_file_downloads(download_paths, key_prefix="pptx_export")


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
    st.caption("管理项目资料，运行结构化汇报生成管线（深层工具页；日常请走制作五阶段）")
    from archium.ui.product_flow import product_flow_chain

    st.info(
        f"推荐主流程：{product_flow_chain()}。"
        f"本页仍可作为快捷路径直接填写{entity_label('PresentationBrief')}并生成。"
    )

    _render_create_project()
    project_id = _render_project_selector()
    if project_id is None:
        return

    _render_overview(project_id)

    tab_materials, tab_generate, tab_review, tab_history = st.tabs(
        ["资料管理", "生成", "审核", "历史"]
    )

    with tab_materials:
        render_materials_stage(project_id)

    with tab_generate:
        render_generate_stage(project_id, include_export=True)

    with tab_review:
        render_review_stage(project_id)

    with tab_history:
        _render_history(project_id)


def ensure_workspace_session() -> None:
    """Initialize session keys shared by workspace and product-flow stages."""
    _init_session_state()


def render_project_picker(*, allow_create: bool = True) -> UUID | None:
    """Shared project create + select controls for product-flow stages."""
    ensure_workspace_session()
    if allow_create:
        _render_create_project()
    return _render_project_selector()


def render_materials_stage(project_id: UUID) -> None:
    """资料阶段：摘要指标 + 文件/事实/素材/缺口；高级工具收折。"""
    from archium.ui.materials_summary import load_materials_summary

    with get_session() as session:
        summary = load_materials_summary(session, project_id)

    metric_cols = st.columns(4)
    metric_cols[0].metric("文件", summary.file_count)
    metric_cols[1].metric("事实", summary.fact_count)
    metric_cols[2].metric("素材", summary.asset_count)
    metric_cols[3].metric("待确认问题", summary.pending_confirm_count)

    st.caption(
        f"{summary.file_count} 个文件 · {summary.fact_count} 条事实 · "
        f"{summary.asset_count} 项素材 · {summary.gap_count} 个资料缺口"
    )

    tab_files, tab_facts, tab_assets, tab_gaps = st.tabs(
        ["文件", "事实", "素材", "缺口"]
    )
    with tab_files:
        _render_documents(project_id)
    with tab_facts:
        render_fact_ledger_panel(project_id)
    with tab_assets:
        render_asset_metadata_panel(project_id)
    with tab_gaps:
        render_knowledge_panel(project_id)

    with st.expander("更多工具（片段 / 叙事 / 风格 / 检索）", expanded=False):
        st.caption("日常资料整理不需要这些面板；需要深度排查时再打开。")
        render_chunk_panel(project_id)
        st.divider()
        render_cultural_narrative_panel(project_id)
        st.divider()
        render_renovation_issue_panel(project_id)
        st.divider()
        render_reference_style_panel(project_id)
        st.divider()
        render_rag_preview_panel(project_id)


def render_generate_stage(project_id: UUID, *, include_export: bool = False) -> None:
    """生成阶段：内容管线与最近结果。

    ``include_export`` is True for the advanced workspace page; the primary
    「交付」stage owns export in the five-stage flow.
    """
    _render_generation_form(project_id)
    _render_last_result()
    if include_export:
        st.divider()
        _render_pptx_export_section(project_id)


def render_review_stage(project_id: UUID) -> None:
    """质量审核区块，供交付阶段与工作台复用。"""
    render_project_review_quality_dashboard(project_id)
    st.divider()
    _render_review_section(project_id)
