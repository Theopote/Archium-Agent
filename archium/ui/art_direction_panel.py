"""Streamlit panel for ArtDirection review and editing."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.enums import ApprovalStatus
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.style import (
    DEFAULT_STYLE_PRESET_ID,
    get_style_preset,
    list_style_presets,
    resolve_style_preset_id,
)
from archium.exceptions import WorkflowError
from archium.application.unit_of_work import unit_of_work
from archium.ui.error_handlers import report_user_error
from archium.ui.visual_service import (
    approve_art_direction,
    continue_visual_after_art_direction_approval,
    regenerate_art_direction,
    update_art_direction,
)

APPROVAL_LABELS = {
    ApprovalStatus.DRAFT: "草稿",
    ApprovalStatus.PENDING: "待审核",
    ApprovalStatus.APPROVED: "已通过",
    ApprovalStatus.REJECTED: "已驳回",
}


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _render_personality_card(preset_id: str, art_direction: ArtDirection) -> None:
    try:
        preset_obj = get_style_preset(preset_id)
    except KeyError:
        return
    tone = " · ".join(art_direction.visual_tone[:3]) or "（未填语气）"
    emotion = " · ".join(art_direction.emotional_keywords[:4]) or "克制专业"
    personality = preset_obj.presentation_personality
    policy = preset_obj.content_policy
    st.markdown(
        f"**{preset_obj.display_name}**  \n"
        f"{preset_obj.description}  \n"
        f"叙事性格：{personality.logic.value} · 情绪 {personality.emotion.value} · "
        f"图面 {personality.image_role.value}  \n"
        f"内容政策：msg≤{policy.max_message_chars} · pts≤{policy.max_key_points} · "
        f"img≤{policy.max_images} · 留白≥{policy.preferred_whitespace}  \n"
        f"语气：{tone}  \n"
        f"情绪曲线关键词：{emotion}  \n"
        f"节奏：{(art_direction.pacing_strategy or '')[:160]}"
    )


def render_art_direction_panel(
    *,
    art_direction: ArtDirection,
    workflow_run_id: UUID | None = None,
    awaiting_approval: bool = False,
) -> None:
    """Show and edit ArtDirection; optionally continue a paused visual workflow."""
    st.markdown("### 汇报气质")
    st.caption(
        f"Presentation Intelligence · "
        f"{APPROVAL_LABELS.get(art_direction.approval_status, art_direction.approval_status.value)}"
        f" · {art_direction.concept_name}"
    )

    if awaiting_approval:
        st.info("视觉工作流已暂停：先确认气质与节奏，再批准继续生成。")

    presets = list_style_presets()
    preset_labels = {p.id.value: f"{p.display_name} — {p.description}" for p in presets}
    try:
        saved_preset = resolve_style_preset_id(
            art_direction.style_preset_id or DEFAULT_STYLE_PRESET_ID
        ).value
    except KeyError:
        saved_preset = DEFAULT_STYLE_PRESET_ID.value

    # Preset lives outside the form so personality card updates immediately.
    preset_key = f"art_style_preset_{art_direction.id}"
    if preset_key not in st.session_state:
        st.session_state[preset_key] = saved_preset
    style_preset_id = st.selectbox(
        "事务所气质（Style Preset）",
        options=list(preset_labels.keys()),
        key=preset_key,
        format_func=lambda key: preset_labels.get(key, key),
        help="打开 PPT 第一印象：留白、字号、主图阈值与版式偏好（不改绝对坐标）。切换后上方读法即时更新。",
    )
    _render_personality_card(style_preset_id, art_direction)

    with st.form(f"art_direction_form_{art_direction.id}"):
        concept_name = st.text_input("视觉概念（一句话）", value=art_direction.concept_name)
        rationale = st.text_area(
            "为什么这样定调",
            value=art_direction.rationale,
            height=80,
        )
        visual_tone = st.text_area(
            "视觉语气（每行一项）",
            value="\n".join(art_direction.visual_tone),
            height=70,
        )
        pacing_strategy = st.text_area(
            "整册节奏（开场 / 证据 / 高潮 / 收束）",
            value=art_direction.pacing_strategy,
            height=70,
        )
        emotional_keywords = st.text_area(
            "情绪关键词（每行一项）",
            value="\n".join(art_direction.emotional_keywords),
            height=60,
        )
        forbidden_styles = st.text_area(
            "禁止风格（每行一项）",
            value="\n".join(art_direction.forbidden_styles),
            height=60,
        )

        with st.expander("工程细节（令牌策略原文）", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                palette_strategy = st.text_area(
                    "色彩策略", value=art_direction.palette_strategy, height=70
                )
                typography_strategy = st.text_area(
                    "字体策略", value=art_direction.typography_strategy, height=70
                )
                image_strategy = st.text_area(
                    "图片策略", value=art_direction.image_strategy, height=70
                )
                diagram_strategy = st.text_area(
                    "图形策略", value=art_direction.diagram_strategy, height=70
                )
            with col_b:
                drawing_strategy = st.text_area(
                    "图纸策略", value=art_direction.drawing_strategy, height=70
                )
                annotation_strategy = st.text_area(
                    "标注策略", value=art_direction.annotation_strategy, height=70
                )
                grid_strategy = st.text_area(
                    "网格策略", value=art_direction.grid_strategy, height=60
                )
                cover_strategy = st.text_area(
                    "封面策略", value=art_direction.cover_strategy, height=60
                )
            section_strategy = st.text_area(
                "章节策略", value=art_direction.section_strategy, height=60
            )
            content_strategy = st.text_area(
                "内容页策略", value=art_direction.content_strategy, height=60
            )
            closing_strategy = st.text_area(
                "收束策略", value=art_direction.closing_strategy, height=60
            )
            consistency_rules = st.text_area(
                "一致性规则（每行一项）",
                value="\n".join(art_direction.consistency_rules),
                height=70,
            )

        c1, c2, c3 = st.columns(3)
        save_clicked = c1.form_submit_button("保存修改", width="stretch")
        approve_clicked = c2.form_submit_button("批准视觉方向", width="stretch")
        approve_continue = c3.form_submit_button(
            "批准并继续工作流",
            width="stretch",
            disabled=workflow_run_id is None,
        )

    if save_clicked or approve_clicked or approve_continue:
        updates: dict[str, object] = {
            "concept_name": concept_name,
            "rationale": rationale,
            "visual_tone": _lines_to_list(visual_tone),
            "palette_strategy": palette_strategy,
            "typography_strategy": typography_strategy,
            "image_strategy": image_strategy,
            "drawing_strategy": drawing_strategy,
            "diagram_strategy": diagram_strategy,
            "annotation_strategy": annotation_strategy,
            "pacing_strategy": pacing_strategy,
            "forbidden_styles": _lines_to_list(forbidden_styles),
            "grid_strategy": grid_strategy,
            "cover_strategy": cover_strategy,
            "section_strategy": section_strategy,
            "content_strategy": content_strategy,
            "closing_strategy": closing_strategy,
            "consistency_rules": _lines_to_list(consistency_rules),
            "emotional_keywords": _lines_to_list(emotional_keywords),
            "style_preset_id": style_preset_id,
        }
        try:
            with unit_of_work() as uow:
                session = uow.session
                update_art_direction(session, art_direction.id, updates)
                if approve_clicked or approve_continue:
                    approve_art_direction(session, art_direction.id)
                if approve_continue and workflow_run_id is not None:
                    result = continue_visual_after_art_direction_approval(
                        session,
                        workflow_run_id,
                        approve=True,
                    )
                    st.session_state.last_visual_workflow_result = result
            if approve_continue:
                st.success("视觉方向已批准，工作流已继续。")
            elif approve_clicked:
                st.success("视觉方向已批准。")
            else:
                st.success("视觉方向已保存。")
            st.rerun()
        except WorkflowError as exc:
            st.error(report_user_error(exc))
        except Exception as exc:
            st.error(report_user_error(exc))

    with st.expander("根据反馈重新生成", expanded=False):
        feedback = st.text_area(
            "反馈",
            key=f"art_regen_feedback_{art_direction.id}",
            placeholder="例如：更克制、减少装饰、医疗场景偏温和蓝绿",
            height=80,
        )
        use_llm = st.checkbox(
            "使用 LLM 重新生成（需已配置 API Key）",
            key=f"art_regen_llm_{art_direction.id}",
            value=False,
        )
        if st.button("重新生成视觉方向", key=f"art_regen_btn_{art_direction.id}"):
            if not feedback.strip():
                st.warning("请填写反馈后再重新生成。")
            else:
                try:
                    with unit_of_work() as uow:
                        session = uow.session
                        regenerate_art_direction(
                            session,
                            art_direction.id,
                            feedback.strip(),
                            use_llm=use_llm,
                        )
                    st.success("视觉方向已重新生成，请再次审核。")
                    st.rerun()
                except Exception as exc:
                    st.error(report_user_error(exc))
