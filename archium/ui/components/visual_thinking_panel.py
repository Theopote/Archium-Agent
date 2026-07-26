"""Visual Thinking panel — multi-slot exploration bound to DesignIntent."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.application.visual.vision.visual_thinking_slots import (
    VISUAL_THINKING_SLOTS,
    focus_hint_for_slot,
    intent_binding_lines,
)
from archium.domain.concept_direction import ConceptDirection
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error, report_user_error


def render_visual_thinking_panel(
    direction: ConceptDirection,
    *,
    key_prefix: str,
    settings,
) -> None:
    """Four Visual Thinking slots + shared feedback refine loop."""
    from archium.application.design_iteration_status import (
        format_vision_user_warning,
        visual_brief_status_label,
    )
    from archium.ui.planning_service import (
        get_visual_concept_brief_for_slot,
    )

    st.markdown("**Visual Thinking**")
    st.caption(
        "按氛围 / 空间 / 材料 / 体量分槽探索；每张图绑定当前方向的设计意图，而非裸生成。"
    )

    cols = st.columns(2)
    for index, slot in enumerate(VISUAL_THINKING_SLOTS):
        with cols[index % 2]:
            st.markdown(f"**{slot.label}**")
            st.caption(slot.caption)
            bindings = intent_binding_lines(direction, slot)
            if bindings:
                for line in bindings:
                    st.caption(line)
            else:
                st.caption(f"对应意图字段：{slot.intent_field}（尚空，将用方向标题）")

            with get_session() as session:
                brief = get_visual_concept_brief_for_slot(session, direction.id, slot.key)
            if brief is not None:
                st.caption(
                    f"{visual_brief_status_label(brief.status)} · {brief.title}"
                )
                if brief.image_path:
                    image_file = Path(brief.image_path)
                    if image_file.is_file():
                        st.image(str(image_file), use_container_width=True)
                binding = str(brief.extra_json.get("intent_binding") or "").strip()
                if binding:
                    st.caption(f"绑定：{binding[:160]}")
                if brief.error_message:
                    st.warning(format_vision_user_warning(brief.error_message))

            btn_cols = st.columns(2)
            if btn_cols[0].button(
                "文字",
                key=f"{key_prefix}_vt_text_{slot.key}_{direction.id}",
                use_container_width=True,
                disabled=not settings.llm_configured,
            ):
                _run_slot_synthesize(
                    direction,
                    slot_key=slot.key,
                    generate_image=False,
                    settings=settings,
                )
            if btn_cols[1].button(
                "出图",
                key=f"{key_prefix}_vt_img_{slot.key}_{direction.id}",
                use_container_width=True,
                disabled=not settings.llm_configured,
                type="primary",
            ):
                if not settings.vision_image_generation_enabled:
                    st.warning(
                        "未开启 Vision 图像生成；将先保存文字简报。"
                        "可在设置中开启 vision_image_generation_enabled。"
                    )
                _run_slot_synthesize(
                    direction,
                    slot_key=slot.key,
                    generate_image=True,
                    settings=settings,
                )

    st.markdown("**示意反馈（边想边画）**")
    feedback = st.text_area(
        "看图后想改什么？",
        key=f"{key_prefix}_vt_feedback_{direction.id}",
        placeholder="例如：改成人视；材质更偏夯土；减少轴线感，加强院落围合…",
        height=88,
    )
    refine_cols = st.columns(2)
    if refine_cols[0].button(
        "按反馈修订方向（文字）",
        key=f"{key_prefix}_vt_refine_text_{direction.id}",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        _run_refine(direction, feedback, generate_image=False, settings=settings)
    if refine_cols[1].button(
        "按反馈修订并出图",
        key=f"{key_prefix}_vt_refine_img_{direction.id}",
        use_container_width=True,
        disabled=not settings.llm_configured,
    ):
        if not settings.vision_image_generation_enabled:
            st.warning("未开启 Vision 图像生成；将修订方向并保存文字简报。")
        _run_refine(direction, feedback, generate_image=True, settings=settings)


def _run_slot_synthesize(direction, *, slot_key: str, generate_image: bool, settings) -> None:
    from archium.application.visual.vision.visual_thinking_slots import slot_by_key
    from archium.ui.planning_service import synthesize_visual_concept_brief

    slot = slot_by_key(slot_key)
    if slot is None:
        st.error("未知 Visual Thinking 分槽。")
        return
    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往设置配置。")
        return
    hint = focus_hint_for_slot(direction, slot)
    with st.spinner(f"正在探索「{slot.label}」…"):
        try:
            with get_session() as session:
                result = synthesize_visual_concept_brief(
                    session,
                    direction.id,
                    generate_image=generate_image,
                    settings=settings,
                    preferred_image_type=slot.image_type,
                    slot_key=slot.key,
                    focus_hint=hint,
                    style_preset=slot.style_preset,
                )
            if result.image_succeeded:
                st.success(f"「{slot.label}」已出图：「{result.brief.title}」。")
            else:
                st.success(f"「{slot.label}」简报已更新：「{result.brief.title}」。")
            from archium.application.design_iteration_status import format_vision_user_warning

            for warning in result.warnings:
                st.warning(format_vision_user_warning(warning))
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(report_user_error(exc))


def _run_refine(direction, feedback: str, *, generate_image: bool, settings) -> None:
    from archium.application.design_iteration_status import format_vision_user_warning
    from archium.ui.planning_service import refine_visual_concept_brief

    if not settings.llm_configured:
        st.error("未配置 LLM API Key。请前往设置配置。")
        return
    with st.spinner("正在根据反馈修订方向…"):
        try:
            with get_session() as session:
                loop = refine_visual_concept_brief(
                    session,
                    direction.id,
                    feedback,
                    generate_image=generate_image,
                    settings=settings,
                )
            st.success(
                f"已修订方向并更新简报「{loop.brief_result.brief.title}」。"
                f"（{loop.change_summary}）"
            )
            for warning in loop.brief_result.warnings:
                st.warning(format_vision_user_warning(warning))
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(format_user_error(exc))
