"""Standalone demo for Canvas Editor component."""


import streamlit as st


# Mock LayoutPlan for demo purposes
class MockElement:
    def __init__(self, id: str, x: float, y: float, width: float, height: float, role: str, locked: bool = False):
        self.id = id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.role = role
        self.locked = locked
        self.text_content = f"Sample text for {id}"

class MockLayoutPlan:
    def __init__(self):
        self.page_width = 10.0
        self.page_height = 5.625
        self.elements = [
            MockElement("hero", 1.0, 0.5, 6.0, 4.0, "HERO_VISUAL"),
            MockElement("title", 7.5, 0.5, 2.0, 0.8, "TITLE", locked=True),
            MockElement("body", 7.5, 1.5, 2.0, 2.5, "BODY"),
            MockElement("caption", 7.5, 4.2, 2.0, 0.5, "CAPTION"),
        ]

st.set_page_config(page_title="Canvas Editor Demo", layout="wide")

st.title("🎨 Canvas Editor Component Demo")

st.markdown("""
这是 Canvas Editor 组件的独立演示。

**功能**:
- ✅ 点击元素进行选择
- ✅ 悬停显示元素信息
- ✅ 颜色编码元素类型
- ✅ 显示锁定状态

**使用方法**:
1. 点击画布上的元素进行选择
2. 悬停查看元素信息
3. 点击空白区域取消选择
""")

# Configuration
col1, col2, col3 = st.columns(3)
with col1:
    show_labels = st.checkbox("显示元素标签", value=True)
with col2:
    show_all_borders = st.checkbox("显示所有边界", value=True)
with col3:
    use_mock_image = st.checkbox("使用占位图", value=True)

st.divider()

# Initialize session state
if "selected_element" not in st.session_state:
    st.session_state.selected_element = None

# Try to import the component
try:
    from archium.ui.components.canvas_editor import canvas_editor

    # Create mock layout plan
    layout_plan = MockLayoutPlan()

    # Use placeholder image or real path
    if use_mock_image:
        image_url = "https://via.placeholder.com/1600x900/f0f0f0/666666?text=Slide+Preview"
    else:
        image_url = st.text_input("图片 URL", "path/to/your/image.png")

    # Render canvas
    st.subheader("交互式画布")

    selected_element_id = canvas_editor(
        image_url=image_url,
        layout_plan=layout_plan,
        selected_element_id=st.session_state.selected_element,
        show_labels=show_labels,
        show_all_borders=show_all_borders,
        key="demo_canvas",
    )

    # Handle selection change
    if selected_element_id != st.session_state.selected_element:
        st.session_state.selected_element = selected_element_id
        st.rerun()

    # Display selection info
    st.divider()

    if st.session_state.selected_element:
        st.success(f"✅ 已选择: **{st.session_state.selected_element}**")

        # Find selected element
        selected = next(
            (e for e in layout_plan.elements if e.id == st.session_state.selected_element),
            None
        )

        if selected:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("角色", selected.role)
            with col2:
                st.metric("位置", f"({selected.x:.1f}, {selected.y:.1f})")
            with col3:
                st.metric("尺寸", f"{selected.width:.1f} × {selected.height:.1f}")
            with col4:
                st.metric("状态", "🔒 锁定" if selected.locked else "✏️ 可编辑")
    else:
        st.info("💡 点击画布上的元素进行选择")

    # Element list
    with st.expander("📋 元素列表", expanded=True):
        for element in layout_plan.elements:
            is_selected = element.id == st.session_state.selected_element
            status = "🔒" if element.locked else "✏️"
            selected_marker = "→ " if is_selected else "   "

            if st.button(
                f"{selected_marker}{status} {element.role}: {element.id}",
                key=f"btn_{element.id}",
                use_container_width=True,
            ):
                st.session_state.selected_element = element.id
                st.rerun()

except ImportError as e:
    st.error(f"""
    ❌ **Canvas Editor 组件未安装或未构建**

    错误: {e}

    **解决方法**:
    1. 确保组件已安装在正确的路径
    2. 运行构建脚本:
       ```bash
       cd archium/ui/components/canvas_editor
       bash build.sh
       ```
    3. 重新运行此演示
    """)

    st.info("""
    **开发模式**:

    如果你正在开发组件，可以:
    1. 在 `frontend/` 目录运行 `npm start`
    2. 在 `__init__.py` 中设置 `_RELEASE = False`
    3. 重新运行此演示
    """)

st.divider()

st.markdown("""
---
**提示**:
- 不同颜色代表不同的元素类型
- 锁定的元素显示 🔒 图标且无法编辑
- 选中的元素显示蓝色粗边框
- 悬停时边框会加粗
""")
