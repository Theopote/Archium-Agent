"""Explainable Next Best Action cards for Streamlit."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import streamlit as st

from archium.application.context.nba_explainability import (
    ExplainableNbaCard,
    build_explainable_nba_card,
)
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def render_explainable_nba_card(
    card: ExplainableNbaCard,
    *,
    key: str,
    primary: bool = False,
    on_click: Callable[[], None] | None = None,
) -> bool:
    """Render one explainable card; return True if the action button was clicked."""
    with st.container(border=True):
        st.markdown(f"**建议：{card.title}**")
        st.caption(f"为什么现在做：{card.why_now}")
        if card.affects:
            st.caption("会修改 / 影响：" + "、".join(card.affects))
        st.caption(f"预计结果：{card.expected_outcome}")
        st.caption(f"可否撤销：{card.reversible_label}")
        if card.question:
            st.caption(f"待澄清：{card.question}")
        clicked = st.button(
            card.title,
            key=key,
            type="primary" if primary else "secondary",
            use_container_width=True,
        )
        if clicked and on_click is not None:
            on_click()
        return clicked


def render_explainable_nba_actions(
    actions: Sequence[NextBestAction],
    *,
    key_prefix: str,
    titles: Sequence[str] | None = None,
    on_action: Callable[[NextBestActionType], None] | None = None,
) -> NextBestActionType | None:
    """Render a vertical stack of explainable cards. Returns clicked action type."""
    clicked: NextBestActionType | None = None
    for index, action in enumerate(actions):
        title = ""
        if titles is not None and index < len(titles):
            title = titles[index]
        card = build_explainable_nba_card(action, title=title)
        action_type = action.action

        def _make_handler(chosen: NextBestActionType) -> Callable[[], None]:
            def _run() -> None:
                if on_action is not None:
                    on_action(chosen)

            return _run

        if render_explainable_nba_card(
            card,
            key=f"{key_prefix}_nba_card_{index}_{action_type.value}",
            primary=index == 0,
            on_click=_make_handler(action_type) if on_action else None,
        ):
            clicked = action_type
    return clicked
