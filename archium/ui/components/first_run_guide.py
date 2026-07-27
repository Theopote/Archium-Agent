"""First-run progress guide — visible 3-step path for new users."""

from __future__ import annotations

import html

import streamlit as st

from archium.ui.app_navigation import get_app_page
from archium.ui.product_flow import product_flow_chain


FIRST_RUN_STEPS: tuple[tuple[str, str], ...] = (
    ("1", "描述项目"),
    ("2", "确认方向与大纲"),
    ("3", "生成并进入工作室"),
)


def render_first_run_steps(*, current_step: int = 1, compact: bool = False) -> None:
    """Render a simple 3-step onboarding strip (1-based current_step)."""
    step = max(1, min(current_step, len(FIRST_RUN_STEPS)))
    chips: list[str] = []
    for index, (num, label) in enumerate(FIRST_RUN_STEPS, start=1):
        state = "done" if index < step else ("active" if index == step else "todo")
        chips.append(
            f'<span class="first-run-step first-run-step-{state}">'
            f'<span class="first-run-step-num">{html.escape(num)}</span>'
            f"{html.escape(label)}</span>"
        )
    st.markdown(
        f'<div class="first-run-steps">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )
    if not compact:
        st.caption(f"推荐路径：{product_flow_chain()}")


def render_genesis_next_steps(*, project_id: str) -> None:
    """After genesis assessment — show step 2/3 CTAs."""
    render_first_run_steps(current_step=2, compact=True)
    st.markdown("**从这里继续**")
    cols = st.columns(2)
    with cols[0]:
        if st.button(
            "探索设计方向",
            key=f"first_run_explore_{project_id}",
            use_container_width=True,
            type="primary",
        ):
            st.switch_page(get_app_page("concept-exploration"))
    with cols[1]:
        if st.button(
            "直接整理大纲",
            key=f"first_run_outline_{project_id}",
            use_container_width=True,
        ):
            st.session_state.selected_project_id = project_id
            st.switch_page(get_app_page("outline"))
