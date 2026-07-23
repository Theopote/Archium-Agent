"""Content adaptation controls for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.content_adaptation_heuristics import parse_content_adaptation_text
from archium.domain.content_adaptation import (
    ACTION_USER_LABELS,
    ContentAdaptationAction,
    ContentAdaptationSuggestion,
)
from archium.domain.slide_split import SlideSplitProposal
from archium.domain.visual.slide_capacity_budget import (
    CapacityStatus,
    SlideCapacityBudget,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio_service import (
    analyze_slide_content_adaptation,
    apply_slide_content_adaptation,
    estimate_slide_capacity,
    restore_slide_content_adaptation,
)
from archium.ui.visual_service import SlideVisualSnapshot

_SPLIT_PROPOSAL_KEY = "studio_slide_split_proposal"

_CAPACITY_ACTION_LABELS = {
    "proceed": "可继续布局",
    "adapt_content": "建议缩短 / 适配内容",
    "split_slide": "建议拆页",
    "blocked": "容量不可行 — 需大幅删减或换版式",
}

_CAPACITY_STATUS_HELP = {
    CapacityStatus.FITS: "内容在固定画布内舒适",
    CapacityStatus.TIGHT: "偏紧：可出候选，但必须 QA",
    CapacityStatus.OVERLOADED: "超载：禁止继续缩字，应适配或拆页",
    CapacityStatus.IMPOSSIBLE: "不可行：当前载荷无法落入固定画布",
}


def render_content_adaptation_panel(*, slide_snapshot: SlideVisualSnapshot | None) -> None:
    """Render SlideSpec content adaptation actions and layout-triggered suggestions."""
    st.markdown("**内容适配**")
    if slide_snapshot is None:
        st.caption("请选择页面后再调整内容。")
        return

    slide_id = slide_snapshot.slide.id
    _render_capacity_gauge(slide_id)
    st.caption("调整页面文字与结构；OVERLOADED 拆页需确认 Before/After 后再执行。")

    pending = st.session_state.get(_SPLIT_PROPOSAL_KEY)
    if isinstance(pending, SlideSplitProposal) and pending.source_slide_id == slide_id:
        _render_split_proposal(pending)
        st.divider()

    suggestions = _load_suggestions(slide_snapshot)
    if suggestions:
        st.markdown("**适配建议**")
        for index, suggestion in enumerate(suggestions):
            label = ACTION_USER_LABELS[suggestion.action]
            help_text = suggestion.reason
            if suggestion.requires_user_approval:
                help_text = f"{help_text}（建议人工确认）"
            if suggestion.action == ContentAdaptationAction.SPLIT_SLIDE:
                if st.button(
                    f"生成拆页提案：{label}",
                    key=f"studio_suggest_split_{slide_id}_{index}",
                    use_container_width=True,
                    help=help_text,
                ):
                    _propose_split(slide_id=slide_id)
            elif st.button(
                f"应用：{label}",
                key=f"studio_suggest_{suggestion.action.value}_{slide_id}_{index}",
                use_container_width=True,
                help=help_text,
            ):
                _run_adaptation(slide_id=slide_id, action=suggestion.action.value)
        for suggestion in suggestions[:3]:
            st.caption(f"· {suggestion.reason}")

    text = st.text_area(
        "描述内容调整",
        placeholder="例如：缩短文字、转为要点、拆分页面、突出核心信息…",
        height=80,
        key=f"studio_content_adapt_input_{slide_id}",
    )

    if st.button(
        "应用内容适配",
        use_container_width=True,
        key=f"studio_apply_content_adapt_{slide_id}",
    ):
        action = parse_content_adaptation_text(text.strip())
        if action is None:
            st.error("无法识别内容适配意图。请使用下方按钮或更明确的描述。")
        elif action == ContentAdaptationAction.SPLIT_SLIDE:
            _propose_split(slide_id=slide_id)
        else:
            _run_adaptation(slide_id=slide_id, action=action.value)

    actions = [
        ContentAdaptationAction.SHORTEN,
        ContentAdaptationAction.CONVERT_TO_BULLETS,
        ContentAdaptationAction.SPLIT_SLIDE,
        ContentAdaptationAction.PROMOTE_KEY_MESSAGE,
    ]
    cols = st.columns(2)
    for index, action in enumerate(actions):
        column = cols[index % 2]
        if column.button(
            ACTION_USER_LABELS[action],
            use_container_width=True,
            key=f"studio_content_{action.value}_{slide_id}",
        ):
            if action == ContentAdaptationAction.SPLIT_SLIDE:
                _propose_split(slide_id=slide_id)
            else:
                _run_adaptation(slide_id=slide_id, action=action.value)

    if st.button(
        "撤销内容修改",
        use_container_width=True,
        key=f"studio_undo_content_{slide_id}",
    ):
        _run_restore(slide_id=slide_id)


def _render_capacity_gauge(slide_id: UUID) -> None:
    budget = _load_capacity(slide_id)
    if budget is None:
        st.caption("容量预算：暂无 DesignSystem，无法估算固定画布容量。")
        return

    st.markdown("**固定画布容量**")
    status = budget.status
    help_text = _CAPACITY_STATUS_HELP.get(status, "")
    action_label = _CAPACITY_ACTION_LABELS.get(
        budget.recommended_action, budget.recommended_action
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("状态", status.value)
    c2.metric("容量比", f"{budget.capacity_ratio:.2f}")
    c3.metric("溢出风险", f"{budget.overflow_risk:.2f}")
    st.caption(
        f"{help_text} · 建议：{action_label} · "
        f"可用 {budget.usable_width:.2f}×{budget.usable_height:.2f} in · "
        f"文字高估 {budget.estimated_text_height:.2f} in"
        + (" · 真实字体度量" if budget.used_real_font_metrics else " · 回退度量")
    )
    if budget.drawing_min_readable_area > 0:
        st.caption(
            f"图纸可读区 ≥ {budget.drawing_min_readable_area:.2f} in² · "
            f"图注高 {budget.caption_required_height:.2f} in · "
            f"图例区 {budget.legend_required_area:.2f} in²"
        )
    if status == CapacityStatus.OVERLOADED:
        st.warning("容量超载：禁止继续缩字。请缩短内容或生成拆页提案。")
    elif status == CapacityStatus.IMPOSSIBLE:
        st.error("容量不可行：即使适配当前载荷也无法落入固定画布。")


def _load_capacity(slide_id: UUID) -> SlideCapacityBudget | None:
    try:
        with get_session() as session:
            return estimate_slide_capacity(session, slide_id)
    except WorkflowError as exc:
        st.caption(format_user_error(exc))
        return None
    except Exception:
        return None


def _render_split_proposal(proposal: SlideSplitProposal) -> None:
    st.markdown("**拆页提案 · Before / After**")
    if proposal.capacity_status:
        st.caption(f"容量状态：`{proposal.capacity_status}`")
    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("**拆分前**")
        st.write(f"**{proposal.before.title}**")
        st.caption(proposal.before.message)
        for point in proposal.before.key_points:
            st.markdown(f"- {point}")
    with after_col:
        st.markdown("**拆分后**")
        for index, page in enumerate(proposal.after, start=1):
            st.write(f"**P{index} · {page.title}**")
            st.caption(page.message)
            for point in page.key_points:
                st.markdown(f"- {point}")
            st.divider()
    if proposal.plan.validation_issues:
        for issue in proposal.plan.validation_issues:
            st.warning(issue)
    c1, c2 = st.columns(2)
    if c1.button("确认拆页", type="primary", use_container_width=True, key="studio_accept_split"):
        _accept_split(proposal)
    if c2.button("取消拆页提案", use_container_width=True, key="studio_reject_split"):
        st.session_state.pop(_SPLIT_PROPOSAL_KEY, None)
        st.info("已取消拆页提案。")
        st.rerun()


def _propose_split(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在生成拆页提案…"), get_session() as session:
            from archium.application.content_adaptation_service import ContentAdaptationService

            proposal = ContentAdaptationService(session).propose_split(slide_id)
        st.session_state[_SPLIT_PROPOSAL_KEY] = proposal
        st.success("拆页提案已生成，请确认 Before/After 后再执行。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _accept_split(proposal: SlideSplitProposal) -> None:
    try:
        with st.spinner("正在执行拆页…"), get_session() as session:
            from archium.application.content_adaptation_service import ContentAdaptationService

            result = ContentAdaptationService(session).accept_split_proposal(proposal)
        st.session_state.pop(_SPLIT_PROPOSAL_KEY, None)
        st.success(getattr(result, "message", None) or "拆页已完成。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _load_suggestions(slide_snapshot: SlideVisualSnapshot) -> list[ContentAdaptationSuggestion]:
    try:
        with get_session() as session:
            return analyze_slide_content_adaptation(
                session,
                slide_snapshot.slide.id,
                layout_report=slide_snapshot.validation,
            )
    except WorkflowError as exc:
        st.caption(format_user_error(exc))
        return []


def _run_adaptation(*, slide_id: UUID, action: str) -> None:
    try:
        with st.spinner("正在适配页面内容并更新版式…"), get_session() as session:
            result = apply_slide_content_adaptation(session, slide_id, action=action)
        message = getattr(result, "message", None) or "内容适配已完成。"
        st.success(message)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_restore(*, slide_id: UUID) -> None:
    try:
        with st.spinner("正在撤销内容修改…"), get_session() as session:
            restore_slide_content_adaptation(session, slide_id)
        st.success("已撤销一步内容修改。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
