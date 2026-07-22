"""Product-flow stage: 大纲 — default summary view + advanced planner."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.pages import project_mission
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.planning_service import PlanningSnapshot, TASK_EXAMPLE_PROMPTS
from archium.ui.workspace_service import list_project_presentations


def _render_task_composer(project_id: UUID) -> None:
    st.markdown("#### 汇报任务")
    st.caption("用一两段话说明对象、目的与必须出现的内容。资料不完整也可以先生成大纲。")
    if "outline_task_draft" not in st.session_state:
        st.session_state.outline_task_draft = st.session_state.get("mission_task_draft", "")
    example = st.selectbox(
        "示例（可选）",
        options=["（不使用示例）", *TASK_EXAMPLE_PROMPTS],
        key="outline_task_example",
    )
    if example != "（不使用示例）" and not st.session_state.outline_task_draft:
        st.session_state.outline_task_draft = example
    task = st.text_area(
        "任务描述",
        height=140,
        placeholder="例如：面向院领导汇报清凉寺前期策划，约 15 页，需覆盖现状问题、概念方案与下一步决策…",
        key="outline_task_draft",
    )
    if st.button("生成大纲", type="primary", use_container_width=True, key="outline_generate"):
        st.session_state.mission_task_draft = task
        project_mission.start_outline_planning(project_id, task)


def _render_mission_summary(snapshot: PlanningSnapshot) -> None:
    mission = snapshot.mission
    if mission is None:
        return
    st.markdown("#### 汇报任务摘要")
    st.write(f"- **标题**：{mission.title}")
    st.write(f"- **任务陈述**：{mission.task_statement}")
    if mission.primary_problems:
        st.write("- **主要问题**：" + "、".join(mission.primary_problems[:5]))
    if mission.desired_changes:
        st.write("- **期望变化**：" + "、".join(mission.desired_changes[:5]))
    if mission.in_scope:
        st.write("- **范围内**：" + "、".join(mission.in_scope[:6]))
    stakeholders = [s.name for s in mission.stakeholders[:5] if s.name]
    if stakeholders:
        st.write("- **相关方**：" + "、".join(stakeholders))


def _render_presentation_request_summary(snapshot: PlanningSnapshot) -> None:
    request = snapshot.presentation_request
    if request is None:
        return
    st.markdown("#### 汇报结构")
    st.write(f"- **标题**：{request.title}")
    st.write(f"- **汇报对象**：{request.audience}")
    st.write(f"- **目的**：{request.purpose}")
    st.write(f"- **核心信息**：{request.core_message or '—'}")
    st.write(f"- **目标页数**：{request.target_slide_count}")
    if request.required_sections:
        st.write("- **必要内容**：" + "、".join(request.required_sections))
    if request.excluded_topics:
        st.write("- **排除**：" + "、".join(request.excluded_topics))
    if request.page_instructions:
        st.markdown("#### 页面意图")
        for index, intent in enumerate(request.page_instructions, start=1):
            text = intent.strip() if isinstance(intent, str) else str(intent)
            if text:
                st.write(f"{index}. {text}")


def _render_page_list(project_id: UUID) -> None:
    with get_session() as session:
        presentations = list_project_presentations(session, project_id)
    if not presentations:
        return
    latest = presentations[0]
    st.markdown("#### 已有汇报页面")
    st.caption(f"{latest.title} · 状态 {latest.status.value}")
    last_result = st.session_state.get("last_presentation_result")
    slides = getattr(last_result, "slides", None) if last_result is not None else None
    if slides:
        for index, slide in enumerate(slides, start=1):
            title = getattr(slide, "title", None) or getattr(slide, "message", None) or f"第 {index} 页"
            intent = getattr(slide, "intent", None) or getattr(slide, "core_message", None) or ""
            line = f"{index}. {title}"
            if intent:
                line = f"{line} — {intent}"
            st.write(line)
    else:
        st.info("已有汇报记录。进入「生成」可继续产出或查看页面内容。")


def _render_default_outline(project_id: UUID, snapshot: PlanningSnapshot) -> None:
    has_mission = snapshot.mission is not None
    has_request = snapshot.presentation_request is not None

    if not has_mission and not has_request:
        st.info("尚未确认大纲。先描述汇报任务，再生成结构摘要。")
        _render_task_composer(project_id)
        return

    _render_mission_summary(snapshot)
    if has_request:
        _render_presentation_request_summary(snapshot)
    else:
        st.markdown("#### 叙事结构")
        st.info(
            "任务理解已就绪，但完整汇报结构尚未确认。"
            "可打开「高级任务规划」完成关键问题、工作路径与成果选择，"
            "或重新生成大纲。"
        )
        if snapshot.deliverable_plan is not None:
            selected = [
                item.title
                for item in snapshot.deliverable_plan.deliverables
                if item.selected
            ]
            if selected:
                st.write("- **已选成果**：" + "、".join(selected))

    _render_page_list(project_id)

    st.divider()
    st.markdown("#### 下一步")
    cols = st.columns(3)
    with cols[0]:
        if st.button("重新规划", use_container_width=True, key="outline_replan"):
            project_mission.reset_planning_session()
            st.rerun()
    with cols[1]:
        ready = has_request or has_mission
        if st.button(
            "确认大纲并进入生成",
            type="primary",
            use_container_width=True,
            disabled=not ready,
            key="outline_confirm",
        ):
            st.switch_page(get_app_page("generate"))
    with cols[2]:
        from archium.ui import icons

        st.page_link(get_app_page("generate"), label="直接前往生成", icon=icons.GENERATE)

    if not has_request and has_mission:
        with st.expander("继续完善任务描述", expanded=False):
            _render_task_composer(project_id)


def render() -> None:
    render_stage_header("outline")
    st.info(
        "在本阶段确认汇报任务、对象、页数与结构。"
        "需要任务理解、关键问题或工作路径时，打开下方「高级任务规划」。"
    )

    project_id = project_mission.select_current_project()
    if project_id is None:
        render_stage_nav("outline")
        return

    snapshot = project_mission.load_planning_snapshot(project_id)
    _render_default_outline(project_id, snapshot)

    st.divider()
    show_advanced = st.toggle(
        "高级任务规划",
        value=False,
        key="outline_advanced_planning",
        help="打开后显示完整六步规划器：任务理解、关键问题、工作路径与成果选择。",
    )
    if show_advanced:
        st.caption("完整六步规划器：描述任务 → 任务理解 → 关键问题 → 工作路径 → 选择成果 → 开始执行。")
        project_mission.render(embedded=True)

    st.divider()
    render_stage_nav("outline")
