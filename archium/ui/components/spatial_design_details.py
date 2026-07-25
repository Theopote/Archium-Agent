"""Render SpatialIntent / DesignRule / DesignDecision in Streamlit."""

from __future__ import annotations

import streamlit as st

from archium.domain.spatial_design import DesignDecision, DesignRule, SpatialIntent


def render_spatial_intent(
    intent: SpatialIntent | None,
    *,
    expanded: bool = True,
    title: str = "空间意图",
) -> None:
    if intent is None or intent.is_empty():
        return
    with st.expander(title, expanded=expanded):
        st.caption("概念如何落成空间关系，而非口号。")
        if intent.landscape_relation.strip():
            st.markdown(f"**景观关系**：{intent.landscape_relation.strip()}")
        if intent.spatial_relationships.strip():
            st.markdown(f"**空间关系**：{intent.spatial_relationships.strip()}")
        if intent.movement_experience.strip():
            st.markdown(f"**动线体验**：{intent.movement_experience.strip()}")
        if intent.public_private_structure.strip():
            st.markdown(f"**公私结构**：{intent.public_private_structure.strip()}")
        if intent.light_strategy.strip():
            st.markdown(f"**光策略**：{intent.light_strategy.strip()}")


def render_design_rules(
    rules: list[DesignRule] | None,
    *,
    expanded: bool = True,
    title: str = "设计规则",
    limit: int = 8,
) -> None:
    items = [rule for rule in (rules or []) if not rule.is_empty()]
    if not items:
        return
    with st.expander(f"{title}（{len(items)}）", expanded=expanded):
        st.caption("原则 → 空间翻译 → 形式翻译 → 评价方式。")
        for index, rule in enumerate(items[:limit], start=1):
            principle = rule.principle.strip() or f"规则 {index}"
            st.markdown(f"**{index}. {principle}**")
            if rule.spatial_translation.strip():
                st.markdown(f"- 空间：{rule.spatial_translation.strip()}")
            if rule.formal_translation.strip():
                st.markdown(f"- 形式：{rule.formal_translation.strip()}")
            if rule.evaluation_method.strip():
                st.markdown(f"- 评价：{rule.evaluation_method.strip()}")
            if rule.confidence > 0:
                st.caption(f"把握度约 {int(round(rule.confidence * 100))}%")


def render_spatial_design_layer(
    *,
    spatial_intent: SpatialIntent | None = None,
    design_rules: list[DesignRule] | None = None,
    expanded: bool = True,
) -> None:
    """Convenience: spatial intent + rules together."""
    render_spatial_intent(spatial_intent, expanded=expanded)
    render_design_rules(design_rules, expanded=expanded)


def render_design_decision(
    decision: DesignDecision | dict[str, object] | None,
    *,
    expanded: bool = False,
    title: str = "设计决策",
) -> None:
    parsed = _coerce_design_decision(decision)
    if parsed is None or parsed.is_empty():
        return
    with st.expander(title, expanded=expanded):
        if parsed.decision.strip():
            st.markdown(f"**决策**：{parsed.decision.strip()}")
        if parsed.chosen.strip():
            st.markdown(f"**选定**：{parsed.chosen.strip()}")
        if parsed.alternatives:
            st.markdown("**备选**")
            for item in parsed.alternatives:
                if str(item).strip():
                    st.markdown(f"- {item}")
        if parsed.reason.strip():
            st.markdown(f"**原因**：{parsed.reason.strip()}")
        if parsed.evidence:
            st.markdown("**证据**")
            for item in parsed.evidence:
                if str(item).strip():
                    st.markdown(f"- {item}")
        if parsed.impact.strip():
            st.markdown(f"**影响**：{parsed.impact.strip()}")
        if parsed.direction_title.strip():
            st.caption(f"方向：{parsed.direction_title.strip()}")


def render_spatial_intent_from_snapshot(
    snapshot: dict[str, object] | None,
    *,
    expanded: bool = False,
) -> None:
    if not snapshot:
        return
    spatial = _coerce_spatial_intent(snapshot.get("spatial_intent"))
    rules_raw = snapshot.get("design_rules")
    rules: list[DesignRule] = []
    if isinstance(rules_raw, list):
        for item in rules_raw:
            rule = _coerce_design_rule(item)
            if rule is not None and not rule.is_empty():
                rules.append(rule)
    render_spatial_intent(spatial, expanded=expanded)
    render_design_rules(rules, expanded=expanded)


def _coerce_spatial_intent(value: object) -> SpatialIntent | None:
    if value is None:
        return None
    if isinstance(value, SpatialIntent):
        return value
    if isinstance(value, dict):
        try:
            return SpatialIntent.model_validate(value)
        except Exception:
            return None
    return None


def _coerce_design_rule(value: object) -> DesignRule | None:
    if value is None:
        return None
    if isinstance(value, DesignRule):
        return value
    if isinstance(value, dict):
        try:
            return DesignRule.model_validate(value)
        except Exception:
            return None
    return None


def _coerce_design_decision(
    value: DesignDecision | dict[str, object] | None,
) -> DesignDecision | None:
    if value is None:
        return None
    if isinstance(value, DesignDecision):
        return value
    if isinstance(value, dict):
        try:
            return DesignDecision.model_validate(value)
        except Exception:
            return None
    return None
