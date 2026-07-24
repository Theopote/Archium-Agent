"""Concept exploration — IdeaSeed → directions → commit Mission."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.domain.enums import ConceptDirectionStatus, ExplorationSessionStatus
from archium.domain.exploration_session import ExplorationSession
from archium.domain.intent.idea_seed import IdeaSeed
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import render_page_header
from archium.ui.components.concept_direction_details import render_concept_direction_details
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
            render_concept_direction_details(direction)

            if direction.visual_prompt is not None and direction.visual_prompt.image_prompt.strip():
                preview_key = f"vision_preview_{direction.id}"
                if st.button(
                    "预览 Vision 编译 prompt",
                    key=f"preview_vision_{direction.id}",
                    use_container_width=True,
                ):
                    from archium.application.visual.vision.concept_direction_visual_seed import (
                        preview_compiled_prompt_for_direction,
                    )

                    st.session_state[preview_key] = preview_compiled_prompt_for_direction(
                        direction
                    )
                if st.session_state.get(preview_key):
                    st.code(st.session_state[preview_key], language="text")

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


def _render_selected_direction_vision(direction, *, settings) -> None:
    """Visual concept brief + optional image for the selected exploration direction."""
    from archium.application.design_iteration_status import (
        format_vision_user_warning,
        visual_brief_status_label,
    )
    from archium.ui.planning_service import (
        get_latest_visual_concept_brief,
        synthesize_visual_concept_brief,
    )

    st.markdown("**概念示意**")
    with get_session() as session:
        visual_brief = get_latest_visual_concept_brief(session, direction.id)
    if visual_brief is not None:
        st.caption(
            f"{visual_brief_status_label(visual_brief.status)} · {visual_brief.title}"
        )
        if visual_brief.composition_intent:
            st.markdown(f"**构图意图**：{visual_brief.composition_intent}")
        if visual_brief.atmosphere:
            st.markdown(f"**氛围**：{visual_brief.atmosphere}")
        if visual_brief.compiled_prompt:
            with st.expander("已编译 Prompt", expanded=False):
                st.code(visual_brief.compiled_prompt[:2000])
        if visual_brief.image_path:
            image_file = Path(visual_brief.image_path)
            if image_file.is_file():
                st.image(str(image_file), use_container_width=True)
            else:
                st.caption(f"示意路径：{visual_brief.image_path}")
        if visual_brief.error_message:
            st.warning(format_vision_user_warning(visual_brief.error_message))
    elif direction.visual_prompt is not None and direction.visual_prompt.image_prompt.strip():
        st.caption("方向已含 visual_prompt 种子；生成示意将优先使用该场景描述。")
    else:
        st.caption("尚未生成概念示意。可在确认 Mission 前先生成文字简报或示意出图。")

    vision_cols = st.columns(2)
    if vision_cols[0].button(
        "生成概念示意（文字）",
        key=f"explore_visual_text_{direction.id}",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        if not settings.llm_configured:
            st.error("未配置 LLM API Key。请前往设置配置。")
            return
        with st.spinner("正在合成视觉概念简报…"):
            try:
                with get_session() as session:
                    result = synthesize_visual_concept_brief(
                        session,
                        direction.id,
                        generate_image=False,
                        settings=settings,
                    )
                st.success(f"已生成视觉简报「{result.brief.title}」。")
                for warning in result.warnings:
                    st.warning(format_vision_user_warning(warning))
                st.rerun()
            except WorkflowError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))
    if vision_cols[1].button(
        "生成概念示意 + 出图",
        key=f"explore_visual_image_{direction.id}",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        if not settings.llm_configured:
            st.error("未配置 LLM API Key。请前往设置配置。")
            return
        if not settings.vision_image_generation_enabled:
            st.warning(
                "当前未开启 Vision 图像生成。将先保存文字简报；"
                "若要出图，请在设置中开启 vision_image_generation_enabled。"
            )
        with st.spinner("正在合成概念示意并尝试出图…"):
            try:
                with get_session() as session:
                    result = synthesize_visual_concept_brief(
                        session,
                        direction.id,
                        generate_image=True,
                        settings=settings,
                    )
                if result.image_succeeded:
                    st.success(f"已生成概念示意并完成出图：「{result.brief.title}」。")
                else:
                    st.success(f"已生成视觉简报「{result.brief.title}」。")
                for warning in result.warnings:
                    st.warning(format_vision_user_warning(warning))
                st.rerun()
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
    from archium.ui.intent_evolution_panel import render_project_knowledge_and_evolution

    render_project_knowledge_and_evolution(
        project_id,
        expanded=True,
        key_prefix="explore_ks_evo",
    )
