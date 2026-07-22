"""Product-flow stage: 交付 — readiness / QA / export / version records."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.studio.export_panel import render_export_panel
from archium.ui.studio_service import (
    StudioPresentationContext,
    get_selected_slide_snapshot,
    list_studio_presentations,
    list_studio_projects,
    load_studio_context,
)


def _workflow_artifacts() -> tuple[list[dict] | None, dict | None, list[str] | None, str | None]:
    result = st.session_state.get("last_visual_workflow_result")
    if not isinstance(result, VisualWorkflowResult):
        return None, None, None, None
    deck_qa = result.deck_qa_report if isinstance(result.deck_qa_report, dict) else None
    critics = list(result.visual_critic_reports or [])
    previews = list(result.render_paths or [])
    output_dir = result.workflow_run.state.get("output_dir")
    return critics, deck_qa, previews, output_dir if isinstance(output_dir, str) else None


def _load_context(
    project_id: UUID,
    presentation_id: UUID,
) -> StudioPresentationContext | None:
    critics, deck_qa, previews, workflow_output_dir = _workflow_artifacts()
    with get_session() as session:
        return load_studio_context(
            session,
            project_id=project_id,
            presentation_id=presentation_id,
            visual_critic_reports=critics,
            deck_qa_report=deck_qa,
            preview_paths=previews,
            workflow_output_dir=workflow_output_dir,
        )


def _resolve_deliver_context() -> StudioPresentationContext | None:
    """Use session selection; offer a compact switcher only when needed."""
    from archium.ui.pages.workspace import ensure_workspace_session

    ensure_workspace_session()
    with get_session() as session:
        projects = list_studio_projects(session)
    if not projects:
        return None

    project_labels = {str(project.id): project.name for project in projects}
    project_options = list(project_labels.keys())
    selected_project = st.session_state.get("selected_project_id")
    if selected_project not in project_options:
        selected_project = project_options[0]
        st.session_state.selected_project_id = selected_project
    project_id = UUID(str(selected_project))

    with get_session() as session:
        presentations = list_studio_presentations(session, project_id)
    if not presentations:
        st.caption(f"项目「{project_labels[str(project_id)]}」尚无汇报可导出。")
        with st.expander("切换项目", expanded=True):
            picked = st.selectbox(
                "项目",
                options=project_options,
                index=project_options.index(str(project_id)),
                format_func=lambda value: project_labels[value],
                key="deliver_switch_project",
            )
            if picked != str(project_id):
                st.session_state.selected_project_id = picked
                st.session_state.selected_presentation_id = None
                st.rerun()
        return None

    presentation_labels = {
        str(item.id): f"{item.title} · {item.status.value}" for item in presentations
    }
    presentation_options = list(presentation_labels.keys())
    selected_presentation = st.session_state.get("selected_presentation_id")
    if selected_presentation not in presentation_options:
        selected_presentation = presentation_options[0]
        st.session_state.selected_presentation_id = selected_presentation

    context = _load_context(project_id, UUID(str(selected_presentation)))
    if context is None:
        return None

    st.caption(
        f"当前导出：{project_labels[str(project_id)]} · "
        f"{presentation_labels[str(selected_presentation)]}"
    )
    with st.expander("切换汇报版本", expanded=False):
        cols = st.columns(2)
        with cols[0]:
            picked_project = st.selectbox(
                "项目",
                options=project_options,
                index=project_options.index(str(project_id)),
                format_func=lambda value: project_labels[value],
                key="deliver_switch_project",
            )
        with cols[1]:
            if picked_project != str(project_id):
                st.session_state.selected_project_id = picked_project
                st.session_state.selected_presentation_id = None
                st.rerun()
            picked_presentation = st.selectbox(
                "汇报版本",
                options=presentation_options,
                index=presentation_options.index(str(selected_presentation)),
                format_func=lambda value: presentation_labels[value],
                key="deliver_switch_presentation",
            )
        if picked_presentation != str(selected_presentation):
            st.session_state.selected_presentation_id = picked_presentation
            st.rerun()
    return context


def _render_readiness(context: StudioPresentationContext) -> None:
    st.markdown("#### 准备度")
    ready = bool(context.ready_for_export)
    pending = max(0, context.slide_count - context.layout_ready_count)

    warn_count = 0
    blocker_count = 0
    deck_qa = st.session_state.get("last_visual_workflow_result")
    if isinstance(deck_qa, VisualWorkflowResult) and isinstance(deck_qa.deck_qa_report, dict):
        warn_count = int(deck_qa.deck_qa_report.get("warning_count") or 0)
        blocker_count = int(deck_qa.deck_qa_report.get("blocker_count") or 0)

    from archium.application.project_evidence import resolve_project_evidence_safe
    from archium.domain.enums import EvidenceAvailability

    evidence = resolve_project_evidence_safe(context.project.id)
    if evidence.availability == EvidenceAvailability.UNKNOWN:
        st.error("资料状态无法验证 · 禁止正式交付（请检查数据库后重试）")
        materials_label = "无法验证"
    elif evidence.is_concept_draft:
        # Global draft banner already shown in stage header; keep metric only.
        materials_label = "0 份"
    else:
        materials_label = f"{evidence.document_count} 份"

    formal_ready = (
        ready
        and evidence.allows_formal_export
        and blocker_count <= 0
    )

    cols = st.columns(6)
    cols[0].metric(
        "页面完成",
        f"{context.layout_ready_count}/{context.slide_count}"
        if context.slide_count
        else "0/0",
    )
    cols[1].metric("待完成页", pending)
    cols[2].metric("警告", warn_count)
    cols[3].metric("阻塞项", blocker_count)
    cols[4].metric("项目资料", materials_label)
    if formal_ready:
        export_label = "可导出"
    elif evidence.availability == EvidenceAvailability.UNKNOWN:
        export_label = "待验证"
    elif evidence.is_concept_draft:
        export_label = "草稿"
    else:
        export_label = "版式未齐"
    cols[5].metric("导出", export_label)
    st.caption(
        "PPTX / PDF 目前共用版式准备度；后续将分别建模 pptx_readiness / pdf_readiness。"
    )


def _render_qa(project_id: UUID) -> None:
    st.markdown("#### QA")
    st.caption("导出前快速检查质量问题。研发 Benchmark 在「设置 → 开发者与验收」。")
    from archium.ui.pages.workspace import render_review_stage

    with st.expander("打开质量检查", expanded=False):
        render_review_stage(project_id)


def _render_delivery_records(presentation_id: UUID) -> None:
    st.markdown("#### 版本记录")
    import logging

    from archium.application.delivery_record_service import DeliveryRecordService

    logger = logging.getLogger(__name__)
    records_load_failed = False
    try:
        with get_session() as session:
            records = DeliveryRecordService(session).list_for_presentation(
                presentation_id, limit=12
            )
    except Exception:
        logger.exception("Failed to load delivery records")
        records = []
        records_load_failed = True
        st.warning("版本记录暂时无法从数据库读取。")

    if not records:
        legacy = list(st.session_state.get("delivery_export_records") or [])
        if not legacy:
            if not records_load_failed:
                st.caption("尚无导出记录。完成导出后会显示格式、时间与操作。")
            return
        st.caption("以下为本次会话的临时记录（尚未写入数据库）：")
        for item in reversed(legacy[-12:]):
            _render_delivery_record_actions(
                key_suffix=f"legacy_{item.get('when', '')}_{item.get('path', '')}",
                fmt=str(item.get("format", "文件")),
                when=str(item.get("when", "")),
                qa_status=str(item.get("qa_status", "unknown")),
                file_uri=str(item.get("path", "")),
                file_hash="",
            )
        return

    for item in records:
        when = item.exported_at.astimezone().strftime("%Y-%m-%d %H:%M")
        _render_delivery_record_actions(
            key_suffix=str(item.id),
            fmt=item.format,
            when=when,
            qa_status=item.qa_status,
            file_uri=item.file_uri,
            file_hash=item.file_hash,
        )


def _render_delivery_record_actions(
    *,
    key_suffix: str,
    fmt: str,
    when: str,
    qa_status: str,
    file_uri: str,
    file_hash: str,
) -> None:
    from pathlib import Path

    hash_note = f" · `{file_hash}`" if file_hash else ""
    st.markdown(f"**{fmt}** · {when} · QA {qa_status}{hash_note}")
    path = Path(file_uri) if file_uri else None
    cols = st.columns([2.4, 1, 1, 1])
    with cols[0]:
        st.caption(file_uri or "（无路径）")
    with cols[1]:
        if path is not None and path.is_file():
            st.download_button(
                "下载",
                data=path.read_bytes(),
                file_name=path.name,
                use_container_width=True,
                key=f"deliver_dl_{key_suffix}",
            )
        else:
            st.button(
                "下载",
                disabled=True,
                use_container_width=True,
                key=f"deliver_dl_{key_suffix}",
            )
    with cols[2]:
        if st.button("打开目录", use_container_width=True, key=f"deliver_open_{key_suffix}"):
            _open_containing_folder(file_uri)
    with cols[3]:
        if st.button("复制路径", use_container_width=True, key=f"deliver_copy_{key_suffix}"):
            st.session_state[f"deliver_copied_path_{key_suffix}"] = file_uri
            st.code(file_uri, language=None)
            st.caption("路径已显示，可手动复制。")


def _open_containing_folder(file_uri: str) -> None:
    import logging
    import os
    import subprocess
    import sys
    from pathlib import Path

    logger = logging.getLogger(__name__)
    path = Path(file_uri)
    target = path if path.is_dir() else path.parent
    if not target.exists():
        st.warning("文件目录不存在。")
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)
    except Exception:
        logger.exception("Failed to open folder %s", target)
        st.warning(f"无法打开目录：{target}")


def render() -> None:
    render_stage_header("deliver")
    st.caption("准备度、QA、导出与版本记录。不在此页做 Benchmark 或复杂工作室配置。")

    context = _resolve_deliver_context()
    if context is None:
        st.warning("尚未选择可导出的汇报。请先在「生成」或「工作室」准备页面内容。")
        from archium.ui import icons

        st.page_link(get_app_page("materials"), label="前往资料", icon=icons.MATERIALS)
        st.page_link(get_app_page("generate"), label="前往生成", icon=icons.GENERATE)
        render_stage_nav("deliver")
        return

    _render_readiness(context)
    st.divider()
    _render_qa(context.project.id)
    st.divider()

    selected_index = int(st.session_state.get("studio_selected_slide_index", 0))
    slide_snapshot = get_selected_slide_snapshot(context, selected_index)
    st.markdown("#### 导出")
    st.caption("选择格式并导出。路径写入下方版本记录。")
    render_export_panel(context=context, slide_snapshot=slide_snapshot)

    st.divider()
    _render_delivery_records(context.presentation.id)
    st.divider()
    render_stage_nav("deliver")
