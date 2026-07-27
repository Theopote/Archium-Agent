"""Element intent panel — role-aware suggestions when a canvas element is selected."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.ui.studio.design_assistant_panel import open_modify_with_prompt
from archium.ui.studio.element_labels import CONTENT_TYPE_LABELS, ROLE_LABELS
from archium.ui.visual_service import SlideVisualSnapshot


@dataclass(frozen=True)
class ElementIntentAction:
    label: str
    prompt: str
    reason: str


def _page_area(plan: LayoutPlan) -> float:
    return max(plan.page_width * plan.page_height, 1.0)


def _element_area_ratio(element: LayoutElement, plan: LayoutPlan) -> float:
    return (element.width * element.height) / _page_area(plan)


def _resolve_selected_element(
    slide_snapshot: SlideVisualSnapshot,
) -> LayoutElement | None:
    plan = slide_snapshot.layout_plan
    if plan is None:
        return None
    raw = st.session_state.get("studio_selected_element_id")
    if not isinstance(raw, str) or not raw:
        selected_ids = st.session_state.get("studio_selected_element_ids") or []
        if selected_ids:
            raw = str(selected_ids[0])
        else:
            return None
    try:
        element_id = str(raw)
    except Exception:
        return None
    return plan.element_by_id(element_id)


def build_element_intent_actions(
    slide_snapshot: SlideVisualSnapshot,
    element: LayoutElement,
) -> list[ElementIntentAction]:
    """Deterministic, architect-facing actions for the selected layout element."""
    plan = slide_snapshot.layout_plan
    if plan is None:
        return []

    actions: list[ElementIntentAction] = []
    role = element.role
    role_label = ROLE_LABELS.get(role, role.value)
    area_ratio = _element_area_ratio(element, plan)
    text_len = len((element.text_content or "").strip())

    validation = slide_snapshot.validation
    if validation is not None:
        for issue in validation.issues:
            if element.id not in issue.element_ids:
                continue
            suggestion = (issue.suggestion or issue.message or "").strip()
            if not suggestion:
                continue
            actions.append(
                ElementIntentAction(
                    label="修复此元素",
                    prompt=f"针对「{role_label}」：{suggestion}",
                    reason=issue.message,
                )
            )

    if role in {LayoutElementRole.HERO_VISUAL, LayoutElementRole.SUPPORTING_VISUAL}:
        if area_ratio < 0.22:
            actions.append(
                ElementIntentAction(
                    label="扩大 15%",
                    prompt=f"将选中的{role_label}放大约 15%，增强页面视觉中心",
                    reason="当前主视觉占比偏小，页面视觉中心不足",
                )
            )
        if element.content_type == LayoutContentType.DRAWING and area_ratio < 0.35:
            actions.append(
                ElementIntentAction(
                    label="提高可读性",
                    prompt="放大选中的图纸元素，确保标注与线型可读",
                    reason="图纸区域偏小，可能影响汇报可读性",
                )
            )

    if role in {
        LayoutElementRole.TITLE,
        LayoutElementRole.SUBTITLE,
        LayoutElementRole.LEAD_STATEMENT,
    }:
        if text_len > 48:
            actions.append(
                ElementIntentAction(
                    label="压缩标题",
                    prompt="缩短选中标题，保留一句有力主张",
                    reason="标题偏长，上屏力量不足",
                )
            )
        elif text_len > 0 and text_len <= 18 and role == LayoutElementRole.TITLE:
            actions.append(
                ElementIntentAction(
                    label="升级为概念标题",
                    prompt="将选中标题强化为建筑概念标题，增强气势与层级",
                    reason="标题较短，可升级为概念陈述",
                )
            )

    if role == LayoutElementRole.BODY_TEXT:
        if text_len > 180:
            actions.append(
                ElementIntentAction(
                    label="减少正文",
                    prompt="缩短选中正文，保留 2–3 个关键要点",
                    reason="正文过多，信息层级不够清晰",
                )
            )

    if role == LayoutElementRole.CAPTION and text_len > 80:
        actions.append(
            ElementIntentAction(
                label="精简图注",
                prompt="压缩选中图注，保留图解关键信息",
                reason="图注偏长，易分散读图注意力",
            )
        )

    return _dedupe_actions(actions)[:5]


def _dedupe_actions(items: list[ElementIntentAction]) -> list[ElementIntentAction]:
    seen: set[str] = set()
    unique: list[ElementIntentAction] = []
    for item in items:
        key = item.prompt.strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def render_element_intent_panel(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
) -> bool:
    """Render selected-element intent block. Returns True when an element is selected."""
    if slide_snapshot is None:
        return False

    element = _resolve_selected_element(slide_snapshot)
    if element is None:
        return False

    plan = slide_snapshot.layout_plan
    role_label = ROLE_LABELS.get(element.role, element.role.value)
    type_label = CONTENT_TYPE_LABELS.get(element.content_type, element.content_type.value)
    st.markdown(f"**选中：{role_label}**")
    st.caption(f"类型 · {type_label} · `{element.id}`")
    if element.text_content and element.text_content.strip():
        preview = element.text_content.strip()
        st.caption(f"内容 · {preview[:80]}{'…' if len(preview) > 80 else ''}")

    actions = build_element_intent_actions(slide_snapshot, element)
    if actions:
        st.markdown("**建议**")
        for index, action in enumerate(actions):
            st.caption(action.reason)
            if st.button(
                action.label,
                key=f"studio_elem_intent_{slide_snapshot.slide.id}_{element.id}_{index}",
                use_container_width=True,
            ):
                open_modify_with_prompt(slide_snapshot.slide.id, action.prompt)
                st.rerun()
    else:
        st.caption("此元素当前无强制修改建议。")

    return True
