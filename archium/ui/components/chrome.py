"""Archium UI chrome primitives — prefer these over ad-hoc markdown/columns."""

from __future__ import annotations

import html
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Literal

import streamlit as st

Tone = Literal["ok", "info", "warn", "error", "neutral"]

_STATUS_MARK = {
    "ok": "●",
    "info": "◆",
    "warn": "▲",
    "error": "■",
    "neutral": "○",
}


def render_page_header(title: str, caption: str | None = None) -> None:
    """Standard page / stage title block."""
    safe_title = html.escape(title)
    st.markdown(
        f'<div class="archium-page-header">'
        f'<h1 class="archium-page-title">{safe_title}</h1>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if caption:
        st.markdown(
            f'<p class="archium-page-caption">{html.escape(caption)}</p>',
            unsafe_allow_html=True,
        )


def render_section_label(label: str) -> None:
    st.markdown(
        f'<div class="section-label">{html.escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_status_badge(label: str, *, tone: Tone = "neutral") -> None:
    mark = _STATUS_MARK.get(tone, "○")
    st.markdown(
        f'<span class="status-chip status-chip-{tone}">'
        f'<span class="status-chip-mark">{mark}</span>'
        f"{html.escape(label)}"
        f"</span>",
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str,
    body: str,
    *,
    primary_label: str | None = None,
    primary_key: str = "empty_primary",
    on_primary: Callable[[], None] | None = None,
) -> bool:
    """Centered empty / onboarding block. Returns True if primary was clicked."""
    st.markdown(
        f'<div class="archium-empty">'
        f'<div class="archium-empty-title">{html.escape(title)}</div>'
        f'<p class="archium-empty-body">{html.escape(body)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if primary_label is None:
        return False
    clicked = st.button(
        primary_label,
        type="primary",
        key=primary_key,
        use_container_width=False,
    )
    if clicked and on_primary is not None:
        on_primary()
    return clicked


def render_primary_action(
    label: str,
    *,
    key: str,
    disabled: bool = False,
    use_container_width: bool = True,
) -> bool:
    return st.button(
        label,
        type="primary",
        key=key,
        disabled=disabled,
        use_container_width=use_container_width,
    )


def render_secondary_action(
    label: str,
    *,
    key: str,
    disabled: bool = False,
    use_container_width: bool = True,
) -> bool:
    return st.button(
        label,
        type="secondary",
        key=key,
        disabled=disabled,
        use_container_width=use_container_width,
    )


def render_danger_action(
    label: str,
    *,
    key: str,
    disabled: bool = False,
    use_container_width: bool = True,
) -> bool:
    """Danger intent — styled via CSS class on a secondary button wrapper."""
    st.markdown('<div class="archium-btn-danger">', unsafe_allow_html=True)
    clicked = st.button(
        label,
        type="secondary",
        key=key,
        disabled=disabled,
        use_container_width=use_container_width,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def render_warning_callout(message: str) -> None:
    st.markdown(
        f'<div class="archium-callout archium-callout-warn">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_info_callout(message: str) -> None:
    st.markdown(
        f'<div class="archium-callout archium-callout-info">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_error_callout(message: str) -> None:
    st.markdown(
        f'<div class="archium-callout archium-callout-error">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_inspector_section(title: str, caption: str | None = None) -> None:
    st.markdown(
        f'<div class="archium-inspector-section">'
        f'<div class="archium-inspector-title">{html.escape(title)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if caption:
        st.caption(caption)


@contextmanager
def render_panel(
    title: str | None = None,
    *,
    bordered: bool = True,
) -> Iterator[None]:
    """Bordered content panel. Prefer this over ad-hoc containers."""
    with st.container(border=bordered):
        if title:
            st.markdown(
                f'<div class="archium-panel-title">{html.escape(title)}</div>',
                unsafe_allow_html=True,
            )
        yield


def render_toolbar(
    actions: Sequence[tuple[str, str]],
    *,
    key_prefix: str,
    primary_index: int | None = 0,
) -> str | None:
    """Horizontal action strip. ``actions`` are (label, action_id). Returns clicked id."""
    if not actions:
        return None
    st.markdown('<div class="archium-toolbar">', unsafe_allow_html=True)
    cols = st.columns(len(actions))
    clicked: str | None = None
    for index, ((label, action_id), col) in enumerate(zip(actions, cols, strict=True)):
        with col:
            is_primary = primary_index is not None and index == primary_index
            if st.button(
                label,
                type="primary" if is_primary else "secondary",
                key=f"{key_prefix}_{action_id}",
                use_container_width=True,
            ):
                clicked = action_id
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def render_stepper(parts_html: str) -> None:
    """Render pre-built stepper markup (markers already escaped by caller)."""
    st.markdown(
        f'<div class="archium-stepper">{parts_html}</div>',
        unsafe_allow_html=True,
    )
