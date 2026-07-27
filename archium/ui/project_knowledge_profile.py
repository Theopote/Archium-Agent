"""Project knowledge profile UI — continuous spectrum, not mode selection."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.project_knowledge_display import (
    ProjectKnowledgeDisplay,
    build_project_knowledge_display,
)
from archium.domain.intent.knowledge_state import KnowledgeState


def load_project_knowledge_display(project_id: UUID) -> ProjectKnowledgeDisplay | None:
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        context = build_project_context(session, project_id)
    if context is None:
        return None
    return build_project_knowledge_display(context)


def render_ai_understanding_panel(
    project_id: UUID,
    *,
    compact: bool = False,
    show_actions: bool = True,
    key_prefix: str = "ai_understanding",
    title: str = "AI 当前理解",
) -> ProjectKnowledgeDisplay | None:
    """Architect-facing understanding panel — known / missing / next, not % dashboards."""
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        context = build_project_context(session, project_id)
        if context is None:
            return None
        display = build_project_knowledge_display(context)
        try:
            from dataclasses import replace

            from archium.application.project_knowledge_service import ProjectKnowledgeService

            gap_report = ProjectKnowledgeService(session).get_view(project_id).gap_report
            if gap_report is not None and gap_report.gaps:
                missing = tuple(
                    f"{'? [阻断] ' if gap.blocking else '? '}{gap.description}"
                    for gap in gap_report.gaps[:6]
                )
                display = replace(
                    display,
                    missing_highlights=missing,
                    blocking_unknown_count=len(gap_report.blocking_gaps),
                )
        except Exception:
            pass

    st.markdown(f"**{title}**")
    st.info(display.partner_headline or display.headline)
    if display.cognition_stale:
        st.warning(
            "认知可能过期：最近一次完整知识评估未成功。"
            "可稍后刷新知识状态。"
        )
    if not compact and display.caption:
        st.caption(display.caption)

    known_col, missing_col = st.columns(2)
    with known_col:
        st.markdown("**已知信息**")
        if display.known_highlights:
            for line in display.known_highlights[:6]:
                st.markdown(f"- {line}")
        else:
            st.caption("尚无结构化已知项 — 可从描述或资料补充。")
    with missing_col:
        st.markdown("**仍缺 / 待澄清**")
        if display.missing_highlights:
            for line in display.missing_highlights[:6]:
                st.markdown(f"- {line}")
        else:
            st.caption("暂无明确缺口。")

    if show_actions:
        st.markdown("**下一步建议**")
        render_project_knowledge_action_buttons(
            project_id,
            key_prefix=key_prefix,
            max_items=3,
        )
    elif display.suggested_actions:
        st.markdown("**下一步建议**")
        for index, action in enumerate(display.suggested_actions[:3], start=1):
            st.markdown(f"{index}. {action}")
    return display


def render_project_knowledge_strip(
    project_id: UUID,
    *,
    compact: bool = False,
    show_known_unknown: bool = True,
    show_metrics: bool = False,
) -> ProjectKnowledgeDisplay | None:
    """Primary knowledge-first chrome — use instead of workspace mode titles.

    ``show_metrics`` exposes legacy % / vector bars for diagnostics; partner UI
    keeps it off by default.
    """
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        context = build_project_context(session, project_id)
    if context is None:
        return None
    display = build_project_knowledge_display(context)

    st.info(display.partner_headline or display.headline)
    if display.cognition_stale:
        st.warning(
            "认知可能过期：最近一次完整知识评估未成功，当前显示基于事实/知识条目索引。"
            "可稍后刷新知识状态。"
        )
    if not compact:
        st.caption(display.caption)
        meta = [f"当前重心：{display.focus}"]
        if show_metrics:
            meta.append(f"把握度约 {display.confidence_pct}%")
            if display.dimension_bits:
                meta.append(" · ".join(display.dimension_bits))
        if display.claim_count:
            meta.append(f"主张 {display.claim_count}（已链接 {display.linked_claim_count}）")
        if display.knowledge_item_count:
            meta.append(f"知识条目 {display.knowledge_item_count}")
        if display.blocking_unknown_count:
            meta.append(f"阻断缺口 {display.blocking_unknown_count}")
        if meta:
            st.caption(" · ".join(meta))
        if show_metrics:
            _render_knowledge_vector_bars(display)

    if show_known_unknown:
        if compact:
            _render_known_unknown(context.knowledge_state, compact=True)
        else:
            _render_partner_known_missing(display, context.knowledge_state)
    if not compact:
        _render_assessment_reasons(context.knowledge_state)
        _render_process_board(project_id)
    return display


def _render_partner_known_missing(
    display: ProjectKnowledgeDisplay,
    state: KnowledgeState,
) -> None:
    if display.known_highlights or display.missing_highlights:
        known_col, missing_col = st.columns(2)
        with known_col:
            st.markdown("**已知信息**")
            for line in display.known_highlights[:6]:
                st.markdown(f"- {line}")
            if not display.known_highlights:
                st.caption("—")
        with missing_col:
            st.markdown("**仍缺**")
            for line in display.missing_highlights[:6]:
                st.markdown(f"- {line}")
            if not display.missing_highlights:
                st.caption("—")
        return
    _render_known_unknown(state, compact=False)


def _render_assessment_reasons(state: KnowledgeState) -> None:
    reasons = list(state.assessment_reasons or [])
    if not reasons:
        return
    with st.expander("判断依据", expanded=False):
        for reason in reasons[:5]:
            mark = {
                "support": "＋",
                "block": "−",
                "nuance": "·",
            }.get(getattr(reason.polarity, "value", ""), "·")
            st.markdown(f"- {mark} {reason.display_line()}")


def _render_knowledge_vector_bars(display: ProjectKnowledgeDisplay) -> None:
    if not display.vector_bars:
        return
    st.caption("Knowledge Vector（诊断）")
    cols = st.columns(min(4, len(display.vector_bars)))
    for index, (label, pct) in enumerate(display.vector_bars):
        with cols[index % len(cols)]:
            st.caption(f"{label} {pct}%")
            st.progress(min(1.0, max(0.0, pct / 100.0)))


def _render_process_board(project_id: UUID) -> None:
    try:
        from archium.application.process import build_project_process_board
        from archium.domain.process import design_focus_label
        from archium.infrastructure.database.session import get_session

        with get_session() as session:
            board = build_project_process_board(session, project_id)
        st.caption(f"过程板：{board.summary_line()}")
        details = []
        for pointer in (board.research, board.design, board.presentation):
            if pointer.phase.value == "idle":
                continue
            bit = pointer.label
            if pointer.kind.value == "design":
                focus_label = design_focus_label(pointer.focus)
                if focus_label:
                    bit = f"[{focus_label}] {bit}"
            if pointer.detail:
                bit = f"{bit}（{pointer.detail}）"
            details.append(bit)
        if details:
            st.caption(" · ".join(details[:3]))
    except Exception:
        return


def render_project_knowledge_action_buttons(
    project_id: UUID,
    *,
    key_prefix: str,
    max_items: int = 3,
    settings=None,
) -> None:
    """Clickable NBA buttons wired to context navigation."""
    from archium.application.context.next_action_selector import resolve_action_target
    from archium.application.context.workflow_navigation import as_session_state
    from archium.application.project_context_builder import build_project_context
    from archium.infrastructure.database.session import get_session
    from archium.ui.context_navigation import (
        dispatch_next_best_action,
        pending_fact_counts,
    )
    from archium.ui.llm_settings import get_ui_effective_settings

    with get_session() as session:
        context = build_project_context(session, project_id)
        if context is None or not context.next_actions:
            display = load_project_knowledge_display(project_id)
            if display is not None:
                render_project_knowledge_actions(display, key_prefix=key_prefix, max_items=max_items)
            return
        pending, conflicts = pending_fact_counts(session, project_id)
        actions = context.next_actions[:max_items]

    st.caption("下一步行动")
    runtime_settings = settings or get_ui_effective_settings()
    cols = st.columns(len(actions))
    for index, action in enumerate(actions):
        from archium.application.context.nba_action_executor import nba_execute_label

        target = resolve_action_target(
            action.action,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
        )
        label = nba_execute_label(
            action.action,
            has_pending_facts=bool(pending or conflicts)
            and action.action.value == "ask",
            reason=action.reason,
        ) or target.label or action.reason or action.action.value
        with cols[index]:
            if st.button(label, key=f"{key_prefix}_nba_{index}_{action.action.value}", use_container_width=True):
                from archium.application.context.nba_action_executor import NbaExecutionResult

                with get_session() as session:
                    result = dispatch_next_best_action(
                        session,
                        as_session_state(st.session_state),
                        action.action,
                        project_id=project_id,
                        settings=runtime_settings,
                    )
                if (
                    isinstance(result, NbaExecutionResult)
                    and result.stay_after_execute
                    and result.success
                ):
                    st.rerun()


def render_project_knowledge_actions(
    display: ProjectKnowledgeDisplay,
    *,
    key_prefix: str,
    max_items: int = 3,
) -> None:
    if not display.suggested_actions:
        return
    st.caption("下一步行动")
    cols = st.columns(min(max_items, len(display.suggested_actions)))
    for index, action in enumerate(display.suggested_actions[:max_items]):
        cols[index % len(cols)].markdown(f"{index + 1}. {action}")


def _render_known_unknown(state: KnowledgeState, *, compact: bool) -> None:
    counts: list[str] = []
    if state.source_count:
        counts.append(f"来源 {state.source_count}")
    if state.fact_count:
        counts.append(f"事实 {state.fact_count}")
    if state.knowledge_item_count:
        counts.append(f"知识条目 {state.knowledge_item_count}")
    if state.claims:
        linked = sum(
            1
            for claim in state.claims
            if claim.fact_id is not None or claim.knowledge_item_id is not None
        )
        counts.append(f"主张 {len(state.claims)}/{linked} 已链接")
    if counts and not compact:
        st.caption(" · ".join(counts))

    if state.claims:
        claim_bits: list[str] = []
        for claim in state.claims[:6]:
            tag = "✓" if claim.confirmed else "·"
            claim_bits.append(f"{tag}{claim.key}={claim.summary[:40]}")
        text = "；".join(claim_bits)
        if compact:
            st.caption(f"主张索引：{text}")
        else:
            st.markdown(f"**主张索引**：{text}")
    elif state.known:
        known_text = "；".join(f"{key}={value}" for key, value in list(state.known.items())[:6])
        if compact:
            st.caption(f"已知：{known_text}")
        else:
            st.markdown(f"**已知**：{known_text}")

    if state.open_unknowns:
        parts: list[str] = []
        for gap in state.open_unknowns[:6]:
            prefix = "[阻断] " if gap.blocking else ""
            parts.append(f"{prefix}{gap.description}")
        text = "；".join(parts)
        if compact:
            st.caption(f"仍缺：{text}")
        else:
            st.markdown(f"**仍缺**：{text}")
    else:
        unknowns = state.unknown or state.missing_information
        if unknowns:
            text = "；".join(unknowns[:6])
            if compact:
                st.caption(f"仍缺：{text}")
            else:
                st.markdown(f"**仍缺**：{text}")
