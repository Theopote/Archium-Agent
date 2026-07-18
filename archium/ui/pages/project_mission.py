"""Project mission planning page — free task description to execution."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.enums import DeliverableType
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.clarification_panel import render_clarification_panel, render_known_unknown_panel
from archium.ui.deliverable_panel import render_deliverable_panel
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.mission_panel import render_mission_panel
from archium.ui.planning_service import (
    TASK_EXAMPLE_PROMPTS,
    PlanningSnapshot,
    continue_after_clarification,
    get_planning_snapshot,
    get_presentation_bridge,
    start_planning,
    start_presentation_from_planning,
)
from archium.ui.workspace_service import list_projects
from archium.ui.workstream_panel import render_workstream_panel

STEP_LABELS = [
    "1. 描述任务",
    "2. 任务理解",
    "3. 关键问题",
    "4. 工作路径",
    "5. 选择成果",
    "6. 开始执行",
]


def _init_state() -> None:
    defaults = {
        "selected_project_id": None,
        "mission_step": 1,
        "planning_session_id": None,
        "planning_workflow_run_id": None,
        "planning_mission_id": None,
        "last_presentation_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _project_selector() -> UUID | None:
    with get_session() as session:
        projects = list_projects(session)
    if not projects:
        st.info("还没有项目。请先到「项目工作台」创建项目并导入资料。")
        return None

    labels = {str(p.id): p.name for p in projects}
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


def _load_snapshot(project_id: UUID) -> PlanningSnapshot:
    session_id = (
        UUID(st.session_state.planning_session_id)
        if st.session_state.planning_session_id
        else None
    )
    run_id = (
        UUID(st.session_state.planning_workflow_run_id)
        if st.session_state.planning_workflow_run_id
        else None
    )
    mission_id = (
        UUID(st.session_state.planning_mission_id)
        if st.session_state.planning_mission_id
        else None
    )
    with get_session() as session:
        snapshot = get_planning_snapshot(
            session,
            planning_session_id=session_id,
            workflow_run_id=run_id,
            mission_id=mission_id,
            project_id=project_id,
        )
    if snapshot.planning_session is not None:
        st.session_state.planning_session_id = str(snapshot.planning_session.id)
    if snapshot.workflow_run is not None:
        st.session_state.planning_workflow_run_id = str(snapshot.workflow_run.id)
    if snapshot.mission is not None:
        st.session_state.planning_mission_id = str(snapshot.mission.id)
    return snapshot


def _sync_step_from_snapshot(snapshot: PlanningSnapshot) -> None:
    """Advance default step based on workflow gate when user has not chosen one."""
    if st.session_state.mission_step > 1:
        return
    if snapshot.mission is None:
        st.session_state.mission_step = 1
        return
    gate = snapshot.review_gate
    if gate == "clarification":
        st.session_state.mission_step = 2
    elif gate == "plan_approval":
        st.session_state.mission_step = 4
    elif snapshot.presentation_request is not None:
        st.session_state.mission_step = 6
    else:
        st.session_state.mission_step = 2


def _render_step_nav() -> int:
    step = st.radio(
        "规划步骤",
        options=list(range(1, 7)),
        format_func=lambda i: STEP_LABELS[i - 1],
        horizontal=True,
        index=max(0, min(5, st.session_state.mission_step - 1)),
        label_visibility="collapsed",
    )
    st.session_state.mission_step = step
    return step


def _render_describe(project_id: UUID) -> None:
    st.markdown("### 告诉 Archium 你接到了什么任务")
    st.caption("资料不完整也没关系。可以描述项目背景、甲方要求、现状问题，以及你希望最终完成什么。")

    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往 **设置 → AI 服务** 配置。")
        return

    if "mission_task_draft" not in st.session_state:
        st.session_state.mission_task_draft = ""
    example = st.selectbox(
        "示例（可选，不会限制你的描述）",
        options=["（不使用示例）", *TASK_EXAMPLE_PROMPTS],
    )
    if example != "（不使用示例）" and not st.session_state.mission_task_draft:
        st.session_state.mission_task_draft = example
    task = st.text_area(
        "任务描述",
        height=160,
        placeholder="例如：清凉寺希望重建，面积未知，先做前期策划和概念汇报…",
        key="mission_task_draft",
    )

    if st.button("分析任务", type="primary", use_container_width=True):
        if not task.strip():
            st.error("请先描述任务。")
            return
        with st.spinner("正在理解任务并识别知识缺口…"):
            try:
                with get_session() as session:
                    result = start_planning(session, project_id, task)
                st.session_state.planning_session_id = str(result.planning_session.id)
                st.session_state.planning_workflow_run_id = str(result.workflow_run.id)
                if result.mission is not None:
                    st.session_state.planning_mission_id = str(result.mission.id)
                st.session_state.mission_step = 2
                st.success("已生成任务理解。请核对并回答关键问题。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))


def _render_mission(snapshot: PlanningSnapshot) -> None:
    if snapshot.mission is None:
        st.info("请先在第 1 步描述并分析任务。")
        return
    render_mission_panel(snapshot.mission)
    if st.button("下一步：回答关键问题", use_container_width=True):
        st.session_state.mission_step = 3
        st.rerun()


def _render_questions(snapshot: PlanningSnapshot, project_id: UUID) -> None:
    if snapshot.mission is None:
        st.info("请先完成任务理解。")
        return
    render_known_unknown_panel(
        gaps=snapshot.knowledge_gaps,
        assumptions=snapshot.assumptions,
        facts=snapshot.project_facts,
        constraints=snapshot.mission.known_constraints if snapshot.mission else [],
    )
    st.divider()
    render_clarification_panel(
        snapshot.clarifying_questions,
        readiness=snapshot.readiness,
    )

    can_continue = snapshot.readiness is None or snapshot.readiness.can_continue
    if st.button(
        "继续规划工作路径与成果",
        type="primary",
        use_container_width=True,
        disabled=not can_continue or not st.session_state.planning_workflow_run_id,
    ):
        with st.spinner("正在修订任务理解并生成工作路径与成果计划…"):
            try:
                with get_session() as session:
                    result = continue_after_clarification(
                        session,
                        UUID(st.session_state.planning_workflow_run_id),
                    )
                if result.mission is not None:
                    st.session_state.planning_mission_id = str(result.mission.id)
                st.session_state.mission_step = 4
                st.success("已生成工作路径与成果计划。")
                st.rerun()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))


def _render_workstreams(snapshot: PlanningSnapshot) -> None:
    render_workstream_panel(snapshot.workstreams)
    if snapshot.workstreams and st.button("下一步：选择成果", use_container_width=True):
        st.session_state.mission_step = 5
        st.rerun()


def _render_deliverables(snapshot: PlanningSnapshot) -> None:
    render_deliverable_panel(
        snapshot.deliverable_plan,
        workstreams=snapshot.workstreams,
    )
    if snapshot.deliverable_plan and st.button(
        "下一步：确认并开始执行",
        use_container_width=True,
    ):
        st.session_state.mission_step = 6
        st.rerun()


def _render_execute(snapshot: PlanningSnapshot, project_id: UUID) -> None:
    st.markdown("#### 开始执行")
    if not st.session_state.planning_workflow_run_id:
        st.info("缺少规划工作流，请从第 1 步重新开始。")
        return

    execution_plans = snapshot.artifact_execution_plans
    if execution_plans:
        st.markdown("**成果执行路由**")
        for item in execution_plans:
            title = item.get("deliverable_title") or item.get("deliverable_id")
            dtype = item.get("deliverable_type", "other")
            if item.get("supported"):
                st.success(f"「{title}」（{dtype}）→ 可启动自动生成")
            else:
                message = item.get("message") or "该成果已完成规划，但当前版本尚未支持自动生成。"
                st.warning(f"「{title}」（{dtype}）：{message}")

    selected_presentations = [
        item
        for item in execution_plans
        if item.get("supported") and item.get("deliverable_type") == DeliverableType.PRESENTATION.value
    ]
    if not selected_presentations and snapshot.deliverable_plan is not None:
        selected_presentations = [
            item
            for item in snapshot.deliverable_plan.deliverables
            if item.selected and item.deliverable_type == DeliverableType.PRESENTATION
        ]

    if not selected_presentations:
        st.info(
            "当前没有可自动生成的「汇报 / Presentation」成果。"
            "非汇报成果不会静默转换成 PPT；请回到第 5 步勾选汇报类成果，或等待后续版本支持对应生成器。"
        )
        return

    try:
        with get_session() as session:
            bridge = get_presentation_bridge(
                session,
                UUID(st.session_state.planning_workflow_run_id),
            )
        request = bridge.request
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return
    except Exception as exc:
        st.error(format_user_error(exc))
        return

    st.markdown("**将进入现有汇报主链的 PresentationRequest 预览**")
    st.write(f"- 标题：{request.title}")
    st.write(f"- 对象：{request.audience}")
    st.write(f"- 目的：{request.purpose}")
    st.write(f"- 核心信息：{request.core_message}")
    st.write(f"- 类型：{request.presentation_type.value}")
    st.write(f"- 目标页数：{request.target_slide_count}")
    if request.required_sections:
        st.write("- 必要内容范围：" + "、".join(request.required_sections))
    if request.excluded_topics:
        st.write("- 排除：" + "、".join(request.excluded_topics))
    if request.user_notes:
        with st.expander("生成上下文（含设计命题与工作路径）", expanded=False):
            st.text(request.user_notes)

    export_json = st.checkbox("导出 JSON", value=True)
    export_marp = st.checkbox("导出 Marp Markdown", value=True)
    require_brief = st.checkbox("Brief 生成后暂停审核", value=True)
    require_storyline = st.checkbox("Storyline 生成后暂停审核", value=True)

    if st.button("批准成果计划并生成汇报", type="primary", use_container_width=True):
        with st.spinner("正在批准规划并启动 Brief → Storyline → SlideSpec…"):
            try:
                with get_session() as session:
                    result = start_presentation_from_planning(
                        session,
                        project_id,
                        UUID(st.session_state.planning_workflow_run_id),
                        export_json=export_json,
                        export_marp=export_marp,
                        require_brief_review=require_brief,
                        require_storyline_review=require_storyline,
                    )
                st.session_state.last_presentation_result = result
                st.session_state.last_workflow_result = result
                if result.awaiting_review:
                    st.warning("汇报工作流已暂停审核。请到「项目工作台」继续审核 Brief / Storyline。")
                elif result.succeeded:
                    st.success(f"汇报已生成，共 {len(result.slides)} 页。")
                else:
                    st.error("汇报工作流完成但存在错误。")
            except WorkflowError as exc:
                st.error(format_user_error(exc))
            except Exception as exc:
                st.error(format_user_error(exc))

    result = st.session_state.get("last_presentation_result")
    if result is not None and result.brief is not None:
        st.caption(
            f"最近结果：{result.brief.title} · 状态 {result.workflow_run.status.value}"
        )


def render() -> None:
    _init_state()
    st.markdown("### 项目任务")
    st.caption("先理解任务，再规划工作路径与成果，最后进入现有汇报主链。")

    project_id = _project_selector()
    if project_id is None:
        return

    snapshot = _load_snapshot(project_id)
    _sync_step_from_snapshot(snapshot)

    if snapshot.workflow_run is not None:
        gate = snapshot.review_gate or "—"
        st.caption(
            f"规划工作流：{snapshot.workflow_run.status.value} · 闸门：{gate}"
        )
        if st.button("重新开始新的任务分析", key="mission_restart"):
            st.session_state.planning_workflow_run_id = None
            st.session_state.planning_mission_id = None
            st.session_state.mission_step = 1
            st.session_state.mission_task_draft = ""
            st.rerun()

    st.divider()
    step = _render_step_nav()
    st.divider()

    if step == 1:
        _render_describe(project_id)
    elif step == 2:
        # Reload after edits / navigation
        snapshot = _load_snapshot(project_id)
        _render_mission(snapshot)
    elif step == 3:
        snapshot = _load_snapshot(project_id)
        _render_questions(snapshot, project_id)
    elif step == 4:
        snapshot = _load_snapshot(project_id)
        _render_workstreams(snapshot)
    elif step == 5:
        snapshot = _load_snapshot(project_id)
        _render_deliverables(snapshot)
    else:
        snapshot = _load_snapshot(project_id)
        _render_execute(snapshot, project_id)
