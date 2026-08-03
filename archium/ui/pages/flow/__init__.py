"""Shared chrome for product-flow stage pages: stepper, gates, nav actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import streamlit as st

from archium.domain.enums import EvidenceAvailability
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import (
    render_draft_mode_banner,
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
    primary_stages,
)
from archium.ui.project_progress_card import (
    ProjectProgressSnapshot,
    load_project_progress_snapshot,
)
from archium.ui.session_context import select_project_context
from archium.application.unit_of_work import unit_of_work

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


def _append_cognition_gate_warnings(project_id: UUID, warnings: list[str]) -> None:
    """Merge presentation cognition readiness messages into stage gate (Topic 07 L2)."""
    try:
        from archium.application.context.presentation_cognition_gate import (
            evaluate_presentation_cognition,
        )
        from archium.application.context.presentation_readiness import (
            PresentationGateVerdict,
        )
        from archium.config.settings import get_settings
        from archium.application.unit_of_work import unit_of_work

        mode = (get_settings().presentation_cognition_gate or "warn").strip().lower()
        if mode == "off":
            return
        with unit_of_work() as uow:
            readiness = evaluate_presentation_cognition(uow, project_id)
        if readiness.verdict == PresentationGateVerdict.PROCEED:
            return
        for msg in readiness.warnings[:3]:
            text = (msg or "").strip()
            if text and text not in warnings:
                warnings.append(f"认知门禁：{text}")
        if (
            readiness.summary
            and readiness.summary not in warnings
            and readiness.verdict != PresentationGateVerdict.PROCEED
        ):
            warnings.append(f"认知门禁：{readiness.summary}")
    except Exception:
        return


def _append_unresolved_design_warning(project_id: UUID, warnings: list[str]) -> None:
    """Soft-guide when concept directions are still open (Topic 07 L1)."""
    try:
        from archium.application.process.design_process_pointer import build_design_pointer
        from archium.application.product_continue_work import design_loop_open

        with unit_of_work() as uow:
            pointer = build_design_pointer(uow, project_id)
            if not design_loop_open(pointer):
                return
            label = pointer.label or "概念方向尚未选定"
    except Exception:
        return
    warnings.append(
        f"设计进程仍在进行（{label}）。建议先完成方向比较/选定，再推进汇报大纲。"
    )


def _append_role_edit_warning(project_id: UUID, warnings: list[str]) -> None:
    """Soft-guide Client/Reviewer away from edit-heavy stages (COLLAB-005)."""
    try:
        from archium.application.role_navigation import resolve_role_navigation
        from archium.ui.session_actor import get_current_actor_id

        with unit_of_work() as uow:
            hint = resolve_role_navigation(
                uow,
                project_id,
                actor_id=get_current_actor_id(),
            )
        if hint.can_edit or not hint.message:
            return
        if hint.message not in warnings:
            warnings.append(hint.message)
    except Exception:
        return


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
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            blockers.append("资料状态无法验证，请稍后重试或检查数据库连接")
            return StageGateResult(
                can_proceed=False,
                blockers=tuple(blockers),
            )
        if (
            snapshot.evidence_availability == EvidenceAvailability.MISSING
            or snapshot.document_count <= 0
        ):
            warnings.append(
                "尚未绑定项目资料，后续生成将标记为草稿预览，不得正式交付"
            )
        _append_unresolved_design_warning(snapshot.project_id, warnings)
        _append_cognition_gate_warnings(snapshot.project_id, warnings)
        _append_role_edit_warning(snapshot.project_id, warnings)
        return StageGateResult(
            can_proceed=True,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "outline":
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            warnings.append("资料状态无法验证；生成前请确认资料可读取")
        elif (
            snapshot.evidence_availability == EvidenceAvailability.MISSING
            or snapshot.document_count <= 0
        ):
            warnings.append("尚未绑定项目资料，生成内容仅作为草稿预览")
        _append_unresolved_design_warning(snapshot.project_id, warnings)
        _append_cognition_gate_warnings(snapshot.project_id, warnings)
        _append_role_edit_warning(snapshot.project_id, warnings)
        if not snapshot.outline_approved:
            if not getattr(snapshot, "has_outline", False) and not snapshot.has_brief:
                blockers.append("确认汇报对象与大纲结构（生成大纲）")
            elif not snapshot.outline_approved and getattr(snapshot, "has_outline", False):
                warnings.append("大纲已生成，请确认后再进入生成")
            elif snapshot.has_brief and not getattr(snapshot, "has_outline", False):
                warnings.append("Brief 已有，请生成并确认 OutlinePlan")
            else:
                warnings.append("建议确认大纲后再生成")
        elif not snapshot.design_briefs_approved:
            if snapshot.design_briefs_total <= 0:
                warnings.append("请生成并批准全部页面设计摘要")
            else:
                pending = snapshot.design_briefs_total - snapshot.design_briefs_approved_count
                warnings.append(f"仍有 {pending} 页设计摘要未批准")
            blockers.append("全部页面设计摘要批准后方可进入生成")
        return StageGateResult(
            can_proceed=snapshot.outline_approved and snapshot.design_briefs_approved and not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "generate":
        if snapshot.slide_count <= 0:
            blockers.append("先生成至少一页内容")
        elif snapshot.pending_count > 0:
            warnings.append(f"仍有 {snapshot.pending_count} 页版式待完成")
        _append_role_edit_warning(snapshot.project_id, warnings)
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
        _append_role_edit_warning(snapshot.project_id, warnings)
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            warnings.append("资料状态无法验证 · 正式交付将被阻止")
        elif (
            snapshot.evidence_availability == EvidenceAvailability.MISSING
            or snapshot.document_count <= 0
        ):
            warnings.append("无项目证据 · 草稿模式，正式交付将被阻止")
        return StageGateResult(
            can_proceed=not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    if stage_id == "deliver":
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            blockers.append("资料状态无法验证，禁止正式交付")
        elif (
            snapshot.evidence_availability == EvidenceAvailability.MISSING
            or snapshot.document_count <= 0
        ):
            blockers.append("草稿预览不可正式交付：请先绑定至少一份项目资料")
        elif not snapshot.formal_delivery_ready:
            if snapshot.export_blocker_count > 0:
                blockers.append(f"仍有 {snapshot.export_blocker_count} 个阻塞项未清除")
            elif not snapshot.ready_for_export:
                warnings.append("版式未齐，导出可能不完整")
        return StageGateResult(
            can_proceed=not blockers,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    return StageGateResult(can_proceed=True)


def _is_genesis_shortcut(snapshot: ProjectProgressSnapshot) -> bool:
    return (
        snapshot.slide_count > 0
        and not snapshot.outline_approved
        and snapshot.has_outline
    )


def evaluate_stage_access(
    stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> tuple[str, ...]:
    """Warnings when the user opens a stage before typical prerequisites."""
    if snapshot is None:
        return ("先创建或选择一个项目",)

    warnings: list[str] = []
    genesis_shortcut = _is_genesis_shortcut(snapshot)

    if stage_id == "generate":
        if genesis_shortcut:
            warnings.append(
                "当前为 Genesis 草稿捷径：建议先在大纲页确认结构与各页设计摘要，"
                "再运行正式生成管线。"
            )
        elif not snapshot.has_outline and not snapshot.has_brief:
            warnings.append("建议先在大纲页描述任务并生成大纲结构。")
        elif snapshot.has_outline and not snapshot.outline_approved:
            warnings.append("大纲尚未确认；正式生成前请在大纲页完成确认。")
        elif not snapshot.design_briefs_approved:
            warnings.append("仍有页面设计摘要未批准；正式生成前需在大纲页完成确认。")

    if stage_id == "edit" and snapshot.slide_count <= 0:
        warnings.append("尚无页面内容；请先在生成页运行内容生成管线，或从大纲确认后生成。")

    if stage_id == "deliver":
        if genesis_shortcut:
            warnings.append(
                "大纲尚未确认：当前导出基于 Genesis 草稿线框，建议先回大纲页确认结构。"
            )
        elif not snapshot.ready_for_export and snapshot.slide_count > 0:
            warnings.append("部分页面版式未齐；导出结果可能不完整。")

    if (
        stage_id in {"generate", "edit", "deliver"}
        and snapshot.document_count <= 0
        and snapshot.evidence_availability != EvidenceAvailability.UNKNOWN
    ):
        warnings.append("尚无项目资料：当前为草稿预览模式，不可正式交付。")

    return tuple(warnings)


def render_stage_access_advisory(
    stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> None:
    """Soft gate when users jump ahead via sidebar navigation."""
    for message in evaluate_stage_access(stage_id, snapshot):
        render_warning_callout(message)


_STAGE_ORDER = ("materials", "outline", "generate", "edit", "deliver")


def render_stage_redirect_hint(
    stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> None:
    """Suggest the recommended stage when sidebar navigation jumps ahead."""
    if snapshot is None:
        return
    recommended = snapshot.current_stage_id
    if recommended not in _STAGE_ORDER or stage_id not in _STAGE_ORDER:
        return
    if _STAGE_ORDER.index(stage_id) <= _STAGE_ORDER.index(recommended):
        return
    target = get_stage(recommended)
    st.info(f"建议先完成「{target.title}」阶段，再继续当前页面。")
    if st.button(
        f"前往{target.title}",
        key=f"flow_redirect_{stage_id}_{recommended}",
    ):
        st.switch_page(get_app_page(target.page_key))


def _stage_next_action_label(
    stage_id: str,
    snapshot: ProjectProgressSnapshot | None,
) -> str:
    nxt = next_stage(stage_id)
    if nxt is None:
        return ""
    if (
        stage_id == "materials"
        and snapshot is not None
        and snapshot.document_count <= 0
        and snapshot.evidence_availability != EvidenceAvailability.UNKNOWN
    ):
        return "暂无资料，先进入大纲 →"
    return _NEXT_ACTION_LABELS.get(stage_id, f"下一阶段：{nxt.title} →")


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
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            return "blocked"
        if (
            snapshot.evidence_availability == EvidenceAvailability.AVAILABLE
            or snapshot.document_count > 0
        ):
            return "done"
        # Concept-draft mode: allow continue, but do not show ✕.
        return "warn"

    if stage_id == "outline":
        if snapshot.outline_approved:
            return "done"
        if getattr(snapshot, "has_outline", False):
            return "warn"
        if snapshot.has_brief:
            return "current"
        return "todo"

    if stage_id == "generate":
        if snapshot.slide_count <= 0:
            return "todo"
        if snapshot.pending_count > 0:
            return "warn"
        return "done"

    if stage_id == "edit":
        if snapshot.slide_count <= 0:
            return "blocked"
        return "done" if snapshot.pptx_ready else "warn"

    if stage_id == "deliver":
        if snapshot.formal_delivery_ready:
            return "done"
        if snapshot.draft_export_ready:
            return "warn"
        return "todo"

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
            elif completion in {"warn", "current"}:
                statuses[stage.id] = "warn" if completion == "warn" else "current"
            else:
                statuses[stage.id] = "current"
        else:
            # "current" is page-relative; off-page treat as unfinished todo.
            statuses[stage.id] = "todo" if completion == "current" else completion
    return statuses


def _stage_status_hint(
    stage_id: str,
    status: str,
    snapshot: ProjectProgressSnapshot | None,
) -> str:
    if status == "warn" and stage_id == "materials":
        return "尚无完整资料，可并行澄清与补资料"
    if status == "blocked" and stage_id == "materials":
        if snapshot is None:
            return "请先创建或选择项目"
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            return "资料状态无法验证"
    if (
        status == "warn"
        and stage_id == "deliver"
        and snapshot is not None
        and snapshot.draft_export_ready
    ):
        if snapshot.evidence_availability == EvidenceAvailability.MISSING:
            return "版式已齐，但无项目资料，不可正式交付"
        if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
            return "资料状态无法验证，禁止正式交付"
        if snapshot.export_blocker_count > 0:
            return "仍有阻塞项，不可正式交付"
    return ""


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
        hint = _stage_status_hint(stage.id, statuses[stage.id], snapshot)
        label = f"{marker} {title}"
        if hint:
            escaped_hint = html.escape(hint)
            label = f'<span title="{escaped_hint}">{label}</span>'
        if stage.id == current_stage_id:
            parts.append(f"<strong>{label}</strong>")
        else:
            parts.append(label)
    render_stepper(" ─ ".join(parts))


def render_design_context_strip(project_id: UUID) -> None:
    """Persistent design identity line for product-flow chrome (Topic 07 / UI-008)."""
    try:
        from archium.domain.access import LOCAL_ACTOR_ID
        from archium.ui.session_actor import get_current_actor_id

        actor = get_current_actor_id()
        if actor and actor != LOCAL_ACTOR_ID:
            st.caption(f"当前身份：{actor}")
    except Exception:
        actor = None
    try:
        from archium.application.role_navigation import (
            resolve_role_navigation,
            role_label,
        )
        from archium.ui.session_actor import get_current_actor_id

        with unit_of_work() as uow:
            hint = resolve_role_navigation(
                uow,
                project_id,
                actor_id=get_current_actor_id(),
            )
        if hint.role is not None:
            st.caption(f"项目角色：{role_label(hint.role)}")
        if hint.message:
            st.info(hint.message)
            if hint.is_read_leaning:
                st.page_link(
                    get_app_page(hint.primary_page_key),
                    label="前往建议页面 →",
                )
    except Exception:
        from archium.logging import get_logger

        get_logger(__name__).debug(
            'design context strip page link unavailable',
            exc_info=True,
        )
    try:
        from archium.application.design_revise_persistence import (
            load_pending_design_revise,
        )
        from archium.application.process.design_process_pointer import build_design_pointer
        from archium.application.product_continue_work import (
            design_loop_open,
            page_for_unresolved_design,
        )

        with unit_of_work() as uow:
            pending = load_pending_design_revise(uow, project_id)
            pointer = build_design_pointer(uow, project_id)
            open_loop = design_loop_open(pointer)
            resume_page = page_for_unresolved_design(uow, pointer)
    except Exception:
        return

    if pending:
        st.warning("待确认：设计批判修订 Ask（刷新后仍可恢复）")
        st.page_link(
            get_app_page("concept-exploration"),
            label="打开概念探索处理 Ask →",
        )
        return

    label = (pointer.label or "").strip()
    if not label or pointer.focus in {"", "idle"}:
        return

    detail = (pointer.detail or "").strip()
    line = f"设计进程：{label}"
    if detail:
        line = f"{line} · {detail[:80]}"
    st.caption(line)
    if open_loop and resume_page:
        st.page_link(
            get_app_page(resume_page),
            label="继续概念方向 →",
        )


def render_concept_draft_banner(snapshot: ProjectProgressSnapshot | None = None) -> None:
    """Show a persistent draft-mode banner on every product-flow stage."""
    if snapshot is None:
        try:
            snapshot = load_project_progress_snapshot()
        except Exception:
            snapshot = None
    if snapshot is None:
        return
    if snapshot.evidence_availability == EvidenceAvailability.UNKNOWN:
        render_draft_mode_banner(
            title="资料状态无法验证",
            detail="正式交付已禁用，请检查数据库连接后重试",
        )
        return
    if (
        snapshot.evidence_availability == EvidenceAvailability.MISSING
        or snapshot.document_count <= 0
    ):
        render_draft_mode_banner(
            title="部分资料 · 草稿交付",
            detail="尚无足够项目证据，可继续推演与预览；正式交付需补资料",
        )


def render_stage_header(stage_id: str) -> None:
    stage = get_stage(stage_id)
    caption = stage.caption
    snapshot = None
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        snapshot = None
    if snapshot is not None:
        from archium.ui.workspace_mode_chrome import flow_stage_caption

        caption = flow_stage_caption(
            stage_id,
            snapshot.project_id,
            default=stage.caption,
            snapshot=snapshot,
        )
        render_page_header(stage.title, caption)
        from archium.ui.project_knowledge_profile import render_project_knowledge_strip

        render_project_knowledge_strip(
            snapshot.project_id,
            compact=True,
            show_known_unknown=False,
        )
        render_design_context_strip(snapshot.project_id)
        try:
            from archium.ui.components.orchestration_status import (
                render_orchestration_status,
            )

            render_orchestration_status(
                snapshot.project_id,
                key_prefix=f"flow_{stage_id}_orch",
                compact=True,
                current_page_key=stage_id,
            )
        except Exception:
            from archium.logging import get_logger

            get_logger(__name__).debug(
                'orchestration status chrome unavailable',
                exc_info=True,
            )
    else:
        render_page_header(stage.title, caption)
    render_stage_access_advisory(stage_id, snapshot)
    render_stage_redirect_hint(stage_id, snapshot)
    render_flow_stepper(stage_id)
    render_concept_draft_banner(snapshot)


def render_flow_project_context(
    *,
    allow_create: bool = False,
    key_prefix: str = "flow",
) -> UUID | None:
    """Compact current-project chrome for product-flow stages.

    Avoids repeating a full project selector on every stage when a project is
    already selected; switching stays behind an expander.
    """
    from uuid import UUID

    from archium.ui.pages.workspace import ensure_workspace_session
    from archium.ui.workspace_service import list_projects

    ensure_workspace_session()
    with unit_of_work() as uow:
        projects = list_projects(uow)
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
    from archium.ui.workspace_mode_chrome import render_flow_knowledge_context

    render_flow_knowledge_context(UUID(str(selected)), key_prefix=f"{key_prefix}_ks")
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
            select_project_context(st.session_state, picked)
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
        if (
            prev is not None
            and not primary_only
            and render_secondary_action(
                f"← 上一阶段：{prev.title}",
                key=f"stage_prev_{stage_id}",
            )
        ):
            st.switch_page(get_app_page(prev.page_key))
    with right:
        if nxt is None:
            return
        label = _stage_next_action_label(stage_id, snapshot)
        if render_primary_action(
            label,
            key=f"stage_next_{stage_id}",
            disabled=gate.has_blockers,
        ):
            st.switch_page(get_app_page(nxt.page_key))
