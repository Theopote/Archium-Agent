"""Render DesignReflection in Streamlit."""

from __future__ import annotations

import streamlit as st

from archium.domain.design_reflection import DesignReflection


def render_design_reflection(
    reflection: DesignReflection | dict[str, object] | None,
    *,
    expanded: bool = False,
    title: str = "设计反思",
) -> None:
    parsed = _coerce(reflection)
    if parsed is None or parsed.is_empty():
        return
    with st.expander(title, expanded=expanded):
        if parsed.why.strip():
            st.markdown(f"**为何**：{parsed.why.strip()}")
        for label, items in (
            ("未验证假设", parsed.unverified_assumptions),
            ("主要风险", parsed.top_risks),
            ("下一步调整", parsed.next_adjustments),
        ):
            clean = [str(item).strip() for item in items if str(item).strip()]
            if not clean:
                continue
            st.markdown(f"**{label}**")
            for item in clean[:6]:
                st.markdown(f"- {item}")
        if parsed.source.strip():
            st.caption(f"来源：{parsed.source.strip()}")


def _coerce(
    value: DesignReflection | dict[str, object] | None,
) -> DesignReflection | None:
    if value is None:
        return None
    if isinstance(value, DesignReflection):
        return value
    if isinstance(value, dict):
        try:
            return DesignReflection.model_validate(value)
        except Exception:
            return None
    return None
