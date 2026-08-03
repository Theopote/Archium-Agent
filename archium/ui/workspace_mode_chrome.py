"""Architectural Workspace mode chrome — knowledge-first; modes are internal routing only."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import streamlit as st

from archium.application.context.workflow_navigation import workflow_entry_for_project
from archium.application.workspace_mode_service import (
    WorkspaceModeService,
    profile_for,
    session_mode_override_key,
)
from archium.domain.enums import ArchitecturalWorkspaceMode
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.error_handlers import report_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.project_knowledge_profile import (
    load_project_knowledge_display,
    render_project_knowledge_strip,
)

if TYPE_CHECKING:
    from archium.ui.project_progress_card import ProjectProgressSnapshot

_MODE_LABELS = {
    ArchitecturalWorkspaceMode.EXISTING_PROJECT: "资料整理优先",
    ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION: "方向推演优先",
    ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING: "策划决策优先",
    ArchitecturalWorkspaceMode.DESIGN_ITERATION: "方案比较优先",
}


def resolve_ui_workspace_mode(project_id: UUID) -> ArchitecturalWorkspaceMode:
    key = session_mode_override_key(project_id)
    raw = st.session_state.get(key)
    override = None
    if raw:
        try:
            override = ArchitecturalWorkspaceMode(str(raw))
        except ValueError:
            override = None
    with get_session() as session:
        return WorkspaceModeService(session).resolve_mode(project_id, override=override)


def render_workspace_mode_chrome(project_id: UUID, *, key_prefix: str = "ws_mode") -> None:
    """Show knowledge profile first; hide discrete mode names from primary chrome."""
    key = session_mode_override_key(project_id)
    raw = st.session_state.get(key)
    override = None
    if raw:
        try:
            override = ArchitecturalWorkspaceMode(str(raw))
        except ValueError:
            override = None

    display = render_project_knowledge_strip(project_id, compact=False)
    if display is not None:
        from archium.ui.project_knowledge_profile import render_project_knowledge_action_buttons

        render_project_knowledge_action_buttons(
            project_id,
            key_prefix=key_prefix,
            settings=get_ui_effective_settings(),
        )
    else:
        st.caption("尚未评估知识状态。请从「开始项目」描述项目情况。")

    try:
        with get_session() as session:
            service = WorkspaceModeService(session)
            profile = service.resolve_profile(project_id, override=override)
            available = service.available_modes(project_id)
            entry = workflow_entry_for_project(session, project_id)
    except WorkflowError as exc:
        st.caption(str(exc))
        return
    except Exception as exc:
        st.caption(report_user_error(exc))
        return

    go_label = entry.label if entry is not None else _primary_label(profile.primary_page_key)
    if st.button(
        f"前往：{go_label}",
        key=f"{key_prefix}_go_{project_id}",
        use_container_width=True,
    ):
        if entry is not None:
            from archium.application.context.workflow_navigation import as_session_state
            from archium.ui.context_navigation import navigate_workflow_entry

            navigate_workflow_entry(as_session_state(st.session_state), entry)
        else:
            st.switch_page(get_app_page(profile.primary_page_key))

    if len(available) > 1:
        with st.expander("工作路径偏好（高级）", expanded=False):
            st.caption(
                "多数项目处于「部分资料」连续态，系统已根据知识完整度建议下一步。"
                "仅在需要时调整内部工作路径偏好。"
            )
            options = list(available)
            current_index = options.index(profile.mode) if profile.mode in options else 0
            selected = st.selectbox(
                "偏好",
                options=options,
                index=current_index,
                format_func=lambda item: _MODE_LABELS.get(item, item.value),
                key=f"{key_prefix}_select_{project_id}",
            )
            if selected != profile.mode:
                st.session_state[key] = selected.value
                st.rerun()


def render_flow_knowledge_context(project_id: UUID, *, key_prefix: str = "flow_ks") -> None:
    """Compact knowledge strip for product-flow stage pages."""
    display = render_project_knowledge_strip(
        project_id,
        compact=True,
        show_known_unknown=False,
    )
    if display is not None:
        from archium.ui.project_knowledge_profile import render_project_knowledge_action_buttons

        render_project_knowledge_action_buttons(project_id, key_prefix=f"{key_prefix}_ks")


def stage_caption_for_mode(
    stage_id: str,
    mode: ArchitecturalWorkspaceMode | None,
    *,
    default: str,
) -> str:
    if mode is None:
        return default
    return profile_for(mode).stage_captions.get(stage_id, default)


def _is_genesis_shortcut(snapshot: ProjectProgressSnapshot) -> bool:
    return (
        snapshot.slide_count > 0
        and not snapshot.outline_approved
        and snapshot.has_outline
    )


def flow_stage_caption(
    stage_id: str,
    project_id: UUID,
    *,
    default: str,
    snapshot: ProjectProgressSnapshot | None = None,
) -> str:
    """Stage subtitle aligned with delivery readiness — not static partial-context text."""
    if snapshot is not None:
        has_docs = snapshot.document_count > 0
        genesis_shortcut = _is_genesis_shortcut(snapshot)

        if stage_id == "deliver":
            if snapshot.formal_delivery_ready:
                return "检查通过，可正式导出 PPTX / PDF。"
            if has_docs and snapshot.draft_export_ready:
                if snapshot.export_blocker_count > 0:
                    return "资料已整理；清除阻塞项后可正式导出。"
                return "资料已整理；完成检查后可正式导出。"
            if has_docs:
                return "资料已整理；完成版式与检查后导出。"
            if snapshot.draft_export_ready:
                return "可导出工作稿；正式交付需绑定项目资料。"
            return "完成版式与检查后导出。"

        if stage_id == "materials":
            if has_docs:
                return "整理项目资料与事实；可并行推进大纲与生成。"
            return "资料可选：无资料也可先定大纲与草稿预览。"

        if stage_id == "outline":
            if snapshot.outline_approved:
                return default
            if genesis_shortcut:
                return "Genesis 已生成草稿大纲；请确认结构与各页设计摘要。"
            if snapshot.has_outline:
                return "确认汇报结构与各页设计摘要后再进入生成。"
            return "描述汇报任务并生成大纲结构。"

        if stage_id == "generate":
            if genesis_shortcut:
                return "当前为草稿捷径预览；确认大纲后可运行正式生成管线。"
            if snapshot.slide_count <= 0:
                return "运行内容生成管线，生成页面文字与结构。"
            if snapshot.pending_count > 0:
                return "部分页面版式待完成；可在工作室补做版式。"

        if stage_id == "edit":
            if genesis_shortcut:
                return "预览 Genesis 线框草稿；确认大纲后可迭代正式版式。"
            if snapshot.slide_count <= 0:
                return "尚无页面；请先在生成页运行内容生成管线。"

    display = load_project_knowledge_display(project_id)
    if display is None:
        mode = resolve_ui_workspace_mode(project_id)
        return stage_caption_for_mode(stage_id, mode, default=default)
    if display.situation.value == "partial_context":
        partial_captions = {
            "materials": "补充或整理已有片段资料；可并行澄清与推演。",
            "outline": "在部分资料下确认沟通结构。",
            "generate": "生成草稿预览；确认大纲后效果更佳。",
            "edit": "迭代叙事与版式。",
            "deliver": "可导出工作稿；正式交付需绑定项目资料。",
        }
        return partial_captions.get(stage_id, default)
    return stage_caption_for_mode(stage_id, resolve_ui_workspace_mode(project_id), default=default)


def _primary_label(page_key: str) -> str:
    labels = {
        "materials": "资料",
        "concept-exploration": "概念探索",
        "project-mission": "项目任务",
        "outline": "大纲",
    }
    return labels.get(page_key, page_key)
