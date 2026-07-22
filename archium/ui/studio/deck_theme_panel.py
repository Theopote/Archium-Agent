"""Deck-wide Design Token controls with ThemeChangeProposal review."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.visual.deck_theme_apply import deck_theme_tokens_from_design_system
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens, IconStyleToken, PageDensityToken
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.theme_change_proposal import ThemeChangeProposal, ThemeProposalStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio_service import (
    accept_theme_proposal,
    create_theme_proposal,
    get_active_theme_proposal,
    load_presentation_design_system,
    reject_theme_proposal,
)
from archium.ui.visual_service import SlideVisualSnapshot

_THEME_PROPOSAL_KEY = "studio_active_theme_proposal"


def _store_theme_proposal(proposal: ThemeChangeProposal) -> None:
    st.session_state[_THEME_PROPOSAL_KEY] = proposal


def _get_stored_theme_proposal(presentation_id: UUID) -> ThemeChangeProposal | None:
    stored = st.session_state.get(_THEME_PROPOSAL_KEY)
    if isinstance(stored, ThemeChangeProposal) and stored.presentation_id == presentation_id:
        return stored
    return None


def render_deck_theme_panel(
    *,
    presentation_id: UUID,
    slide_snapshot: SlideVisualSnapshot | None,
) -> None:
    """Token form → ThemeChangeProposal → accept/reject (never silent CSS override)."""
    st.markdown("**全稿风格**")
    st.caption(
        "修改 Token 只生成 ThemeChangeProposal，不会静默覆盖正式 DesignSystem。"
        "接受后切换 DesignSystem 指针并按 Token 引用重解析 Scene，"
        "不会把主题颜色批量写死进每个节点的 SceneRevision。"
    )

    with get_session() as session:
        design = load_presentation_design_system(session, presentation_id)
        active = get_active_theme_proposal(session, presentation_id)

    if design is None:
        st.warning("当前汇报尚无 DesignSystem / ArtDirection，请先完成视觉编排。")
        return

    seeds = deck_theme_tokens_from_design_system(design)
    preferred_slide_id = slide_snapshot.slide.id if slide_snapshot is not None else None

    c1, c2, c3 = st.columns(3)
    primary = c1.text_input("主色", value=seeds.primary or "#1F4E79", key=f"theme_primary_{presentation_id}")
    accent = c2.text_input("强调色", value=seeds.accent or "#C45C26", key=f"theme_accent_{presentation_id}")
    background = c3.text_input(
        "背景",
        value=seeds.background or "#FFFFFF",
        key=f"theme_bg_{presentation_id}",
    )

    f1, f2 = st.columns(2)
    title_font = f1.text_input(
        "标题字体",
        value=seeds.title_font or "Microsoft YaHei",
        key=f"theme_title_font_{presentation_id}",
    )
    body_font = f2.text_input(
        "正文字体",
        value=seeds.body_font or "Microsoft YaHei",
        key=f"theme_body_font_{presentation_id}",
    )

    title_scale = st.slider(
        "标题比例",
        min_value=0.85,
        max_value=1.25,
        value=float(seeds.title_scale or 1.0),
        step=0.05,
        key=f"theme_title_scale_{presentation_id}",
    )
    density_options: list[PageDensityToken] = ["dense", "balanced", "spacious"]
    density_labels = {"dense": "紧凑", "balanced": "适中", "spacious": "疏朗"}
    page_density = st.selectbox(
        "页面密度",
        options=density_options,
        index=density_options.index(seeds.page_density or "balanced"),
        format_func=lambda value: density_labels.get(value, value),
        key=f"theme_density_{presentation_id}",
    )

    g1, g2 = st.columns(2)
    corner_radius = g1.number_input(
        "圆角",
        min_value=0.0,
        value=float(seeds.corner_radius or 0.0),
        step=0.02,
        key=f"theme_radius_{presentation_id}",
    )
    line_weight = g2.number_input(
        "线宽",
        min_value=0.1,
        value=float(seeds.line_weight or 1.0),
        step=0.05,
        key=f"theme_line_{presentation_id}",
    )

    photo_values = list(PhotoTreatment)
    photo_treatment = st.selectbox(
        "图片处理方式",
        options=photo_values,
        index=photo_values.index(seeds.photo_treatment or PhotoTreatment.NONE),
        format_func=lambda value: value.value,
        key=f"theme_photo_{presentation_id}",
    )
    icon_options: list[IconStyleToken] = ["line", "filled", "minimal"]
    icon_labels = {"line": "线框", "filled": "填充", "minimal": "极简"}
    icon_style = st.selectbox(
        "图标风格",
        options=icon_options,
        index=icon_options.index(seeds.icon_style or "filled"),
        format_func=lambda value: icon_labels.get(value, value),
        key=f"theme_icon_{presentation_id}",
    )

    if st.button(
        "生成风格提案",
        type="primary",
        use_container_width=True,
        key=f"theme_create_proposal_{presentation_id}",
    ):
        tokens = DeckThemeTokens(
            primary=primary.strip() or None,
            accent=accent.strip() or None,
            background=background.strip() or None,
            title_font=title_font.strip() or None,
            body_font=body_font.strip() or None,
            title_scale=float(title_scale),
            page_density=page_density,
            corner_radius=float(corner_radius),
            line_weight=float(line_weight),
            photo_treatment=photo_treatment,
            icon_style=icon_style,
        )
        try:
            with st.spinner("正在应用 Token、编译样本页并跑 QA…"), get_session() as session:
                proposal = create_theme_proposal(
                    session,
                    presentation_id,
                    tokens,
                    preferred_slide_id=preferred_slide_id,
                )
            _store_theme_proposal(proposal)
            st.success("风格提案已生成，请审阅样本 QA 后再接受。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

    proposal = _get_stored_theme_proposal(presentation_id) or active
    if proposal is None:
        st.caption("尚未生成风格提案。")
        return

    if proposal.status not in {
        ThemeProposalStatus.READY,
        ThemeProposalStatus.READY_WITH_WARNINGS,
        ThemeProposalStatus.DRAFT,
    }:
        st.caption(f"最近提案状态：`{proposal.status.value}`")
        return

    st.divider()
    st.markdown(f"**待审风格提案** · `{proposal.status.value}`")
    st.caption(
        f"样本页 {len(proposal.sample_slide_ids)} · "
        f"DesignSystem `{proposal.base_design_system.name}` → "
        f"`{proposal.proposed_design_system.name}`"
    )
    if proposal.sample_selection_reason:
        st.caption("抽样说明：" + "；".join(
            f"`{sid[:8]}…` → {reason}"
            if len(sid) > 12
            else f"`{sid}` → {reason}"
            for sid, reason in proposal.sample_selection_reason.items()
        ))
    patch = proposal.token_patch
    st.write(
        {
            "主色": patch.primary,
            "强调色": patch.accent,
            "背景": patch.background,
            "标题字体": patch.title_font,
            "正文字体": patch.body_font,
            "标题比例": patch.title_scale,
            "密度": patch.page_density,
            "圆角": patch.corner_radius,
            "线宽": patch.line_weight,
            "图片处理": patch.photo_treatment.value if patch.photo_treatment else None,
            "图标": patch.icon_style,
        }
    )

    impact = proposal.deck_impact
    st.markdown("**全稿影响（接受前）**")
    impact_cols = st.columns(4)
    impact_cols[0].metric("受影响页面", impact.affected_pages)
    impact_cols[1].metric("字体变化", impact.font_changes)
    impact_cols[2].metric("背景变化", impact.background_changes)
    impact_cols[3].metric("图纸节点变化", impact.drawing_node_changes)
    impact_cols2 = st.columns(3)
    impact_cols2[0].metric("证据照片变化", impact.evidence_photo_changes)
    impact_cols2[1].metric("警告", impact.warnings)
    impact_cols2[2].metric("阻塞", impact.blockers)

    has_blocker = any(
        issue.severity == IssueSeverity.BLOCKER for issue in proposal.qa_summary
    )
    if proposal.qa_summary:
        st.markdown("**样本 QA**")
        for issue in proposal.qa_summary[:12]:
            st.markdown(f"- `{issue.severity.value}` · {issue.message}")
    else:
        st.caption("样本页 QA 未发现问题。")

    if has_blocker:
        st.warning("存在 Blocker：默认禁止接受。勾选下方选项可强制接受。")
        allow_blockers = st.checkbox(
            "我了解风险，仍要强制接受",
            value=False,
            key=f"theme_allow_blockers_{proposal.proposal_id}",
        )
    else:
        allow_blockers = False

    a1, a2 = st.columns(2)
    if a1.button(
        "接受风格提案",
        type="primary",
        use_container_width=True,
        key=f"theme_accept_{proposal.proposal_id}",
        disabled=has_blocker and not allow_blockers,
    ):
        try:
            with st.spinner("正在切换 DesignSystem 并重编译全稿…"), get_session() as session:
                accepted = accept_theme_proposal(
                    session,
                    proposal,
                    allow_blockers=allow_blockers,
                )
            _store_theme_proposal(accepted)
            st.success("全稿风格已应用，各页已写入 Revision。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

    if a2.button(
        "拒绝",
        use_container_width=True,
        key=f"theme_reject_{proposal.proposal_id}",
    ):
        try:
            with get_session() as session:
                rejected = reject_theme_proposal(session, proposal)
            _store_theme_proposal(rejected)
            st.info("已拒绝风格提案，正式 DesignSystem 未改动。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))
