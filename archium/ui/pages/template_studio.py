"""Template Studio — convert reference PPTX into ArchitecturalTemplate."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.visual.template_studio_service import TemplateStudioService
from archium.domain.visual.architectural_template import (
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
    TemplateStatus,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error


def _selected_template_id() -> UUID | None:
    raw = st.session_state.get("template_studio_selected_id")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def _render_upload_panel() -> None:
    st.markdown("#### 1. 上传 PPTX")
    uploaded = st.file_uploader("选择参考汇报 PPTX", type=["pptx", "pptm"], key="template_pptx")
    name = st.text_input("模板名称", value="", placeholder="例如：院区改造汇报模板")
    if st.button("导入并分析", type="primary", disabled=uploaded is None, use_container_width=True):
        if uploaded is None:
            return
        from archium.config.settings import get_settings

        staging = get_settings().output_path / "template-studio" / "_upload_staging"
        staging.mkdir(parents=True, exist_ok=True)
        staged = staging / uploaded.name
        staged.write_bytes(uploaded.getvalue())
        with st.spinner("正在导入、截图并提取结构…"), get_session() as session:
            service = TemplateStudioService(session)
            try:
                result = service.import_pptx(
                    staged,
                    name=name.strip() or Path(uploaded.name).stem,
                )
                session.commit()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
                return
            except Exception as exc:  # noqa: BLE001
                st.error(format_user_error(exc))
                return
        st.session_state.template_studio_selected_id = str(result.template.id)
        st.success(
            f"已导入「{result.template.name}」：{len(result.template.layouts)} 页 · "
            f"截图 {result.screenshot_count} 张"
        )
        for warning in result.warnings:
            st.warning(warning)
        st.rerun()


def _render_template_list() -> None:
    st.markdown("#### 已保存模板")
    with get_session() as session:
        templates = TemplateStudioService(session).list_templates()
    if not templates:
        st.info("尚无模板。请先上传 PPTX。")
        return
    options = {f"{item.name} · {item.status.value} · {item.id}": item.id for item in templates}
    labels = list(options.keys())
    current = _selected_template_id()
    default_index = 0
    if current is not None:
        for index, template_id in enumerate(options.values()):
            if template_id == current:
                default_index = index
                break
    choice = st.selectbox("选择模板", labels, index=default_index)
    st.session_state.template_studio_selected_id = str(options[choice])


def _render_slot_overlay(layout) -> None:
    if layout.preview_image_path and Path(layout.preview_image_path).is_file():
        st.image(layout.preview_image_path, use_container_width=True)
    else:
        st.caption("暂无页面截图（可继续标注槽位）。")
    if not layout.slots:
        st.caption("尚无槽位。")
        return
    width = float(layout.page_width or 10)
    height = float(layout.page_height or 5.625)
    boxes: list[str] = []
    for slot in layout.slots:
        left = 100.0 * slot.x / width
        top = 100.0 * slot.y / height
        w = 100.0 * slot.width / width
        h = 100.0 * slot.height / height
        boxes.append(
            f"<div style='position:absolute;left:{left:.2f}%;top:{top:.2f}%;"
            f"width:{w:.2f}%;height:{h:.2f}%;border:2px solid #175cd3;"
            f"background:rgba(23,92,211,0.12);box-sizing:border-box;'>"
            f"<span style='font-size:11px;background:#175cd3;color:#fff;"
            f"padding:1px 4px;'>{slot.role.value}</span></div>"
        )
    st.markdown(
        "<div style='position:relative;width:100%;aspect-ratio:16/9;"
        "background:#faf9f7;border:1px solid #eceae4;border-radius:8px;'>"
        + "".join(boxes)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"{layout.name} · {layout.page_type.value} · 槽位 {len(layout.slots)}")


def _render_layout_editor(template_id: UUID) -> None:
    with get_session() as session:
        template = TemplateStudioService(session).get_template(template_id)
    if template is None:
        st.warning("模板不存在。")
        return

    st.markdown("#### 2–4. 分类、槽位与预览")
    st.write(
        f"**{template.name}** · 状态 `{template.status.value}` · "
        f"字体 {len(template.fonts)} · 颜色 {len(template.colors)} · "
        f"页面 {len(template.layouts)}"
    )
    if template.colors:
        st.caption("提取颜色：" + " · ".join(template.colors[:8]))
    if template.fonts:
        st.caption("提取字体：" + " · ".join(font.family for font in template.fonts[:8]))

    if not template.layouts:
        st.info("未提取到页面结构。")
        return

    page_labels = {
        f"P{layout.page_index + 1} · {layout.page_type.value} · {len(layout.slots)} 槽": layout.id
        for layout in template.layouts
    }
    selected_label = st.selectbox("页面", list(page_labels.keys()))
    layout_id = page_labels[selected_label]
    layout = template.layout_by_id(layout_id)
    assert layout is not None

    col_a, col_b = st.columns([1.4, 1.0], gap="medium")
    with col_a:
        _render_slot_overlay(layout)
    with col_b:
        page_type = st.selectbox(
            "页面类型",
            options=[item.value for item in TemplatePageType],
            index=[item.value for item in TemplatePageType].index(layout.page_type.value),
        )
        if st.button("保存页面分类", use_container_width=True):
            with get_session() as session:
                TemplateStudioService(session).update_page_type(
                    template_id,
                    layout_id,
                    TemplatePageType(page_type),
                )
                session.commit()
            st.success("已更新页面分类。")
            st.rerun()

        st.markdown("##### 槽位标注")
        for slot in layout.slots:
            with st.expander(f"{slot.role.value} · {slot.id}", expanded=False):
                role = st.selectbox(
                    "角色",
                    options=[item.value for item in TemplateSlotRole],
                    index=[item.value for item in TemplateSlotRole].index(slot.role.value),
                    key=f"slot_role_{layout_id}_{slot.id}",
                )
                required = st.checkbox(
                    "必填",
                    value=slot.required,
                    key=f"slot_req_{layout_id}_{slot.id}",
                )
                c1, c2 = st.columns(2)
                with c1:
                    x = st.number_input("X", value=float(slot.x), key=f"slot_x_{layout_id}_{slot.id}")
                    width = st.number_input(
                        "宽",
                        value=float(slot.width),
                        min_value=0.05,
                        key=f"slot_w_{layout_id}_{slot.id}",
                    )
                with c2:
                    y = st.number_input("Y", value=float(slot.y), key=f"slot_y_{layout_id}_{slot.id}")
                    height = st.number_input(
                        "高",
                        value=float(slot.height),
                        min_value=0.05,
                        key=f"slot_h_{layout_id}_{slot.id}",
                    )
                if st.button("保存槽位", key=f"save_slot_{layout_id}_{slot.id}"):
                    updated = slot.model_copy(
                        update={
                            "role": TemplateSlotRole(role),
                            "required": required,
                            "x": float(x),
                            "y": float(y),
                            "width": float(width),
                            "height": float(height),
                            "auto_detected": False,
                        }
                    )
                    with get_session() as session:
                        TemplateStudioService(session).upsert_slot(
                            template_id,
                            layout_id,
                            updated,
                        )
                        session.commit()
                    st.success("槽位已保存。")
                    st.rerun()
                if st.button("删除槽位", key=f"del_slot_{layout_id}_{slot.id}"):
                    with get_session() as session:
                        TemplateStudioService(session).delete_slot(
                            template_id,
                            layout_id,
                            slot.id,
                        )
                        session.commit()
                    st.rerun()

        with st.form(f"add_slot_{layout_id}"):
            st.caption("新增槽位")
            new_role = st.selectbox(
                "新槽位角色",
                options=[item.value for item in TemplateSlotRole],
                key=f"new_role_{layout_id}",
            )
            nx = st.number_input("新 X", value=0.7, key=f"new_x_{layout_id}")
            ny = st.number_input("新 Y", value=0.5, key=f"new_y_{layout_id}")
            nw = st.number_input("新 宽", value=3.0, min_value=0.05, key=f"new_w_{layout_id}")
            nh = st.number_input("新 高", value=0.6, min_value=0.05, key=f"new_h_{layout_id}")
            if st.form_submit_button("添加槽位"):
                new_slot = TemplateSlot(
                    id=f"manual_{layout.page_index}_{len(layout.slots) + 1}",
                    role=TemplateSlotRole(new_role),
                    x=float(nx),
                    y=float(ny),
                    width=float(nw),
                    height=float(nh),
                    auto_detected=False,
                    label=new_role,
                )
                with get_session() as session:
                    TemplateStudioService(session).upsert_slot(template_id, layout_id, new_slot)
                    session.commit()
                st.rerun()

    st.markdown("#### 5. 测试内容填充")
    if st.button("用测试内容填充并预览本页", type="primary"):
        with st.spinner("正在填充并渲染预览…"), get_session() as session:
            try:
                preview = TemplateStudioService(session).fill_test_content_preview(
                    template_id,
                    layout_id,
                )
                session.commit()
            except WorkflowError as exc:
                st.error(format_user_error(exc))
                return
        st.image(str(preview.preview_path), use_container_width=True)
        st.success(f"已生成测试填充预览：`{preview.preview_path.name}`")

    st.markdown("#### 6. 发布")
    if template.status != TemplateStatus.PUBLISHED:
        if st.button("发布 ArchitecturalTemplate", type="secondary"):
            with get_session() as session:
                try:
                    published = TemplateStudioService(session).publish(template_id)
                    session.commit()
                except WorkflowError as exc:
                    st.error(format_user_error(exc))
                    return
            st.success(f"已发布：{published.name}（v{published.version}）")
            st.rerun()
    else:
        st.success("模板已发布。")


def render() -> None:
    st.markdown("### 模板工作室")
    st.caption(
        "上传既有 PPTX → 截图与结构提取 → 页面分类 → 槽位人工标注 → "
        "测试内容填充 → 发布 ArchitecturalTemplate。"
    )
    _render_upload_panel()
    st.divider()
    _render_template_list()
    selected = _selected_template_id()
    if selected is not None:
        st.divider()
        _render_layout_editor(selected)
