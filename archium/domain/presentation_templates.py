"""Professional presentation templates for architectural projects.

This module defines templates for different architectural presentation scenarios:
- Design competitions
- Client presentations
- Internal reviews
- Planning submissions
- Academic presentations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from archium.domain.design_system import (
    ColorRole,
    ColorShade,
    DesignSystem,
    create_default_design_system,
)


class PresentationType(str, Enum):
    """Types of architectural presentations."""
    DESIGN_COMPETITION = "design_competition"
    CLIENT_PRESENTATION = "client_presentation"
    INTERNAL_REVIEW = "internal_review"
    PLANNING_SUBMISSION = "planning_submission"
    ACADEMIC_PRESENTATION = "academic_presentation"
    TECHNICAL_REPORT = "technical_report"
    PUBLIC_CONSULTATION = "public_consultation"


class SlideLayout(str, Enum):
    """Standard slide layouts."""
    TITLE = "title"
    TITLE_SUBTITLE = "title_subtitle"
    TITLE_CONTENT = "title_content"
    TWO_COLUMN = "two_column"
    THREE_COLUMN = "three_column"
    CONTENT_LEFT = "content_left"
    CONTENT_RIGHT = "content_right"
    FULL_IMAGE = "full_image"
    IMAGE_TEXT = "image_text"
    TEXT_IMAGE = "text_image"
    COMPARISON = "comparison"
    DATA_CHART = "data_chart"
    QUOTE = "quote"
    CONCLUSION = "conclusion"
    THANK_YOU = "thank_you"


@dataclass
class SlideTemplate:
    """Individual slide template definition."""
    id: str
    name: str
    layout: SlideLayout
    description: str
    content_areas: list[dict[str, Any]]
    style_overrides: dict[str, Any] = field(default_factory=dict)
    required_elements: list[str] = field(default_factory=list)
    optional_elements: list[str] = field(default_factory=list)
    
    def get_content_area(self, area_name: str) -> dict[str, Any] | None:
        """Get a specific content area definition."""
        for area in self.content_areas:
            if area.get("name") == area_name:
                return area
        return None


@dataclass
class PresentationTemplate:
    """Complete presentation template for a specific use case."""
    id: str
    name: str
    presentation_type: PresentationType
    description: str
    design_system: DesignSystem
    slide_templates: list[SlideTemplate]
    master_slides: dict[str, dict[str, Any]]
    color_scheme: str
    font_scheme: str
    aspect_ratio: str = "16:9"
    default_transition: str = "fade"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def get_slide_template(self, layout: SlideLayout) -> SlideTemplate | None:
        """Get a slide template by layout type."""
        for template in self.slide_templates:
            if template.layout == layout:
                return template
        return None
    
    def get_recommended_structure(self) -> list[dict[str, Any]]:
        """Get recommended slide structure for this template type."""
        structure = []
        
        if self.presentation_type == PresentationType.DESIGN_COMPETITION:
            structure = [
                {"slide": 1, "layout": SlideLayout.TITLE, "title": "项目标题", "subtitle": "设计竞赛"},
                {"slide": 2, "layout": SlideLayout.TITLE_SUBTITLE, "title": "设计理念", "subtitle": "核心概念"},
                {"slide": 3, "layout": SlideLayout.FULL_IMAGE, "title": "场地分析", "content": "场地照片/分析图"},
                {"slide": 4, "layout": SlideLayout.TWO_COLUMN, "title": "设计策略", "content": "策略说明+示意图"},
                {"slide": 5, "layout": SlideLayout.IMAGE_TEXT, "title": "总平面图", "content": "总平面+说明"},
                {"slide": 6, "layout": SlideLayout.COMPARISON, "title": "方案对比", "content": "多方案对比"},
                {"slide": 7, "layout": SlideLayout.THREE_COLUMN, "title": "功能分析", "content": "功能分区"},
                {"slide": 8, "layout": SlideLayout.FULL_IMAGE, "title": "效果图", "content": "主要效果图"},
                {"slide": 9, "layout": SlideLayout.IMAGE_TEXT, "title": "技术图纸", "content": "平面/立面/剖面"},
                {"slide": 10, "layout": SlideLayout.DATA_CHART, "title": "技术指标", "content": "数据图表"},
                {"slide": 11, "layout": SlideLayout.CONTENT_LEFT, "title": "可持续设计", "content": "绿色建筑策略"},
                {"slide": 12, "layout": SlideLayout.CONCLUSION, "title": "总结", "content": "设计亮点"},
                {"slide": 13, "layout": SlideLayout.THANK_YOU, "title": "谢谢", "content": "联系方式"},
            ]
        elif self.presentation_type == PresentationType.CLIENT_PRESENTATION:
            structure = [
                {"slide": 1, "layout": SlideLayout.TITLE, "title": "项目汇报", "subtitle": "客户名称"},
                {"slide": 2, "layout": SlideLayout.TITLE_SUBTITLE, "title": "项目背景", "subtitle": "需求分析"},
                {"slide": 3, "layout": SlideLayout.FULL_IMAGE, "title": "现状分析", "content": "现状照片"},
                {"slide": 4, "layout": SlideLayout.TWO_COLUMN, "title": "设计目标", "content": "目标说明"},
                {"slide": 5, "layout": SlideLayout.IMAGE_TEXT, "title": "总平面设计", "content": "总平面图"},
                {"slide": 6, "layout": SlideLayout.THREE_COLUMN, "title": "功能布局", "content": "功能分区"},
                {"slide": 7, "layout": SlideLayout.FULL_IMAGE, "title": "效果图展示", "content": "效果图"},
                {"slide": 8, "layout": SlideLayout.IMAGE_TEXT, "title": "立面设计", "content": "立面图"},
                {"slide": 9, "layout": SlideLayout.DATA_CHART, "title": "技术参数", "content": "技术指标"},
                {"slide": 10, "layout": SlideLayout.CONTENT_LEFT, "title": "实施计划", "content": "时间计划"},
                {"slide": 11, "layout": SlideLayout.CONCLUSION, "title": "项目亮点", "content": "核心优势"},
                {"slide": 12, "layout": SlideLayout.THANK_YOU, "title": "谢谢", "content": "联系方式"},
            ]
        elif self.presentation_type == PresentationType.PLANNING_SUBMISSION:
            structure = [
                {"slide": 1, "layout": SlideLayout.TITLE, "title": "规划申报", "subtitle": "项目名称"},
                {"slide": 2, "layout": SlideLayout.TITLE_SUBTITLE, "title": "项目概况", "subtitle": "基本信息"},
                {"slide": 3, "layout": SlideLayout.FULL_IMAGE, "title": "区位分析", "content": "区位图"},
                {"slide": 4, "layout": SlideLayout.TWO_COLUMN, "title": "规划依据", "content": "法规政策"},
                {"slide": 5, "layout": SlideLayout.IMAGE_TEXT, "title": "总平面图", "content": "总平面"},
                {"slide": 6, "layout": SlideLayout.THREE_COLUMN, "title": "技术经济指标", "content": "指标表"},
                {"slide": 7, "layout": SlideLayout.IMAGE_TEXT, "title": "日照分析", "content": "日照图"},
                {"slide": 8, "layout": SlideLayout.IMAGE_TEXT, "title": "交通分析", "content": "交通图"},
                {"slide": 9, "layout": SlideLayout.IMAGE_TEXT, "title": "市政配套", "content": "配套图"},
                {"slide": 10, "layout": SlideLayout.CONTENT_LEFT, "title": "环境影响", "content": "环评分析"},
                {"slide": 11, "layout": SlideLayout.CONCLUSION, "title": "规划符合性", "content": "合规说明"},
                {"slide": 12, "layout": SlideLayout.THANK_YOU, "title": "申报完毕", "content": "联系方式"},
            ]
        
        return structure


def create_standard_slide_templates() -> list[SlideTemplate]:
    """Create standard slide templates."""
    
    templates = [
        SlideTemplate(
            id="title_slide",
            name="Title Slide)",
            layout=SlideLayout.TITLE,
            description="Main title slide with project name and subtitle",
            content_areas=[
                {"name": "title", "type": "text", "position": "center", "style": "h1"},
                {"name": "subtitle", "type": "text", "position": "center", "style": "h2"},
                {"name": "logo", "type": "image", "position": "top_left", "optional": True},
                {"name": "date", "type": "text", "position": "bottom_right", "optional": True},
            ],
            required_elements=["title"],
            optional_elements=["subtitle", "logo", "date"],
        ),
        SlideTemplate(
            id="title_subtitle",
            name="Title with Subtitle",
            layout=SlideLayout.TITLE_SUBTITLE,
            description="Title slide with prominent subtitle",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h1"},
                {"name": "subtitle", "type": "text", "position": "middle", "style": "h2"},
                {"name": "content", "type": "text", "position": "bottom", "style": "body"},
            ],
            required_elements=["title", "subtitle"],
            optional_elements=["content"],
        ),
        SlideTemplate(
            id="title_content",
            name="Title with Content",
            layout=SlideLayout.TITLE_CONTENT,
            description="Title with main content area",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "content", "type": "text", "position": "middle", "style": "body"},
                {"name": "image", "type": "image", "position": "bottom", "optional": True},
            ],
            required_elements=["title", "content"],
            optional_elements=["image"],
        ),
        SlideTemplate(
            id="two_column",
            name="Two Column Layout",
            layout=SlideLayout.TWO_COLUMN,
            description="Split layout with two equal columns",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "left_column", "type": "mixed", "position": "middle_left", "style": "body"},
                {"name": "right_column", "type": "mixed", "position": "middle_right", "style": "body"},
            ],
            required_elements=["title", "left_column", "right_column"],
        ),
        SlideTemplate(
            id="three_column",
            name="Three Column Layout",
            layout=SlideLayout.THREE_COLUMN,
            description="Split layout with three equal columns",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "column_1", "type": "mixed", "position": "middle_left", "style": "body"},
                {"name": "column_2", "type": "mixed", "position": "middle_center", "style": "body"},
                {"name": "column_3", "type": "mixed", "position": "middle_right", "style": "body"},
            ],
            required_elements=["title", "column_1", "column_2", "column_3"],
        ),
        SlideTemplate(
            id="full_image",
            name="Full Image",
            layout=SlideLayout.FULL_IMAGE,
            description="Full-width image with optional overlay text",
            content_areas=[
                {"name": "image", "type": "image", "position": "full", "style": "cover"},
                {"name": "overlay_title", "type": "text", "position": "overlay_top", "style": "h2", "optional": True},
                {"name": "overlay_text", "type": "text", "position": "overlay_bottom", "style": "body", "optional": True},
            ],
            required_elements=["image"],
            optional_elements=["overlay_title", "overlay_text"],
        ),
        SlideTemplate(
            id="image_text",
            name="Image with Text",
            layout=SlideLayout.IMAGE_TEXT,
            description="Image on left, text on right",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "image", "type": "image", "position": "left", "style": "half_width"},
                {"name": "content", "type": "text", "position": "right", "style": "body"},
            ],
            required_elements=["title", "image", "content"],
        ),
        SlideTemplate(
            id="text_image",
            name="Text with Image",
            layout=SlideLayout.TEXT_IMAGE,
            description="Text on left, image on right",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "content", "type": "text", "position": "left", "style": "body"},
                {"name": "image", "type": "image", "position": "right", "style": "half_width"},
            ],
            required_elements=["title", "content", "image"],
        ),
        SlideTemplate(
            id="comparison",
            name="Comparison Layout",
            layout=SlideLayout.COMPARISON,
            description="Side-by-side comparison of two items",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "left_item", "type": "mixed", "position": "left", "style": "body"},
                {"name": "right_item", "type": "mixed", "position": "right", "style": "body"},
                {"name": "comparison_notes", "type": "text", "position": "bottom", "style": "small", "optional": True},
            ],
            required_elements=["title", "left_item", "right_item"],
            optional_elements=["comparison_notes"],
        ),
        SlideTemplate(
            id="data_chart",
            name="Data Chart",
            layout=SlideLayout.DATA_CHART,
            description="Chart or data visualization with explanation",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "chart", "type": "chart", "position": "middle", "style": "large"},
                {"name": "legend", "type": "text", "position": "bottom_left", "style": "small", "optional": True},
                {"name": "notes", "type": "text", "position": "bottom_right", "style": "small", "optional": True},
            ],
            required_elements=["title", "chart"],
            optional_elements=["legend", "notes"],
        ),
        SlideTemplate(
            id="quote",
            name="Quote Slide",
            layout=SlideLayout.QUOTE,
            description="Featured quote or highlight",
            content_areas=[
                {"name": "quote", "type": "text", "position": "center", "style": "quote"},
                {"name": "attribution", "type": "text", "position": "bottom_center", "style": "small", "optional": True},
            ],
            required_elements=["quote"],
            optional_elements=["attribution"],
        ),
        SlideTemplate(
            id="conclusion",
            name="Conclusion Slide",
            layout=SlideLayout.CONCLUSION,
            description="Summary and key takeaways",
            content_areas=[
                {"name": "title", "type": "text", "position": "top", "style": "h2"},
                {"name": "summary", "type": "text", "position": "middle", "style": "body"},
                {"name": "key_points", "type": "list", "position": "bottom", "style": "bullet"},
            ],
            required_elements=["title", "summary", "key_points"],
        ),
        SlideTemplate(
            id="thank_you",
            name="Thank You Slide",
            layout=SlideLayout.THANK_YOU,
            description="Closing slide with contact information",
            content_areas=[
                {"name": "message", "type": "text", "position": "center", "style": "h1"},
                {"name": "contact_info", "type": "text", "position": "center", "style": "body"},
                {"name": "logo", "type": "image", "position": "center", "optional": True},
            ],
            required_elements=["message", "contact_info"],
            optional_elements=["logo"],
        ),
    ]
    
    return templates


def create_design_competition_template() -> PresentationTemplate:
    """Create a template for design competition presentations."""
    
    design_system = create_default_design_system()
    slide_templates = create_standard_slide_templates()
    
    master_slides = {
        "title_master": {
            "background": design_system.color_palette.get_color(ColorRole.PRIMARY, ColorShade._900).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._50).hex_value,
            "accent_color": design_system.color_palette.get_color(ColorRole.ACCENT, ColorShade._500).hex_value,
        },
        "content_master": {
            "background": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._50).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._900).hex_value,
            "accent_color": design_system.color_palette.get_color(ColorRole.PRIMARY, ColorShade._600).hex_value,
        },
        "image_master": {
            "background": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._100).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._900).hex_value,
        },
    }
    
    return PresentationTemplate(
        id="design_competition_v1",
        name="Design Competition Template",
        presentation_type=PresentationType.DESIGN_COMPETITION,
        description="Professional template for architectural design competitions",
        design_system=design_system,
        slide_templates=slide_templates,
        master_slides=master_slides,
        color_scheme="professional_blue",
        font_scheme="modern_sans",
        aspect_ratio="16:9",
        default_transition="fade",
        metadata={
            "target_audience": "Competition jury",
            "formality_level": "high",
            "visual_style": "professional",
            "typical_duration": "20-30 minutes",
        },
    )


def create_client_presentation_template() -> PresentationTemplate:
    """Create a template for client presentations."""
    
    design_system = create_default_design_system()
    slide_templates = create_standard_slide_templates()
    
    master_slides = {
        "title_master": {
            "background": design_system.color_palette.get_color(ColorRole.SECONDARY, ColorShade._800).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._50).hex_value,
            "accent_color": design_system.color_palette.get_color(ColorRole.ACCENT, ColorShade._500).hex_value,
        },
        "content_master": {
            "background": "#FFFFFF",
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._800).hex_value,
            "accent_color": design_system.color_palette.get_color(ColorRole.PRIMARY, ColorShade._600).hex_value,
        },
        "image_master": {
            "background": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._100).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._900).hex_value,
        },
    }
    
    return PresentationTemplate(
        id="client_presentation_v1",
        name="Client Presentation Template",
        presentation_type=PresentationType.CLIENT_PRESENTATION,
        description="Professional template for client presentations",
        design_system=design_system,
        slide_templates=slide_templates,
        master_slides=master_slides,
        color_scheme="corporate_slate",
        font_scheme="clean_sans",
        aspect_ratio="16:9",
        default_transition="fade",
        metadata={
            "target_audience": "Clients and stakeholders",
            "formality_level": "medium",
            "visual_style": "approachable",
            "typical_duration": "30-45 minutes",
        },
    )


def create_planning_submission_template() -> PresentationTemplate:
    """Create a template for planning submissions."""
    
    design_system = create_default_design_system()
    slide_templates = create_standard_slide_templates()
    
    master_slides = {
        "title_master": {
            "background": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._900).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._50).hex_value,
            "accent_color": design_system.color_palette.get_color(ColorRole.INFO, ColorShade._500).hex_value,
        },
        "content_master": {
            "background": "#FFFFFF",
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._900).hex_value,
            "accent_color": design_system.color_palette.get_color(ColorRole.SECONDARY, ColorShade._700).hex_value,
        },
        "image_master": {
            "background": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._50).hex_value,
            "text_color": design_system.color_palette.get_color(ColorRole.NEUTRAL, ColorShade._900).hex_value,
        },
    }
    
    return PresentationTemplate(
        id="planning_submission_v1",
        name="Planning Submission Template",
        presentation_type=PresentationType.PLANNING_SUBMISSION,
        description="Professional template for planning submissions",
        design_system=design_system,
        slide_templates=slide_templates,
        master_slides=master_slides,
        color_scheme="official_grey",
        font_scheme="formal_sans",
        aspect_ratio="16:9",
        default_transition="none",
        metadata={
            "target_audience": "Planning authorities",
            "formality_level": "high",
            "visual_style": "official",
            "typical_duration": "15-20 minutes",
        },
    )


# Template registry
TEMPLATE_REGISTRY: dict[str, PresentationTemplate] = {
    "design_competition": create_design_competition_template(),
    "client_presentation": create_client_presentation_template(),
    "planning_submission": create_planning_submission_template(),
}


def get_template(template_id: str) -> PresentationTemplate | None:
    """Get a template by ID."""
    return TEMPLATE_REGISTRY.get(template_id)


def list_templates() -> list[PresentationTemplate]:
    """List all available templates."""
    return list(TEMPLATE_REGISTRY.values())


def register_template(template: PresentationTemplate) -> None:
    """Register a new template."""
    TEMPLATE_REGISTRY[template.id] = template
