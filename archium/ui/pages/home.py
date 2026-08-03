"""Archium home — focused project cockpit."""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from archium.domain.delivery_record import DeliveryRecord
from archium.application.unit_of_work import application_api, unit_of_work
from archium.ui.app_navigation import get_app_page
from archium.ui.project_progress_card import (
    ProjectProgressSnapshot,
    _format_relative_time,
    continue_work_page_key,
    greeting_for_now,
    list_recent_project_snapshots,
    load_cockpit_task_summary,
)
from archium.ui.session_context import select_project_context
from archium.ui.workspace_service import list_project_presentations

logger = logging.getLogger(__name__)


def _apply_studio_overview_for_wireframe_deck(snapshot: ProjectProgressSnapshot) -> None:
    """When genesis wireframes are ready, open studio in deck overview mode."""
    try:
        from archium.application.genesis_starter_service import (
            get_genesis_starter_state,
            presentation_has_formal_visual_previews,
        )

        with unit_of_work() as uow:
            starter = get_genesis_starter_state(uow, snapshot.project_id)
            if starter is None:
                return
            if starter.layout_ready_count < max(1, starter.page_count):
                return
            if presentation_has_formal_visual_previews(uow, starter.presentation_id):
                return
        st.session_state.studio_center_mode = "overview"
        st.session_state.studio_selected_slide_index = 0
    except Exception:
        logger.exception("Failed to apply studio overview defaults")


def _select_and_continue(snapshot: ProjectProgressSnapshot) -> None:
    select_project_context(
        st.session_state,
        snapshot.project_id,
        presentation_id=snapshot.presentation_id,
    )
    page_key = continue_work_page_key(snapshot)
    if page_key == "edit":
        _apply_studio_overview_for_wireframe_deck(snapshot)
    st.switch_page(get_app_page(page_key))


def _resolve_primary(snapshots: list[ProjectProgressSnapshot]) -> ProjectProgressSnapshot | None:
    if not snapshots:
        return None
    selected = st.session_state.get("selected_project_id")
    if selected:
        for item in snapshots:
            if str(item.project_id) == str(selected):
                return item
    return snapshots[0]


def _go_new_project() -> None:
    st.session_state.pop("genesis_intent", None)
    st.session_state.show_create_form = True
    st.switch_page(get_app_page("project-genesis"))


def _go_fast_deck() -> None:
    """少追问、尽快出稿：进入 Genesis 快速线。"""
    st.session_state.genesis_intent = "fast_deck"
    st.session_state.show_create_form = True
    st.session_state.genesis_go_studio_after = True
    st.switch_page(get_app_page("project-genesis"))


def _go_open_projects() -> None:
    st.session_state.home_show_project_picker = True
    st.switch_page(get_app_page("project-management"))


def _go_tool_hub() -> None:
    st.switch_page(get_app_page("tool-hub"))


def _render_task_entries(*, empty: bool = False) -> None:
    """Homepage only exposes tasks — not the five-stage system flow."""
    st.markdown(f"### {greeting_for_now()}")
    if empty:
        st.caption("选择要做的事。不必先了解系统流程，也不必创建 Mission。")
    else:
        st.caption("从任务进入。完整五阶段在侧栏「制作」中，仅在你需要时使用。")

    cols = st.columns(2)
    with cols[0]:
        with st.container(border=True):
            st.markdown("**新项目**")
            st.caption("描述想法或项目情况，让 Archium 评估知识状态。")
            if st.button("开始新项目", key="home_entry_new", type="primary", width="stretch"):
                _go_new_project()
        with st.container(border=True):
            st.markdown("**快速生成一份汇报**")
            st.caption("少追问、尽快出初稿，完成后可进工作室预览。")
            if st.button("快速出稿", key="home_entry_fast", width="stretch"):
                _go_fast_deck()
    with cols[1]:
        with st.container(border=True):
            st.markdown("**打开已有项目**")
            st.caption("继续最近项目，或到项目列表中选择。")
            if st.button("打开项目", key="home_entry_open", width="stretch"):
                _go_open_projects()
        with st.container(border=True):
            st.markdown("**使用单项工具**")
            st.caption("只做一件事：复活页面、套模板、查事实等。")
            if st.button("打开工具台", key="home_entry_tools", width="stretch"):
                _go_tool_hub()


def _render_load_failed(exc: Exception) -> None:
    from archium.ui import icons
    from archium.ui.components.chrome import (
        render_empty_state,
        render_error_callout,
        render_primary_action,
    )

    logger.exception("Failed to load home project snapshots: %s", exc)
    render_error_callout("项目列表暂时无法加载，请重试。")
    render_empty_state(
        "无法加载项目",
        "这通常是数据或连接问题，并不表示你没有项目。",
    )
    if render_primary_action("重试", key="home_retry_load", use_container_width=False):
        st.rerun()
    st.page_link(
        get_app_page("project-management"),
        label="前往项目管理",
        icon=icons.PROJECT,
    )


def _render_progress_bar(snapshot: ProjectProgressSnapshot) -> None:
    if snapshot.slide_count <= 0:
        st.progress(0.0, text=snapshot.completion_label)
        return
    ratio = min(1.0, snapshot.layout_ready_count / max(1, snapshot.slide_count))
    st.progress(ratio, text=snapshot.completion_label)


def _render_pending_issues(snapshot: ProjectProgressSnapshot) -> None:
    st.markdown("**待处理问题**")
    try:
        tasks = load_cockpit_task_summary(snapshot)
    except Exception:
        logger.exception("Failed to load cockpit task summary")
        st.caption("任务摘要暂不可用。")
        return
    if not tasks.has_tasks:
        if snapshot.ready_for_export:
            st.success("暂无阻塞项，可以前往交付导出。")
        else:
            st.info("暂无紧急问题。")
        return
    for line in tasks.lines:
        st.markdown(f"- {line}")


def _render_recent_versions(snapshot: ProjectProgressSnapshot) -> None:
    st.markdown("**最近版本**")
    try:
        with unit_of_work() as uow:
            presentations = list_project_presentations(uow, snapshot.project_id)
    except Exception:
        logger.exception("Failed to list presentations for home")
        presentations = []

    export_records: list[DeliveryRecord | dict[str, object]] = []
    try:
        from archium.application.unit_of_work import application_api

        with application_api() as api:
            export_records = [
                record
                for record in api.delivery.list_for_project(
                    snapshot.project_id, limit=4
                )
            ]
    except Exception:
        export_records = [
            record
            for record in (st.session_state.get("delivery_export_records") or [])
            if str(record.get("project_id") or "") in {"", str(snapshot.project_id)}
        ]

    if presentations:
        for presentation in presentations[:4]:
            st.caption(
                f"{presentation.title} · {presentation.status.value} · "
                f"{presentation.updated_at.strftime('%Y-%m-%d %H:%M')}"
            )
    if export_records:
        st.caption("最近导出")
        for record in export_records[:4]:
            if isinstance(record, DeliveryRecord):
                when = record.exported_at.astimezone().strftime("%Y-%m-%d %H:%M")
                st.caption(f"{record.format} · {when} · {_export_basename(record.file_uri)}")
            else:
                path_label = _export_basename(str(record.get("path", "") or record.get("file_uri", "")))
                when = str(record.get("when", "") or "")
                st.caption(f"{record.get('format', '导出')} · {when} · {path_label}")
    if not presentations and not export_records:
        st.caption("尚无汇报版本。完成生成或导出后会显示在此。")


def _export_basename(path_or_uri: str) -> str:
    text = (path_or_uri or "").strip()
    if not text:
        return "导出文件"
    name = Path(text.replace("\\", "/")).name
    return name or "导出文件"

def _task_statement_for(snapshot: ProjectProgressSnapshot) -> str:
    """Prefer mission/brief task text; fall back to presentation title/type."""
    try:
        from archium.ui.pages import project_mission

        planning = project_mission.load_planning_snapshot(snapshot.project_id)
        if planning.mission is not None and planning.mission.task_statement.strip():
            return planning.mission.task_statement.strip()
        if planning.presentation_request is not None:
            request = planning.presentation_request
            bits = [request.title, request.purpose or request.core_message]
            text = " — ".join(part for part in bits if part)
            if text:
                return text
    except Exception:
        logger.exception("Failed to load planning snapshot for home task statement")
    if snapshot.presentation_title:
        return snapshot.presentation_title
    return snapshot.presentation_type_label


def _render_recent_design_changes(snapshot: ProjectProgressSnapshot) -> None:
    """Partner-facing design timeline snippet for Project Home."""
    st.markdown("**最近设计变化**")
    try:
        from archium.ui.intent_evolution_panel import (
            format_intent_event_time,
            intent_evolution_kind_label,
        )

        with application_api() as api:
            try:
                project = api.project.get(snapshot.project_id)
            except Exception:
                project = None
        evolution = project.intent_evolution if project is not None else None
        events = list(evolution.events) if evolution is not None else []
        if not events:
            st.caption("尚无设计决策记录。理解项目、选定方向或反思后会出现。")
            return
        st.caption(f"共 {len(events)} 次设计演进")
        for event in reversed(events[-5:]):
            kind = intent_evolution_kind_label(event.kind)
            when = format_intent_event_time(event.at)
            line = _partner_design_event_line(event.display_line())
            st.markdown(f"- **{kind}** · `{when}` — {line}")
        with st.expander("完整设计时间线", expanded=False):
            from archium.ui.intent_evolution_panel import render_intent_evolution_timeline

            render_intent_evolution_timeline(
                evolution,
                key_prefix=f"home_evo_{snapshot.project_id}",
                limit=16,
            )
    except Exception:
        logger.exception("Failed to render home design timeline")
        st.caption("设计演进暂不可用。")


def _partner_design_event_line(raw: str) -> str:
    """Collapse metric-heavy AI refresh noise for the home timeline."""
    text = (raw or "").strip()
    if "规则评估" in text and "%" in text:
        return "已根据最新资料刷新理解"
    return text

def _render_partner_next_steps(snapshot: ProjectProgressSnapshot) -> None:
    st.markdown("**下一步**")
    st.caption(
        f"点击下方「继续工作」进入 **{snapshot.continue_work_label}**。"
    )


def _render_home_starter_preview(snapshot: ProjectProgressSnapshot) -> None:
    """Show genesis draft card while deck is still in wireframe / placeholder mode."""
    if snapshot.slide_count <= 0:
        return
    try:
        from archium.application.genesis_starter_service import (
            get_genesis_starter_state,
            presentation_has_formal_visual_previews,
        )
        from archium.ui.components.genesis_draft_card import render_genesis_draft_card

        with unit_of_work() as uow:
            starter = get_genesis_starter_state(uow, snapshot.project_id)
            formal_previews = False
            if starter is not None:
                formal_previews = presentation_has_formal_visual_previews(
                    uow, starter.presentation_id
                )
        if starter is None or not starter.has_first_slide:
            return
        if formal_previews:
            return
        if snapshot.presentation_id is not None:
            st.session_state.selected_presentation_id = str(snapshot.presentation_id)
        render_genesis_draft_card(starter, compact=True)
        wireframe_complete = starter.layout_ready_count >= max(1, starter.page_count)
        if wireframe_complete:
            with st.container(horizontal=True):
                if st.button(
                    "全稿鸟瞰",
                    key=f"home_deck_overview_{snapshot.project_id}",
                    width="stretch",
                    type="primary",
                ):
                    if snapshot.presentation_id is not None:
                        st.session_state.selected_presentation_id = str(
                            snapshot.presentation_id
                        )
                    st.session_state.studio_selected_slide_index = 0
                    st.session_state.studio_center_mode = "overview"
                    st.switch_page(get_app_page("edit"))
                if snapshot.outline_approved:
                    if st.button(
                        "继续生成",
                        key=f"home_continue_generate_{snapshot.project_id}",
                        width="stretch",
                    ):
                        if snapshot.presentation_id is not None:
                            st.session_state.selected_presentation_id = str(
                                snapshot.presentation_id
                            )
                        st.switch_page(get_app_page("generate"))
                elif st.button(
                    "前往确认大纲",
                    key=f"home_confirm_outline_{snapshot.project_id}",
                    width="stretch",
                ):
                    st.switch_page(get_app_page("outline"))
        elif st.button(
            "预览封面页",
            key=f"home_studio_preview_{snapshot.project_id}",
            width="content",
        ):
            if snapshot.presentation_id is not None:
                st.session_state.selected_presentation_id = str(snapshot.presentation_id)
            st.session_state.studio_selected_slide_index = 0
            st.switch_page(get_app_page("edit"))
    except Exception:
        logger.exception("Failed to render home starter preview")


def _render_project_details(snapshot: ProjectProgressSnapshot) -> None:
    """Render expensive project diagnostics only when the user asks for them."""
    try:
        from archium.ui.llm_settings import render_project_llm_tier_selector

        render_project_llm_tier_selector(
            snapshot.project_id,
            key_prefix="home_llm_tier",
        )
    except Exception:
        logger.exception("Failed to render project LLM tier selector")

    left, right = st.columns(2)
    with left:
        _render_recent_design_changes(snapshot)
        try:
            from archium.ui.project_event_panel import (
                render_project_event_log,
                render_project_usage_strip,
            )

            render_project_event_log(
                snapshot.project_id,
                limit=6,
                expanded=False,
                title="项目事件记忆",
            )
            render_project_usage_strip(
                snapshot.project_id,
                expanded=False,
                title="本月 LLM 用量",
            )
        except Exception:
            logger.exception("Failed to render project event details")

    with right:
        try:
            from archium.ui.project_event_panel import render_job_progress_strip

            render_job_progress_strip(
                snapshot.project_id,
                limit=4,
                active_only=False,
                title="任务进度",
                allow_process_once=True,
                show_worker_hint=False,
            )
        except Exception:
            logger.exception("Failed to render project job progress")
        try:
            from archium.ui.project_members_panel import render_project_members_panel

            render_project_members_panel(
                snapshot.project_id,
                key_prefix="home_members",
                expanded=False,
            )
        except Exception:
            logger.exception("Failed to render project members panel")

    _render_pending_issues(snapshot)
    _render_recent_versions(snapshot)


def _render_project_cockpit(snapshot: ProjectProgressSnapshot) -> None:
    with st.container(border=True):
        header_l, header_r = st.columns([3.2, 1])
        with header_l:
            st.markdown(f"### 当前项目 · {snapshot.project_name}")
            st.caption("打开后可继续工作；下方为简要状态，细节已收起。")
        with header_r:
            if st.button("切换项目", width="stretch", key="home_switch_project"):
                st.switch_page(get_app_page("project-management"))

        st.markdown(f"**汇报任务**  \n{_task_statement_for(snapshot)}")

        _render_home_starter_preview(snapshot)

        if snapshot.outline_changes_pending:
            st.warning("大纲已编辑 · 待重新确认后再进入生成。")
        elif (
            snapshot.slide_count > 0
            and not snapshot.outline_approved
            and snapshot.has_outline
        ):
            st.info("Genesis 草稿已生成线框；确认大纲后可运行正式生成管线。")

        with st.container(horizontal=True):
            st.metric("当前阶段", snapshot.current_stage_label, border=True)
            st.metric("待完成页面", snapshot.pending_count, border=True)
            st.metric("交付状态", snapshot.deliver_label, border=True)
        st.caption(snapshot.narrative_summary)
        st.caption("总体进度")
        _render_progress_bar(snapshot)

        st.space("small")
        _render_partner_next_steps(snapshot)
        with st.container(horizontal=True, vertical_alignment="center"):
            if st.button(
                f"继续：{snapshot.continue_work_label}",
                type="primary",
                width="stretch",
                key="home_continue_primary",
            ):
                _select_and_continue(snapshot)

        details = st.expander(
            "项目详情与高级信息",
            expanded=False,
            icon=":material/tune:",
            on_change="rerun",
        )
        if details.open:
            with details:
                try:
                    from archium.ui.project_knowledge_profile import render_ai_understanding_panel

                    render_ai_understanding_panel(
                        snapshot.project_id,
                        compact=True,
                        show_actions=True,
                        key_prefix=f"home_understand_{snapshot.project_id}",
                        title="AI 当前理解",
                    )
                except Exception:
                    logger.exception("Failed to render home understanding panel")
                with st.container(border=True):
                    st.markdown("**项目动作**")
                    with st.container(horizontal=True):
                        st.page_link(
                            get_app_page("project-mission"),
                            label="项目任务",
                            icon=":material/assignment:",
                        )
                        st.page_link(
                            get_app_page("concept-exploration"),
                            label="概念探索",
                            icon=":material/lightbulb:",
                        )
                        st.page_link(
                            get_app_page("project-management"),
                            label="项目管理",
                            icon=":material/folder_managed:",
                        )
                _render_project_details(snapshot)

def _render_other_projects(
    snapshots: list[ProjectProgressSnapshot],
    *,
    primary: ProjectProgressSnapshot,
) -> None:
    others = [item for item in snapshots if item.project_id != primary.project_id]
    if not others:
        return
    with st.expander("其他最近项目", expanded=False):
        for snapshot in others:
            cols = st.columns([3.4, 1])
            with cols[0]:
                st.markdown(f"**{snapshot.project_name}**")
                st.caption(
                    f"{snapshot.current_stage_label} · {snapshot.completion_label} · "
                    f"{_format_relative_time(snapshot.updated_at)}"
                )
            with cols[1]:
                if st.button(
                    "继续工作",
                    key=f"home_open_{snapshot.project_id}",
                    width="stretch",
                    help="设为当前项目并进入建议阶段",
                ):
                    _select_and_continue(snapshot)


def render() -> None:
    from archium.ui.invite_deep_link import (
        consume_invite_query_param,
        peek_pending_invite_code,
    )

    pending_invite = consume_invite_query_param()
    if peek_pending_invite_code():
        st.info(
            f"检测到邀请码 `{peek_pending_invite_code()}`。"
            "请在下方「项目成员与角色」中确认成员 ID 并兑换。"
        )

    _render_task_entries(empty=False)

    try:
        snapshots = list_recent_project_snapshots(limit=6)
    except Exception as exc:
        _render_load_failed(exc)
        return

    primary = _resolve_primary(snapshots)
    if primary is None:
        st.caption("暂无项目。用上方「新项目」或「快速出稿」开始。")
        if pending_invite:
            st.caption("暂无项目时，可先到「项目管理」创建项目，或请邀请方确认项目仍有效。")
        return

    st.divider()
    _render_project_cockpit(primary)
    _render_other_projects(snapshots, primary=primary)