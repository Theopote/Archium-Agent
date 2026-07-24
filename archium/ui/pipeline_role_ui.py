"""Streamlit helpers for PipelineRole labels (UI only)."""

from __future__ import annotations

import streamlit as st

from archium.domain.enums import PipelineRole
from archium.domain.pipeline_role_mapping import (
    pipeline_role_label,
    to_product_agent_role,
)


def role_caption(*roles: PipelineRole, show_internal: bool = False) -> None:
    """Show a one-line logical-role hint above an action.

    By default collapses Architecture/Composition/Layout onto the product
    **Visual** seat so the UI does not look like extra Agents.
    """
    if not roles:
        return
    display = (
        roles
        if show_internal
        else tuple(dict.fromkeys(to_product_agent_role(role) for role in roles))
    )
    text = " · ".join(pipeline_role_label(role) for role in display)
    st.caption(f"逻辑角色：{text}")


def role_button_label(label: str, *roles: PipelineRole, show_internal: bool = False) -> str:
    """Append product-seat tag to button text for quick scan."""
    if not roles:
        return label
    display = (
        roles
        if show_internal
        else tuple(dict.fromkeys(to_product_agent_role(role) for role in roles))
    )
    tags = "/".join(role.value for role in display)
    return f"{label} 〔{tags}〕"
