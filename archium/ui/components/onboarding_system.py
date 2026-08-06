"""
新手引导和帮助系统

提供首次使用引导、交互式教程和上下文帮助
"""

import streamlit as st
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class OnboardingStep(Enum):
    """引导步骤"""
    WELCOME = "welcome"
    CREATE_PROJECT = "create_project"
    UPLOAD_MATERIALS = "upload_materials"
    EDIT_OUTLINE = "edit_outline"
    GENERATE_SLIDES = "generate_slides"
    EDIT_STUDIO = "edit_studio"
    EXPORT = "export"
    COMPLETE = "complete"


@dataclass
class GuideStep:
    """引导步骤定义"""
    id: str
    title: str
    description: str
    icon: str
    page: str  # 对应的页面
    action: Optional[str] = None  # 可执行的操作
    tips: List[str] = None  # 提示信息


# 新手引导流程
ONBOARDING_STEPS = [
    GuideStep(
        id="welcome",
        title="欢迎使用 Archium",
        description="Archium 是专为建筑师设计的智能汇报制作工具，让您轻松创建专业的建筑汇报文档。",
        icon="👋",
        page="home",
        tips=[
            "📚 5 分钟快速上手教程",
            "🎨 精美的设计模板",
            "🤖 AI 智能生成内容",
            "⚡ 批量操作提升效率",
        ]
    ),
    GuideStep(
        id="create_project",
        title="创建项目",
        description="描述您的项目，Archium 会理解您的需求并建议下一步操作。",
        icon="➕",
        page="project_genesis",
        action="创建第一个项目",
        tips=[
            "用自然语言描述项目即可",
            "不需要完整的项目背景",
            "系统会判断现有信息的完整度",
            "可以随时补充更多细节",
        ]
    ),
    GuideStep(
        id="upload_materials",
        title="上传资料",
        description="上传项目相关的文档、图片等资料，系统会自动提取关键信息。",
        icon="📚",
        page="materials",
        action="上传资料",
        tips=[
            "支持 PDF、Word、图片等格式",
            "自动提取事实和数据",
            "可以随时添加新资料",
            "资料会自动整理到知识库",
        ]
    ),
    GuideStep(
        id="edit_outline",
        title="编辑大纲",
        description="调整汇报的结构和章节安排，定义每页的内容意图。",
        icon="📝",
        page="outline",
        action="编辑大纲",
        tips=[
            "拖拽调整章节顺序",
            "批量修改章节属性",
            "预览大纲结构",
            "可以添加或删除章节",
        ]
    ),
    GuideStep(
        id="generate_slides",
        title="生成页面",
        description="AI 根据大纲和资料自动生成页面内容。",
        icon="🎨",
        page="generate",
        action="开始生成",
        tips=[
            "自动生成所有页面",
            "失败页面可批量重试",
            "实时查看生成进度",
            "生成后可继续编辑",
        ]
    ),
    GuideStep(
        id="edit_studio",
        title="工作室编辑",
        description="在可视化工作室中调整页面布局和内容。",
        icon="✏️",
        page="studio",
        action="打开工作室",
        tips=[
            "可视化编辑画布",
            "拖拽调整元素位置",
            "实时预览效果",
            "支持多种布局模板",
        ]
    ),
    GuideStep(
        id="export",
        title="导出交付",
        description="将汇报导出为 PowerPoint 或 PDF 格式。",
        icon="📦",
        page="deliver",
        action="导出汇报",
        tips=[
            "支持 PPTX 和 PDF 格式",
            "保留所有格式和样式",
            "可以多次导出",
            "支持自定义模板",
        ]
    ),
    GuideStep(
        id="complete",
        title="完成引导",
        description="恭喜！您已经掌握了 Archium 的基本使用方法。",
        icon="🎉",
        page="home",
        tips=[
            "可以创建更多项目",
            "探索高级功能",
            "查看帮助文档",
            "随时可以重新查看引导",
        ]
    ),
]


def render_onboarding_welcome() -> None:
    """
    渲染欢迎引导页面

    改进点：
    1. 友好的欢迎界面
    2. 清晰的流程概览
    3. 可跳过选项
    """

    # 居中布局
    col1, col2, col3 = st.columns([1, 3, 1])

    with col2:
        # 欢迎标题
        st.markdown(
            "<h1 style='text-align: center;'>👋 欢迎使用 Archium</h1>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align: center; font-size: 18px; color: #666;'>"
            "专为建筑师设计的智能汇报制作工具"
            "</p>",
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # 特色功能
        st.markdown("### ✨ 核心特性")

        features = [
            ("🤖", "AI 智能生成", "根据项目资料自动生成汇报内容"),
            ("📚", "资料管理", "智能整理和提取项目文档信息"),
            ("🎨", "可视化编辑", "直观的画布编辑和实时预览"),
            ("⚡", "批量操作", "提升10倍工作效率的批量功能"),
        ]

        for icon, title, desc in features:
            col_icon, col_text = st.columns([1, 5])
            with col_icon:
                st.markdown(f"## {icon}")
            with col_text:
                st.markdown(f"**{title}**")
                st.caption(desc)
            st.markdown("")

        st.markdown("---")

        # 开始选项
        st.markdown("### 🚀 开始使用")

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button(
                "📖 查看快速教程 (5分钟)",
                use_container_width=True,
                type="primary",
                key="start_tutorial"
            ):
                st.session_state["onboarding_active"] = True
                st.session_state["onboarding_step"] = 0
                st.rerun()

        with col_b:
            if st.button(
                "🚀 直接开始创建",
                use_container_width=True,
                key="skip_tutorial"
            ):
                st.session_state["onboarding_completed"] = True
                st.switch_page("pages/project_genesis.py")

        st.markdown("<br>", unsafe_allow_html=True)

        # 额外选项
        with st.expander("💡 我有问题", expanded=False):
            st.markdown("""
            **常见问题：**

            - **Q: Archium 适合什么样的项目？**
              A: 适合各类建筑项目，从概念方案到施工图汇报都可以使用。

            - **Q: 需要准备什么资料？**
              A: 可以从零开始，也可以上传现有的文档、图片、CAD图纸等。

            - **Q: 如何保证数据安全？**
              A: 所有数据存储在本地，您完全掌控自己的项目文件。

            - **Q: 能导出什么格式？**
              A: 支持 PowerPoint (.pptx) 和 PDF 格式。
            """)

            if st.button("查看完整帮助文档", use_container_width=True):
                st.session_state["show_help_docs"] = True
                st.rerun()


def render_onboarding_progress(current_step: int) -> None:
    """
    渲染引导进度条

    改进点：
    1. 可视化进度
    2. 步骤导航
    3. 可跳过或重新开始
    """

    total_steps = len(ONBOARDING_STEPS)
    progress = current_step / total_steps

    st.markdown("### 📚 快速教程")

    # 进度条
    st.progress(progress, text=f"步骤 {current_step + 1} / {total_steps}")

    # 步骤指示器
    cols = st.columns(total_steps)

    for i, col in enumerate(cols):
        with col:
            if i < current_step:
                st.markdown(f"<div style='text-align: center;'>✅</div>", unsafe_allow_html=True)
            elif i == current_step:
                st.markdown(f"<div style='text-align: center;'>👉</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: center;'>⚪</div>", unsafe_allow_html=True)

    st.markdown("---")


def render_onboarding_step(step_index: int) -> None:
    """
    渲染当前引导步骤

    改进点：
    1. 清晰的步骤说明
    2. 可交互的演示
    3. 实用的提示
    """

    if step_index >= len(ONBOARDING_STEPS):
        render_onboarding_complete()
        return

    step = ONBOARDING_STEPS[step_index]

    # 步骤头部
    col1, col2 = st.columns([1, 5])

    with col1:
        st.markdown(f"<div style='font-size: 60px; text-align: center;'>{step.icon}</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(f"### {step.title}")
        st.markdown(step.description)

    st.markdown("---")

    # 提示信息
    if step.tips:
        st.markdown("**💡 要点：**")
        for tip in step.tips:
            st.markdown(f"- {tip}")

        st.markdown("")

    # 操作按钮
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        if step.action and step_index < len(ONBOARDING_STEPS) - 1:
            if st.button(
                f"▶️ {step.action}",
                use_container_width=True,
                type="primary",
                key=f"action_{step.id}"
            ):
                # 跳转到对应页面
                _navigate_to_step_page(step.page)

    with col2:
        if st.button(
            "➡️ 下一步",
            use_container_width=True,
            key=f"next_{step.id}"
        ):
            st.session_state["onboarding_step"] = step_index + 1
            st.rerun()

    with col3:
        if st.button(
            "⏭️ 跳过教程",
            use_container_width=True,
            key=f"skip_{step.id}"
        ):
            st.session_state["onboarding_completed"] = True
            st.session_state["onboarding_active"] = False
            st.rerun()

    # 演示视频或图片（可选）
    if step_index in [1, 3, 4, 5]:  # 关键步骤显示演示
        with st.expander("🎬 查看演示", expanded=False):
            st.info(f"这里可以放置 {step.title} 的演示视频或截图")


def render_onboarding_complete() -> None:
    """
    渲染引导完成页面

    改进点：
    1. 庆祝动画
    2. 下一步建议
    3. 继续学习资源
    """

    col1, col2, col3 = st.columns([1, 3, 1])

    with col2:
        st.markdown(
            "<h1 style='text-align: center;'>🎉 恭喜完成！</h1>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align: center; font-size: 18px;'>"
            "您已经掌握了 Archium 的基本使用方法"
            "</p>",
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # 下一步建议
        st.markdown("### 🚀 接下来可以")

        suggestions = [
            ("➕ 创建第一个真实项目", "project_genesis"),
            ("📚 浏览模板库", "template_library"),
            ("🛠️ 探索工具中心", "tool_hub"),
            ("📖 查看完整文档", "help_docs"),
        ]

        for title, action in suggestions:
            if st.button(title, use_container_width=True, key=f"suggest_{action}"):
                _handle_suggestion_action(action)

        st.markdown("---")

        # 反馈
        st.markdown("### 💬 给我们反馈")
        st.caption("您的意见能帮助我们做得更好")

        feedback = st.text_area(
            "分享您的体验或建议",
            placeholder="例如：教程很清晰，但希望有更多实际案例...",
            key="onboarding_feedback"
        )

        if st.button("提交反馈", use_container_width=True, key="submit_feedback"):
            if feedback:
                # 保存反馈
                st.session_state["onboarding_feedback_submitted"] = True
                st.success("感谢您的反馈！")
            else:
                st.warning("请输入反馈内容")

        # 标记为完成
        st.session_state["onboarding_completed"] = True
        st.session_state["onboarding_active"] = False


def render_contextual_help(page_key: str) -> None:
    """
    渲染上下文相关的帮助信息

    改进点：
    1. 页面特定的帮助
    2. 常见问题
    3. 快捷操作提示
    """

    help_content = _get_page_help_content(page_key)

    if not help_content:
        return

    with st.sidebar:
        with st.expander("❓ 页面帮助", expanded=False):
            st.markdown(f"**{help_content['title']}**")
            st.caption(help_content["description"])

            if help_content.get("tips"):
                st.markdown("**💡 提示：**")
                for tip in help_content["tips"]:
                    st.caption(f"• {tip}")

            if help_content.get("shortcuts"):
                st.markdown("**⌨️ 快捷键：**")
                for shortcut in help_content["shortcuts"]:
                    st.caption(f"• `{shortcut['key']}` - {shortcut['desc']}")

            if help_content.get("related_pages"):
                st.markdown("**🔗 相关页面：**")
                for page in help_content["related_pages"]:
                    if st.button(page["title"], key=f"help_goto_{page['key']}"):
                        st.switch_page(f"pages/{page['key']}.py")


def render_help_tooltip(text: str, help_text: str) -> None:
    """
    渲染带帮助提示的文本

    改进点：
    1. 悬浮提示
    2. 详细说明
    3. 可点击查看更多
    """

    col1, col2 = st.columns([10, 1])

    with col1:
        st.markdown(text)

    with col2:
        with st.popover("❓"):
            st.caption(help_text)


def check_and_show_onboarding() -> bool:
    """
    检查是否需要显示引导，并渲染引导界面

    返回：是否正在显示引导
    """

    # 检查是否已完成引导
    if st.session_state.get("onboarding_completed", False):
        return False

    # 检查是否是首次使用
    is_first_time = not st.session_state.get("has_visited_before", False)

    # 如果是首次使用，显示欢迎页面
    if is_first_time and not st.session_state.get("onboarding_active", False):
        render_onboarding_welcome()
        st.session_state["has_visited_before"] = True
        return True

    # 如果引导已激活，显示引导步骤
    if st.session_state.get("onboarding_active", False):
        current_step = st.session_state.get("onboarding_step", 0)
        render_onboarding_progress(current_step)
        render_onboarding_step(current_step)
        return True

    return False


def _navigate_to_step_page(page_key: str) -> None:
    """导航到引导步骤对应的页面"""

    page_map = {
        "home": "pages/home.py",
        "project_genesis": "pages/project_genesis.py",
        "materials": "pages/flow/materials.py",
        "outline": "pages/flow/outline.py",
        "generate": "pages/flow/generate.py",
        "studio": "pages/flow/edit.py",
        "deliver": "pages/flow/deliver.py",
    }

    page_path = page_map.get(page_key, "pages/home.py")
    st.switch_page(page_path)


def _handle_suggestion_action(action: str) -> None:
    """处理完成页面的建议操作"""

    if action == "project_genesis":
        st.switch_page("pages/project_genesis.py")
    elif action == "template_library":
        st.switch_page("pages/template_library.py")
    elif action == "tool_hub":
        st.switch_page("pages/tool_hub.py")
    elif action == "help_docs":
        st.session_state["show_help_docs"] = True
        st.rerun()


def _get_page_help_content(page_key: str) -> Optional[Dict[str, Any]]:
    """获取页面的帮助内容"""

    help_contents = {
        "materials": {
            "title": "资料管理",
            "description": "上传和管理项目相关的文档、图片等资料",
            "tips": [
                "支持拖拽上传多个文件",
                "自动提取文本和图片",
                "可以随时添加新资料",
            ],
            "shortcuts": [
                {"key": "Ctrl+U", "desc": "快速上传"},
            ],
            "related_pages": [
                {"title": "编辑大纲", "key": "flow/outline"},
            ],
        },
        "outline": {
            "title": "大纲编辑",
            "description": "调整汇报结构和章节安排",
            "tips": [
                "使用批量操作提高效率",
                "拖拽调整章节顺序",
                "预览大纲结构",
            ],
            "shortcuts": [
                {"key": "N", "desc": "新建章节"},
                {"key": "E", "desc": "批量编辑"},
            ],
            "related_pages": [
                {"title": "生成页面", "key": "flow/generate"},
            ],
        },
        "generate": {
            "title": "生成页面",
            "description": "AI 自动生成页面内容",
            "tips": [
                "失败页面可批量重试",
                "实时查看生成进度",
                "生成后可在工作室编辑",
            ],
            "shortcuts": [
                {"key": "R", "desc": "重试失败"},
                {"key": "Shift+R", "desc": "批量重试"},
            ],
            "related_pages": [
                {"title": "工作室编辑", "key": "flow/edit"},
            ],
        },
    }

    return help_contents.get(page_key)
