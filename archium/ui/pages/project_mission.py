"""Project mission planning page — free task description to execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import streamlit as st

from archium.config.settings import Settings
from archium.domain.enums import DeliverableType, ProjectOriginMode
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.background_workflow_runner import (
    PlanningJobAction,
    background_workflows_enabled,
    submit_planning_job,
    warn_background_workflows_required,
)
from archium.ui.clarification_panel import render_clarification_panel, render_known_unknown_panel
from archium.ui.deliverable_panel import render_deliverable_panel
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import (
    brief_storyline_pair,
    content_pipeline_chain,
    entity_label,
)
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.mission_panel import render_mission_panel
from archium.ui.planning_service import (
    PROGRAMMING_TASK_EXAMPLE_PROMPTS,
    TASK_EXAMPLE_PROMPTS,
    PlanningSnapshot,
    generate_case_study_artifact,
    generate_checklist_artifact,
    generate_memo_artifact,
    generate_question_list_artifact,
    generate_report_artifact,
    generate_work_plan_artifact,
    get_planning_snapshot,
    get_presentation_bridge,
    list_artifact_jobs,
)
from archium.ui.workflow_progress_panel import (
    render_workflow_progress_panel,
    set_active_job_id,
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


def _render_post_presentation_links() -> None:
    st.markdown("**下一步**")
    link_cols = st.columns(2)
    with link_cols[0]:
        st.page_link(
            get_app_page("generate"),
            label="到「生成」产出页面内容",
            icon=":material/bolt:",
        )
    with link_cols[1]:
        st.page_link(
            get_app_page("edit"),
            label="到「工作室」调整版式",
            icon=":material/slideshow:",
        )


def _apply_planning_result(result: object) -> None:
    from archium.application.planning_workflow_service import PlanningWorkflowResult

    if not isinstance(result, PlanningWorkflowResult):
        return
    st.session_state.planning_session_id = str(result.planning_session.id)
    st.session_state.planning_workflow_run_id = str(result.workflow_run.id)
    if result.mission is not None:
        st.session_state.planning_mission_id = str(result.mission.id)


def _apply_presentation_bridge_result(result: object) -> None:
    from archium.application.workflow_models import WorkflowRunResult

    if isinstance(result, WorkflowRunResult):
        st.session_state.last_presentation_result = result
        st.session_state.last_workflow_result = result


def _launch_planning_job(
    project_id: UUID,
    action: PlanningJobAction,
    *,
    settings: Settings,
    task_description: str | None = None,
    workflow_run_id: UUID | None = None,
    on_complete: Callable[[object], None],
    success_message: str | None = None,
    awaiting_review_message: str | None = None,
    export_kwargs: dict[str, Any] | None = None,
) -> bool:
    """Start a background planning job. Returns True if background mode was used."""
    if not background_workflows_enabled(settings):
        warn_background_workflows_required()
        return False
    job = submit_planning_job(
        project_id,
        action,
        settings=settings,
        task_description=task_description,
        workflow_run_id=workflow_run_id,
        **(export_kwargs or {}),
    )
    set_active_job_id(project_id, job.job_id, scope="planning")
    st.info("已在后台运行规划工作流，下方将实时显示进度。")
    render_workflow_progress_panel(
        project_id,
        scope="planning",
        job_id=job.job_id,
        result_session_key=None,
        on_complete=on_complete,
        success_message=success_message,
        awaiting_review_message=awaiting_review_message,
    )
    return True


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


def _project_selector(*, key: str = "mission_project_selector") -> UUID | None:
    with get_session() as session:
        projects = list_projects(session)
    if not projects:
        st.info("还没有项目。")
        if st.button("从想法或资料开始", type="primary"):
            st.switch_page(get_app_page("project-genesis"))
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
        key=key,
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
    if gate in {"mission_correction", "clarification", "mission_approval"}:
        st.session_state.mission_step = 2
    elif gate == "plan_approval":
        st.session_state.mission_step = 4
    elif snapshot.presentation_request is not None:
        st.session_state.mission_step = 6
    else:
        st.session_state.mission_step = 2


def _render_step_nav(*, key: str = "mission_step_nav") -> int:
    step = st.radio(
        "规划步骤",
        options=list(range(1, 7)),
        format_func=lambda i: STEP_LABELS[i - 1],
        horizontal=True,
        index=max(0, min(5, st.session_state.mission_step - 1)),
        label_visibility="collapsed",
        key=key,
    )
    st.session_state.mission_step = int(step)
    return int(step)


def _render_describe(project_id: UUID) -> None:
    st.markdown("### 告诉 Archium 你接到了什么任务")
    with get_session() as session:
        from archium.infrastructure.database.repositories import ProjectRepository

        project = ProjectRepository(session).get_by_id(project_id)
        if project is not None and project.origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION:
            st.info(
                "当前为概念探索草稿 — 假设可随研究修正；正式交付需后续补充资料。"
            )
        elif project is not None and project.origin_mode == ProjectOriginMode.RESEARCH_PROGRAMMING:
            st.info(
                "当前为策划与可研模式 — 重点梳理决策背景与未知项；"
                "成果以问题清单、工作路径或备忘录为主；正式交付需后续补充资料。"
            )
        else:
            st.caption(
                "资料不完整也没关系。可以描述项目背景、甲方要求、现状问题，以及你希望最终完成什么。"
            )

    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往 **设置 → AI 服务** 配置。")
        return

    if "mission_task_draft" not in st.session_state:
        st.session_state.mission_task_draft = ""
    genesis_task = st.session_state.pop("genesis_task_description", None)
    if genesis_task and not st.session_state.mission_task_draft:
        st.session_state.mission_task_draft = genesis_task
    example_pool = TASK_EXAMPLE_PROMPTS
    if project is not None and project.origin_mode == ProjectOriginMode.RESEARCH_PROGRAMMING:
        example_pool = PROGRAMMING_TASK_EXAMPLE_PROMPTS
    example = st.selectbox(
        "示例（可选，不会限制你的描述）",
        options=["（不使用示例）", *example_pool],
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

        def _on_start_complete(result: object) -> None:
            _apply_planning_result(result)
            st.session_state.mission_step = 2

        if not _launch_planning_job(
            project_id,
            PlanningJobAction.START,
            settings=settings,
            task_description=task,
            on_complete=_on_start_complete,
            success_message="已生成任务理解。请核对并回答关键问题。",
            awaiting_review_message="已生成任务理解，但存在可修复问题。请先编辑后再继续。",
        ):
            return



def _render_mission(snapshot: PlanningSnapshot, project_id: UUID) -> None:
    if snapshot.mission is None:
        st.info("请先在第 1 步描述并分析任务。")
        return

    if snapshot.review_gate == "mission_correction":
        st.warning("任务理解存在可修复问题。请先编辑下方字段，再重新校验。")
        validation = snapshot.mission_validation or {}
        recoverable = validation.get("recoverable_errors") or []
        if isinstance(recoverable, list) and recoverable:
            for item in recoverable:
                if isinstance(item, str) and item.strip():
                    st.error(item)
        elif snapshot.warnings:
            for item in snapshot.warnings:
                st.error(item)
        render_mission_panel(snapshot.mission)
        if st.session_state.planning_workflow_run_id and st.button(
            "重新校验并继续",
            type="primary",
            use_container_width=True,
        ):
            run_id = UUID(st.session_state.planning_workflow_run_id)

            def _on_correction_complete(result: object) -> None:
                _apply_planning_result(result)
                from archium.application.planning_workflow_service import PlanningWorkflowResult

                if isinstance(result, PlanningWorkflowResult):
                    gate = result.review_gate
                    if gate == "clarification":
                        st.session_state.mission_step = 3
                    else:
                        st.session_state.mission_step = 2

            if not _launch_planning_job(
                project_id,
                PlanningJobAction.CONTINUE_MISSION_CORRECTION,
                settings=get_ui_effective_settings(),
                workflow_run_id=run_id,
                on_complete=_on_correction_complete,
                success_message="校验通过，请继续下一步。",
                awaiting_review_message="仍有待修复问题，请继续编辑后重试。",
            ):
                return

        return

    render_mission_panel(snapshot.mission)

    if snapshot.review_gate == "mission_approval" and st.session_state.planning_workflow_run_id:
        st.info("澄清已完成。请确认任务理解无误后批准，再进入工作路径与成果规划。")
        if st.button("批准任务理解并继续规划", type="primary", use_container_width=True):
            run_id = UUID(st.session_state.planning_workflow_run_id)

            def _on_approve_complete(result: object) -> None:
                _apply_planning_result(result)
                st.session_state.mission_step = 4

            if not _launch_planning_job(
                project_id,
                PlanningJobAction.APPROVE_MISSION,
                settings=get_ui_effective_settings(),
                workflow_run_id=run_id,
                on_complete=_on_approve_complete,
                success_message="任务理解已批准，已生成工作路径与成果计划。",
            ):
                return

        return

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
        "完成澄清，提交任务理解审批",
        type="primary",
        use_container_width=True,
        disabled=not can_continue or not st.session_state.planning_workflow_run_id,
    ):
        run_id = UUID(st.session_state.planning_workflow_run_id)

        def _on_clarification_complete(result: object) -> None:
            _apply_planning_result(result)
            st.session_state.mission_step = 2

        if not _launch_planning_job(
            project_id,
            PlanningJobAction.CONTINUE_CLARIFICATION,
            settings=get_ui_effective_settings(),
            workflow_run_id=run_id,
            on_complete=_on_clarification_complete,
            success_message="已修订任务理解，请确认并批准后再继续规划。",
        ):
            return



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

    mission_id = snapshot.mission.id if snapshot.mission is not None else None
    question_plans = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type") == DeliverableType.QUESTION_LIST.value
    ]
    work_plan_plans = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type")
        in {
            DeliverableType.WORK_PLAN.value,
            DeliverableType.IMPLEMENTATION_ROADMAP.value,
        }
    ]
    report_plans = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type")
        in {
            DeliverableType.REPORT.value,
            DeliverableType.TECHNICAL_PROPOSAL.value,
        }
    ]
    memo_plans = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type") == DeliverableType.MEMO.value
    ]
    checklist_plans = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type") == DeliverableType.CHECKLIST.value
    ]
    case_study_plans = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type") == DeliverableType.CASE_STUDY.value
    ]

    text_artifact_groups = [
        (question_plans, "提问清单", "gen_ql_", "artifact_ql_", "正在从 Mission 上下文生成提问清单…", generate_question_list_artifact),
        (work_plan_plans, "工作大纲", "gen_wp_", "artifact_wp_", "正在生成工作大纲…", generate_work_plan_artifact),
        (report_plans, "报告", "gen_report_", "artifact_report_", "正在生成报告提纲…", generate_report_artifact),
        (memo_plans, "备忘录", "gen_memo_", "artifact_memo_", "正在生成备忘录…", generate_memo_artifact),
        (checklist_plans, "清单", "gen_cl_", "artifact_cl_", "正在生成清单…", generate_checklist_artifact),
        (case_study_plans, "案例研究", "gen_cs_", "artifact_cs_", "正在生成案例研究提纲…", generate_case_study_artifact),
    ]
    has_text_artifacts = any(group[0] for group in text_artifact_groups)

    if mission_id is not None and has_text_artifacts:
        st.markdown("**非汇报成果生成**")
        for plans, kind_label, btn_prefix, cache_prefix, spinner_text, generator in text_artifact_groups:
            for item in plans:
                label = item.get("deliverable_title") or kind_label
                deliverable_id = str(item.get("deliverable_id") or "") or None
                cache_key = f"{cache_prefix}{item.get('deliverable_id')}"
                if st.button(
                    f"生成{kind_label}：{label}",
                    key=f"{btn_prefix}{item.get('deliverable_id')}",
                    use_container_width=True,
                ):
                    with st.spinner(spinner_text):
                        try:
                            with get_session() as session:
                                output = generator(
                                    session,
                                    mission_id,
                                    deliverable_id=deliverable_id,
                                )
                            st.session_state[cache_key] = output
                            count = output.payload.get("item_count")
                            paths = [f"Markdown：{output.markdown_path}"]
                            if getattr(output, "docx_path", None):
                                paths.append(f"DOCX：{output.docx_path}")
                            if count is not None:
                                st.success(f"已生成 {count} 项。" + " ".join(paths))
                            else:
                                st.success(f"已生成{kind_label}。" + " ".join(paths))
                        except WorkflowError as exc:
                            st.error(format_user_error(exc))
                        except Exception as exc:
                            st.error(format_user_error(exc))
                cached = st.session_state.get(cache_key)
                if cached is not None:
                    with st.expander(f"预览：{label}", expanded=False):
                        st.markdown(cached.markdown)
                        if cached.markdown_path:
                            st.caption(f"Markdown：{cached.markdown_path}")
                        if cached.json_path:
                            st.caption(f"JSON：{cached.json_path}")
                        if getattr(cached, "docx_path", None):
                            st.caption(f"DOCX：{cached.docx_path}")

        with get_session() as session:
            recent_jobs = list_artifact_jobs(session, mission_id, limit=8)
        if recent_jobs:
            st.markdown("**最近成果作业**")
            for job in recent_jobs:
                status = job.status.value
                st.caption(
                    f"{job.deliverable_title or job.deliverable_id} · {job.request_kind} · {status}"
                    + (f" · {job.markdown_path}" if job.markdown_path else "")
                    + (f" · 错误：{job.error_message}" if job.error_message else "")
                )

    selected_presentations: list[object] = [
        item
        for item in execution_plans
        if item.get("supported")
        and item.get("deliverable_type") == DeliverableType.PRESENTATION.value
    ]
    if not selected_presentations and snapshot.deliverable_plan is not None:
        selected_presentations = [
            item
            for item in snapshot.deliverable_plan.deliverables
            if item.selected and item.deliverable_type == DeliverableType.PRESENTATION
        ]

    if not selected_presentations:
        if not has_text_artifacts:
            st.info(
                "当前没有可自动生成的成果。"
                "请回到第 5 步勾选汇报或非汇报类成果（提问清单 / 工作大纲 / 报告 / 备忘录等）。"
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
    require_brief = st.checkbox(
        f"{entity_label('PresentationBrief')} 生成后暂停审核",
        value=True,
    )
    require_storyline = st.checkbox(
        f"{entity_label('Storyline')} 生成后暂停审核",
        value=True,
    )

    if st.button("批准成果计划并生成汇报", type="primary", use_container_width=True):
        run_id = UUID(st.session_state.planning_workflow_run_id)
        settings = get_ui_effective_settings()
        export_kwargs = {
            "export_json": export_json,
            "export_marp": export_marp,
            "require_brief_review": require_brief,
            "require_storyline_review": require_storyline,
        }

        def _on_presentation_complete(result: object) -> None:
            _apply_presentation_bridge_result(result)

        if not _launch_planning_job(
            project_id,
            PlanningJobAction.START_PRESENTATION,
            settings=settings,
            workflow_run_id=run_id,
            on_complete=_on_presentation_complete,
            success_message="汇报管线已启动并完成当前阶段。",
            awaiting_review_message=(
                f"汇报工作流已暂停审核。请到「项目工作台」继续审核 {brief_storyline_pair()}。"
            ),
            export_kwargs=export_kwargs,
        ):
            return


    last_result = st.session_state.get("last_presentation_result")
    if last_result is not None and last_result.brief is not None:
        st.caption(
            f"最近结果：{last_result.brief.title} · 状态 {last_result.workflow_run.status.value}"
        )
        if last_result.succeeded and not last_result.awaiting_review:
            _render_post_presentation_links()


def render(*, embedded: bool = False) -> None:
    """Render the six-step mission planner.

    When ``embedded`` is True (e.g. inside the 大纲 advanced expander), skip the
    outer page title and reuse the host page's selected project.
    """
    _init_state()
    if not embedded:
        st.markdown("### 项目任务")
        st.caption("先理解任务，再规划工作路径与成果，最后进入现有汇报主链。")
    else:
        st.caption("任务理解、关键问题、工作路径与成果选择。")

    if embedded:
        raw = st.session_state.get("selected_project_id")
        if raw is None:
            st.info("请先在上方选择项目。")
            return
        selected_project_id: UUID | None = UUID(str(raw))
    else:
        selected_project_id = _project_selector()

    if selected_project_id is None:
        return

    project_id = selected_project_id
    snapshot = _load_snapshot(project_id)
    _sync_step_from_snapshot(snapshot)

    render_workflow_progress_panel(
        project_id,
        scope="planning",
        on_complete=_apply_planning_result,
        result_session_key=None,
        rerun_on_complete=False,
    )

    if snapshot.workflow_run is not None:
        gate = snapshot.review_gate or "—"
        st.caption(
            f"规划工作流：{snapshot.workflow_run.status.value} · 闸门：{gate}"
        )
        restart_key = "mission_restart_embedded" if embedded else "mission_restart"
        if st.button("重新开始新的任务分析", key=restart_key):
            st.session_state.planning_workflow_run_id = None
            st.session_state.planning_mission_id = None
            st.session_state.mission_step = 1
            st.session_state.mission_task_draft = ""
            st.rerun()

    st.divider()
    step = _render_step_nav(key="mission_step_nav_embedded" if embedded else "mission_step_nav")
    st.divider()

    if step == 1:
        _render_describe(project_id)
    elif step == 2:
        # Reload after edits / navigation
        snapshot = _load_snapshot(project_id)
        _render_mission(snapshot, project_id)
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


def select_current_project() -> UUID | None:
    """Shared project picker used by the 大纲 default view."""
    _init_state()
    return _project_selector(key="outline_project_selector")


def load_planning_snapshot(project_id: UUID) -> PlanningSnapshot:
    """Shared planning snapshot loader used by the 大纲 default view."""
    _init_state()
    return _load_snapshot(project_id)


def reset_planning_session() -> None:
    """Clear active planning ids so the user can start a new outline."""
    _init_state()
    st.session_state.planning_workflow_run_id = None
    st.session_state.planning_mission_id = None
    st.session_state.planning_session_id = None
    st.session_state.mission_step = 1
    st.session_state.mission_task_draft = ""


def start_outline_planning(project_id: UUID, task_description: str) -> bool:
    """Start planning from the 大纲 default view. Returns True if background job launched."""
    _init_state()
    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往 **设置 → AI 服务** 配置。")
        return False
    if not task_description.strip():
        st.error("请先描述汇报任务。")
        return False

    def _on_start_complete(result: object) -> None:
        _apply_planning_result(result)
        st.session_state.mission_step = 2

    if not _launch_planning_job(
        project_id,
        PlanningJobAction.START,
        settings=settings,
        task_description=task_description,
        on_complete=_on_start_complete,
        success_message="已生成任务理解。可在下方确认大纲，或打开高级任务规划继续细化。",
        awaiting_review_message="已生成任务理解，但存在可修复问题。请打开高级任务规划继续处理。",
    ):
        return False
    return True
