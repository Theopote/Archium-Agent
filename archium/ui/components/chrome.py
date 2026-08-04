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


def render_stat_chips(
    items: Sequence[tuple[str, str] | tuple[str, str, Tone]],
) -> None:
    """Compact label/value strip — prefer over ``st.metric`` dashboard rows.

    Each item is ``(label, value)`` or ``(label, value, tone)``.
    """
    if not items:
        return
    chips: list[str] = []
    for item in items:
        label = html.escape(str(item[0]))
        value = html.escape(str(item[1]))
        tone: Tone = "neutral"
        if len(item) >= 3:
            candidate = item[2]
            if candidate in _STATUS_MARK:
                tone = candidate  # type: ignore[assignment]
        chips.append(
            f'<span class="archium-stat-chip archium-stat-chip-{tone}">'
            f'<span class="archium-stat-chip-label">{label}</span>'
            f'<span class="archium-stat-chip-value">{value}</span>'
            f"</span>"
        )
    st.markdown(
        f'<div class="archium-stat-chip-row">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


def render_status_chip_row(
    items: Sequence[tuple[str, Tone]],
) -> None:
    """Inline status badges in one row."""
    if not items:
        return
    parts: list[str] = []
    for label, tone in items:
        mark = _STATUS_MARK.get(tone, "○")
        safe_tone = tone if tone in _STATUS_MARK else "neutral"
        parts.append(
            f'<span class="status-chip status-chip-{safe_tone}">'
            f'<span class="status-chip-mark">{mark}</span>'
            f"{html.escape(label)}"
            f"</span>"
        )
    st.markdown(
        f'<div class="archium-status-chip-row">{"".join(parts)}</div>',
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


def render_draft_mode_banner(
    *,
    title: str = "部分资料 · 草稿交付",
    detail: str = "无项目资料，不得正式交付",
) -> None:
    """Persistent, high-visibility banner for concept-draft sessions."""
    st.markdown(
        (
            f'<div class="archium-callout archium-callout-draft">'
            f"<strong>{html.escape(title)}</strong>"
            f"{html.escape(detail)}"
            f"</div>"
        ),
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
