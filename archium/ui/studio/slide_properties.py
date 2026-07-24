"""Right-hand properties panel for Presentation Studio."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import streamlit as st

from archium.application.asset_board_service import AssetBoardService
from archium.domain.visual.element_lock import canvas_geometry_locked, is_drawing_element
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import entity_label, field_label
from archium.ui.layout_family_ui import format_layout_family_label, layout_family_implemented
from archium.ui.studio.canvas_command_bridge import set_studio_selection
from archium.ui.studio.element_labels import CONTENT_TYPE_LABELS, ROLE_LABELS, format_element_label
from archium.ui.studio_service import (
    SlideVisualSnapshot,
    apply_slide_element_asset,
    apply_slide_element_style,
    apply_slide_element_text,
    generate_slide_vision_illustration,
)


def _element_ids_for_panel(slide_snapshot: SlideVisualSnapshot) -> list[str]:
    plan = slide_snapshot.layout_plan
    if plan is None:
        return []
    visible_ids = [element.id for element in plan.elements]
    scene = slide_snapshot.render_scene
    if scene is None:
        return visible_ids
    visible_set = set(visible_ids)
    hidden_ids: list[str] = []
    for node in scene.nodes:
        if node.visible:
            continue
        element_id = node.source_layout_element_id or node.id
        if element_id not in visible_set and element_id not in hidden_ids:
            hidden_ids.append(element_id)
    return visible_ids + hidden_ids


def _element_visibility(slide_snapshot: SlideVisualSnapshot, element_id: str) -> bool:
    scene = slide_snapshot.render_scene
    if scene is not None:
        node = scene.node_by_layout_element_id(element_id) or scene.node_by_id(element_id)
        if node is not None:
            return node.visible
    return True


def _element_z_index(slide_snapshot: SlideVisualSnapshot, element_id: str) -> int:
    scene = slide_snapshot.render_scene
    if scene is not None:
        node = scene.node_by_layout_element_id(element_id) or scene.node_by_id(element_id)
        if node is not None:
            return node.z_index
    plan = slide_snapshot.layout_plan
    if plan is not None:
        element = plan.element_by_id(element_id)
        if element is not None:
            return element.z_index
    return 0


def _element_locked(slide_snapshot: SlideVisualSnapshot, element_id: str) -> bool:
    scene = slide_snapshot.render_scene
    if scene is not None:
        node = scene.node_by_layout_element_id(element_id) or scene.node_by_id(element_id)
        if node is not None:
            return node.locked
    plan = slide_snapshot.layout_plan
    if plan is not None:
        element = plan.element_by_id(element_id)
        if element is not None:
            return element.locked
    return False


def _run_lock(
    slide_id: UUID,
    element_id: str,
    *,
    locked: bool,
) -> None:
    try:
        with get_session() as session:
            from archium.ui.studio_service import apply_slide_element_lock

            apply_slide_element_lock(
                session,
                slide_id,
                element_id=element_id,
                locked=locked,
            )
        st.success("已锁定元素。" if locked else "已解锁元素。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_reorder(
    slide_id: UUID,
    element_id: str,
    direction: str,
) -> None:
    try:
        with get_session() as session:
            from archium.ui.studio_service import apply_slide_element_reorder

            apply_slide_element_reorder(
                session,
                slide_id,
                element_id=element_id,
                direction=direction,
            )
        labels = {
            "forward": "上移",
            "backward": "下移",
            "front": "置顶",
            "back": "置底",
        }
        st.success(f"已{labels.get(direction, '调整')}图层。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_visibility(
    slide_id: UUID,
    element_id: str,
    *,
    visible: bool,
) -> None:
    try:
        with get_session() as session:
            from archium.ui.studio_service import apply_slide_element_visibility

            apply_slide_element_visibility(
                session,
                slide_id,
                element_id=element_id,
                visible=visible,
            )
        st.success("已显示元素。" if visible else "已隐藏元素。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))


def _run_align(
    slide_id: UUID,
    element_ids: list[str],
    alignment: str,
    *,
    reference_element_id: str | None = None,
) -> None:
    try:
        with get_session() as session:
            from archium.ui.studio_service import apply_slide_element_align

            apply_slide_element_align(
                session,
                slide_id,
                element_ids=element_ids,
                alignment=alignment,
                reference_element_id=reference_element_id,
            )
        st.success("已更新对齐。")
        st.rerun()
    except Exception as exc:
        st.error(format_user_error(exc))


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

        _render_vision_illustration_panel(
            slide_snapshot=slide_snapshot,
            project_id=project_id,
        )

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


def _render_vision_illustration_panel(
    *,
    slide_snapshot: SlideVisualSnapshot,
    project_id: UUID | None,
) -> None:
    """Vision Engine — generate illustrative image for the current slide (v0.2 templates)."""
    if project_id is None:
        return

    st.divider()
    st.markdown("**Vision 示意生成**")
    st.caption(
        "建筑语义 → Prompt Compiler → 生成/改图。结果标记为 `ai_generated` / 仅示意，"
        "不会当作现场证据。场地/流线可底图叠加；照片可条件改图（示意改造意象）。"
    )
    slide = slide_snapshot.slide
    default_subject = (slide.message or slide.title or "").strip() or "architectural concept illustration"
    subject = st.text_input(
        "生成主题",
        value=default_subject,
        key=f"studio_vision_subject_{slide.id}",
    )
    mode_options = {
        "text_to_image": "文生图 / 底图叠加",
        "edit_from_photo": "基于照片改图（示意）",
        "edit_from_drawing": "基于图纸改图（示意）",
    }
    generation_mode = st.selectbox(
        "模式",
        options=list(mode_options.keys()),
        format_func=lambda key: mode_options[key],
        key=f"studio_vision_mode_{slide.id}",
    )
    type_options = {
        "flow_diagram": "流线分析图",
        "site_diagram": "场地关系图",
        "concept_sketch": "概念草图",
        "section_illustration": "剖面示意",
        "atmosphere_image": "氛围 / 封面",
        "material_study": "材料研究",
        "presentation_illustration": "页级插图",
        "sketch_note": "手绘笔记感",
    }
    image_type = st.selectbox(
        "图类",
        options=list(type_options.keys()),
        format_func=lambda key: type_options[key],
        key=f"studio_vision_type_{slide.id}",
    )
    style_options = {
        "": "（按图类默认）",
        "axonometric_diagram": "轴测分析图",
        "flat_analytical_diagram": "扁平分析图",
        "competition_concept_sketch": "竞赛概念草图",
        "marker_sketch": "马克笔",
        "pencil_sketch": "铅笔手绘",
        "soft_atmosphere": "柔和氛围",
        "watercolor_note": "水彩笔记",
    }
    style = st.selectbox(
        "风格",
        options=list(style_options.keys()),
        format_func=lambda key: style_options[key],
        key=f"studio_vision_style_{slide.id}",
    )
    overlay_raw = st.text_input(
        "叠加标注（逗号分隔，可选）",
        value="",
        key=f"studio_vision_cues_{slide.id}",
        help="例如：入口, 风雨连廊, 门诊大厅",
    )
    overlay_cues = [part.strip() for part in overlay_raw.split(",") if part.strip()]

    plan = slide_snapshot.layout_plan
    image_elements = [
        element
        for element in (plan.elements if plan is not None else [])
        if element.content_type == LayoutContentType.IMAGE and not canvas_geometry_locked(element)
    ]
    base_element_id: str | None = None
    needs_base = generation_mode != "text_to_image" or image_type in {
        "flow_diagram",
        "site_diagram",
    }
    if needs_base and image_elements:
        base_labels = {
            element.id: format_element_label(element_id=element.id, role=element.role)
            for element in image_elements
        }
        base_label = (
            "底图（改图必选）"
            if generation_mode != "text_to_image"
            else "底图（总平/图纸叠加，可选）"
        )
        base_choice = st.selectbox(
            base_label,
            options=["（不使用底图）", *list(base_labels.keys())],
            format_func=lambda value: (
                value if value.startswith("（") else base_labels.get(value, value)
            ),
            key=f"studio_vision_base_{slide.id}",
        )
        if not base_choice.startswith("（"):
            base_element_id = base_choice

    apply_target: str | None = None
    if image_elements:
        target_labels = {
            element.id: format_element_label(element_id=element.id, role=element.role)
            for element in image_elements
        }
        apply_target = st.selectbox(
            "生成后应用到",
            options=["（仅入库，不换图）", *list(target_labels.keys())],
            format_func=lambda value: (
                value if value.startswith("（") else target_labels.get(value, value)
            ),
            key=f"studio_vision_target_{slide.id}",
        )
        if apply_target.startswith("（"):
            apply_target = None

    if st.button(
        "生成示意并入库",
        use_container_width=True,
        key=f"studio_vision_generate_{slide.id}",
    ):
        try:
            with get_session() as session:
                result = generate_slide_vision_illustration(
                    session,
                    slide.id,
                    project_id=project_id,
                    subject=subject,
                    image_type=image_type,
                    style=style or None,
                    apply_to_element_id=apply_target,
                    base_element_id=base_element_id,
                    overlay_cues=overlay_cues,
                    generation_mode=generation_mode,
                )
            warnings = []
            if result.input_evaluation is not None:
                warnings = list(result.input_evaluation.warnings)
            st.session_state[f"studio_vision_last_{slide.id}"] = {
                "asset_id": str(result.asset_id) if result.asset_id else None,
                "provider": result.provider,
                "prompt_hash": result.spec.prompt_hash,
                "path": result.storage_path,
                "compose": bool(result.spec.metadata.get("compose_mode")),
                "edit": bool(result.spec.metadata.get("edit_mode")),
                "harmonized": bool(result.harmonized),
                "warnings": warnings,
            }
            if apply_target:
                st.success("已生成示意并应用到所选图片元素（仅示意，非现场证据）。")
            else:
                st.success("已生成示意并入库。可在「更换素材」中选用。")
            if warnings:
                st.warning("底图 QA：" + "；".join(warnings))
            st.rerun()
        except Exception as exc:
            st.error(format_user_error(exc))

    last = st.session_state.get(f"studio_vision_last_{slide.id}")
    if isinstance(last, dict) and last.get("asset_id"):
        flags = []
        if last.get("compose"):
            flags.append("底图叠加")
        if last.get("edit"):
            flags.append("条件改图")
        if last.get("harmonized"):
            flags.append("软统一")
        flag_note = f" · {'/'.join(flags)}" if flags else ""
        st.caption(
            f"最近生成：asset `{last['asset_id']}` · {last.get('provider')} · "
            f"hash `{last.get('prompt_hash')}`{flag_note}"
        )


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
    element_ids = _element_ids_for_panel(slide_snapshot)
    if not element_ids:
        st.caption("当前页面没有可编辑元素。")
        return
    selected_raw = st.session_state.get("studio_selected_element_id")
    selected_id: str = (
        selected_raw
        if isinstance(selected_raw, str) and selected_raw in element_ids
        else element_ids[0]
    )

    def _format_element_option(value: str) -> str:
        element = plan.element_by_id(value)
        if element is not None:
            return format_element_label(element_id=value, role=element.role)
        if not _element_visibility(slide_snapshot, value):
            return f"{value}（已隐藏）"
        return value

    selected_from_ui = st.selectbox(
        "选择元素",
        options=cast(list[str], element_ids),
        index=element_ids.index(selected_id),
        format_func=_format_element_option,
        key=f"studio_element_select_{slide_snapshot.slide.id}",
    )
    if not isinstance(selected_from_ui, str):
        return
    set_studio_selection([selected_from_ui])

    element = plan.element_by_id(selected_from_ui)
    is_visible = _element_visibility(slide_snapshot, selected_from_ui)
    if element is None and not is_visible:
        st.caption("此元素已隐藏，恢复显示后可继续编辑属性。")
        if st.button(
            "显示此元素",
            use_container_width=True,
            type="primary",
            key=f"studio_show_element_{slide_snapshot.slide.id}_{selected_from_ui}",
        ):
            _run_visibility(slide_snapshot.slide.id, selected_from_ui, visible=True)
        return
    if element is None:
        return

    role_label = ROLE_LABELS.get(element.role, element.role.value)
    content_label = CONTENT_TYPE_LABELS.get(element.content_type, element.content_type.value)
    st.write(f"角色：{role_label}")
    st.write(f"类型：{content_label}")
    st.write(f"位置：{element.x:.2f}, {element.y:.2f}")
    st.write(f"尺寸：{element.width:.2f} × {element.height:.2f}")
    st.write(f"显示：{'是' if is_visible else '否'}")
    st.write(f"图层：{_element_z_index(slide_snapshot, selected_from_ui)}")
    element_locked = _element_locked(slide_snapshot, selected_from_ui)
    st.write(f"锁定：{'是' if element_locked else '否'}")

    if is_drawing_element(element) or canvas_geometry_locked(element):
        if is_drawing_element(element):
            st.info("图纸元素位置与尺寸已固定，画布上不可拖拽或缩放。")
        elif element_locked:
            st.caption("此元素已锁定几何，画布上不可拖拽或缩放。")

    focus_text = st.session_state.get("studio_focus_text_edit") == element.id
    if focus_text and element.content_type == LayoutContentType.TEXT:
        st.info("请在下方编辑文字，保存后将写入版式并刷新预览。")
    elif focus_text and element.content_type != LayoutContentType.TEXT:
        st.caption("当前元素不是文字类型；请在属性栏选择文字元素进行改字。")
        st.session_state.pop("studio_focus_text_edit", None)

    if is_visible:
        st.markdown("**图层顺序**")
        layer_cols = st.columns(4)
        layer_actions = (
            ("上移", "forward"),
            ("下移", "backward"),
            ("置顶", "front"),
            ("置底", "back"),
        )
        for column, (label, direction) in zip(layer_cols, layer_actions, strict=True):
            with column:
                if st.button(
                    label,
                    use_container_width=True,
                    key=(
                        f"studio_layer_{direction}_"
                        f"{slide_snapshot.slide.id}_{element.id}"
                    ),
                ):
                    _run_reorder(slide_snapshot.slide.id, element.id, direction)
        st.caption("图层顺序影响导出时的叠放关系；数值越大越靠前。")

    if element.content_type == LayoutContentType.TEXT:
        edited_text = st.text_area(
            "文字内容",
            value=element.text_content or "",
            height=100 if focus_text else 80,
            key=f"studio_element_text_{slide_snapshot.slide.id}_{element.id}",
        )
        scene_node = None
        if slide_snapshot.render_scene is not None:
            scene_node = (
                slide_snapshot.render_scene.node_by_layout_element_id(element.id)
                or slide_snapshot.render_scene.node_by_id(element.id)
            )
        current_color = "#111111"
        current_font = 16.0
        if scene_node is not None and hasattr(scene_node, "color"):
            current_color = str(getattr(scene_node, "color", None) or "#111111")
        if scene_node is not None and hasattr(scene_node, "font_size"):
            current_font = float(getattr(scene_node, "font_size", None) or 16.0)

        style_cols = st.columns(2)
        with style_cols[0]:
            color_value = st.color_picker(
                "文字颜色",
                value=current_color if current_color.startswith("#") else "#111111",
                key=f"studio_element_color_{slide_snapshot.slide.id}_{element.id}",
            )
        with style_cols[1]:
            font_size_value = st.number_input(
                "字号",
                min_value=8.0,
                max_value=96.0,
                value=float(current_font),
                step=1.0,
                key=f"studio_element_font_{slide_snapshot.slide.id}_{element.id}",
            )
        if st.button(
            "保存文字",
            use_container_width=True,
            type="primary" if focus_text else "secondary",
            key=f"studio_save_element_text_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    apply_slide_element_text(
                        session,
                        slide_snapshot.slide.id,
                        element_id=element.id,
                        text=edited_text,
                    )
                st.session_state.pop("studio_focus_text_edit", None)
                st.success("已更新元素文字。")
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))
        if st.button(
            "应用颜色 / 字号",
            use_container_width=True,
            key=f"studio_save_element_style_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    apply_slide_element_style(
                        session,
                        slide_snapshot.slide.id,
                        element_id=element.id,
                        color=color_value,
                        font_size=float(font_size_value),
                    )
                st.success("已更新文字样式。")
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
                            apply_slide_element_asset(
                                session,
                                slide_snapshot.slide.id,
                                element_id=element.id,
                                asset_id=UUID(selected_asset),
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

    # Shape fill color when scene has a ShapeNode for this element
    if slide_snapshot.render_scene is not None:
        from archium.domain.visual.render_scene import ShapeNode

        shape_node = (
            slide_snapshot.render_scene.node_by_layout_element_id(element.id)
            or slide_snapshot.render_scene.node_by_id(element.id)
        )
        if isinstance(shape_node, ShapeNode):
            fill_default = shape_node.fill_color or "#CCCCCC"
            if not str(fill_default).startswith("#"):
                fill_default = "#CCCCCC"
            fill_value = st.color_picker(
                "色块填充",
                value=fill_default,
                key=f"studio_element_fill_{slide_snapshot.slide.id}_{element.id}",
            )
            if st.button(
                "应用填充色",
                use_container_width=True,
                key=f"studio_apply_fill_{slide_snapshot.slide.id}_{element.id}",
            ):
                try:
                    with get_session() as session:
                        apply_slide_element_style(
                            session,
                            slide_snapshot.slide.id,
                            element_id=element.id,
                            fill_color=fill_value,
                        )
                    st.success("已更新色块颜色。")
                    st.rerun()
                except Exception as exc:
                    st.error(format_user_error(exc))

    if not element_locked:
        multi_ids = [
            item
            for item in (st.session_state.get("studio_selected_element_ids") or [element.id])
            if isinstance(item, str) and plan.element_by_id(item) is not None
        ]
        if len(multi_ids) < 2:
            multi_ids = [element.id]

        if len(multi_ids) >= 2:
            st.caption(f"多选 {len(multi_ids)} 个元素：对齐 / 分布 / 等宽高")
            row1 = st.columns(3)
            with row1[0]:
                if st.button(
                    "左对齐",
                    use_container_width=True,
                    key=f"studio_multi_align_left_{slide_snapshot.slide.id}",
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "left")
            with row1[1]:
                if st.button(
                    "水平居中",
                    use_container_width=True,
                    key=f"studio_multi_align_center_{slide_snapshot.slide.id}",
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "center")
            with row1[2]:
                if st.button(
                    "右对齐",
                    use_container_width=True,
                    key=f"studio_multi_align_right_{slide_snapshot.slide.id}",
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "right")
            row2 = st.columns(3)
            with row2[0]:
                if st.button(
                    "顶对齐",
                    use_container_width=True,
                    key=f"studio_multi_align_top_{slide_snapshot.slide.id}",
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "top")
            with row2[1]:
                if st.button(
                    "垂直居中",
                    use_container_width=True,
                    key=f"studio_multi_align_middle_{slide_snapshot.slide.id}",
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "middle")
            with row2[2]:
                if st.button(
                    "底对齐",
                    use_container_width=True,
                    key=f"studio_multi_align_bottom_{slide_snapshot.slide.id}",
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "bottom")
            row3 = st.columns(2)
            with row3[0]:
                if st.button(
                    "水平分布",
                    use_container_width=True,
                    key=f"studio_multi_dist_h_{slide_snapshot.slide.id}",
                    disabled=len(multi_ids) < 3,
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "distribute_h")
            with row3[1]:
                if st.button(
                    "垂直分布",
                    use_container_width=True,
                    key=f"studio_multi_dist_v_{slide_snapshot.slide.id}",
                    disabled=len(multi_ids) < 3,
                ):
                    _run_align(slide_snapshot.slide.id, multi_ids, "distribute_v")
            row4 = st.columns(2)
            with row4[0]:
                if st.button(
                    "等宽",
                    use_container_width=True,
                    key=f"studio_multi_eq_w_{slide_snapshot.slide.id}",
                ):
                    _run_align(
                        slide_snapshot.slide.id,
                        multi_ids,
                        "equal_width",
                        reference_element_id=element.id,
                    )
            with row4[1]:
                if st.button(
                    "等高",
                    use_container_width=True,
                    key=f"studio_multi_eq_h_{slide_snapshot.slide.id}",
                ):
                    _run_align(
                        slide_snapshot.slide.id,
                        multi_ids,
                        "equal_height",
                        reference_element_id=element.id,
                    )

        align_cols = st.columns(3)
        with align_cols[0]:
            if st.button(
                "左对齐页面",
                use_container_width=True,
                key=f"studio_align_left_{slide_snapshot.slide.id}_{element.id}",
            ):
                _run_align(slide_snapshot.slide.id, [element.id], "left")
        with align_cols[1]:
            if st.button(
                "居中页面",
                use_container_width=True,
                key=f"studio_align_center_{slide_snapshot.slide.id}_{element.id}",
            ):
                _run_align(slide_snapshot.slide.id, [element.id], "center")
        with align_cols[2]:
            if st.button(
                "右对齐页面",
                use_container_width=True,
                key=f"studio_align_right_{slide_snapshot.slide.id}_{element.id}",
            ):
                _run_align(slide_snapshot.slide.id, [element.id], "right")
        st.caption("单选时左/中/右以整页为参考；多选时用上方批量工具。")
        other_ids = [
            item.id
            for item in plan.elements
            if item.id != element.id and not item.locked
        ]
        if other_ids and st.button(
            "将其他元素对齐到当前元素",
            use_container_width=True,
            key=f"studio_align_to_current_{slide_snapshot.slide.id}_{element.id}",
        ):
            _run_align(
                slide_snapshot.slide.id,
                other_ids,
                "left",
                reference_element_id=element.id,
            )

        if st.button(
            "隐藏此元素",
            use_container_width=True,
            key=f"studio_hide_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            _run_visibility(slide_snapshot.slide.id, element.id, visible=False)

        if st.button(
            "复制此元素",
            use_container_width=True,
            key=f"studio_duplicate_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    from archium.ui.studio_service import apply_slide_element_duplicate

                    result = apply_slide_element_duplicate(
                        session,
                        slide_snapshot.slide.id,
                        element_ids=[element.id],
                    )
                new_ids = [
                    action.node_id
                    for action in getattr(result, "applied_actions", ())
                    if getattr(action, "action_type", "") == "insert_node"
                ]
                set_studio_selection(new_ids or [element.id])
                st.success("已复制元素。")
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))

        if st.button(
            "删除此元素",
            use_container_width=True,
            key=f"studio_delete_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            try:
                with get_session() as session:
                    from archium.ui.studio_service import apply_slide_element_delete

                    apply_slide_element_delete(
                        session,
                        slide_snapshot.slide.id,
                        element_id=element.id,
                    )
                st.session_state.pop("studio_selected_element_id", None)
                st.session_state.pop("studio_selected_element_ids", None)
                set_studio_selection([])
                st.success("已删除元素。")
                st.rerun()
            except Exception as exc:
                st.error(format_user_error(exc))

        if st.button(
            "锁定此元素",
            use_container_width=True,
            key=f"studio_lock_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            _run_lock(slide_snapshot.slide.id, element.id, locked=True)
    else:
        if st.button(
            "解锁此元素",
            use_container_width=True,
            key=f"studio_unlock_element_{slide_snapshot.slide.id}_{element.id}",
        ):
            _run_lock(slide_snapshot.slide.id, element.id, locked=False)

    if advanced:
        st.caption(f"元素 ID：`{element.id}` · style `{element.style_token or '—'}`")
