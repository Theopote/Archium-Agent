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
from archium.ui.components.concept_direction_compare import render_concept_direction_compare
from archium.ui.error_handlers import report_user_error
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
        "左侧思考与建议，右侧可比较的概念成果；选定后再生成设计使命与项目任务。",
    )
    critique_warnings = st.session_state.pop("design_critique_warnings", None)
    if critique_warnings:
        st.warning("设计批判（选定前独立质疑）\n\n" + "\n\n".join(critique_warnings))

    from archium.ui.components.design_revise_ask_panel import (
        clear_pending_revise_state,
        render_pending_revise_ask,
        store_pending_revise_from_selection,
    )

    def _apply_revise(direction_id: UUID) -> None:
        try:
            with get_session() as session:
                selection = select_exploration_direction(
                    session, direction_id, revise_action="apply"
                )
            clear_pending_revise_state()
            if store_pending_revise_from_selection(selection):
                st.rerun()
                return
            st.session_state["design_critique_warnings"] = list(
                getattr(selection, "critique_warnings", None) or []
            )
            report = getattr(selection, "critique_report", None)
            if report is not None and hasattr(report, "as_dict"):
                st.session_state["last_design_critique_report"] = report.as_dict()
            st.success("已应用修订并选中方向。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(report_user_error(exc))

    def _reject_revise(direction_id: UUID) -> None:
        try:
            with get_session() as session:
                selection = select_exploration_direction(
                    session, direction_id, revise_action="reject"
                )
            clear_pending_revise_state()
            st.session_state["design_critique_warnings"] = list(
                getattr(selection, "critique_warnings", None) or []
            )
            report = getattr(selection, "critique_report", None)
            if report is not None and hasattr(report, "as_dict"):
                st.session_state["last_design_critique_report"] = report.as_dict()
            st.success("已拒绝修订，按原方向选中。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(report_user_error(exc))

    with get_session() as session:
        projects = list_projects(session)
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

    render_pending_revise_ask(
        key_prefix="explore",
        on_apply=_apply_revise,
        on_reject=_reject_revise,
        project_id=project_id,
    )

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

    # Studio dual-rail: Thinking (left) + Artifacts (right)
    think_col, artifact_col = st.columns([1.05, 1.35], gap="large")
    with think_col:
        _render_thinking_rail(exploration, project_id, settings=settings)
    with artifact_col:
        directions = _render_artifact_rail(exploration, settings=settings)

    if not directions:
        return

    selected = next(
        (item for item in directions if item.status == ConceptDirectionStatus.SELECTED),
        None,
    )
    if selected is None:
        st.info("请在右侧比较并选择一个方向，再生成项目任务（DesignIntent + Mission）。")
        return

    st.markdown("---")
    st.markdown(f"**当前方向**：{selected.title}")
    _render_selected_direction_vision(selected, settings=settings)
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


def _render_thinking_rail(exploration: ExplorationSession, project_id: UUID, *, settings) -> None:
    """Chat / thinking side — understanding, seed, suggestions (not a wall of prose)."""
    st.markdown("### 思考与建议")
    from archium.ui.project_knowledge_profile import render_ai_understanding_panel

    render_ai_understanding_panel(
        project_id,
        compact=True,
        show_actions=True,
        key_prefix="explore_think",
        title="AI 当前理解",
    )

    with st.expander("想法种子", expanded=True):
        _render_idea_seed(exploration)

    seed = exploration.idea_seed or IdeaSeed.from_raw(exploration.idea_text)
    action_cols = st.columns(1)
    with action_cols[0]:
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

        if not seed.is_enriched:
            st.info("想法尚未结构化解读。配置 LLM 后可重新解读。")
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
            key="explore_gen_directions",
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

    with st.expander("设计演进", expanded=False):
        from archium.ui.intent_evolution_panel import render_project_knowledge_and_evolution

        render_project_knowledge_and_evolution(
            project_id,
            expanded=True,
            key_prefix="explore_ks_evo",
            show_knowledge=False,
            title="意图演进时间线",
        )


def _render_artifact_rail(exploration: ExplorationSession, *, settings) -> list:
    """Artifact side — comparable concept direction cards."""
    st.markdown("### 设计成果")
    with get_session() as session:
        directions = list_exploration_directions(session, exploration.id)

    if not directions:
        st.caption("尚未生成概念方向。在左侧推演后，这里会出现可比较的方案卡片。")
        return []

    clicked = render_concept_direction_compare(
        directions,
        key_prefix="explore_cmp",
        allow_select=True,
        allow_archive=False,
        show_details_expander=True,
    )
    if clicked and clicked[0] == "select":
        try:
            with get_session() as session:
                selection = select_exploration_direction(session, clicked[1])
            from archium.ui.components.design_revise_ask_panel import (
                store_pending_revise_from_selection,
            )

            if store_pending_revise_from_selection(selection):
                st.info("批判建议修订 — 请在上方确认应用或拒绝。")
                st.rerun()
                return list(directions)
            st.session_state["design_critique_warnings"] = list(
                getattr(selection, "critique_warnings", None) or []
            )
            report = getattr(selection, "critique_report", None)
            if report is not None and hasattr(report, "as_dict"):
                st.session_state["last_design_critique_report"] = report.as_dict()
            st.success("已选中方向。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(report_user_error(exc))
    return list(directions)


def _render_selected_direction_vision(direction, *, settings) -> None:
    """Visual Thinking slots bound to the selected ConceptDirection."""
    from archium.ui.components.visual_thinking_panel import render_visual_thinking_panel

    render_visual_thinking_panel(
        direction,
        key_prefix="explore",
        settings=settings,
    )


def _render_idea_seed(exploration: ExplorationSession) -> None:
    seed = exploration.idea_seed or IdeaSeed.from_raw(exploration.idea_text)
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
