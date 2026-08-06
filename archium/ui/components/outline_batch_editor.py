"""Outline 批量编辑组件 - 提供批量修改页面属性的UI。"""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.batch_operations import OutlineBatchOperations
from archium.application.unit_of_work import unit_of_work
from archium.domain.visual.visual_grammar import PageArchetype


def render_outline_batch_editor(
    project_id: UUID,
    outline,
) -> None:
    """渲染大纲批量编辑面板。

    Args:
        project_id: 项目ID
        outline: 大纲对象
    """
    if not outline or not outline.sections:
        st.info("暂无章节可编辑")
        return

    st.markdown("### 批量编辑")
    st.caption("选择要批量修改的章节或页面，然后应用统一的属性。")

    # 选择编辑目标
    target = st.radio(
        "编辑目标",
        options=["章节", "页面意图"],
        horizontal=True,
        key="batch_edit_target",
    )

    if target == "章节":
        _render_section_batch_editor(outline)
    else:
        _render_intent_batch_editor(outline)


def _render_section_batch_editor(outline) -> None:
    """渲染章节批量编辑器。"""
    sections = sorted(outline.sections, key=lambda s: s.order)

    # 选择要编辑的章节
    st.markdown("#### 选择章节")
    selected_sections = []

    for section in sections:
        if st.checkbox(
            f"{section.order + 1}. {section.title}",
            key=f"batch_section_{section.id}",
        ):
            selected_sections.append(section)

    if not selected_sections:
        st.info("请至少选择一个章节")
        return

    st.markdown(f"**已选择**: {len(selected_sections)} 个章节")

    # 选择要修改的属性
    st.markdown("#### 修改属性")

    property_type = st.selectbox(
        "属性类型",
        options=[
            "页面类型 (category)",
            "页数 (estimated_slide_count)",
            "是否必需 (required)",
        ],
        key="batch_section_property",
    )

    new_value = None

    if "页面类型" in property_type:
        new_value = st.selectbox(
            "新页面类型",
            options=["general", "title", "content", "comparison", "data", "summary"],
            key="batch_section_category",
        )
    elif "页数" in property_type:
        new_value = st.number_input(
            "新页数",
            min_value=1,
            max_value=20,
            value=3,
            key="batch_section_count",
        )
    elif "是否必需" in property_type:
        new_value = st.checkbox("必需", value=True, key="batch_section_required")

    # 执行批量修改
    if st.button(
        f"应用到 {len(selected_sections)} 个章节",
        type="primary",
        use_container_width=True,
        key="apply_batch_section",
    ):
        _execute_section_batch_update(
            selected_sections,
            property_type,
            new_value,
        )


def _render_intent_batch_editor(outline) -> None:
    """渲染页面意图批量编辑器。"""
    if not outline.page_intents:
        st.info("暂无页面意图可编辑")
        return

    intents = sorted(outline.page_intents, key=lambda i: i.order)

    # 选择要编辑的意图
    st.markdown("#### 选择页面")
    selected_intents = []

    for intent in intents:
        title = intent.notes or intent.page_task or f"第 {intent.order + 1} 页"
        if st.checkbox(
            f"{intent.order + 1}. {title}",
            key=f"batch_intent_{intent.order}",
        ):
            selected_intents.append(intent)

    if not selected_intents:
        st.info("请至少选择一个页面")
        return

    st.markdown(f"**已选择**: {len(selected_intents)} 页")

    # 选择要修改的属性
    st.markdown("#### 修改属性")

    property_type = st.selectbox(
        "属性类型",
        options=[
            "页面原型 (page_archetype)",
            "预期布局 (expected_layout)",
        ],
        key="batch_intent_property",
    )

    new_value = None

    if "页面原型" in property_type:
        archetype_options = [a.value for a in PageArchetype]
        new_value = st.selectbox(
            "新页面原型",
            options=archetype_options,
            format_func=lambda x: x.replace("_", " ").title(),
            key="batch_intent_archetype",
        )
    elif "预期布局" in property_type:
        new_value = st.selectbox(
            "新预期布局",
            options=["title", "content", "comparison", "image_grid", "data"],
            key="batch_intent_layout",
        )

    # 执行批量修改
    if st.button(
        f"应用到 {len(selected_intents)} 页",
        type="primary",
        use_container_width=True,
        key="apply_batch_intent",
    ):
        _execute_intent_batch_update(
            selected_intents,
            property_type,
            new_value,
        )


def _execute_section_batch_update(
    sections: list,
    property_type: str,
    new_value,
) -> None:
    """执行章节批量更新。"""
    from archium.ui.components.enhanced_ui import render_error_message

    property_map = {
        "页面类型": "category",
        "页数": "estimated_slide_count",
        "是否必需": "required",
    }

    property_name = None
    for key, value in property_map.items():
        if key in property_type:
            property_name = value
            break

    if not property_name:
        st.error("未知的属性类型")
        return

    section_ids = [section.id for section in sections]

    with st.spinner(f"正在批量更新 {len(section_ids)} 个章节..."):
        try:
            with unit_of_work() as uow:
                batch_ops = OutlineBatchOperations(uow)
                result = batch_ops.batch_update_section_property(
                    section_ids,
                    property_name,
                    new_value,
                )

            # 显示结果
            if result.all_succeeded:
                st.success(f"✅ 全部更新成功！共 {result.success_count} 个章节")
                st.balloons()
                st.rerun()
            elif result.any_succeeded:
                st.warning(
                    f"⚠️ 部分成功：{result.success_count} 成功，{result.failure_count} 失败"
                )
            else:
                st.error(f"❌ 批量更新失败")

        except Exception as e:
            render_error_message(
                e,
                title="批量更新失败",
                show_details=True,
            )


def _execute_intent_batch_update(
    intents: list,
    property_type: str,
    new_value,
) -> None:
    """执行页面意图批量更新。"""
    from archium.ui.components.enhanced_ui import render_error_message

    property_map = {
        "页面原型": "page_archetype",
        "预期布局": "expected_layout",
    }

    property_name = None
    for key, value in property_map.items():
        if key in property_type:
            property_name = value
            break

    if not property_name:
        st.error("未知的属性类型")
        return

    intent_orders = [intent.order for intent in intents]

    with st.spinner(f"正在批量更新 {len(intent_orders)} 个页面..."):
        try:
            with unit_of_work() as uow:
                batch_ops = OutlineBatchOperations(uow)

                if property_name == "page_archetype":
                    result = batch_ops.batch_update_page_archetype(
                        intent_orders,
                        new_value,
                    )
                else:
                    # 其他属性的通用更新逻辑
                    result = batch_ops.batch_update_page_archetype(
                        intent_orders,
                        new_value,
                    )

            # 显示结果
            if result.all_succeeded:
                st.success(f"✅ 全部更新成功！共 {result.success_count} 页")
                st.balloons()
                st.rerun()
            elif result.any_succeeded:
                st.warning(
                    f"⚠️ 部分成功：{result.success_count} 成功，{result.failure_count} 失败"
                )
            else:
                st.error(f"❌ 批量更新失败")

        except Exception as e:
            render_error_message(
                e,
                title="批量更新失败",
                show_details=True,
            )
