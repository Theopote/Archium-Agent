"""Design system integration service for Archium workflows.

This module integrates the professional design system, templates, and quality
assessment into the existing presentation workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.design_quality_assessment import DesignQualityAssessor, DesignQualityReport
from archium.application.intelligent_layout import (
    ContentBlock,
    ContentType,
    LayoutConsistencyChecker,
    LayoutOptimizer,
    LayoutPriority,
)
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.design_system import (
    DesignSystem,
    create_default_design_system,
)
from archium.domain.presentation_templates import (
    SlideLayout,
    get_template,
    list_templates,
)
from archium.domain.visual_elements import get_visual_elements_library


class DesignSystemIntegrationService:
    """Main integration service for design system components."""
    
    def __init__(
        self,
        session: SessionLike,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._settings = settings or get_settings()
        
        # Initialize design system components
        self.design_system = create_default_design_system()
        self.visual_library = get_visual_elements_library()
        self.layout_optimizer = LayoutOptimizer(self.design_system, self.visual_library)
        self.consistency_checker = LayoutConsistencyChecker(self.design_system)
        self.quality_assessor = DesignQualityAssessor(self.design_system)
        
        # Cache for presentation-specific design systems
        self._presentation_design_systems: dict[UUID, DesignSystem] = {}
    
    def get_design_system_for_presentation(
        self,
        presentation_id: UUID,
        template_id: str | None = None,
    ) -> DesignSystem:
        """Get or create a design system for a specific presentation."""
        
        # Check cache first
        if presentation_id in self._presentation_design_systems:
            return self._presentation_design_systems[presentation_id]
        
        # If template is specified, use template's design system
        if template_id:
            template = get_template(template_id)
            if template and template.design_system:
                self._presentation_design_systems[presentation_id] = template.design_system
                return template.design_system
        
        # Otherwise use default design system
        self._presentation_design_systems[presentation_id] = self.design_system
        return self.design_system
    
    def apply_template_to_presentation(
        self,
        presentation_id: UUID,
        template_id: str,
        presentation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply a presentation template to presentation data."""
        
        template = get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Get design system from template
        design_system = template.design_system
        
        # Apply template's master slides
        master_slides = template.master_slides
        
        # Get recommended structure
        recommended_structure = template.get_recommended_structure()
        
        # Apply color scheme
        color_scheme = template.color_scheme
        
        # Apply font scheme
        font_scheme = template.font_scheme
        
        return {
            "template_id": template_id,
            "template_name": template.name,
            "design_system": design_system.to_dict(),
            "master_slides": master_slides,
            "recommended_structure": recommended_structure,
            "color_scheme": color_scheme,
            "font_scheme": font_scheme,
            "aspect_ratio": template.aspect_ratio,
        }
    
    def optimize_slide_layout(
        self,
        slide_data: dict[str, Any],
        available_layouts: list[SlideLayout] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Optimize layout for a single slide using intelligent algorithms."""
        
        # Convert slide data to content blocks
        content_blocks = self._convert_to_content_blocks(slide_data)
        
        # Get available layouts
        if available_layouts is None:
            available_layouts = [
                SlideLayout.TITLE,
                SlideLayout.TITLE_CONTENT,
                SlideLayout.TWO_COLUMN,
                SlideLayout.THREE_COLUMN,
                SlideLayout.IMAGE_TEXT,
                SlideLayout.TEXT_IMAGE,
                SlideLayout.FULL_IMAGE,
                SlideLayout.DATA_CHART,
            ]
        
        # Optimize layout
        layout_score = self.layout_optimizer.optimize_layout(
            content_blocks,
            available_layouts,
            constraints,
        )
        
        # Calculate optimal positions
        layout_zones = self.layout_optimizer._get_layout_zones(layout_score.layout_type)
        positions = self.layout_optimizer.optimize_element_positions(
            content_blocks,
            layout_zones,
        )
        
        return {
            "recommended_layout": layout_score.layout_type.value,
            "layout_score": layout_score.score,
            "layout_details": layout_score.details,
            "element_positions": positions,
        }
    
    def _convert_to_content_blocks(self, slide_data: dict[str, Any]) -> list[ContentBlock]:
        """Convert slide data to content blocks for layout optimization."""
        
        content_blocks = []
        
        # Extract title
        if slide_data.get("title"):
            content_blocks.append(ContentBlock(
                id="title",
                content_type=ContentType.TITLE,
                text=slide_data["title"],
                priority=LayoutPriority.CRITICAL,
                estimated_size=(100, 30),
            ))
        
        # Extract subtitle
        if slide_data.get("subtitle"):
            content_blocks.append(ContentBlock(
                id="subtitle",
                content_type=ContentType.SUBTITLE,
                text=slide_data["subtitle"],
                priority=LayoutPriority.HIGH,
                estimated_size=(100, 20),
            ))
        
        # Extract body text
        if slide_data.get("body"):
            content_blocks.append(ContentBlock(
                id="body",
                content_type=ContentType.BODY_TEXT,
                text=slide_data["body"],
                priority=LayoutPriority.MEDIUM,
                estimated_size=(100, 60),
            ))
        
        # Extract image
        if slide_data.get("image"):
            content_blocks.append(ContentBlock(
                id="image",
                content_type=ContentType.IMAGE,
                image_path=slide_data["image"],
                priority=LayoutPriority.HIGH,
                estimated_size=(100, 80),
            ))
        
        # Extract chart data
        if slide_data.get("chart"):
            content_blocks.append(ContentBlock(
                id="chart",
                content_type=ContentType.CHART,
                priority=LayoutPriority.MEDIUM,
                estimated_size=(100, 70),
            ))
        
        return content_blocks
    
    def assess_presentation_quality(
        self,
        presentation_id: UUID,
        presentation_data: list[dict[str, Any]],
    ) -> dict[str, DesignQualityReport]:
        """Assess design quality of an entire presentation."""
        
        # Get design system for this presentation
        design_system = self.get_design_system_for_presentation(presentation_id)
        
        # Update quality assessor with presentation-specific design system
        self.quality_assessor = DesignQualityAssessor(design_system)
        
        # Assess each slide
        quality_reports = {}
        for i, slide_data in enumerate(presentation_data):
            previous_slides = presentation_data[:i]
            report = self.quality_assessor.assess_slide(slide_data, previous_slides)
            slide_id = slide_data.get("id", f"slide_{i}")
            quality_reports[slide_id] = report
        
        return quality_reports
    
    def get_quality_summary(
        self,
        quality_reports: dict[str, DesignQualityReport],
    ) -> dict[str, Any]:
        """Generate a summary of quality assessment results."""
        
        total_slides = len(quality_reports)
        if total_slides == 0:
            return {"total_slides": 0, "average_score": 0.0, "overall_level": "unknown"}
        
        # Calculate average scores
        overall_scores = [report.overall_score for report in quality_reports.values()]
        average_score = sum(overall_scores) / total_slides
        
        # Count quality levels
        level_counts: dict[str, int] = {}
        for report in quality_reports.values():
            level = report.overall_level.value
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Collect all priority improvements
        all_improvements = []
        for report in quality_reports.values():
            all_improvements.extend(report.priority_improvements)
        
        # Get top 5 priority improvements
        top_improvements = all_improvements[:5]
        
        return {
            "total_slides": total_slides,
            "average_score": round(average_score, 1),
            "overall_level": self._get_quality_level_from_score(average_score),
            "level_distribution": level_counts,
            "priority_improvements": top_improvements,
            "needs_review": [slide_id for slide_id, report in quality_reports.items() 
                          if report.overall_score < 75],
        }
    
    def _get_quality_level_from_score(self, score: float) -> str:
        """Get quality level from average score."""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "satisfactory"
        elif score >= 40:
            return "needs_improvement"
        else:
            return "poor"
    
    def get_visual_element(
        self,
        element_id: str,
        style_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get a visual element with optional styling."""
        
        element = self.visual_library.get_visual_element(element_id)
        if not element:
            raise ValueError(f"Visual element {element_id} not found")
        
        # Apply style overrides
        svg = element.apply_style(style_overrides) if style_overrides else element.svg_definition
        
        return {
            "id": element.id,
            "name": element.name,
            "element_type": element.element_type.value,
            "svg": svg,
            "default_style": element.default_style,
            "customizable": element.customizable,
        }
    
    def search_visual_elements(
        self,
        query: str,
        element_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search visual elements by query and type."""
        
        results = []
        
        # Search icons
        if element_type is None or element_type == "icon":
            icons = self.visual_library.search_icons(query)
            for icon in icons:
                results.append({
                    "type": "icon",
                    "id": icon.id,
                    "name": icon.name,
                    "category": icon.category.value,
                    "description": icon.description,
                })
        
        # Search chart templates
        if element_type is None or element_type == "chart":
            for _template_id, template in self.visual_library.chart_templates.items():
                if query.lower() in template.name.lower():
                    results.append({
                        "type": "chart",
                        "id": template.id,
                        "name": template.name,
                        "chart_type": template.chart_type.value,
                        "description": template.description,
                    })
        
        return results
    
    def export_design_system(
        self,
        presentation_id: UUID,
        output_path: Path,
    ) -> Path:
        """Export the design system for a presentation to a JSON file."""
        
        import json
        
        design_system = self.get_design_system_for_presentation(presentation_id)
        design_system_dict = design_system.to_dict()
        
        output_path.write_text(json.dumps(design_system_dict, indent=2), encoding='utf-8')
        
        return output_path
    
    def import_custom_design_system(
        self,
        presentation_id: UUID,
        design_system_path: Path,
    ) -> DesignSystem:
        """Import a custom design system from a JSON file."""
        
        import json

        
        _design_system_data = json.loads(design_system_path.read_text(encoding='utf-8'))
        
        # Create DesignSystem from imported data
        # This would need proper deserialization logic
        # For now, create a modified default system
        
        custom_system = create_default_design_system()
        
        # Cache the custom system
        self._presentation_design_systems[presentation_id] = custom_system
        
        return custom_system
    
    def get_available_templates(self) -> list[dict[str, Any]]:
        """Get list of available presentation templates."""
        
        templates = list_templates()
        
        return [
            {
                "id": template.id,
                "name": template.name,
                "type": template.presentation_type.value,
                "description": template.description,
                "color_scheme": template.color_scheme,
                "font_scheme": template.font_scheme,
                "aspect_ratio": template.aspect_ratio,
            }
            for template in templates
        ]
    
    def validate_design_system_compliance(
        self,
        presentation_id: UUID,
        presentation_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate that a presentation complies with its design system."""
        
        design_system = self.get_design_system_for_presentation(presentation_id)
        
        # Validate accessibility
        accessibility_issues = design_system.validate_accessibility()
        
        # Assess quality
        quality_reports = self.assess_presentation_quality(presentation_id, presentation_data)
        quality_summary = self.get_quality_summary(quality_reports)
        
        return {
            "design_system_valid": len(accessibility_issues) == 0,
            "accessibility_issues": accessibility_issues,
            "quality_summary": quality_summary,
            "compliance_score": quality_summary["average_score"],
            "is_compliant": quality_summary["average_score"] >= 75,
        }
