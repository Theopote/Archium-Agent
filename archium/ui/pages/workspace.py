"""Streamlit project workspace page."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.unit_of_work import unit_of_work
from archium.application.workflow_models import WorkflowRunResult
from archium.domain.enums import ProjectType
from archium.domain.render import RenderResult
from archium.exceptions import WorkflowError
from archium.ui.asset_metadata_panel import render_asset_metadata_panel
from archium.ui.background_workflow_runner import (
    VisualJobAction,
    background_workflows_enabled,
    submit_presentation_workflow,
    submit_resume_workflow,
    submit_visual_job,
    warn_background_workflows_required,
)
from archium.ui.chunk_panel import render_chunk_panel
from archium.ui.components import render_file_downloads
from archium.ui.cultural_narrative_panel import render_cultural_narrative_panel
from archium.ui.error_handlers import report_user_error
from archium.ui.fact_ledger_panel import render_fact_ledger_panel
from archium.ui.knowledge_panel import render_knowledge_panel
from archium.ui.label_map import (
    CONTENT_PIPELINE_ACTION,
    brief_storyline_pair,
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
    presentation_has_visual_layout,
)
from archium.ui.workflow_progress_panel import (
    render_workflow_progress_panel,
    set_active_job_id,
)
from archium.ui.workflow_resume_ux import (
    RESUME_EXPORT_BUTTON_LABEL,
    RESUME_EXPORT_HELP,
    RESUME_EXPORT_STARTED,
    render_resume_failure,
)
from archium.ui.workspace_service import (
    UploadKnowledgeTip,
    backfill_project_asset_vision,
    build_presentation_request,
    create_project,
    export_presentation_pptx_legacy,
    get_project_overview,
    import_uploaded_file,
    list_project_documents,
    list_project_presentations,
    list_projects,
    reassess_knowledge_after_upload,
)

_UPLOAD_FEEDBACK_KEY = "materials_upload_feedback"

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
    preferred = (
        result.presentation.id
        if result is not None and result.presentation is not None
        else st.session_state.get("selected_presentation_id")
    )
    with unit_of_work() as uow:
        session = uow
        from archium.application.presentation_selection import select_presentation

        presentations = list_project_presentations(session, project_id)
        picked = select_presentation(
            session,
            presentations,
            preferred_id=preferred,
            keep_empty_preferred=False,
        )
    return picked.id if picked is not None else None


def _pptx_export_prompt_key(presentation_id: UUID) -> str:
    return f"pptx_export_prompt_{presentation_id}"


def _store_pptx_export_result(result: RenderResult) -> None:
    st.session_state.last_pptx_export_result = result


def _render_project_selector() -> UUID | None:
    with unit_of_work() as uow:
        projects = list_projects(uow)

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
        submitted = st.form_submit_button("创建项目", width="stretch")
        if submitted:
            if not name.strip():
                st.error("请填写项目名称")
                return
            with unit_of_work() as uow:
                session = uow
                from archium.ui.session_actor import get_current_actor_id

                project = create_project(
                    session,
                    name=name,
                    project_type=project_type,
                    description=description,
                    actor_id=get_current_actor_id(),
                )
            st.session_state.selected_project_id = str(project.id)
            st.success(f"已创建项目：{project.name}")
            st.rerun()


def _render_overview(project_id: UUID) -> None:
    from archium.ui.components.chrome import render_stat_chips

    with unit_of_work() as uow:
        overview = get_project_overview(uow, project_id)
    if overview is None:
        st.warning("项目不存在或已被删除。")
        return

    render_stat_chips(
        [
            ("资料文件", str(overview.document_count), "info"),
            ("文本片段", str(overview.chunk_count), "neutral"),
            ("汇报版本", str(overview.presentation_count), "info"),
            (
                "项目类型",
                PROJECT_TYPE_LABELS.get(overview.project.project_type, "其他"),
                "neutral",
            ),
        ]
    )


def _render_documents(project_id: UUID, *, show_uploader: bool = True) -> None:
    st.markdown("#### 项目资料")
    with unit_of_work() as uow:
        documents = list_project_documents(uow, project_id)

    if documents:
        rows = [
            {
                "文件名": doc.filename,
                "类型": doc.file_type.value,
                "状态": doc.processing_status.value,
                # Keep as str so mixed missing/present counts stay Arrow-compatible.
                "页数": str(doc.page_count) if doc.page_count else "-",
            }
            for doc in documents
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        with unit_of_work() as uow:
            from archium.application.project_context_routing import (
                is_concept_leaning,
                is_research_programming,
            )

            try:
                project = uow.api.project.get(project_id)
            except Exception:
                project = None
            if project is not None and is_concept_leaning(uow, project) and not is_research_programming(
                uow, project
            ):
                st.caption("概念探索中 — 资料可后续补充 enrich 任务理解。")
            elif project is not None and is_research_programming(uow, project):
                st.caption("策划与可研中 — 资料可后续补充 enrich 任务理解。")
            else:
                st.caption("尚未导入资料。上传任务书、图纸说明或调研文档后再生成汇报。")

    if show_uploader:
        _render_upload_controls(project_id, key_prefix="docs_upload")


def _consume_upload_feedback(project_id: UUID, *, key_prefix: str) -> None:
    """Show import + knowledge tip persisted across the post-upload rerun."""
    payload = st.session_state.get(_UPLOAD_FEEDBACK_KEY)
    if not isinstance(payload, dict):
        return
    if payload.get("project_id") != str(project_id):
        return

    for item in payload.get("file_messages", []):
        level = item.get("level", "success")
        text = item.get("text", "")
        if not text:
            continue
        if level == "error":
            st.error(text)
        elif level == "warning":
            st.warning(text)
        else:
            st.success(text)

    tip_data = payload.get("knowledge")
    tip: UploadKnowledgeTip | None = None
    if isinstance(tip_data, dict) and tip_data.get("summary_line"):
        tip = UploadKnowledgeTip(
            summary_line=str(tip_data.get("summary_line") or ""),
            understanding_summary=str(tip_data.get("understanding_summary") or ""),
            missing_information=tuple(tip_data.get("missing_information") or ()),
            next_action_labels=tuple(tip_data.get("next_action_labels") or ()),
            primary_action=tip_data.get("primary_action"),
            primary_action_label=str(tip_data.get("primary_action_label") or ""),
        )
        lines = [f"知识状态已更新：{tip.summary_line}"]
        if tip.understanding_summary:
            lines.append(tip.understanding_summary)
        if tip.missing_information:
            lines.append("仍缺：" + "；".join(tip.missing_information))
        if tip.next_action_labels:
            lines.append("建议下一步：" + " · ".join(tip.next_action_labels))
        st.info("\n\n".join(lines))

    cols = st.columns(2 if tip and tip.primary_action and tip.primary_action_label else 1)
    if tip and tip.primary_action and tip.primary_action_label:
        from archium.domain.intent.next_best_action import NextBestActionType
        from archium.ui.app_navigation import get_app_page
        from archium.ui.planning_service import resolve_next_best_action_target

        try:
            action = NextBestActionType(tip.primary_action)
        except ValueError:
            action = None
        if action is not None and cols[0].button(
            tip.primary_action_label,
            key=f"{key_prefix}_ks_next_{project_id}",
            type="primary",
            width="stretch",
        ):
            st.session_state.pop(_UPLOAD_FEEDBACK_KEY, None)
            pending = 0
            conflicts = 0
            try:
                from archium.application.fact_ledger_service import FactLedgerService

                with unit_of_work() as uow:
                    ledger = FactLedgerService(uow).get_ledger(project_id)
                pending = ledger.pending_count
                conflicts = ledger.conflict_count
            except Exception:
                from archium.logging import get_logger

                get_logger(__name__, operation="workspace_nba").debug(
                    "fact ledger unavailable for next-best-action",
                    exc_info=True,
                )
            target = resolve_next_best_action_target(
                action,
                pending_fact_count=pending,
                conflict_fact_count=conflicts,
            )
            if target.mission_step is not None:
                st.session_state.mission_step = target.mission_step
            if getattr(target, "focus", None):
                st.session_state["materials_focus"] = target.focus
            st.switch_page(get_app_page(target.page_key))
            return

    dismiss_col = cols[-1]
    if dismiss_col.button(
        "收起提示",
        key=f"{key_prefix}_ks_dismiss_{project_id}",
        width="stretch",
    ):
        st.session_state.pop(_UPLOAD_FEEDBACK_KEY, None)
        st.rerun()


def _render_upload_controls(project_id: UUID, *, key_prefix: str) -> None:
    """Primary materials upload action."""
    from archium.ui.upload_file_types import (
        PROJECT_MATERIAL_UPLOAD_CAPTION,
        PROJECT_MATERIAL_UPLOAD_TYPES,
    )

    _consume_upload_feedback(project_id, key_prefix=key_prefix)

    uploads = st.file_uploader(
        "选择文件",
        type=PROJECT_MATERIAL_UPLOAD_TYPES,
        accept_multiple_files=True,
        key=f"{key_prefix}_{project_id}",
        label_visibility="collapsed",
    )
    st.caption(PROJECT_MATERIAL_UPLOAD_CAPTION)
    if uploads and st.button(
        "上传资料",
        type="primary",
        width="stretch",
        key=f"{key_prefix}_import_{project_id}",
    ):
        results = []
        knowledge_tip: UploadKnowledgeTip | None = None
        settings = get_ui_effective_settings()
        with unit_of_work() as uow:
            for upload in uploads:
                results.append(
                    import_uploaded_file(
                        uow,
                        project_id,
                        filename=upload.name,
                        data=upload.getvalue(),
                        settings=settings,
                        reassess=False,
                    )
                )
            if any(not result.error for result in results):
                knowledge_tip = reassess_knowledge_after_upload(
                    uow, project_id, settings=settings
                )

        file_messages: list[dict[str, str]] = []
        for result in results:
            name = result.source_path.name
            if result.error:
                file_messages.append({"level": "error", "text": f"{name}: {result.error}"})
            elif result.duplicate:
                file_messages.append(
                    {"level": "warning", "text": f"{name}: 已存在相同文件，已跳过"}
                )
            else:
                chunk_count = len(result.chunks)
                asset_captions = sum(
                    1 for chunk in result.chunks if chunk.content_type == "asset_caption"
                )
                detail = f"{chunk_count} 个片段"
                if asset_captions:
                    detail += f"（含 {asset_captions} 个图档语义索引）"
                if result.visual_idea_seed_message:
                    detail += f"；{result.visual_idea_seed_message}"
                file_messages.append(
                    {"level": "success", "text": f"{name}: 导入成功（{detail}）"}
                )

        feedback: dict[str, object] = {
            "project_id": str(project_id),
            "file_messages": file_messages,
        }
        if knowledge_tip is not None:
            feedback["knowledge"] = {
                "summary_line": knowledge_tip.summary_line,
                "understanding_summary": knowledge_tip.understanding_summary,
                "missing_information": list(knowledge_tip.missing_information),
                "next_action_labels": list(knowledge_tip.next_action_labels),
                "primary_action": knowledge_tip.primary_action,
                "primary_action_label": knowledge_tip.primary_action_label,
            }
        st.session_state[_UPLOAD_FEEDBACK_KEY] = feedback
        st.rerun()
    settings = get_ui_effective_settings()
    if settings.asset_vision_rag_enabled and key_prefix.startswith("docs"):
        st.caption(
            "图档语义索引：导入时会为图纸/大图生成可检索描述并写入向量库。"
            "历史项目可点击下方按钮补建。"
        )
        if st.button("补建图档语义索引", key=f"backfill_vision_{project_id}"):
            try:
                with unit_of_work() as uow:
                    backfill_result = backfill_project_asset_vision(
                        uow, project_id, settings=settings
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


def _load_generation_contract(project_id: UUID):
    """Load the selected persisted plan; generation must not re-plan it."""
    from archium.application.review_service import PresentationReviewService

    preferred = st.session_state.get("selected_presentation_id")
    with unit_of_work() as uow:
        presentations = uow.api.project.list_presentations(project_id)
        if preferred:
            presentations.sort(key=lambda item: str(item.id) != str(preferred))
        for presentation in presentations:
            context = PresentationReviewService(uow).get_review_context(presentation.id)
            if context is not None and context.outline is not None:
                return context
    return None


def _render_approved_generation_contract(project_id: UUID, settings) -> bool:
    """Render a frozen human-approved input summary. Return True when handled."""
    context = _load_generation_contract(project_id)
    if context is None:
        return False

    from archium.application.slide_design_brief_service import design_briefs_ready
    from archium.domain.enums import ApprovalStatus
    from archium.ui.app_navigation import get_app_page

    brief = context.brief
    storyline = context.storyline
    outline = context.outline
    artifacts_approved = all(
        item is not None and item.approval_status == ApprovalStatus.APPROVED
        for item in (brief, storyline, outline)
    )
    briefs_ready, brief_missing = design_briefs_ready(outline)
    blockers: list[str] = []
    if not artifacts_approved:
        blockers.append("Brief、Storyline 与 Outline 必须保持批准状态")
    if not briefs_ready:
        blockers.extend(brief_missing)

    from archium.ui.components.chrome import render_stat_chips

    with st.container(border=True):
        st.markdown("#### 本次生成输入")
        st.caption("以下内容是生成合同。页面生成会复用这些已批准版本，不会重新规划任务或大纲。")
        approved_briefs = sum(
            1
            for item in outline.page_design_briefs
            if item.status == ApprovalStatus.APPROVED
        )
        render_stat_chips(
            [
                ("汇报", context.presentation.title, "info"),
                ("Outline", f"v{outline.version}", "info"),
                ("页面意图", str(len(outline.page_intents)), "neutral"),
                (
                    "设计摘要",
                    f"{approved_briefs}/{len(outline.page_design_briefs)}",
                    "ok"
                    if approved_briefs == len(outline.page_design_briefs)
                    else "warn",
                ),
            ]
        )
        st.markdown(f"**对象：** {outline.audience}  ")
        st.markdown(f"**目的：** {outline.purpose}  ")
        st.markdown(f"**核心论点：** {outline.thesis}")
        if blockers:
            st.warning("生成合同尚未就绪：" + "；".join(blockers))
            st.page_link(
                get_app_page("outline"),
                label="返回大纲完成确认",
                icon=":material/account_tree:",
            )
            return True

        replace_confirmed = True
        if context.slides:
            st.warning(
                f"当前已有 {len(context.slides)} 页。重新生成会先归档当前页面，再按批准输入生成新版本。"
            )
            replace_confirmed = st.checkbox(
                "我已理解并确认归档当前页面后重新生成",
                key=f"generate_replace_confirm_{context.presentation.id}",
            )

        if st.button(
            "按批准输入生成页面",
            type="primary",
            width="stretch",
            disabled=not replace_confirmed,
            key=f"generate_from_contract_{context.presentation.id}",
        ):
            if not settings.llm_configured:
                st.error("未配置 LLM API Key。请先前往设置。")
                st.page_link(get_app_page("settings"), label="前往 AI 服务设置")
                return True
            request = build_presentation_request(
                title=brief.title,
                audience=brief.audience,
                purpose=brief.purpose,
                core_message=brief.core_message,
                target_slide_count=outline.target_slide_count,
                required_sections_text="\n".join(brief.required_sections),
            )
            if background_workflows_enabled(settings):
                job = submit_presentation_workflow(
                    project_id,
                    request,
                    settings=settings,
                    export_json=True,
                    export_marp=True,
                    export_preview_images=True,
                    require_brief_review=False,
                    require_storyline_review=False,
                    require_outline_review=False,
                    require_slides_review=True,
                    reuse_presentation_id=context.presentation.id,
                )
                st.session_state.selected_presentation_id = str(context.presentation.id)
                set_active_job_id(project_id, job.job_id)
                st.info("已锁定批准输入并开始生成页面。生成后将暂停，等待人工复核页面内容。")
                render_workflow_progress_panel(project_id, job_id=job.job_id)
            else:
                warn_background_workflows_required()
    return True


def _render_generation_form(project_id: UUID) -> None:
    st.markdown("#### 生成汇报")
    settings = get_ui_effective_settings()
    if render_workflow_progress_panel(project_id):
        return
    if _render_approved_generation_contract(project_id, settings):
        return

    st.caption(
        f"生成{entity_label('SlideSpec')}后，可直接在本页「导出 PPTX」。"
        "若尚未运行视觉编排，导出时会提示是否先生成版式。"
    )
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往 **设置 → AI 服务** 配置，或在 `.env` 中设置 `GEMINI_API_KEY`。")
        return

    from archium.ui.workspace_service import (
        resolve_generation_form_defaults as _resolve_form_defaults,
    )

    with unit_of_work() as uow:
        defaults = _resolve_form_defaults(uow, project_id)

    with st.form("presentation_form"):
        title = st.text_input("汇报标题", value=defaults.title)
        audience = st.text_input("汇报对象", value=defaults.audience)
        purpose = st.text_input("汇报目的", value=defaults.purpose)
        core_message = st.text_area("核心信息", value=defaults.core_message)
        target_slide_count = st.number_input(
            "目标页数",
            min_value=3,
            max_value=40,
            value=int(defaults.target_slide_count),
        )
        required_sections = st.text_area(
            "必要章节（每行一项，或用顿号分隔）",
            value=defaults.sections,
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
                "导出 PresentationSpec JSON（遗留）",
                value=False,
                help="兼容用派生规格 presentation.spec.json，非正式交付 SSOT（正式可编辑 PPTX 认 RenderScene）。",
            )
            export_editable_pptx = spec_col2.checkbox(
                "导出可编辑 PPTX（正式：RenderScene）",
                value=False,
                help=(
                    "有视觉版式时走 RenderScene → presentation.pptx。"
                    "无版式时默认失败；需遗留 Spec 回退时在配置中启用 "
                    "allow_legacy_presentation_spec_pptx_fallback。"
                ),
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
        submitted = st.form_submit_button(CONTENT_PIPELINE_ACTION, width="stretch")

    if not submitted:
        return

    resolved_title = title.strip() or defaults.title
    resolved_audience = audience.strip() or defaults.audience
    resolved_purpose = purpose.strip() or defaults.purpose
    resolved_core = core_message.strip() or defaults.core_message
    if not all([resolved_title, resolved_audience, resolved_purpose, resolved_core]):
        st.error("请完整填写标题、对象、目的与核心信息。")
        return

    request = build_presentation_request(
        title=resolved_title,
        audience=resolved_audience,
        purpose=resolved_purpose,
        core_message=resolved_core,
        target_slide_count=int(target_slide_count),
        required_sections_text=required_sections,
    )

    export_kwargs = {
        "export_json": export_json,
        "export_marp": export_marp,
        "export_presentation_spec": export_presentation_spec,
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

    warn_background_workflows_required()


def _render_review_section(project_id: UUID) -> None:
    st.markdown(f"#### {brief_storyline_pair()} 审核")
    result = st.session_state.get("last_workflow_result")
    presentation_id = result.presentation.id if result is not None else None
    workflow_run_id = result.workflow_run.id if result is not None else None

    if presentation_id is None:
        with unit_of_work() as uow:
            presentations = list_project_presentations(uow, project_id)
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
        with unit_of_work() as uow:
            session = uow
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
        project_id = (
            result.presentation.project_id
            if result.presentation is not None
            else st.session_state.get("selected_project_id")
        )
        if project_id is None:
            st.caption("缺少项目上下文，无法重试导出。")
            return
        if st.button(
            RESUME_EXPORT_BUTTON_LABEL,
            key=f"retry_export_{workflow_run_id}",
            help=RESUME_EXPORT_HELP,
        ):
            settings = get_ui_effective_settings()
            if not background_workflows_enabled(settings):
                warn_background_workflows_required()
                return
            try:
                job = submit_resume_workflow(
                    project_id,
                    workflow_run_id,
                    settings=settings,
                )
                set_active_job_id(project_id, job.job_id)
                st.info(RESUME_EXPORT_STARTED)
                render_workflow_progress_panel(project_id, job_id=job.job_id)
            except WorkflowError as exc:
                render_resume_failure(exc, project_id=project_id)
            except Exception as exc:
                render_resume_failure(exc, project_id=project_id)

    download_paths: list[Path] = list(result.render.output_paths())
    if result.render.warnings:
        for warning in result.render.warnings:
            st.warning(warning)
    if result.render.preview_images:
        st.markdown("**幻灯片预览**")
        preview_cols = st.columns(min(3, len(result.render.preview_images)))
        for index, image_path in enumerate(result.render.preview_images):
            with preview_cols[index % len(preview_cols)]:
                st.image(str(image_path), caption=f"第 {index + 1} 页", width="stretch")
    if download_paths:
        render_file_downloads(download_paths, key_prefix="workflow_result")


def _render_pptx_export_section(project_id: UUID) -> None:
    presentation_id = _resolve_active_presentation_id(project_id)
    if presentation_id is None:
        st.caption("生成汇报后可在此导出 PPTX。")
        return

    st.markdown("#### 导出 PPTX")
    st.caption(
        "推荐路径：先完成视觉编排，再按 RenderScene 导出可编辑 PPTX。"
        "也可跳过视觉编排，直接使用旧版 PresentationSpec 模板。"
    )

    with unit_of_work() as uow:
        has_visual_layout = presentation_has_visual_layout(uow, presentation_id)

    prompt_key = _pptx_export_prompt_key(presentation_id)
    show_prompt = bool(st.session_state.get(prompt_key))

    if st.button(
        "导出 PPTX",
        type="primary",
        width="stretch",
        key=f"export_pptx_main_{presentation_id}",
    ):
        if has_visual_layout:
            st.session_state.pop(prompt_key, None)
            try:
                with st.spinner("正在按 RenderScene 导出 PPTX…"), unit_of_work() as uow:
                    session = uow
                    export_result = export_presentation_pptx_from_layout_plans(
                        session,
                        presentation_id,
                    )
                _store_pptx_export_result(export_result)
                st.success("PPTX 已导出（视觉版式）。")
            except WorkflowError as exc:
                st.error(report_user_error(exc))
            except Exception as exc:
                st.error(report_user_error(exc))
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
            width="stretch",
            key=f"export_pptx_generate_{presentation_id}",
        ):
            st.session_state.pop(prompt_key, None)
            settings = get_ui_effective_settings()
            if not background_workflows_enabled(settings):
                warn_background_workflows_required()
                return
            try:
                job = submit_visual_job(
                    project_id,
                    presentation_id,
                    VisualJobAction.RUN,
                    settings=settings,
                    require_art_direction_review=True,
                    use_llm=False,
                    export_pptx=True,
                )
                set_active_job_id(
                    project_id,
                    job.job_id,
                    scope="visual",
                    presentation_id=presentation_id,
                )
                st.info("已在后台生成视觉编排并导出 PPTX，请查看进度。")
                render_workflow_progress_panel(
                    project_id,
                    scope="visual",
                    presentation_id=presentation_id,
                    job_id=job.job_id,
                    result_session_key="last_visual_workflow_result",
                    success_message="视觉编排完成。",
                )
            except WorkflowError as exc:
                st.error(report_user_error(exc))
            except Exception as exc:
                st.error(report_user_error(exc))

        if col_legacy.button(
            "直接用旧版模板导出",
            width="stretch",
            key=f"export_pptx_legacy_{presentation_id}",
        ):
            st.session_state.pop(prompt_key, None)
            try:
                with st.spinner("正在使用旧版模板导出 PPTX…"), unit_of_work() as uow:
                    session = uow
                    export_result = export_presentation_pptx_legacy(
                        session,
                        presentation_id,
                    )
                _store_pptx_export_result(export_result)
                st.success("PPTX 已导出（旧版模板）。")
                st.rerun()
            except WorkflowError as exc:
                st.error(report_user_error(exc))
            except Exception as exc:
                st.error(report_user_error(exc))
    elif has_visual_layout:
        st.caption("当前汇报已具备视觉版式，点击上方按钮将按 RenderScene 导出。")

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
    with unit_of_work() as uow:
        presentations = list_project_presentations(uow, project_id)

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
    st.dataframe(rows, width="stretch", hide_index=True)


def render() -> None:
    from archium.ui.components.chrome import render_page_header
    from archium.ui.components.enhanced_ui import render_info_tooltip

    _init_session_state()
    render_page_header(
        "项目工作台",
        "完整工作台，包含高级诊断和深度管理功能。日常使用请走制作五阶段。",
    )

    st.markdown(
        "💡 **使用建议**: 日常工作使用简化的五阶段流程；"
        "需要深度诊断或批量管理时使用本页。"
    )

    _render_create_project()
    project_id = _render_project_selector()
    if project_id is None:
        return

    _render_overview(project_id)

    # 重新组织为更清晰的三个主标签页
    tab_materials, tab_diagnostics, tab_advanced = st.tabs(
        ["📁 资料与事实", "🔍 诊断工具", "⚙️ 高级功能"]
    )

    with tab_materials:
        st.markdown("### 资料管理")
        st.caption("上传文档、管理事实台账、组织素材。")
        render_materials_stage(project_id)

    with tab_diagnostics:
        st.markdown("### 诊断工具")
        st.caption("检索预览、分块检查、事实冲突检测等高级诊断功能。")
        _render_diagnostics_tab(project_id)

    with tab_advanced:
        st.markdown("### 高级功能")
        st.caption("生成管线、审核工具、历史记录等完整功能。")
        _render_advanced_tab(project_id)


def _render_diagnostics_tab(project_id: UUID) -> None:
    """诊断工具标签页 - 整合 RAG、分块、文化叙事等功能。"""
    diag_tabs = st.tabs(["🔎 检索预览", "📦 分块检查", "📊 事实冲突", "🏛️ 文化叙事"])

    with diag_tabs[0]:
        st.caption("测试 RAG 检索效果，查看返回的文档片段。")
        render_rag_preview_panel(project_id)

    with diag_tabs[1]:
        st.caption("查看文档如何被切分为片段，检查分块质量。")
        render_chunk_panel(project_id)

    with diag_tabs[2]:
        st.caption("查看待确认和冲突的事实，进行人工核实。")
        render_fact_ledger_panel(project_id, highlight_pending=True)

    with diag_tabs[3]:
        st.caption("文化建筑项目的叙事线索和主题提取。")
        render_cultural_narrative_panel(project_id)


def _render_advanced_tab(project_id: UUID) -> None:
    """高级功能标签页 - 生成、审核、历史。"""
    adv_tabs = st.tabs(["⚡ 生成管线", "✅ 审核工具", "📜 历史记录"])

    with adv_tabs[0]:
        st.caption("直接填写 Brief 并运行生成管线（高级用户）。")
        render_generate_stage(project_id, include_export=True)

    with adv_tabs[1]:
        st.caption("查看审核质量、批评报告和改进建议。")
        render_review_stage(project_id)

    with adv_tabs[2]:
        st.caption("查看项目历史、版本记录和导出日志。")
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
    """资料阶段：摘要指标 + 上传主操作 + 文件/事实/素材/缺口；高级工具收折。"""
    from archium.ui.materials_summary import load_materials_summary

    with unit_of_work() as uow:
        summary = load_materials_summary(uow, project_id)

    from archium.ui.components.chrome import render_stat_chips

    pending = summary.pending_confirm_count
    render_stat_chips(
        [
            ("文件", str(summary.file_count), "info"),
            ("事实", str(summary.fact_count), "info"),
            ("素材", str(summary.asset_count), "neutral"),
            ("待确认", str(pending), "warn" if pending else "ok"),
        ]
    )

    focus = st.session_state.pop("materials_focus", None)
    if focus == "pending_facts":
        st.info(
            "建议先确认待核实 / 冲突事实，再继续概念探索或任务理解。"
            "确认后会写入意图出处。"
        )
        with st.container(border=True):
            render_fact_ledger_panel(project_id, highlight_pending=True)

    with st.container(border=False):
        st.markdown("**上传资料**")
        st.caption("任务书、图纸、调研文档或图片。导入成功后会刷新知识状态并提示下一步。")
        _render_upload_controls(project_id, key_prefix="materials_top")

    tab_files, tab_facts, tab_assets, tab_gaps = st.tabs(
        ["文件", "事实", "素材", "缺口"]
    )
    with tab_files:
        _render_documents(project_id, show_uploader=False)
    with tab_facts:
        if focus != "pending_facts":
            render_fact_ledger_panel(project_id)
        else:
            st.caption("待确认事实已在上方突出显示。")
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
