"""
全局快捷操作系统

提供跨页面的快捷键、快速操作面板和命令调色板
"""

import streamlit as st
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ShortcutScope(Enum):
    """快捷键作用域"""
    GLOBAL = "global"  # 全局可用
    PAGE = "page"  # 仅当前页面
    MODAL = "modal"  # 仅在模态框中


@dataclass
class Shortcut:
    """快捷键定义"""
    key: str  # 快捷键组合，如 "Ctrl+S"
    description: str  # 功能描述
    action: str  # 操作标识
    scope: ShortcutScope = ShortcutScope.GLOBAL
    icon: str = "⚡"


@dataclass
class QuickAction:
    """快速操作定义"""
    id: str
    title: str
    description: str
    icon: str
    action: Callable
    category: str = "常用"
    keywords: List[str] = None


# 预定义的全局快捷键
GLOBAL_SHORTCUTS = [
    Shortcut(
        key="Ctrl+K",
        description="打开命令面板",
        action="open_command_palette",
        icon="🎯"
    ),
    Shortcut(
        key="Ctrl+N",
        description="新建项目",
        action="new_project",
        icon="➕"
    ),
    Shortcut(
        key="Ctrl+O",
        description="打开项目",
        action="open_project",
        icon="📂"
    ),
    Shortcut(
        key="Ctrl+S",
        description="保存当前工作",
        action="save_work",
        icon="💾"
    ),
    Shortcut(
        key="Ctrl+/",
        description="显示快捷键帮助",
        action="show_shortcuts",
        icon="❓"
    ),
    Shortcut(
        key="Ctrl+P",
        description="快速搜索页面",
        action="quick_search",
        icon="🔍"
    ),
]


def render_command_palette() -> None:
    """
    渲染命令调色板 - 类似 VS Code 的命令面板

    改进点：
    1. 快速搜索所有操作
    2. 模糊匹配
    3. 最近使用记录
    4. 快捷键提示
    """

    # 检查是否应该显示命令面板
    if not st.session_state.get("show_command_palette", False):
        return

    # 创建模态框效果
    st.markdown(
        """
        <style>
        .command-palette-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 999;
        }
        .command-palette {
            position: fixed;
            top: 20%;
            left: 50%;
            transform: translateX(-50%);
            width: 600px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            z-index: 1000;
            padding: 20px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.container():
        st.markdown("### 🎯 命令面板")

        # 搜索框
        search_query = st.text_input(
            "输入命令或功能名称...",
            placeholder="例如：新建项目、打开工作室、生成汇报...",
            key="command_palette_search",
            label_visibility="collapsed"
        )

        # 获取所有可用命令
        commands = _get_available_commands()

        # 过滤命令
        if search_query:
            filtered_commands = [
                cmd for cmd in commands
                if search_query.lower() in cmd["title"].lower()
                or search_query.lower() in cmd["description"].lower()
                or any(search_query.lower() in kw.lower() for kw in cmd.get("keywords", []))
            ]
        else:
            # 显示最近使用的命令
            recent_commands = st.session_state.get("recent_commands", [])
            filtered_commands = [
                cmd for cmd in commands
                if cmd["id"] in recent_commands[:5]
            ]

            if not filtered_commands:
                filtered_commands = commands[:10]  # 显示前10个

        # 显示命令列表
        st.markdown("---")

        if filtered_commands:
            for cmd in filtered_commands:
                col1, col2, col3 = st.columns([1, 5, 2])

                with col1:
                    st.markdown(f"## {cmd['icon']}")

                with col2:
                    st.markdown(f"**{cmd['title']}**")
                    st.caption(cmd["description"])

                with col3:
                    shortcut = cmd.get("shortcut", "")
                    if shortcut:
                        st.caption(f"`{shortcut}`")

                    if st.button("执行", key=f"cmd_{cmd['id']}", use_container_width=True):
                        _execute_command(cmd["id"])
                        st.session_state["show_command_palette"] = False
                        st.rerun()

                st.markdown("")

        else:
            st.info("未找到匹配的命令")

        # 关闭按钮
        st.markdown("---")
        if st.button("关闭 (Esc)", use_container_width=True, key="close_palette"):
            st.session_state["show_command_palette"] = False
            st.rerun()


def render_shortcuts_help() -> None:
    """
    渲染快捷键帮助面板

    改进点：
    1. 按类别分组
    2. 可打印的快捷键卡片
    3. 自定义快捷键设置
    """

    st.markdown("### ⌨️ 快捷键参考")

    # 按类别分组
    categories = {
        "导航": [
            ("Ctrl+K", "打开命令面板"),
            ("Ctrl+P", "快速搜索页面"),
            ("Ctrl+Home", "返回首页"),
            ("Ctrl+1~9", "切换到对应页面"),
        ],
        "项目": [
            ("Ctrl+N", "新建项目"),
            ("Ctrl+O", "打开项目"),
            ("Ctrl+W", "关闭项目"),
            ("Ctrl+Shift+D", "删除项目"),
        ],
        "编辑": [
            ("Ctrl+S", "保存"),
            ("Ctrl+Z", "撤销"),
            ("Ctrl+Y", "重做"),
            ("Ctrl+F", "查找"),
        ],
        "工作流": [
            ("Alt+M", "跳转到资料页面"),
            ("Alt+O", "跳转到大纲页面"),
            ("Alt+G", "跳转到生成页面"),
            ("Alt+E", "跳转到编辑页面"),
            ("Alt+D", "跳转到交付页面"),
        ],
    }

    for category, shortcuts in categories.items():
        with st.expander(f"📌 {category}", expanded=True):
            for key, desc in shortcuts:
                col1, col2 = st.columns([2, 3])

                with col1:
                    st.code(key, language=None)

                with col2:
                    st.caption(desc)


def render_quick_actions_panel() -> None:
    """
    渲染快速操作面板 - 浮动的快捷操作按钮

    改进点：
    1. 可折叠的浮动面板
    2. 上下文相关的快捷操作
    3. 自定义操作
    """

    # 检查是否显示快速操作面板
    if not st.session_state.get("show_quick_actions", True):
        return

    # 获取当前页面上下文
    current_page = st.session_state.get("current_page_key", "home")
    project_id = st.session_state.get("selected_project_id")

    # 根据上下文显示不同的快速操作
    quick_actions = _get_contextual_quick_actions(current_page, project_id)

    if not quick_actions:
        return

    # 浮动面板
    with st.sidebar:
        st.markdown("---")
        with st.expander("⚡ 快速操作", expanded=True):
            for action in quick_actions:
                if st.button(
                    f"{action['icon']} {action['title']}",
                    key=f"quick_action_{action['id']}",
                    use_container_width=True,
                    help=action["description"]
                ):
                    _execute_quick_action(action["id"])


def render_keyboard_shortcuts_indicator() -> None:
    """
    渲染键盘快捷键指示器 - 显示当前可用的快捷键

    改进点：
    1. 底部栏显示常用快捷键
    2. 上下文相关提示
    3. 动画提示新手使用
    """

    # 获取当前页面可用的快捷键
    current_shortcuts = _get_page_shortcuts(st.session_state.get("current_page_key", "home"))

    if not current_shortcuts:
        return

    # 在底部显示快捷键提示
    st.markdown("---")

    col1, col2 = st.columns([1, 5])

    with col1:
        st.caption("⌨️ 快捷键:")

    with col2:
        shortcuts_text = " · ".join([
            f"`{s['key']}` {s['description']}"
            for s in current_shortcuts[:3]
        ])
        st.caption(shortcuts_text)

        # 显示更多按钮
        if len(current_shortcuts) > 3:
            if st.button("查看全部", key="show_all_shortcuts"):
                st.session_state["show_shortcuts_help"] = True
                st.rerun()


def _get_available_commands() -> List[Dict[str, Any]]:
    """获取所有可用的命令"""

    commands = [
        {
            "id": "new_project",
            "title": "新建项目",
            "description": "创建一个新的建筑项目",
            "icon": "➕",
            "shortcut": "Ctrl+N",
            "keywords": ["创建", "项目", "新建"],
        },
        {
            "id": "open_project",
            "title": "打开项目",
            "description": "打开现有项目",
            "icon": "📂",
            "shortcut": "Ctrl+O",
            "keywords": ["打开", "项目", "切换"],
        },
        {
            "id": "goto_materials",
            "title": "资料管理",
            "description": "跳转到资料页面",
            "icon": "📚",
            "shortcut": "Alt+M",
            "keywords": ["资料", "上传", "文档"],
        },
        {
            "id": "goto_outline",
            "title": "编辑大纲",
            "description": "跳转到大纲编辑页面",
            "icon": "📝",
            "shortcut": "Alt+O",
            "keywords": ["大纲", "结构", "章节"],
        },
        {
            "id": "goto_generate",
            "title": "生成页面",
            "description": "跳转到页面生成",
            "icon": "🎨",
            "shortcut": "Alt+G",
            "keywords": ["生成", "AI", "自动"],
        },
        {
            "id": "goto_studio",
            "title": "打开工作室",
            "description": "在工作室中编辑页面",
            "icon": "✏️",
            "shortcut": "Alt+E",
            "keywords": ["工作室", "编辑", "画布"],
        },
        {
            "id": "goto_deliver",
            "title": "导出交付",
            "description": "导出 PPT 或 PDF",
            "icon": "📦",
            "shortcut": "Alt+D",
            "keywords": ["导出", "下载", "PPT", "PDF"],
        },
        {
            "id": "batch_retry",
            "title": "批量重试失败页面",
            "description": "重试所有生成失败的页面",
            "icon": "🔄",
            "keywords": ["批量", "重试", "失败"],
        },
        {
            "id": "save_work",
            "title": "保存工作",
            "description": "保存当前的编辑内容",
            "icon": "💾",
            "shortcut": "Ctrl+S",
            "keywords": ["保存", "存储"],
        },
        {
            "id": "template_library",
            "title": "浏览模板库",
            "description": "查看和使用模板",
            "icon": "🎨",
            "keywords": ["模板", "样式", "库"],
        },
    ]

    return commands


def _get_contextual_quick_actions(
    page_key: str,
    project_id: Optional[str]
) -> List[Dict[str, Any]]:
    """根据当前页面获取上下文相关的快速操作"""

    actions = []

    # 全局操作
    actions.append({
        "id": "command_palette",
        "title": "命令面板",
        "description": "打开命令面板 (Ctrl+K)",
        "icon": "🎯",
    })

    # 如果有选中的项目
    if project_id:
        actions.extend([
            {
                "id": "goto_materials",
                "title": "资料",
                "description": "管理项目资料",
                "icon": "📚",
            },
            {
                "id": "goto_outline",
                "title": "大纲",
                "description": "编辑汇报大纲",
                "icon": "📝",
            },
            {
                "id": "goto_generate",
                "title": "生成",
                "description": "生成页面内容",
                "icon": "🎨",
            },
        ])

    # 页面特定操作
    if page_key == "generate":
        actions.append({
            "id": "batch_retry",
            "title": "批量重试",
            "description": "重试失败的页面",
            "icon": "🔄",
        })

    elif page_key == "outline":
        actions.append({
            "id": "batch_edit",
            "title": "批量编辑",
            "description": "批量修改章节",
            "icon": "📦",
        })

    return actions


def _get_page_shortcuts(page_key: str) -> List[Dict[str, Any]]:
    """获取当前页面可用的快捷键"""

    # 全局快捷键
    shortcuts = [
        {"key": "Ctrl+K", "description": "命令面板"},
        {"key": "Ctrl+S", "description": "保存"},
        {"key": "Ctrl+/", "description": "快捷键帮助"},
    ]

    # 页面特定快捷键
    page_shortcuts = {
        "generate": [
            {"key": "R", "description": "重试失败"},
            {"key": "Shift+R", "description": "批量重试"},
        ],
        "outline": [
            {"key": "N", "description": "新建章节"},
            {"key": "E", "description": "批量编辑"},
        ],
        "studio": [
            {"key": "Space", "description": "预览/编辑切换"},
            {"key": "Z", "description": "缩放适应"},
        ],
    }

    if page_key in page_shortcuts:
        shortcuts.extend(page_shortcuts[page_key])

    return shortcuts


def _execute_command(command_id: str) -> None:
    """执行命令"""

    # 记录到最近使用
    recent = st.session_state.get("recent_commands", [])
    if command_id in recent:
        recent.remove(command_id)
    recent.insert(0, command_id)
    st.session_state["recent_commands"] = recent[:10]

    # 执行命令
    command_actions = {
        "new_project": lambda: st.switch_page("pages/project_genesis.py"),
        "open_project": lambda: st.switch_page("pages/project_management.py"),
        "goto_materials": lambda: st.switch_page("pages/flow/materials.py"),
        "goto_outline": lambda: st.switch_page("pages/flow/outline.py"),
        "goto_generate": lambda: st.switch_page("pages/flow/generate.py"),
        "goto_studio": lambda: st.switch_page("pages/flow/edit.py"),
        "goto_deliver": lambda: st.switch_page("pages/flow/deliver.py"),
        "template_library": lambda: st.switch_page("pages/template_library.py"),
        "batch_retry": lambda: st.session_state.update({"trigger_batch_retry": True}),
        "save_work": lambda: st.session_state.update({"trigger_save": True}),
    }

    action = command_actions.get(command_id)
    if action:
        action()


def _execute_quick_action(action_id: str) -> None:
    """执行快速操作"""

    if action_id == "command_palette":
        st.session_state["show_command_palette"] = True
        st.rerun()
    else:
        _execute_command(action_id)


def inject_keyboard_shortcuts() -> None:
    """
    注入键盘快捷键监听器

    使用 JavaScript 监听键盘事件，并触发 Streamlit 状态更新
    """

    shortcuts_js = """
    <script>
    document.addEventListener('keydown', function(event) {
        // Ctrl+K - 命令面板
        if (event.ctrlKey && event.key === 'k') {
            event.preventDefault();
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: {action: 'command_palette'}}, '*');
        }

        // Ctrl+S - 保存
        if (event.ctrlKey && event.key === 's') {
            event.preventDefault();
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: {action: 'save'}}, '*');
        }

        // Ctrl+/ - 快捷键帮助
        if (event.ctrlKey && event.key === '/') {
            event.preventDefault();
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: {action: 'shortcuts_help'}}, '*');
        }

        // Esc - 关闭模态框
        if (event.key === 'Escape') {
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: {action: 'close_modal'}}, '*');
        }
    });
    </script>
    """

    st.markdown(shortcuts_js, unsafe_allow_html=True)
