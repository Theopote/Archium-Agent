"""
Project Genesis 页面增强组件

改进评估结果的展示，使信息更清晰、更易理解
"""

import streamlit as st
from typing import List, Dict, Any, Optional


def render_knowledge_state_card(state_data: Dict[str, Any]) -> None:
    """
    渲染知识状态卡片 - 使用标签页分组展示

    改进点：
    1. 使用标签页分组：已知/未知/建议
    2. 视觉化进度指示
    3. 更清晰的分类展示
    """

    known = state_data.get("known") or {}
    unknown = state_data.get("unknown") or state_data.get("missing_information") or []

    # 计算知识完整度
    total_items = len(known) + len(unknown)
    if total_items > 0:
        completeness = len(known) / total_items
    else:
        completeness = 0.5

    # 总览卡片
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="已知信息",
            value=len(known),
            delta=None
        )

    with col2:
        st.metric(
            label="待补充",
            value=len(unknown),
            delta=None
        )

    with col3:
        percentage = int(completeness * 100)
        st.metric(
            label="知识完整度",
            value=f"{percentage}%",
            delta=None
        )

    # 进度条
    st.progress(completeness, text=f"项目信息完整度：{percentage}%")

    # 详细信息标签页
    tab1, tab2, tab3 = st.tabs(["✅ 已知信息", "❓ 待补充", "💡 建议行动"])

    with tab1:
        if known:
            st.markdown("##### 目前了解到的信息")
            for key, value in known.items():
                st.markdown(f"**{key}**")
                st.caption(value)
                st.markdown("")
        else:
            st.info("暂无已知信息")

    with tab2:
        if unknown:
            st.markdown("##### 需要进一步确认的信息")
            for i, item in enumerate(unknown[:8], 1):
                st.markdown(f"{i}. {item}")
        else:
            st.success("信息已经很完整了！")

    with tab3:
        st.markdown("##### 建议的下一步行动")
        st.caption("根据当前项目信息，推荐以下行动：")


def render_project_context_card(context_data: Optional[Dict[str, Any]]) -> None:
    """
    渲染项目上下文卡片 - 更清晰的展示项目阶段和推荐工作流

    改进点：
    1. 突出显示生命周期阶段
    2. 可视化推荐工作流
    3. 清晰展示假设
    """

    if not context_data:
        return

    st.markdown("---")
    st.markdown("### 📋 项目情况分析")

    # 项目阶段和工作流
    col1, col2 = st.columns(2)

    with col1:
        lifecycle_stage = context_data.get("lifecycle_stage", "unknown")
        stage_labels = {
            "IDEA": "💡 概念构思",
            "RESEARCH": "🔍 前期研究",
            "CONCEPT": "🎨 方案设计",
            "SCHEMATIC": "📐 初步设计",
            "DETAILED": "📋 详细设计",
            "CONSTRUCTION": "🏗️ 施工阶段",
            "POST_OCCUPANCY": "✅ 使用阶段",
        }
        stage_label = stage_labels.get(lifecycle_stage, lifecycle_stage)

        st.markdown("**当前项目阶段**")
        st.info(stage_label)

    with col2:
        workflow = context_data.get("recommended_workflow", "unknown")
        workflow_labels = {
            "EXPLORE": "🔍 探索方向",
            "GATHER": "📚 收集资料",
            "COMPILE": "📝 整理汇报",
            "REFINE": "✨ 精修内容",
        }
        workflow_label = workflow_labels.get(workflow, workflow)

        st.markdown("**推荐工作流**")
        st.success(workflow_label)

    # 假设和不确定性
    assumptions = context_data.get("assumptions", [])
    if assumptions:
        with st.expander("🤔 当前假设（待确认）", expanded=False):
            st.caption("系统基于现有信息做出了以下假设，请确认或修正：")
            for i, assumption in enumerate(assumptions[:6], 1):
                st.markdown(f"{i}. {assumption}")


def render_genesis_summary_header(
    understanding_summary: str,
    project_name: str,
) -> None:
    """
    渲染评估摘要头部 - 更友好的展示理解结果

    改进点：
    1. 使用对话式语言
    2. 突出关键信息
    3. 清晰的视觉层次
    """

    st.markdown("### 🎯 项目理解")

    # 项目名称
    st.markdown(f"**{project_name}**")

    # 理解摘要
    if understanding_summary:
        with st.container():
            st.markdown("##### 我的理解")
            st.markdown(understanding_summary)
            st.caption("如果理解有误，请点击「重新描述」修正")

    st.markdown("---")


def render_next_actions_grouped(
    actions: List[Dict[str, Any]],
    project_id: str
) -> None:
    """
    渲染分组的下一步行动 - 按优先级和类型分组

    改进点：
    1. 按行动类型分组
    2. 视觉化优先级
    3. 清晰的操作按钮
    """

    if not actions:
        st.info("✅ 项目信息已经很完整了，可以开始下一步工作")
        return

    st.markdown("### 🚀 推荐的下一步")

    # 按行动类型分组
    explore_actions = []
    gather_actions = []
    compile_actions = []
    other_actions = []

    for action in actions:
        action_type = action.get("action", "")
        if "EXPLORE" in action_type:
            explore_actions.append(action)
        elif "UPLOAD" in action_type or "GATHER" in action_type:
            gather_actions.append(action)
        elif "COMPILE" in action_type or "DRAFT" in action_type:
            compile_actions.append(action)
        else:
            other_actions.append(action)

    # 渲染分组的行动
    action_groups = [
        ("🔍 探索方向", explore_actions, "探索不同的设计方向和可能性"),
        ("📚 收集资料", gather_actions, "上传文档、图片等项目资料"),
        ("📝 整理汇报", compile_actions, "开始编写和组织汇报内容"),
        ("🛠️ 其他操作", other_actions, "其他推荐的操作"),
    ]

    for group_name, group_actions, group_desc in action_groups:
        if not group_actions:
            continue

        with st.expander(f"{group_name} ({len(group_actions)})", expanded=True):
            st.caption(group_desc)

            for i, action in enumerate(group_actions):
                reason = action.get("reason", "")
                action_type = action.get("action", "")

                col1, col2 = st.columns([4, 1])

                with col1:
                    st.markdown(f"**{i + 1}. {reason or action_type}**")

                    # 详细说明
                    details = action.get("details", "")
                    if details:
                        st.caption(details)

                with col2:
                    if st.button("执行", key=f"action_{action_type}_{i}"):
                        # 这里会触发行动执行
                        st.session_state[f"genesis_action_clicked"] = action
                        st.rerun()

                if i < len(group_actions) - 1:
                    st.markdown("")


def render_starter_draft_status(
    starter_data: Dict[str, Any],
    presentation_id: str
) -> None:
    """
    渲染起稿状态卡片 - 更直观的展示生成进度

    改进点：
    1. 可视化生成进度
    2. 清晰的状态指示
    3. 一键跳转到工作室
    """

    st.markdown("---")
    st.markdown("### 📄 起稿状态")

    has_first_slide = starter_data.get("has_first_slide", False)
    page_count = starter_data.get("page_count", 0)
    slides_ready = starter_data.get("slides_ready_count", 0)
    layout_ready = starter_data.get("layout_ready_count", 0)

    if not has_first_slide:
        st.warning("⏳ 正在准备封面页...")
        return

    # 进度指标
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="总页数",
            value=page_count,
        )

    with col2:
        st.metric(
            label="内容就绪",
            value=f"{slides_ready}/{page_count}",
        )

    with col3:
        st.metric(
            label="布局就绪",
            value=f"{layout_ready}/{page_count}",
        )

    # 进度条
    if page_count > 0:
        content_progress = slides_ready / page_count
        layout_progress = layout_ready / page_count

        st.caption("内容生成进度")
        st.progress(content_progress, text=f"{int(content_progress * 100)}%")

        st.caption("布局生成进度")
        st.progress(layout_progress, text=f"{int(layout_progress * 100)}%")

    # 封面预览
    cover_preview_path = starter_data.get("cover_preview_path")
    if cover_preview_path:
        with st.expander("👀 封面预览", expanded=True):
            try:
                st.image(cover_preview_path, use_container_width=True)
            except Exception:
                st.caption("封面预览暂不可用")

    # 操作按钮
    summary = starter_data.get("summary", "")
    if summary:
        st.info(summary)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "📝 进入工作室编辑",
            type="primary",
            use_container_width=True,
            key="goto_studio"
        ):
            st.session_state.selected_presentation_id = presentation_id
            st.session_state.studio_selected_slide_index = 0
            if layout_ready >= max(1, page_count):
                st.session_state.studio_center_mode = "overview"
            st.switch_page("pages/flow/edit.py")

    with col2:
        if st.button(
            "🔄 继续生成",
            use_container_width=True,
            key="continue_generate"
        ):
            st.switch_page("pages/flow/generate.py")


def render_enhanced_assessment_card(
    project_id: str,
    project_name: str,
    assessment_payload: Dict[str, Any]
) -> None:
    """
    渲染增强版的评估结果卡片 - 整合所有改进

    这是主入口函数，协调所有子组件
    """

    # 1. 摘要头部
    understanding_summary = assessment_payload.get("understanding_summary", "")
    render_genesis_summary_header(understanding_summary, project_name)

    # 2. 项目上下文
    project_context = assessment_payload.get("project_context")
    if project_context:
        render_project_context_card(project_context)

    # 3. 知识状态
    knowledge_state = assessment_payload.get("knowledge_state", {})
    if knowledge_state:
        st.markdown("---")
        render_knowledge_state_card(knowledge_state)

    # 4. 起稿状态
    starter_draft = assessment_payload.get("starter_draft")
    if starter_draft:
        presentation_id = starter_draft.get("presentation_id", "")
        render_starter_draft_status(starter_draft, presentation_id)

    # 5. 下一步行动
    actions = assessment_payload.get("actions", [])
    st.markdown("---")
    render_next_actions_grouped(actions, project_id)

    # 6. 重新描述按钮
    st.markdown("---")
    if st.button("🔄 重新描述项目", key="reset_genesis", use_container_width=True):
        st.session_state.pop("genesis_assessed_project_id", None)
        st.session_state.pop("genesis_context_assessment", None)
        st.rerun()


def render_genesis_example_prompts() -> None:
    """
    渲染示例提示 - 帮助新手快速开始

    改进点：
    1. 提供多个示例
    2. 一键填充
    3. 按场景分类
    """

    with st.expander("💡 不知道如何描述？查看示例", expanded=False):
        st.markdown("##### 选择一个场景，快速开始")

        examples = [
            {
                "name": "🏢 新建项目（有想法）",
                "prompt": "我想在西安设计一个青年文化中心，用地在秦岭脚下，希望结合陕西传统建筑元素和现代设计。目标人群是18-35岁的年轻人，功能包括展览、演出、共享办公等。"
            },
            {
                "name": "🔄 改扩建项目（有资料）",
                "prompt": "医院门诊楼改扩建项目，手头有旧总平面图和现场照片。甲方要求增加200张床位，但功能分区还不清楚。需要尽快出一版初步方案汇报。"
            },
            {
                "name": "🎨 方案汇报（正在设计）",
                "prompt": "文化综合体项目，方案设计已经完成，现在需要准备给甲方的方案汇报。项目包含图书馆、美术馆、剧院三个主要功能，用地2.5公顷。"
            },
            {
                "name": "🏘️ 更新改造（复杂情况）",
                "prompt": "老城区历史街区微更新，涉及15栋历史建筑修缮，需要做现状调研汇报。已经完成了现场踏勘和测绘，有大量照片和CAD图纸。"
            },
        ]

        for example in examples:
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**{example['name']}**")
                st.caption(example['prompt'][:80] + "...")

            with col2:
                if st.button("使用", key=f"example_{example['name']}"):
                    st.session_state["genesis_example_prompt"] = example['prompt']
                    st.rerun()


def render_genesis_tips() -> None:
    """
    渲染使用提示 - 帮助用户更好地描述项目
    """

    st.markdown("---")
    st.markdown("##### 💡 描述提示")

    tips_col1, tips_col2 = st.columns(2)

    with tips_col1:
        st.markdown("**包含这些信息更好：**")
        st.caption("• 项目类型和规模")
        st.caption("• 当前阶段（想法/设计中/已完成）")
        st.caption("• 现有资料情况")
        st.caption("• 主要需求或目标")

    with tips_col2:
        st.markdown("**不需要：**")
        st.caption("• 过于详细的技术参数")
        st.caption("• 完整的项目背景")
        st.caption("• 规范的格式")
        st.caption("• 用自然语言描述即可")
