"""Multi-column ConceptDirection compare cards — architect scheme review, not stacked expanders."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import streamlit as st

from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus
from archium.ui.components.concept_direction_details import render_concept_direction_details

_STATUS_BADGE = {
    ConceptDirectionStatus.SELECTED: "已选中",
    ConceptDirectionStatus.DRAFT: "草稿",
    ConceptDirectionStatus.ARCHIVED: "已归档",
}


def _clip(text: str, *, limit: int = 120) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def compare_card_fields(direction: ConceptDirection) -> dict[str, str]:
    """Extract architect-facing compare fields (pure, for tests + UI)."""
    core = direction.theme.strip() or _clip(direction.summary, limit=90)
    spatial = direction.spatial_strategy.strip() or direction.spatial_idea.strip()
    if not spatial and direction.spatial_intent is not None:
        spatial = (
            direction.spatial_intent.spatial_relationships.strip()
            or direction.spatial_intent.landscape_relation.strip()
        )
    form = direction.formal_language.strip()
    if not form and direction.design_rules:
        form = next(
            (
                rule.formal_translation.strip()
                for rule in direction.design_rules
                if rule.formal_translation.strip()
            ),
            "",
        )
    advantage = direction.differentiator.strip() or direction.experience_focus.strip()
    risks = "；".join(item.strip() for item in direction.risks[:2] if item.strip())
    suited = direction.experience_focus.strip()
    if not suited and direction.open_questions:
        suited = "待澄清：" + _clip(direction.open_questions[0], limit=60)
    return {
        "title": direction.title,
        "badge": _STATUS_BADGE.get(direction.status, direction.status.value),
        "core": core,
        "spatial": spatial,
        "form": form,
        "advantage": advantage,
        "risks": risks,
        "suited": suited,
    }


def render_concept_direction_compare(
    directions: Sequence[ConceptDirection],
    *,
    key_prefix: str,
    allow_select: bool = True,
    allow_archive: bool = False,
    show_details_expander: bool = True,
) -> tuple[str, UUID] | None:
    """Render 2–3 column compare cards.

    Returns ``("select"|"archive", direction_id)`` when a card action is clicked.
    """
    visible = [
        item
        for item in directions
        if item.status != ConceptDirectionStatus.ARCHIVED or allow_archive
    ]
    if not visible:
        st.caption("尚无可比较的概念方向。")
        return None

    st.markdown("**方案比较**")
    st.caption("并排列出核心理念 · 空间策略 · 形式语言 · 优势与风险，便于像评标一样选择。")

    cols = st.columns(min(3, len(visible)))
    clicked: tuple[str, UUID] | None = None
    for index, direction in enumerate(visible[:3]):
        fields = compare_card_fields(direction)
        with cols[index % len(cols)]:
            selected = direction.status == ConceptDirectionStatus.SELECTED
            title_prefix = "● " if selected else ""
            st.markdown(f"#### {title_prefix}{fields['title']}")
            st.caption(fields["badge"])
            if fields["core"]:
                st.markdown(f"**核心理念**  \n{_clip(fields['core'], limit=140)}")
            if fields["spatial"]:
                st.markdown(f"**空间策略**  \n{_clip(fields['spatial'], limit=140)}")
            if fields["form"]:
                st.markdown(f"**形式语言**  \n{_clip(fields['form'], limit=100)}")
            if fields["advantage"]:
                st.markdown(f"**优势**  \n{_clip(fields['advantage'], limit=100)}")
            if fields["risks"]:
                st.markdown(f"**风险**  \n{_clip(fields['risks'], limit=100)}")
            if fields["suited"]:
                st.markdown(f"**适合场景**  \n{_clip(fields['suited'], limit=100)}")

            if allow_select and direction.status != ConceptDirectionStatus.SELECTED:
                if st.button(
                    "选择此方向",
                    key=f"{key_prefix}_cmp_select_{direction.id}",
                    type="primary",
                    use_container_width=True,
                ):
                    clicked = ("select", direction.id)
            elif selected:
                st.success("当前方向")

            if allow_archive and direction.status == ConceptDirectionStatus.DRAFT:
                if st.button(
                    "归档",
                    key=f"{key_prefix}_cmp_archive_{direction.id}",
                    use_container_width=True,
                ):
                    clicked = ("archive", direction.id)

            if show_details_expander:
                with st.expander("查看完整详情", expanded=False):
                    render_concept_direction_details(direction)

    if len(visible) > 3:
        st.caption(f"另有 {len(visible) - 3} 个方向未并排显示，可在详情中查看。")
        for direction in visible[3:]:
            badge = _STATUS_BADGE.get(direction.status, direction.status.value)
            with st.expander(f"{direction.title} · {badge}", expanded=False):
                render_concept_direction_details(direction)
                if allow_select and direction.status != ConceptDirectionStatus.SELECTED:
                    if st.button(
                        "选择此方向",
                        key=f"{key_prefix}_cmp_select_extra_{direction.id}",
                        use_container_width=True,
                    ):
                        clicked = ("select", direction.id)

    return clicked
