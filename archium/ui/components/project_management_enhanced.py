"""
项目管理页面增强组件

改进项目列表展示、筛选和操作体验
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum


class ProjectSortKey(Enum):
    """项目排序键"""
    UPDATED_DESC = "最近更新"
    CREATED_DESC = "创建时间"
    NAME_ASC = "名称 A-Z"
    NAME_DESC = "名称 Z-A"


class ProjectFilterType(Enum):
    """项目筛选类型"""
    ALL = "全部项目"
    RECENT = "最近7天"
    THIS_MONTH = "本月"
    ARCHIVED = "已归档"


def render_project_list_header(
    total_count: int,
    filtered_count: Optional[int] = None
) -> None:
    """
    渲染项目列表头部 - 统计和快速操作

    改进点：
    1. 清晰的项目统计
    2. 快速创建入口
    3. 搜索和筛选控制
    """

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        st.markdown("### 📁 我的项目")
        if filtered_count is not None and filtered_count < total_count:
            st.caption(f"显示 {filtered_count} / {total_count} 个项目")
        else:
            st.caption(f"共 {total_count} 个项目")

    with col2:
        # 搜索框
        search_query = st.text_input(
            "搜索项目",
            placeholder="搜索项目名称或描述...",
            label_visibility="collapsed",
            key="project_search_query"
        )

    with col3:
        # 创建新项目按钮
        if st.button("➕ 新建项目", type="primary", use_container_width=True):
            st.session_state["show_create_project_form"] = True
            st.rerun()


def render_project_filters() -> Dict[str, Any]:
    """
    渲染项目筛选和排序控件

    改进点：
    1. 多维度筛选
    2. 灵活排序
    3. 视图切换

    返回：筛选和排序配置
    """

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        filter_type = st.selectbox(
            "筛选",
            options=[f.value for f in ProjectFilterType],
            index=0,
            label_visibility="collapsed",
            key="project_filter_type"
        )

    with col2:
        sort_key = st.selectbox(
            "排序",
            options=[s.value for s in ProjectSortKey],
            index=0,
            label_visibility="collapsed",
            key="project_sort_key"
        )

    with col3:
        view_mode = st.radio(
            "视图",
            options=["卡片", "列表"],
            horizontal=True,
            label_visibility="collapsed",
            key="project_view_mode"
        )

    return {
        "filter_type": filter_type,
        "sort_key": sort_key,
        "view_mode": view_mode,
        "search_query": st.session_state.get("project_search_query", "")
    }


def render_enhanced_project_card(
    project: Dict[str, Any],
    show_stats: bool = True
) -> Optional[str]:
    """
    渲染增强版项目卡片 - 更丰富的信息和操作

    改进点：
    1. 项目状态徽章
    2. 进度指示
    3. 快速操作菜单
    4. 最近活动预览

    返回：点击的操作类型（"open"/"edit"/"delete"/"archive"）
    """

    project_id = project.get("id", "")
    project_name = project.get("name", "未命名项目")
    description = project.get("description", "")
    created_at = project.get("created_at")
    updated_at = project.get("updated_at")

    # 计算项目活跃度
    if updated_at:
        days_ago = (datetime.now() - updated_at).days
        if days_ago == 0:
            activity_label = "今天活跃"
            activity_color = "🟢"
        elif days_ago <= 7:
            activity_label = f"{days_ago} 天前"
            activity_color = "🟡"
        elif days_ago <= 30:
            activity_label = f"{days_ago} 天前"
            activity_color = "🟠"
        else:
            activity_label = f"{days_ago} 天前"
            activity_color = "⚪"
    else:
        activity_label = "未知"
        activity_color = "⚪"

    with st.container():
        # 卡片头部
        col1, col2 = st.columns([5, 1])

        with col1:
            st.markdown(f"### {project_name}")

            # 状态徽章和活跃度
            badge_col1, badge_col2, badge_col3 = st.columns([1, 1, 3])
            with badge_col1:
                st.caption(f"{activity_color} {activity_label}")
            with badge_col2:
                # 项目阶段徽章
                stage = project.get("lifecycle_stage", "unknown")
                stage_labels = {
                    "IDEA": "💡 构思",
                    "CONCEPT": "🎨 方案",
                    "SCHEMATIC": "📐 初设",
                    "DETAILED": "📋 详设",
                }
                st.caption(stage_labels.get(stage, ""))

        with col2:
            # 操作菜单
            with st.popover("⋮", use_container_width=True):
                if st.button("📂 打开", key=f"open_{project_id}", use_container_width=True):
                    return "open"

                if st.button("✏️ 编辑", key=f"edit_{project_id}", use_container_width=True):
                    return "edit"

                if st.button("📦 归档", key=f"archive_{project_id}", use_container_width=True):
                    return "archive"

                st.divider()

                if st.button("🗑️ 删除", key=f"delete_{project_id}", use_container_width=True):
                    return "delete"

        # 项目描述
        if description:
            with st.expander("📝 描述", expanded=False):
                st.caption(description[:200] + ("..." if len(description) > 200 else ""))
        else:
            st.caption("_暂无描述_")

        # 项目统计（如果启用）
        if show_stats:
            st.markdown("---")

            col1, col2, col3, col4 = st.columns(4)

            # 这些数据需要从实际项目中获取
            presentations = project.get("presentation_count", 0)
            materials = project.get("material_count", 0)
            slides = project.get("slide_count", 0)

            with col1:
                st.metric("汇报", presentations)

            with col2:
                st.metric("资料", materials)

            with col3:
                st.metric("页面", slides)

            with col4:
                # 完成度
                completion = project.get("completion_percentage", 0)
                st.metric("完成度", f"{completion}%")

        # 快速操作按钮
        st.markdown("")
        btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 2])

        with btn_col1:
            if st.button(
                "📂 打开项目",
                key=f"open_btn_{project_id}",
                use_container_width=True,
                type="primary"
            ):
                return "open"

        with btn_col2:
            if st.button(
                "✏️ 编辑信息",
                key=f"edit_btn_{project_id}",
                use_container_width=True
            ):
                return "edit"

        with btn_col3:
            if st.button(
                "📊 查看详情",
                key=f"details_btn_{project_id}",
                use_container_width=True
            ):
                return "details"

        st.divider()

    return None


def render_project_list_view(
    project: Dict[str, Any]
) -> Optional[str]:
    """
    渲染列表视图的项目条目 - 紧凑展示

    改进点：
    1. 单行紧凑布局
    2. 关键信息突出
    3. 快速操作按钮
    """

    project_id = project.get("id", "")
    project_name = project.get("name", "未命名项目")
    updated_at = project.get("updated_at")

    # 计算更新时间
    if updated_at:
        days_ago = (datetime.now() - updated_at).days
        if days_ago == 0:
            time_label = "今天"
        elif days_ago == 1:
            time_label = "昨天"
        elif days_ago <= 7:
            time_label = f"{days_ago}天前"
        else:
            time_label = updated_at.strftime("%m-%d")
    else:
        time_label = "未知"

    # 单行布局
    col1, col2, col3, col4 = st.columns([4, 2, 2, 2])

    with col1:
        st.markdown(f"**{project_name}**")

    with col2:
        presentations = project.get("presentation_count", 0)
        st.caption(f"📊 {presentations} 个汇报")

    with col3:
        st.caption(f"🕒 {time_label}")

    with col4:
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            if st.button("打开", key=f"list_open_{project_id}", use_container_width=True, type="primary"):
                return "open"

        with btn_col2:
            if st.button("⋮", key=f"list_menu_{project_id}", use_container_width=True):
                return "menu"

    st.divider()

    return None


def render_empty_project_state() -> None:
    """
    渲染空状态 - 无项目时的引导

    改进点：
    1. 友好的空状态插图
    2. 清晰的操作引导
    3. 示例和教程链接
    """

    st.markdown("<br><br>", unsafe_allow_html=True)

    # 居中容器
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # 空状态图标
        st.markdown(
            "<div style='text-align: center; font-size: 80px;'>📁</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<h3 style='text-align: center;'>还没有项目</h3>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align: center; color: #666;'>创建你的第一个项目，开始制作精美的建筑汇报</p>",
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # 操作按钮
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            if st.button(
                "🚀 快速创建项目",
                use_container_width=True,
                type="primary",
                key="empty_quick_create"
            ):
                st.session_state["genesis_intent"] = "fast_deck"
                st.switch_page("pages/project_genesis.py")

        with btn_col2:
            if st.button(
                "📚 查看教程",
                use_container_width=True,
                key="empty_tutorial"
            ):
                st.session_state["show_tutorial"] = True
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # 示例场景
        with st.expander("💡 不知道从哪开始？看看这些场景", expanded=True):
            st.markdown("""
            **常见使用场景：**

            - 🏢 **新项目方案汇报** - 从零开始创建项目，生成方案展示文档
            - 🔄 **改扩建项目** - 上传现有资料，快速整理成汇报
            - 🎨 **设计成果展示** - 将设计作品整理成精美的展示文档
            - 📊 **进度汇报** - 定期更新项目进展，生成阶段性汇报
            """)


def render_project_quick_actions() -> None:
    """
    渲染快速操作面板 - 常用操作快捷入口

    改进点：
    1. 常用操作集中展示
    2. 一键到达
    3. 操作统计
    """

    with st.expander("⚡ 快速操作", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**创建**")
            if st.button("🚀 快速出稿", key="quick_fast_deck", use_container_width=True):
                st.session_state["genesis_intent"] = "fast_deck"
                st.switch_page("pages/project_genesis.py")

            if st.button("📝 完整项目", key="quick_full_project", use_container_width=True):
                st.session_state.pop("genesis_intent", None)
                st.switch_page("pages/project_genesis.py")

        with col2:
            st.markdown("**导入**")
            if st.button("📄 从 PPT 恢复", key="quick_recover", use_container_width=True):
                st.switch_page("pages/slide_recovery.py")

            if st.button("📁 从资料开始", key="quick_materials", use_container_width=True):
                # 创建项目并进入资料页面
                pass

        with col3:
            st.markdown("**工具**")
            if st.button("🎨 模板库", key="quick_templates", use_container_width=True):
                st.switch_page("pages/template_library.py")

            if st.button("🛠️ 工具中心", key="quick_tools", use_container_width=True):
                st.switch_page("pages/tool_hub.py")


def render_project_statistics(projects: List[Dict[str, Any]]) -> None:
    """
    渲染项目统计面板 - 总体数据概览

    改进点：
    1. 可视化统计数据
    2. 活跃度分析
    3. 趋势展示
    """

    if not projects:
        return

    st.markdown("---")
    st.markdown("### 📊 统计概览")

    # 基础统计
    total_projects = len(projects)

    # 计算活跃项目（7天内更新）
    now = datetime.now()
    active_projects = sum(
        1 for p in projects
        if p.get("updated_at") and (now - p["updated_at"]).days <= 7
    )

    # 计算本月创建
    this_month_projects = sum(
        1 for p in projects
        if p.get("created_at") and p["created_at"].month == now.month
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("总项目数", total_projects)

    with col2:
        st.metric("活跃项目", active_projects)

    with col3:
        st.metric("本月新增", this_month_projects)

    with col4:
        # 完成项目（有交付记录的）
        completed = sum(1 for p in projects if p.get("has_deliverables", False))
        st.metric("已完成", completed)

    # 活跃度分布（可选）
    with st.expander("📈 查看详细统计", expanded=False):
        st.caption("活跃度分布")

        # 按更新时间分组
        today_count = sum(
            1 for p in projects
            if p.get("updated_at") and (now - p["updated_at"]).days == 0
        )
        week_count = sum(
            1 for p in projects
            if p.get("updated_at") and 0 < (now - p["updated_at"]).days <= 7
        )
        month_count = sum(
            1 for p in projects
            if p.get("updated_at") and 7 < (now - p["updated_at"]).days <= 30
        )
        older_count = total_projects - today_count - week_count - month_count

        st.markdown(f"- 今天更新：{today_count} 个")
        st.markdown(f"- 本周更新：{week_count} 个")
        st.markdown(f"- 本月更新：{month_count} 个")
        st.markdown(f"- 更早：{older_count} 个")
