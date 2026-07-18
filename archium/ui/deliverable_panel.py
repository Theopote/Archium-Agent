"""Deliverable selection panel."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.planning_service import set_deliverable_selected


def render_deliverable_panel(
    plan: DeliverablePlan | None,
    *,
    workstreams: list[Workstream] | None = None,
    key_prefix: str = "del",
) -> None:
    st.markdown("#### 成果选择")
    if plan is None or not plan.deliverables:
        st.info("尚未生成成果计划。请先确认工作路径并继续。")
        return

    st.caption(f"计划版本 v{plan.version} · 状态 {plan.approval_status.value}")
    by_id = {ws.id: ws for ws in (workstreams or [])}

    for item in plan.deliverables:
        with st.container(border=True):
            label = f"{item.title} · `{item.deliverable_type.value}`"
            if item.required:
                label += " · 必要"
            if item.notes and "不建议" in item.notes:
                label += " · 不建议"

            disabled = item.required and item.selected
            selected = st.checkbox(
                label,
                value=item.selected,
                key=f"{key_prefix}_sel_{item.id}",
                disabled=disabled,
            )
            st.write(item.purpose)
            c1, c2, c3 = st.columns(3)
            c1.caption(f"服务对象：{item.audience or '—'}")
            c2.caption(f"预计篇幅：{item.expected_length or '—'}")
            c3.caption(f"格式：{item.format}")
            if item.content_scope:
                st.caption("内容范围：" + "、".join(item.content_scope))
            sources = _source_labels(item, by_id)
            if sources:
                st.caption("来源工作路径：" + "、".join(sources))
            if item.notes:
                st.caption(item.notes)

            if not disabled and selected != item.selected:
                _toggle(plan.id, item.id, selected)


def _source_labels(item: PlannedDeliverable, by_id: dict[UUID, Workstream]) -> list[str]:
    labels: list[str] = []
    for ws_id in item.source_workstream_ids:
        ws = by_id.get(ws_id)
        if ws is not None:
            labels.append(ws.title)
    return labels


def _toggle(plan_id: UUID, deliverable_id: str, selected: bool) -> None:
    try:
        with get_session() as session:
            set_deliverable_selected(session, plan_id, deliverable_id, selected)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
