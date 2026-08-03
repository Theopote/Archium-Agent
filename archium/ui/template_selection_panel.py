"""Streamlit panel for professional template selection and design system integration."""

from __future__ import annotations

from uuid import UUID
from typing import Any

import streamlit as st

from archium.application.design_system_integration import DesignSystemIntegrationService
from archium.domain.presentation_templates import PresentationType, get_template, list_templates
from archium.application.unit_of_work import unit_of_work


def render_template_selection_panel(
    *,
    project_id: UUID,
    presentation_id: UUID | None = None,
    on_template_selected: callable | None = None,
) -> dict[str, Any] | None:
    """Render professional template selection interface.
    
    Args:
        project_id: Current project ID
        presentation_id: Optional current presentation ID
        on_template_selected: Callback function when template is selected
    
    Returns:
        Selected template information or None
    """
    st.markdown("### 🎨 专业模板选择")
    st.caption("选择适合您演示场景的专业模板，确保输出质量与风格统一")
    
    # Initialize design system integration
    with unit_of_work() as uow:
        design_system_service = DesignSystemIntegrationService(uow)
    
    # Get available templates
    templates = list_templates()
    
    if not templates:
        st.warning("暂无可用模板")
        return None
    
    # Group templates by type
    template_groups = {}
    for template in templates:
        group = template.presentation_type.value
        if group not in template_groups:
            template_groups[group] = []
        template_groups[group].append(template)
    
    # Create template selection UI
    selected_template = None
    
    # Use tabs for different presentation types
    tab_names = list(template_groups.keys())
    if not tab_names:
        tab_names = ["全部模板"]
        template_groups["全部模板"] = templates
    
    tabs = st.tabs(tab_names)
    
    for tab, (group_name, group_templates) in zip(tabs, template_groups.items()):
        with tab:
            for template in group_templates:
                with st.container():
                    # Template card
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        # Template preview (placeholder)
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, {template.color_scheme or '#0EA5E9'} 0%, {template.color_scheme or '#0369A1'} 100%);
                            height: 80px;
                            border-radius: 8px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                            font-weight: bold;
                            margin-bottom: 10px;
                        ">
                            {template.name[:10]}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"**{template.name}**")
                        st.caption(template.description)
                        
                        # Template metadata
                        metadata_col1, metadata_col2, metadata_col3 = st.columns(3)
                        with metadata_col1:
                            st.metric("配色", template.color_scheme or "默认")
                        with metadata_col2:
                            st.metric("字体", template.font_scheme or "默认")
                        with metadata_col3:
                            st.metric("比例", template.aspect_ratio)
                        
                        # Select button
                        if st.button(
                            f"选择模板",
                            key=f"select_{template.id}",
                            use_container_width=True,
                        ):
                            selected_template = {
                                "id": template.id,
                                "name": template.name,
                                "type": template.presentation_type.value,
                                "description": template.description,
                            }
                            
                            if on_template_selected:
                                on_template_selected(template.id)
                            
                            st.success(f"已选择模板：{template.name}")
                            st.rerun()
                    
                    st.divider()
    
    # Advanced options
    with st.expander("⚙️ 高级选项"):
        st.markdown("#### 设计系统自定义")
        
        # Color customization
        st.markdown("**色彩方案**")
        primary_color = st.color_picker(
            "主色调",
            value="#0EA5E9",
            key="primary_color_custom",
        )
        secondary_color = st.color_picker(
            "次色调",
            value="#64748B",
            key="secondary_color_custom",
        )
        accent_color = st.color_picker(
            "强调色",
            value="#F59E0B",
            key="accent_color_custom",
        )
        
        # Typography customization
        st.markdown("**排版设置**")
        font_family = st.selectbox(
            "字体族",
            ["Arial", "Helvetica", "Georgia", "Times New Roman", "Microsoft YaHei"],
            index=0,
            key="font_family_custom",
        )
        
        base_font_size = st.slider(
            "基础字号",
            min_value=10,
            max_value=24,
            value=14,
            key="base_font_size_custom",
        )
        
        # Layout preferences
        st.markdown("**布局偏好**")
        layout_style = st.selectbox(
            "布局风格",
            ["专业保守", "现代简约", "创意大胆"],
            index=0,
            key="layout_style_custom",
        )
        
        whitespace_preference = st.slider(
            "留白程度",
            min_value=1,
            max_value=5,
            value=3,
            key="whitespace_custom",
        )
        
        # Save custom settings
        if st.button("保存自定义设置", key="save_custom_settings"):
            custom_settings = {
                "colors": {
                    "primary": primary_color,
                    "secondary": secondary_color,
                    "accent": accent_color,
                },
                "typography": {
                    "font_family": font_family,
                    "base_font_size": base_font_size,
                },
                "layout": {
                    "style": layout_style,
                    "whitespace": whitespace_preference,
                },
            }
            st.session_state["custom_design_settings"] = custom_settings
            st.success("自定义设置已保存")
    
    # Template preview
    if selected_template:
        st.markdown("---")
        st.markdown("### 📋 模板详情")
        
        template = get_template(selected_template["id"])
        if template:
            st.markdown(f"**{template.name}**")
            st.write(template.description)
            
            st.markdown("#### 推荐幻灯片结构")
            structure = template.get_recommended_structure()
            if structure:
                for i, slide_info in enumerate(structure, 1):
                    st.markdown(f"{i}. **{slide_info.get('title', 'Slide')}** - {slide_info.get('layout', 'content')}")
            
            st.markdown("#### 包含的布局类型")
            layout_types = set(t.layout.value for t in template.slide_templates)
            st.write(", ".join(layout_types))
    
    return selected_template


def render_design_quality_panel(
    *,
    presentation_id: UUID,
    slides_data: list[dict[str, Any]],
) -> None:
    """Render design quality assessment panel.
    
    Args:
        presentation_id: Presentation ID
        slides_data: List of slide data for quality assessment
    """
    st.markdown("### 📊 设计质量评估")
    st.caption("基于专业标准评估演示文稿的设计质量")
    
    # Initialize design system integration
    with unit_of_work() as uow:
        design_system_service = DesignSystemIntegrationService(uow)
    
    # Assess quality
    with st.spinner("正在评估设计质量..."):
        quality_result = design_system_service.assess_presentation_quality(
            presentation_id,
            slides_data,
        )
    
    summary = quality_result["summary"]
    
    # Overall score
    score_col1, score_col2, score_col3 = st.columns(3)
    
    with score_col1:
        st.metric(
            "总体评分",
            f"{summary['average_score']}/100",
            delta=None,
            delta_color="normal" if summary['average_score'] >= 75 else "inverse",
        )
    
    with score_col2:
        st.metric(
            "质量等级",
            summary['overall_level'].upper(),
            delta=None,
        )
    
    with score_col3:
        needs_review = len(summary.get('needs_review', []))
        st.metric(
            "需要改进",
            needs_review,
            delta=None,
            delta_color="inverse" if needs_review > 0 else "normal",
        )
    
    # Quality level distribution
    if summary.get('level_distribution'):
        st.markdown("#### 质量等级分布")
        level_dist = summary['level_distribution']
        for level, count in level_dist.items():
            st.progress(count / len(slides_data), text=f"{level.upper()}: {count}")
    
    # Priority improvements
    if summary.get('priority_improvements'):
        st.markdown("#### 🎯 优先改进建议")
        for i, improvement in enumerate(summary['priority_improvements'], 1):
            st.markdown(f"{i}. {improvement}")
    
    # Detailed slide-by-slide assessment
    with st.expander("📋 详细评估报告"):
        for slide_id, report in quality_result['quality_reports'].items():
            with st.container():
                st.markdown(f"**幻灯片 {slide_id}**")
                st.metric(
                    "评分",
                    f"{report.overall_score}/100",
                    delta=None,
                )
                
                # Category scores
                for category, metric in report.metrics.items():
                    with st.expander(f"{category.value}"):
                        st.metric("得分", f"{metric.score}/100")
                        if metric.issues:
                            st.warning("问题:")
                            for issue in metric.issues:
                                st.markdown(f"- {issue}")
                        if metric.suggestions:
                            st.info("建议:")
                            for suggestion in metric.suggestions:
                                st.markdown(f"- {suggestion}")
                
                st.divider()


def render_visual_elements_panel(
    *,
    query: str = "",
    element_type: str | None = None,
) -> None:
    """Render visual elements library panel.
    
    Args:
        query: Search query for elements
        element_type: Filter by element type (icon, chart, etc.)
    """
    st.markdown("### 🎨 视觉元素库")
    st.caption("专业的建筑图标、图表和视觉元素")
    
    # Initialize visual elements library
    with unit_of_work() as uow:
        design_system_service = DesignSystemIntegrationService(uow)
    
    # Search interface
    search_col1, search_col2 = st.columns([3, 1])
    
    with search_col1:
        search_query = st.text_input(
            "搜索元素",
            value=query,
            placeholder="输入关键词搜索图标、图表等...",
        )
    
    with search_col2:
        element_type_filter = st.selectbox(
            "元素类型",
            ["全部", "图标", "图表", "图元素", "通用元素"],
            index=0,
        )
    
    # Search elements
    if search_query or element_type_filter != "全部":
        with st.spinner("正在搜索..."):
            type_filter = None if element_type_filter == "全部" else element_type_filter.lower()
            results = design_system_service.search_visual_elements(
                search_query,
                type_filter,
            )
    else:
        results = []
    
    # Display results
    if results:
        st.markdown(f"找到 {len(results)} 个元素")
        
        # Grid layout for elements
        cols_per_row = 4
        for i in range(0, len(results), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, element in enumerate(results[i:i + cols_per_row]):
                with cols[j]:
                    st.markdown(f"""
                    <div style="
                        border: 1px solid #e2e8f0;
                        border-radius: 8px;
                        padding: 16px;
                        text-align: center;
                        height: 120px;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                    ">
                        <div style="font-size: 24px; margin-bottom: 8px;">🎨</div>
                        <div style="font-weight: bold; font-size: 12px;">{element['name']}</div>
                        <div style="font-size: 10px; color: #64748B;">{element['type']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"使用", key=f"use_{element['id']}_{i}_{j}", use_container_width=True):
                        st.session_state['selected_element'] = element
                        st.success(f"已选择: {element['name']}")
    else:
        st.info("未找到匹配的元素，请尝试其他关键词")
    
    # Element categories
    with st.expander("📂 元素分类"):
        st.markdown("**图标分类**")
        icon_categories = [
            "场地规划", "建筑元素", "分析", "可持续性", 
            "交通", "景观", "结构", "设备", "家具", "符号"
        ]
        for category in icon_categories:
            if st.button(category, key=f"cat_{category}", use_container_width=True):
                st.session_state['search_query'] = category
                st.rerun()
        
        st.markdown("**图表类型**")
        chart_types = [
            "面积分析", "时间线", "可持续指标", "数据对比"
        ]
        for chart_type in chart_types:
            if st.button(chart_type, key=f"chart_{chart_type}", use_container_width=True):
                st.session_state['search_query'] = chart_type
                st.rerun()
