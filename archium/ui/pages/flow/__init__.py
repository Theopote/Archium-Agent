"""Shared chrome for product-flow stage pages: stepper, gates, nav actions."""

from __future__ import annotations

from dataclasses import dataclass, field

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import (
    render_page_header,
    render_primary_action,
    render_secondary_action,
    render_stepper,
    render_warning_callout,
)
from archium.ui.product_flow import (
    get_stage,
    next_stage,
    previous_stage,
    primary_stage_ids,
    primary_stages,
)
from archium.ui.project_progress_card import (
    ProjectProgressSnapshot,
    load_project_progress_snapshot,
)

_NEXT_ACTION_LABELS = {
    "materials": "确认资料并进入大纲 →",
    "outline": "确认大纲并开始生成 →",
    "generate": "进入工作室 →",
    "edit": "进入交付 →",
}


@dataclass(frozen=True)
class StageGateResult:
    can_proceed: bool
    blockers: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_blockers(self) -> bool:
        return bool(self.blockers)


def evaluate_stage_gate(
    stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> StageGateResult:
    """Decide whether the user can advance from ``stage_id`` to the next stage."""
    blockers: list[str] = []
    warnings: list[str] = []

    if snapshot is None:
        blockers.append("先创建或选择一个项目")
        return StageGateResult(can_proceed=False, blockers=tuple(blockers))

    if stage_id == "materials":
        if snapshot.document_count <= 0:
            warnings.append(
                "尚未绑定项目资料，后续生成将标记为概念草稿，不得正式交付"
            )
        return StageGateResult(
            can_proceed=True,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "outline":
        if snapshot.document_count <= 0:
            warnings.append("尚未绑定项目资料，生成内容仅作为概念草稿")
        if (
            not snapshot.outline_approved
            and not snapshot.has_brief
            and snapshot.presentation_id is None
        ):
            blockers.append("确认汇报对象与大纲结构（生成大纲）")
        elif not snapshot.outline_approved and not snapshot.has_brief:
            warnings.append("建议确认大纲后再生成")
        return StageGateResult(
            can_proceed=not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "generate":
        if snapshot.slide_count <= 0:
            blockers.append("先生成至少一页内容")
        elif snapshot.pending_count > 0:
            warnings.append(f"仍有 {snapshot.pending_count} 页版式待完成")
        return StageGateResult(
            can_proceed=not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "edit":
        if snapshot.slide_count <= 0:
            blockers.append("尚无可编辑页面，请先完成生成")
        elif not snapshot.ready_for_export:
            warnings.append("部分页面版式未齐，交付时可能受限")
        if snapshot.document_count <= 0:
            warnings.append("无项目证据 · 草稿模式，正式交付将被阻止")
        return StageGateResult(
            can_proceed=not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "deliver":
        if snapshot.document_count <= 0:
            blockers.append("概念草稿不可正式交付：请先绑定至少一份项目资料")
        elif not snapshot.ready_for_export:
            warnings.append("版式未齐，导出可能不完整")
        return StageGateResult(
            can_proceed=not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    return StageGateResult(can_proceed=True)


def _stage_marker(status: str) -> str:
    return {
        "done": "●",
        "current": "◉",
        "todo": "○",
        "warn": "◐",
        "blocked": "✕",
    }.get(status, "○")


def stage_completion_status(
    stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> str:
    """Real completion for one stage from project data (never inferred from page index)."""
    if snapshot is None:
        return "blocked"

    if stage_id == "materials":
        return "done" if snapshot.document_count > 0 else "warn"

    if stage_id == "outline":
        if snapshot.has_brief or getattr(snapshot, "outline_approved", False):
            return "done"
        return "warn" if snapshot.presentation_id else "todo"

    if stage_id == "generate":
        if snapshot.slide_count <= 0:
            return "todo"
        if snapshot.pending_count > 0:
            return "warn"
        return "done"

    if stage_id == "edit":
        if snapshot.slide_count <= 0:
            return "blocked"
        return "done" if snapshot.ready_for_export else "warn"

    if stage_id == "deliver":
        return "done" if snapshot.ready_for_export else "todo"

    return "todo"


def _stage_statuses(
    current_stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> dict[str, str]:
    """Highlight current page; completion comes from snapshot, not navigation order."""
    statuses: dict[str, str] = {}
    for stage in primary_stages():
        completion = stage_completion_status(stage.id, snapshot)
        if stage.id == current_stage_id:
            # Current page is highlighted; do not fake "done" for unfinished work.
            if completion in {"blocked", "todo"}:
                statuses[stage.id] = "blocked" if completion == "blocked" else "current"
            elif completion == "warn":
                statuses[stage.id] = "warn"
            else:
                statuses[stage.id] = "current"
        else:
            statuses[stage.id] = completion
    return statuses


def render_flow_stepper(current_stage_id: str) -> None:
    """Visual stepper replacing the repeated plain-text flow chain."""
    import html

    snapshot = None
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        snapshot = None

    statuses = _stage_statuses(current_stage_id, snapshot)
    parts: list[str] = []
    for stage in primary_stages():
        marker = _stage_marker(statuses[stage.id])
        title = html.escape(stage.title)
        if stage.id == current_stage_id:
            parts.append(f"<strong>{marker} {title}</strong>")
        else:
            parts.append(f"{marker} {title}")
    render_stepper(" ─ ".join(parts))


def render_stage_header(stage_id: str) -> None:
    stage = get_stage(stage_id)
    render_page_header(stage.title, stage.caption)
    render_flow_stepper(stage_id)


def render_flow_project_context(
    *,
    allow_create: bool = False,
    key_prefix: str = "flow",
) -> object | None:
    """Compact current-project chrome for product-flow stages.

    Avoids repeating a full project selector on every stage when a project is
    already selected; switching stays behind an expander.
    """
    from uuid import UUID

    from archium.infrastructure.database.session import get_session
    from archium.ui.pages.workspace import ensure_workspace_session
    from archium.ui.workspace_service import list_projects

    ensure_workspace_session()
    with get_session() as session:
        projects = list_projects(session)
    if not projects:
        if allow_create:
            from archium.ui.pages.workspace import render_project_picker

            return render_project_picker(allow_create=True)
        st.info("请先在「资料」阶段创建或选择项目。")
        return None

    labels = {str(project.id): project.name for project in projects}
    options = list(labels.keys())
    selected = st.session_state.get("selected_project_id")
    if selected not in options:
        from archium.ui.pages.workspace import render_project_picker

        return render_project_picker(allow_create=allow_create)

    st.caption(f"当前项目：{labels[str(selected)]}")
    with st.expander("切换项目", expanded=False):
        if allow_create:
            from archium.ui.pages.workspace import _render_create_project

            _render_create_project()
        picked = st.selectbox(
            "项目",
            options=options,
            index=options.index(str(selected)),
            format_func=lambda value: labels[value],
            key=f"{key_prefix}_project_switch",
        )
        if picked != str(selected):
            st.session_state.selected_project_id = picked
            st.session_state.selected_presentation_id = None
            st.rerun()
    return UUID(str(selected))


def render_stage_nav(
    stage_id: str,
    *,
    primary_only: bool = False,
    include_next: bool = True,
) -> None:
    """Conditional primary next-stage action; previous stage is secondary.

    ``include_next=False`` lets a stage page own its confirm CTA (e.g. 大纲).
    """
    snapshot = None
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        snapshot = None

    prev = previous_stage(stage_id)
    nxt = next_stage(stage_id) if include_next else None
    gate = evaluate_stage_gate(stage_id, snapshot)

    st.divider()
    if include_next:
        if gate.blockers:
            render_warning_callout(
                "进入下一阶段前还需完成："
                + "；".join(gate.blockers)
            )
        elif gate.warnings:
            for item in gate.warnings:
                render_warning_callout(item)

    left, right = st.columns([1, 1.4])
    with left:
        if prev is not None and not primary_only:
            if render_secondary_action(
                f"← 上一阶段：{prev.title}",
                key=f"stage_prev_{stage_id}",
            ):
                st.switch_page(get_app_page(prev.page_key))
    with right:
        if nxt is None:
            return
        label = _NEXT_ACTION_LABELS.get(stage_id, f"下一阶段：{nxt.title} →")
        if render_primary_action(
            label,
            key=f"stage_next_{stage_id}",
            disabled=gate.has_blockers,
        ):
            st.switch_page(get_app_page(nxt.page_key))
