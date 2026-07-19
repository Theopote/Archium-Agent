"""Streamlit panel for per-slide VisualIntent / LayoutPlan review."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.visual.layout import LayoutPlan
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.layout_family_ui import (
    FAMILY_LABELS,
    format_layout_family_label,
    layout_family_availability_status,
    layout_family_implemented,
)
from archium.ui.visual_service import (
    SlideVisualSnapshot,
    replan_slide,
    select_layout_candidate,
)

# Backward-compatible re-export for modules that imported labels from here.
__all__ = ["FAMILY_LABELS", "render_slide_visual_panel"]

PRESET_BUTTONS = [
    ("reduce_text", "减少文字"),
    ("enlarge_hero", "放大主图"),
    ("more_whitespace", "增加留白"),
    ("drawing_focus", "切换到图纸优先"),
]


def render_slide_visual_panel(*, snapshot: SlideVisualSnapshot) -> None:
    """Render one slide's visual intent, current layout, candidates, and actions."""
    slide = snapshot.slide
    intent = snapshot.visual_intent
    plan = snapshot.layout_plan

    st.markdown(f"#### P{slide.order + 1} · {slide.title}")
    st.caption(slide.message)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**视觉意图**")
        if intent is None:
            st.caption("尚未生成 VisualIntent。请先运行视觉编排。")
        else:
            st.write(f"沟通目标：{intent.communication_goal}")
            st.write(f"受众带走：{intent.audience_takeaway}")
            st.write(f"视觉优先级：{intent.visual_priority}")
            st.write(f"主导内容：`{intent.dominant_content_type.value}`")
            st.write(f"密度：`{intent.density_level.value}`")
            st.write(f"连续角色：`{intent.continuity_role.value}`")
            families = ", ".join(
                format_layout_family_label(family)
                for family in intent.preferred_layout_families
            )
            st.write(f"推荐版式族：{families or '—'}")
            st.write(f"阅读顺序：{' → '.join(intent.reading_order) or '—'}")
            if intent.hero_asset_id:
                st.write(f"主资产：`{str(intent.hero_asset_id)[:8]}…`")
            if intent.supporting_asset_ids:
                st.write(f"辅助资产：{len(intent.supporting_asset_ids)} 个")

    with col2:
        st.markdown("**当前版式**")
        if plan is None:
            st.caption("尚未生成 LayoutPlan。")
        else:
            st.write(f"版式族：{format_layout_family_label(plan.layout_family)}")
            if not layout_family_implemented(plan.layout_family):
                st.caption("该版式族尚未实现 generator，当前页面可能无法正确导出。")
            st.write(f"变体：`{plan.layout_variant}`")
            st.write(f"元素数：{len(plan.elements)}")
            st.write(f"留白率：{plan.whitespace_ratio:.0%}")
            st.write(f"校验状态：`{plan.validation_status.value}`")
            if snapshot.validation is not None:
                score = snapshot.validation.score
                valid = snapshot.validation.valid
                st.write(
                    f"版式质量评分：{score:.2f} · {'通过' if valid else '需修复'}"
                )
                st.caption("Layout Quality Score（几何/规则）· 非完整视觉质量")
                if snapshot.validation.issues:
                    with st.expander("校验问题", expanded=not valid):
                        for issue in snapshot.validation.issues[:8]:
                            st.write(
                                f"- `{issue.rule_code}` · {issue.severity.value} · {issue.message}"
                            )
            if snapshot.visual_critic is not None:
                critic = snapshot.visual_critic
                total = critic.get("total_score")
                score_label = (
                    f"{total:.2f}" if isinstance(total, (int, float)) else "—"
                )
                st.write(f"视觉质量（Critic）：{score_label}")
                st.caption("Visual Quality · 只读启发式，不自动修复")
                findings = list(critic.get("findings") or [])
                if findings:
                    with st.expander("Visual Critic 发现", expanded=False):
                        for item in findings[:8]:
                            st.write(
                                f"- `{item.get('rule_code')}` · "
                                f"{item.get('severity')} · {item.get('message')}"
                            )
            if snapshot.preview_image:
                st.image(snapshot.preview_image, use_container_width=True)

    _render_candidates(snapshot)
    _render_actions(snapshot)


def _render_candidates(snapshot: SlideVisualSnapshot) -> None:
    candidates = snapshot.candidates
    if not candidates:
        return
    st.markdown("**候选版式**")
    current_id = snapshot.layout_plan.id if snapshot.layout_plan else None
    rows = []
    selectable: dict[str, LayoutPlan] = {}
    for plan in candidates:
        rows.append(
            {
                "id": str(plan.id),
                "当前": "✓" if plan.id == current_id else "",
                "版式族": format_layout_family_label(plan.layout_family, show_availability=False),
                "可用性": layout_family_availability_status(plan.layout_family),
                "变体": plan.layout_variant,
                "元素": len(plan.elements),
                "留白": f"{plan.whitespace_ratio:.0%}",
                "状态": plan.validation_status.value,
            }
        )
        if layout_family_implemented(plan.layout_family):
            selectable[str(plan.id)] = plan
    st.dataframe(rows, use_container_width=True, hide_index=True)

    unimplemented_count = len(candidates) - len(selectable)
    if unimplemented_count:
        st.caption(
            f"{unimplemented_count} 个候选属于「即将支持」版式族，已从可选列表中隐藏。"
        )

    if not selectable:
        st.warning("当前候选版式均尚未实现 generator，暂不可切换。请尝试其他重新排版方式。")
        return

    selected = st.selectbox(
        "选择候选版式",
        options=list(selectable.keys()),
        format_func=lambda value: (
            f"{format_layout_family_label(selectable[value].layout_family, show_availability=False)}"
            f" · {selectable[value].layout_variant}"
            f"{'（当前）' if selectable[value].id == current_id else ''}"
        ),
        key=f"candidate_select_{snapshot.slide.id}",
    )
    if st.button("选择此版式", key=f"select_plan_{snapshot.slide.id}", use_container_width=True):
        try:
            with get_session() as session:
                select_layout_candidate(
                    session,
                    slide_id=snapshot.slide.id,
                    layout_plan_id=UUID(selected),
                )
            st.success("已切换版式。")
            st.rerun()
        except Exception as exc:
            st.error(format_user_error(exc))


def _render_actions(snapshot: SlideVisualSnapshot) -> None:
    st.markdown("**重新排版**")
    cols = st.columns(len(PRESET_BUTTONS) + 1)
    if cols[0].button("生成候选 / 重新排版", key=f"replan_{snapshot.slide.id}", use_container_width=True):
        _run_replan(snapshot.slide.id, preset=None)
    for index, (preset, label) in enumerate(PRESET_BUTTONS, start=1):
        if cols[index].button(label, key=f"preset_{preset}_{snapshot.slide.id}", use_container_width=True):
            _run_replan(snapshot.slide.id, preset=preset)


def _run_replan(slide_id: UUID, *, preset: str | None) -> None:
    try:
        with get_session() as session:
            replan_slide(session, slide_id=slide_id, preset=preset, candidate_count=3)
        st.success("已重新生成候选版式。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))
