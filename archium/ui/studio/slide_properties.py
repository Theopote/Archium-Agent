"""Right-hand properties panel for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.asset_board_service import AssetBoardService
from archium.domain.visual.element_lock import canvas_geometry_locked, is_drawing_element
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import entity_label, field_label
from archium.ui.layout_family_ui import format_layout_family_label, layout_family_implemented
from archium.ui.studio.element_labels import CONTENT_TYPE_LABELS, ROLE_LABELS, format_element_label
from archium.ui.studio_service import SlideVisualSnapshot, apply_slide_visual_edit


def render_slide_properties(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    advanced: bool,
    project_id: UUID | None = None,
) -> None:
    """Render user-language slide and element properties."""
    st.markdown("**页面属性**")
    if slide_snapshot is None:
        st.caption("暂无选中页面。")
        return

    intent = slide_snapshot.visual_intent
    plan = slide_snapshot.layout_plan

    st.markdown(f"**{entity_label('VisualIntent', advanced=advanced)}**")
    if intent is None:
        st.caption("尚未生成页面视觉意图。请运行视觉编排。")
    else:
        st.write(f"{field_label('communication_goal', advanced=advanced)}：{intent.communication_goal}")
        st.write(f"{field_label('audience_takeaway', advanced=advanced)}：{intent.audience_takeaway}")
        st.write(f"{field_label('dominant_content_type', advanced=advanced)}：`{intent.dominant_content_type.value}`")
        st.write(f"{field_label('density_level', advanced=advanced)}：`{intent.density_level.value}`")

    st.markdown(f"**{entity_label('LayoutPlan', advanced=advanced)}**")
    if plan is None:
        st.caption("尚未生成页面版式。")
    else:
        st.write(f"{field_label('layout_family', advanced=advanced)}：{format_layout_family_label(plan.layout_family)}")
        if not layout_family_implemented(plan.layout_family):
            st.caption("该版式类型尚未实现导出器。")
        st.write(f"{field_label('layout_variant', advanced=advanced)}：`{plan.layout_variant}`")
        st.write(f"{field_label('whitespace_ratio', advanced=advanced)}：{plan.whitespace_ratio:.0%}")
        st.write(f"元素数：{len(plan.elements)}")
        if slide_snapshot.validation is not None:
            validation = slide_snapshot.validation
            st.write(
                f"版式质量：{validation.score:.2f} · "
                f"{'通过' if validation.valid else '需修复'}"
            )
            if validation.issues:
                with st.expander("版式问题", expanded=not validation.valid):
                    for issue in validation.issues[:6]:
                        st.write(f"- {issue.severity.value} · {issue.message}")

        _render_element_properties(
            slide_snapshot=slide_snapshot,
            advanced=advanced,
            project_id=project_id,
        )

    if slide_snapshot.visual_critic is not None:
        critic = slide_snapshot.visual_critic
        total = critic.get("total_score")
        score_label = f"{total:.2f}" if isinstance(total, (int, float)) else "—"
        st.markdown(f"**{entity_label('Visual Critic', advanced=advanced)}**")
        st.write(f"评分：{score_label}")


def _render_element_properties(
    *,
    slide_snapshot: SlideVisualSnapshot,
    advanced: bool,
    project_id: UUID | None,
) -> None:
    plan = slide_snapshot.layout_plan
    if plan is None or not plan.elements:
        return

    st.divider()
    st.markdown("**元素属性**")
    element_ids = [element.id for element in plan.elements]
    selected_raw = st.session_state.get("studio_selected_element_id")
    selected_id: str = (
        selected_raw
        if isinstance(selected_raw, str) and selected_raw in element_ids
        else element_ids[0]
    )

    selected_from_ui = st.selectbox(
        "选择元素",
        options=element_ids,  # type: ignore[arg-type]
        index=element_ids.index(selected_id),
        format_func=lambda value: format_element_label(
            element_id=value,
            role=plan.element_by_id(value).role,  # type: ignore[union-attr]
        ),
        key=f"studio_element_select_{slide_snapshot.slide.id}",
    )
    if not isinstance(selected_from_ui, str):
        return
    st.session_state.studio_selected_element_id = selected_from_ui

    element = plan.element_by_id(selected_from_ui)
    if element is None:
        return

    role_label = ROLE_LABELS.get(element.role, element.role.value)
    content_label = CONTENT_TYPE_LABELS.get(element.content_type, element.content_type.value)
    st.write(f"角色：{role_label}")
    st.write(f"类型：{content_label}")
    st.write(f"位置：{element.x:.2f}, {element.y:.2f}")
    st.write(f"尺寸：{element.width:.2f} × {element.height:.2f}")
    st.write(f"锁定：{'是' if element.locked else '否'}")

    if is_drawing_element(element) or canvas_geometry_locked(element):
        if is_drawing_element(element):
            st.info("图纸元素位置与尺寸已固定，画布上不可拖拽或缩放。")
        elif element.locked:
            st.caption("此元素已锁定几何，画布上不可拖拽或缩放。")

    focus_text = st.session_state.get("studio_focus_text_edit") == element.id
    if focus_text and element.content_type == LayoutContentType.TEXT:
        st.info("请在下方编辑文字，保存后将写入版式并刷新预览。")
    elif focus_text and element.content_type != LayoutContentType.TEXT:
        st.caption("当前元素不是文字类型；请在属性栏选择文字元素进行改字。")
        st.session_state.pop("studio_focus_text_edit", None)

    if element.content_type == LayoutContentType.TEXT:
        edited_text = st.text_area(
            "文字内容",
            value=element.text_content or "",
            height=100 if focus_text else 80,
            key=f"studio_element_text_{slide_snapshot.slide.id}_{element.id}",
        )
        if st.button(
            "保存文字",
            use_container_width=True,
            type="primary" if focus_text else "secondary",
            key=f"studio_save_element_text_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    apply_slide_visual_edit(
                        session,
                        slide_snapshot.slide.id,
                        intent="update_element_text",
                        params={"element_id": element.id, "text": edited_text},
                    )
                st.session_state.pop("studio_focus_text_edit", None)
                st.success("已更新元素文字。")
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))
    elif element.content_type in {LayoutContentType.IMAGE, LayoutContentType.DRAWING}:
        if element.content_ref:
            st.write(f"当前素材：`{element.content_ref}`")
        if element.fit_mode is not None:
            st.write(f"适配方式：`{element.fit_mode.value}`")
        if element.crop_policy is not None:
            st.write(f"裁切策略：`{element.crop_policy.value}`")

        if project_id is not None and element.content_type == LayoutContentType.IMAGE:
            with get_session() as session:
                assets = AssetBoardService(session).list_project_assets(project_id)
            asset_options = {str(asset.id): asset.filename for asset in assets}
            if asset_options:
                current_ref = str(element.content_ref) if element.content_ref else None
                default_index = 0
                option_keys = list(asset_options.keys())
                if current_ref in asset_options:
                    default_index = option_keys.index(current_ref)
                selected_asset = st.selectbox(
                    "更换素材",
                    options=option_keys,
                    index=default_index,
                    format_func=lambda value: asset_options[value],
                    key=f"studio_element_asset_{slide_snapshot.slide.id}_{element.id}",
                )
                if st.button(
                    "应用素材",
                    use_container_width=True,
                    key=f"studio_apply_element_asset_{slide_snapshot.slide.id}_{element.id}",
                ):
                    try:
                        with get_session() as session:
                            apply_slide_visual_edit(
                                session,
                                slide_snapshot.slide.id,
                                intent="set_element_asset",
                                params={
                                    "element_id": element.id,
                                    "content_ref": selected_asset,
                                },
                            )
                        st.success("已更新元素素材。")
                        st.rerun()
                    except Exception as exc:
                        st.error(format_user_error(exc))
            else:
                st.caption("项目暂无可用素材，请先在资料阶段上传。")
        elif element.content_type == LayoutContentType.DRAWING:
            st.caption("图纸素材由版式生成绑定；最小可编辑阶段仅锁定几何，不支持直接换图。")
    elif element.content_ref:
        st.write(f"素材引用：`{element.content_ref}`")
        if element.fit_mode is not None:
            st.write(f"适配方式：`{element.fit_mode.value}`")
        if element.crop_policy is not None:
            st.write(f"裁切策略：`{element.crop_policy.value}`")

    if not element.locked:
        if st.button(
            "锁定此元素",
            use_container_width=True,
            key=f"studio_lock_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    apply_slide_visual_edit(
                        session,
                        slide_snapshot.slide.id,
                        intent="lock_element",
                        params={"element_id": element.id},
                    )
                st.success("已锁定元素。")
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))
    else:
        if st.button(
            "解锁此元素",
            use_container_width=True,
            key=f"studio_unlock_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    apply_slide_visual_edit(
                        session,
                        slide_snapshot.slide.id,
                        intent="unlock_element",
                        params={"element_id": element.id},
                    )
                st.success("已解锁元素。")
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))

    if advanced:
        st.caption(f"元素 ID：`{element.id}` · style `{element.style_token or '—'}`")
