"""Workstream selection panel — checkable capability cards."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.enums import EffortLevel, Priority
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.planning_service import set_workstream_selected

PRIORITY_LABELS = {
    Priority.CRITICAL: "关键",
    Priority.HIGH: "高",
    Priority.MEDIUM: "中",
    Priority.LOW: "低",
}

EFFORT_LABELS = {
    EffortLevel.MINIMAL: "极低",
    EffortLevel.LOW: "低",
    EffortLevel.MEDIUM: "中",
    EffortLevel.HIGH: "高",
    EffortLevel.EXTENSIVE: "很高",
}


def render_workstream_panel(
    workstreams: list[Workstream],
    *,
    key_prefix: str = "ws",
) -> None:
    st.markdown("#### 工作路径")
    st.caption("勾选本轮需要推进的能力路径。名称不会自动变成汇报章节大纲。")

    if not workstreams:
        st.info("尚未生成工作路径。请先完成关键问题并继续规划。")
        return

    by_id = {ws.id: ws for ws in workstreams}
    for workstream in workstreams:
        with st.container(border=True):
            header = f"{workstream.title} · `{workstream.workstream_type.value}`"
            if workstream.recommended:
                header += " · 推荐"
            selected = st.checkbox(
                header,
                value=workstream.selected,
                key=f"{key_prefix}_sel_{workstream.id}",
            )
            st.write(workstream.objective)
            meta1, meta2, meta3 = st.columns(3)
            meta1.caption(
                f"优先级：{PRIORITY_LABELS.get(workstream.priority, workstream.priority.value)}"
            )
            meta2.caption(
                f"工作量：{EFFORT_LABELS.get(workstream.effort_level, workstream.effort_level.value)}"
            )
            if workstream.dependencies:
                deps = [
                    by_id[dep_id].title
                    for dep_id in workstream.dependencies
                    if dep_id in by_id
                ]
                meta3.caption("依赖：" + ("、".join(deps) if deps else "—"))
            else:
                meta3.caption("依赖：—")

            if workstream.inputs_required:
                st.caption("需要的资料：" + "、".join(workstream.inputs_required))
            if workstream.outputs:
                st.caption("预计输出：" + "、".join(workstream.outputs))
            if workstream.questions:
                with st.expander("相关问题", expanded=False):
                    for item in workstream.questions:
                        st.write(f"- {item}")

            if selected != workstream.selected:
                _toggle(workstream.id, selected)


def _toggle(workstream_id: UUID, selected: bool) -> None:
    try:
        with get_session() as session:
            set_workstream_selected(session, workstream_id, selected)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
