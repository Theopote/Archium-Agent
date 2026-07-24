"""Concept exploration — IdeaSeed → directions → commit Mission."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.enums import ConceptDirectionStatus, ExplorationSessionStatus
from archium.domain.exploration_session import ExplorationSession
from archium.domain.intent.idea_seed import IdeaSeed
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import render_page_header
from archium.ui.error_handlers import format_user_error, report_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.planning_service import (
    commit_exploration_to_mission,
    enrich_exploration_idea_seed,
    generate_exploration_directions,
    get_latest_exploration_for_project,
    list_exploration_directions,
    select_exploration_direction,
)
from archium.ui.workspace_service import list_projects


def render() -> None:
    """Push concept directions before ProjectMission exists."""
    render_page_header(
        "概念探索",
        "从一句话想法解读 IdeaSeed、推演可比较方向，选定后再生成设计使命与项目任务。",
    )

    projects = list_projects()
    if not projects:
        st.info("请先在「开始项目」创建概念探索项目。")
        st.page_link(get_app_page("project-genesis"), label="去开始项目", icon=":material/add:")
        return

    selected_raw = st.session_state.get("selected_project_id")
    options = {str(p.id): p.name for p in projects}
    default_index = 0
    if selected_raw and str(selected_raw) in options:
        default_index = list(options.keys()).index(str(selected_raw))
    project_id_str = st.selectbox(
        "项目",
        options=list(options.keys()),
        format_func=lambda key: options[key],
        index=default_index,
    )
    st.session_state.selected_project_id = project_id_str
    project_id = UUID(project_id_str)

    with get_session() as session:
        exploration = get_latest_exploration_for_project(session, project_id)

    if exploration is None:
        st.warning("当前项目尚无探索会话。请从「开始项目」重新描述想法进入。")
        st.page_link(get_app_page("project-genesis"), label="返回开始项目", icon=":material/arrow_back:")
        return

    pending_warnings = st.session_state.pop("exploration_seed_warnings", None)
    if pending_warnings:
        for warning in pending_warnings:
            st.warning(warning)

    _render_idea_seed(exploration)
    _render_knowledge_and_evolution(project_id)

    status_label = {
        ExplorationSessionStatus.EXPLORING: "探索中",
        ExplorationSessionStatus.DIRECTION_SELECTED: "已选定方向",
        ExplorationSessionStatus.COMMITTED: "已生成 Mission",
    }.get(exploration.status, exploration.status.value)
    st.caption(f"探索状态：{status_label}")

    if exploration.status == ExplorationSessionStatus.COMMITTED:
        st.success("已提交为项目任务。可继续完善 Mission、研究与成果。")
        if st.button("进入项目任务", type="primary", use_container_width=True):
            st.session_state.mission_step = 1
            if exploration.mission_id is not None:
                st.session_state.planning_mission_id = str(exploration.mission_id)
            st.switch_page(get_app_page("project-mission"))
        return

    settings = get_ui_effective_settings()
    if st.button("刷新知识状态", key="explore_reassess", use_container_width=True):
        from archium.ui.planning_service import reassess_project_context

        with st.spinner("正在重新评估知识状态…"):
            try:
                with get_session() as session:
                    result = reassess_project_context(
                        session,
                        project_id,
                        user_text=exploration.idea_text,
                        settings=settings,
                    )
                for warning in result.warnings:
                    st.warning(warning)
                st.success(result.knowledge_state.summary_line())
                st.rerun()
            except WorkflowError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))

    seed = exploration.idea_seed or IdeaSeed.from_raw(exploration.idea_text)
    if not seed.is_enriched:
        st.info("想法尚未结构化解读。配置 LLM 后可点击下方按钮重新解读。")
    if st.button(
        "重新解读想法",
        key="enrich_idea_seed",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        if not settings.llm_configured:
            st.error("未配置 LLM API Key。请前往设置配置。")
            return
        with st.spinner("正在解读想法…"):
            try:
                with get_session() as session:
                    result = enrich_exploration_idea_seed(
                        session, exploration.id, settings=settings
                    )
                for warning in result.warnings:
                    st.warning(warning)
                st.success("已更新 IdeaSeed。")
                st.rerun()
            except WorkflowError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))

    if st.button(
        "推演概念方向（2–3 个）",
        type="primary",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        if not settings.llm_configured:
            st.error("未配置 LLM API Key。请前往设置配置。")
            return
        with st.spinner("正在推演概念方向…"):
            try:
                with get_session() as session:
                    result = generate_exploration_directions(
                        session,
                        exploration.id,
                        count=3,
                        settings=settings,
                    )
                st.success(f"已生成 {len(result.directions)} 个概念方向。")
                for warning in result.warnings:
                    st.warning(warning)
                st.rerun()
            except WorkflowError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))

    with get_session() as session:
        directions = list_exploration_directions(session, exploration.id)

    if not directions:
        st.caption("尚未生成概念方向。点击上方按钮开始推演。")
        return

    for direction in directions:
        badge = {
            ConceptDirectionStatus.SELECTED: "已选中",
            ConceptDirectionStatus.DRAFT: "草稿",
            ConceptDirectionStatus.ARCHIVED: "已归档",
        }.get(direction.status, direction.status.value)
        with st.expander(
            f"{direction.title} · {badge}",
            expanded=direction.status == ConceptDirectionStatus.SELECTED,
        ):
            if direction.theme:
                st.markdown(f"**主题**：{direction.theme}")
            if direction.summary:
                st.markdown(direction.summary)
            if direction.spatial_idea:
                st.markdown(f"**空间想法**：{direction.spatial_idea}")
            if direction.experience_focus:
                st.markdown(f"**体验焦点**：{direction.experience_focus}")
            if direction.differentiator:
                st.markdown(f"**差异点**：{direction.differentiator}")
            if direction.open_questions:
                st.markdown("**开放问题**")
                for item in direction.open_questions:
                    st.markdown(f"- {item}")
            if direction.risks:
                st.markdown("**风险**")
                for item in direction.risks:
                    st.markdown(f"- {item}")

            if direction.status != ConceptDirectionStatus.SELECTED and st.button(
                "选为当前方向",
                key=f"explore_select_{direction.id}",
                use_container_width=True,
            ):
                try:
                    with get_session() as session:
                        select_exploration_direction(session, direction.id)
                    st.success(f"已选中「{direction.title}」。")
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(format_user_error(exc))

    selected = next(
        (item for item in directions if item.status == ConceptDirectionStatus.SELECTED),
        None,
    )
    if selected is None:
        st.info("请选择一个方向，再生成项目任务（DesignIntent + Mission）。")
        return

    st.markdown("---")
    st.markdown(f"**当前方向**：{selected.title}")
    if st.button(
        "确认方向并生成项目任务",
        type="primary",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        if not settings.llm_configured:
            st.error("未配置 LLM API Key。请前往设置配置。")
            return
        with st.spinner("正在合成设计使命并生成 Mission…"):
            try:
                with get_session() as session:
                    result = commit_exploration_to_mission(
                        session,
                        exploration.id,
                        settings=settings,
                    )
                st.session_state.planning_mission_id = str(result.mission.id)
                st.session_state.mission_step = 1
                st.success(f"已生成 Mission：「{result.mission.title}」")
                st.switch_page(get_app_page("project-mission"))
            except WorkflowError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))


def _render_idea_seed(exploration: ExplorationSession) -> None:
    seed = exploration.idea_seed or IdeaSeed.from_raw(exploration.idea_text)
    st.markdown("**想法种子（IdeaSeed）**")
    st.write(seed.raw_input)
    cols = st.columns(2)
    with cols[0]:
        if seed.theme:
            st.markdown(f"**主题线索**：{seed.theme}")
        if seed.inspiration:
            st.markdown(f"**灵感**：{seed.inspiration}")
    with cols[1]:
        if seed.keywords:
            st.markdown("**关键词**：" + "、".join(seed.keywords))
        st.caption(f"想象尺度：{seed.imagination_level}")


def _render_knowledge_and_evolution(project_id: UUID) -> None:
    from archium.infrastructure.database.repositories import ProjectRepository

    with get_session() as session:
        project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return
    if project.knowledge_state is not None:
        st.caption(project.knowledge_state.summary_line())
    latest = (
        project.intent_evolution.latest_summary() if project.intent_evolution else None
    )
    if latest:
        st.caption(f"意图演进：{latest}")
