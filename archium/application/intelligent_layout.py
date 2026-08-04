"""Intelligent layout algorithms for professional slide composition.

This module provides smart layout optimization algorithms that consider:
- Visual balance and hierarchy
- Content-aware layout selection
- White space optimization
- Cross-page consistency
- Professional design principles
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from archium.domain.design_system import DesignSystem, create_default_design_system
from archium.domain.presentation_templates import SlideLayout
from archium.domain.visual_elements import VisualElementsLibrary, get_visual_elements_library


class LayoutPriority(str, Enum):
    """Priority levels for layout elements."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentType(str, Enum):
    """Types of content for layout decisions."""
    TITLE = "title"
    SUBTITLE = "subtitle"
    BODY_TEXT = "body_text"
    HEADING = "heading"
    IMAGE = "image"
    CHART = "chart"
    DIAGRAM = "diagram"
    QUOTE = "quote"
    LIST = "list"
    TABLE = "table"
    MIXED = "mixed"


@dataclass
class ContentBlock:
    """A block of content to be laid out."""
    id: str
    content_type: ContentType
    text: str | None = None
    image_path: str | None = None
    priority: LayoutPriority = LayoutPriority.MEDIUM
    estimated_size: tuple[int, int] = (100, 100)  # width, height in relative units
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def get_aspect_ratio(self) -> float:
        """Calculate aspect ratio of the content block."""
        width, height = self.estimated_size
        if height == 0:
            return 1.0
        return width / height


@dataclass
class LayoutZone:
    """A zone within a slide layout."""
    id: str
    name: str
    position: tuple[float, float, float, float]  # x, y, width, height (normalized 0-1)
    content_type: ContentType | None = None
    min_size: tuple[float, float] = (0.1, 0.1)  # minimum width, height (normalized)
    preferred_content: list[ContentType] = field(default_factory=list)
    
    def get_area(self) -> float:
        """Calculate the area of the zone."""
        _, _, width, height = self.position
        return width * height
    
    def get_center(self) -> tuple[float, float]:
        """Get the center point of the zone."""
        x, y, width, height = self.position
        return (x + width / 2, y + height / 2)


@dataclass
class LayoutScore:
    """Score for a layout configuration."""
    layout_type: SlideLayout
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: LayoutScore) -> bool:
        return self.score < other.score


class LayoutOptimizer:
    """Intelligent layout optimization engine."""
    
    def __init__(
        self,
        design_system: DesignSystem | None = None,
        visual_library: VisualElementsLibrary | None = None,
    ) -> None:
        self.design_system = design_system or create_default_design_system()
        self.visual_library = visual_library or get_visual_elements_library()
        
        # Golden ratio for aesthetically pleasing proportions
        self.golden_ratio = 1.618
        
        # Standard slide dimensions (16:9 aspect ratio)
        self.slide_width = 1600
        self.slide_height = 900
        
    def optimize_layout(
        self,
        content_blocks: list[ContentBlock],
        available_layouts: list[SlideLayout],
        constraints: dict[str, Any] | None = None,
    ) -> LayoutScore:
        """Find the optimal layout for given content blocks.
        
        Args:
            content_blocks: List of content blocks to layout
            available_layouts: List of layout types to consider
            constraints: Optional layout constraints
        
        Returns:
            LayoutScore with the best layout and its score
        """
        constraints = constraints or {}
        
        # Score each available layout
        scored_layouts = []
        for layout in available_layouts:
            score = self._score_layout(layout, content_blocks, constraints)
            scored_layouts.append(score)
        
        # Sort by score (higher is better)
        scored_layouts.sort(key=lambda x: x.score, reverse=True)
        
        return scored_layouts[0] if scored_layouts else LayoutScore(
            layout_type=SlideLayout.TITLE_CONTENT,
            score=0.0,
            details={"reason": "No suitable layout found"},
        )
    
    def _score_layout(
        self,
        layout: SlideLayout,
        content_blocks: list[ContentBlock],
        constraints: dict[str, Any],
    ) -> LayoutScore:
        """Score a specific layout for the given content."""
        score = 0.0
        details = {}
        
        # Get layout zones for this layout type
        zones = self._get_layout_zones(layout)
        
        # 1. Content fit score (0-30 points)
        fit_score = self._score_content_fit(content_blocks, zones)
        score += fit_score * 0.30
        details["content_fit"] = fit_score
        
        # 2. Visual balance score (0-25 points)
        balance_score = self._score_visual_balance(content_blocks, zones)
        score += balance_score * 0.25
        details["visual_balance"] = balance_score
        
        # 3. Hierarchy score (0-20 points)
        hierarchy_score = self._score_hierarchy(content_blocks, zones)
        score += hierarchy_score * 0.20
        details["hierarchy"] = hierarchy_score
        
        # 4. White space score (0-15 points)
        whitespace_score = self._score_whitespace(content_blocks, zones)
        score += whitespace_score * 0.15
        details["whitespace"] = whitespace_score
        
        # 5. Constraint satisfaction (0-10 points)
        constraint_score = self._score_constraints(layout, constraints)
        score += constraint_score * 0.10
        details["constraints"] = constraint_score
        
        return LayoutScore(layout_type=layout, score=score, details=details)
    
    def _get_layout_zones(self, layout: SlideLayout) -> list[LayoutZone]:
        """Get the zones for a specific layout type."""
        
        if layout == SlideLayout.TITLE:
            return [
                LayoutZone(
                    id="title_center",
                    name="Title Center",
                    position=(0.2, 0.4, 0.6, 0.2),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE],
                ),
            ]
        
        elif layout == SlideLayout.TITLE_SUBTITLE:
            return [
                LayoutZone(
                    id="title_top",
                    name="Title Top",
                    position=(0.1, 0.2, 0.8, 0.15),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE],
                ),
                LayoutZone(
                    id="subtitle_middle",
                    name="Subtitle Middle",
                    position=(0.2, 0.4, 0.6, 0.1),
                    content_type=ContentType.SUBTITLE,
                    preferred_content=[ContentType.SUBTITLE],
                ),
            ]
        
        elif layout == SlideLayout.TWO_COLUMN:
            return [
                LayoutZone(
                    id="title_top",
                    name="Title Top",
                    position=(0.05, 0.05, 0.9, 0.15),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE, ContentType.HEADING],
                ),
                LayoutZone(
                    id="left_column",
                    name="Left Column",
                    position=(0.05, 0.25, 0.42, 0.7),
                    content_type=ContentType.MIXED,
                    preferred_content=[ContentType.BODY_TEXT, ContentType.IMAGE, ContentType.CHART],
                ),
                LayoutZone(
                    id="right_column",
                    name="Right Column",
                    position=(0.53, 0.25, 0.42, 0.7),
                    content_type=ContentType.MIXED,
                    preferred_content=[ContentType.BODY_TEXT, ContentType.IMAGE, ContentType.CHART],
                ),
            ]
        
        elif layout == SlideLayout.THREE_COLUMN:
            return [
                LayoutZone(
                    id="title_top",
                    name="Title Top",
                    position=(0.02, 0.05, 0.96, 0.12),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE, ContentType.HEADING],
                ),
                LayoutZone(
                    id="column_1",
                    name="Column 1",
                    position=(0.02, 0.2, 0.31, 0.75),
                    content_type=ContentType.MIXED,
                ),
                LayoutZone(
                    id="column_2",
                    name="Column 2",
                    position=(0.34, 0.2, 0.31, 0.75),
                    content_type=ContentType.MIXED,
                ),
                LayoutZone(
                    id="column_3",
                    name="Column 3",
                    position=(0.66, 0.2, 0.31, 0.75),
                    content_type=ContentType.MIXED,
                ),
            ]
        
        elif layout == SlideLayout.IMAGE_TEXT:
            return [
                LayoutZone(
                    id="title_top",
                    name="Title Top",
                    position=(0.05, 0.05, 0.9, 0.12),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE],
                ),
                LayoutZone(
                    id="image_left",
                    name="Image Left",
                    position=(0.05, 0.2, 0.48, 0.75),
                    content_type=ContentType.IMAGE,
                    preferred_content=[ContentType.IMAGE, ContentType.DIAGRAM],
                ),
                LayoutZone(
                    id="text_right",
                    name="Text Right",
                    position=(0.55, 0.2, 0.4, 0.75),
                    content_type=ContentType.BODY_TEXT,
                    preferred_content=[ContentType.BODY_TEXT, ContentType.LIST],
                ),
            ]
        
        elif layout == SlideLayout.TEXT_IMAGE:
            return [
                LayoutZone(
                    id="title_top",
                    name="Title Top",
                    position=(0.05, 0.05, 0.9, 0.12),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE],
                ),
                LayoutZone(
                    id="text_left",
                    name="Text Left",
                    position=(0.05, 0.2, 0.4, 0.75),
                    content_type=ContentType.BODY_TEXT,
                    preferred_content=[ContentType.BODY_TEXT, ContentType.LIST],
                ),
                LayoutZone(
                    id="image_right",
                    name="Image Right",
                    position=(0.48, 0.2, 0.48, 0.75),
                    content_type=ContentType.IMAGE,
                    preferred_content=[ContentType.IMAGE, ContentType.DIAGRAM],
                ),
            ]
        
        elif layout == SlideLayout.FULL_IMAGE:
            return [
                LayoutZone(
                    id="image_full",
                    name="Full Image",
                    position=(0.0, 0.0, 1.0, 1.0),
                    content_type=ContentType.IMAGE,
                    preferred_content=[ContentType.IMAGE],
                ),
            ]
        
        elif layout == SlideLayout.DATA_CHART:
            return [
                LayoutZone(
                    id="title_top",
                    name="Title Top",
                    position=(0.05, 0.05, 0.9, 0.1),
                    content_type=ContentType.TITLE,
                    preferred_content=[ContentType.TITLE],
                ),
                LayoutZone(
                    id="chart_center",
                    name="Chart Center",
                    position=(0.1, 0.18, 0.8, 0.65),
                    content_type=ContentType.CHART,
                    preferred_content=[ContentType.CHART],
                ),
                LayoutZone(
                    id="legend_bottom",
                    name="Legend Bottom",
                    position=(0.1, 0.85, 0.8, 0.1),
                    content_type=ContentType.BODY_TEXT,
                    preferred_content=[ContentType.BODY_TEXT],
                ),
            ]
        
        # Default fallback
        return [
            LayoutZone(
                id="content_area",
                name="Content Area",
                position=(0.05, 0.05, 0.9, 0.9),
                content_type=ContentType.MIXED,
            ),
        ]
    
    def _score_content_fit(
        self,
        content_blocks: list[ContentBlock],
        zones: list[LayoutZone],
    ) -> float:
        """Score how well content fits into the layout zones."""
        if not zones:
            return 0.0
        
        score = 0.0
        total_zones = len(zones)
        matched_zones = 0
        
        # Simple matching: count content blocks that fit in preferred zones
        for block in content_blocks:
            for zone in zones:
                if not zone.preferred_content:
                    matched_zones += 1
                    break
                if block.content_type in zone.preferred_content:
                    matched_zones += 1
                    break
        
        # Calculate fit ratio
        if total_zones > 0:
            score = matched_zones / max(len(content_blocks), total_zones)
        
        return min(score, 1.0)
    
    def _score_visual_balance(
        self,
        content_blocks: list[ContentBlock],
        zones: list[LayoutZone],
    ) -> float:
        """Score the visual balance of the layout."""
        if not zones or not content_blocks:
            return 0.5  # Neutral score
        
        # Calculate center of mass for content
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        
        for i, _block in enumerate(content_blocks):
            if i < len(zones):
                zone = zones[i]
                center_x, center_y = zone.get_center()
                weight = zone.get_area()
                
                weighted_x += center_x * weight
                weighted_y += center_y * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.5
        
        # Calculate center of mass
        center_of_mass_x = weighted_x / total_weight
        center_of_mass_y = weighted_y / total_weight
        
        # Ideal center is (0.5, 0.5)
        ideal_x, ideal_y = 0.5, 0.5
        
        # Calculate deviation from ideal center
        deviation = math.sqrt((center_of_mass_x - ideal_x) ** 2 + (center_of_mass_y - ideal_y) ** 2)
        
        # Max possible deviation is ~0.5
        max_deviation = 0.5
        
        # Score: less deviation = higher score
        balance_score = 1.0 - (deviation / max_deviation)
        
        return max(balance_score, 0.0)
    
    def _score_hierarchy(
        self,
        content_blocks: list[ContentBlock],
        zones: list[LayoutZone],
    ) -> float:
        """Score the information hierarchy of the layout."""
        if not content_blocks or not zones:
            return 0.5
        
        score = 0.0
        
        # Check that high-priority content gets prominent placement
        high_priority_blocks = [b for b in content_blocks if b.priority == LayoutPriority.CRITICAL]
        
        if not high_priority_blocks:
            return 0.8  # No critical content, neutral score
        
        # Check if critical content is in top zones (by position)
        top_zones = sorted(zones, key=lambda z: z.position[1])[:min(2, len(zones))]
        
        matched_critical = 0
        for block in high_priority_blocks:
            for zone in top_zones:
                if block.content_type in zone.preferred_content or not zone.preferred_content:
                    matched_critical += 1
                    break
        
        if high_priority_blocks:
            score = matched_critical / len(high_priority_blocks)
        
        return score
    
    def _score_whitespace(
        self,
        content_blocks: list[ContentBlock],
        zones: list[LayoutZone],
    ) -> float:
        """Score the white space distribution."""
        if not zones:
            return 0.5
        
        # Calculate total content area vs total slide area
        total_content_area = sum(zone.get_area() for zone in zones)
        total_slide_area = 1.0  # Normalized
        
        # Ideal content coverage is around 60-75%
        coverage_ratio = total_content_area / total_slide_area
        
        # Score based on how close to ideal coverage
        ideal_coverage = 0.65
        deviation = abs(coverage_ratio - ideal_coverage)
        
        # Max reasonable deviation is 0.35
        max_deviation = 0.35
        
        whitespace_score = 1.0 - (deviation / max_deviation)
        
        return max(whitespace_score, 0.0)
    
    def _score_constraints(
        self,
        layout: SlideLayout,
        constraints: dict[str, Any],
    ) -> float:
        """Score how well the layout satisfies constraints."""
        if not constraints:
            return 1.0  # No constraints, perfect score
        
        score = 1.0
        total_constraints = len(constraints)
        satisfied_constraints = 0
        
        # Check specific constraints
        if "require_image" in constraints and constraints["require_image"]:
            image_layouts = [SlideLayout.IMAGE_TEXT, SlideLayout.TEXT_IMAGE, SlideLayout.FULL_IMAGE]
            if layout in image_layouts:
                satisfied_constraints += 1
        
        if "require_columns" in constraints:
            required_columns = constraints["require_columns"]
            if required_columns == 2 and layout == SlideLayout.TWO_COLUMN or required_columns == 3 and layout == SlideLayout.THREE_COLUMN:
                satisfied_constraints += 1
        
        if "max_content_blocks" in constraints:
            _max_blocks = constraints["max_content_blocks"]
            # This would need actual content block count, simplified here
            satisfied_constraints += 1  # Placeholder
        
        if total_constraints > 0:
            score = satisfied_constraints / total_constraints
        
        return score
    
    def calculate_optimal_spacing(
        self,
        content_blocks: list[ContentBlock],
        container_size: tuple[int, int],
    ) -> dict[str, int]:
        """Calculate optimal spacing between elements.
        
        Args:
            content_blocks: List of content blocks
            container_size: Container width and height in pixels
        
        Returns:
            Dictionary with spacing values in pixels
        """
        container_width, container_height = container_size
        
        # Use design system spacing scale
        _spacing_scale = self.design_system.spacing.scale
        
        # Calculate base spacing based on container size
        base_spacing = min(container_width, container_height) * 0.02
        
        # Apply golden ratio for different spacing levels
        spacing_levels = {
            "xs": int(base_spacing * 0.5),
            "sm": int(base_spacing * 0.75),
            "md": int(base_spacing),
            "lg": int(base_spacing * 1.5),
            "xl": int(base_spacing * 2.0),
        }
        
        return spacing_levels
    
    def optimize_element_positions(
        self,
        content_blocks: list[ContentBlock],
        layout_zones: list[LayoutZone],
        slide_size: tuple[int, int] = (1600, 900),
    ) -> list[dict[str, Any]]:
        """Optimize actual positions of elements within zones.
        
        Args:
            content_blocks: List of content blocks
            layout_zones: List of layout zones
            slide_size: Slide dimensions in pixels
        
        Returns:
            List of element position dictionaries
        """
        slide_width, slide_height = slide_size
        positions = []
        
        # Calculate optimal spacing
        spacing = self.calculate_optimal_spacing(content_blocks, slide_size)
        
        for _i, (block, zone) in enumerate(zip(content_blocks, layout_zones, strict=True)):
            # Convert normalized zone coordinates to pixels
            zone_x, zone_y, zone_width, zone_height = zone.position
            
            pixel_x = int(zone_x * slide_width)
            pixel_y = int(zone_y * slide_height)
            pixel_width = int(zone_width * slide_width)
            pixel_height = int(zone_height * slide_height)
            
            # Apply spacing
            inner_margin = spacing["sm"]
            
            element_position = {
                "id": block.id,
                "x": pixel_x + inner_margin,
                "y": pixel_y + inner_margin,
                "width": max(pixel_width - 2 * inner_margin, 100),
                "height": max(pixel_height - 2 * inner_margin, 50),
                "zone_id": zone.id,
                "priority": block.priority.value,
            }
            
            positions.append(element_position)
        
        return positions


class LayoutConsistencyChecker:
    """Ensures consistency across slides in a presentation."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
        self.slide_history: list[dict[str, Any]] = []
    
    def check_consistency(
        self,
        current_slide: dict[str, Any],
        previous_slides: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Check consistency of current slide with previous slides.
        
        Args:
            current_slide: Current slide layout and content
            previous_slides: Optional list of previous slides
        
        Returns:
            Dictionary with consistency scores and issues
        """
        previous_slides = previous_slides or self.slide_history
        
        consistency_report = {
            "overall_score": 0.0,
            "issues": [],
            "warnings": [],
        }
        
        if not previous_slides:
            consistency_report["overall_score"] = 1.0
            return consistency_report
        
        # Check title position consistency
        title_consistency = self._check_title_position(current_slide, previous_slides)
        consistency_report["title_consistency"] = title_consistency
        
        # Check color usage consistency
        color_consistency = self._check_color_consistency(current_slide, previous_slides)
        consistency_report["color_consistency"] = color_consistency
        
        # Check font consistency
        font_consistency = self._check_font_consistency(current_slide, previous_slides)
        consistency_report["font_consistency"] = font_consistency
        
        # Calculate overall score
        scores = [
            title_consistency.get("score", 0.5),
            color_consistency.get("score", 0.5),
            font_consistency.get("score", 0.5),
        ]
        consistency_report["overall_score"] = sum(scores) / len(scores)
        
        return consistency_report
    
    def _check_title_position(
        self,
        current_slide: dict[str, Any],
        previous_slides: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Check title position consistency."""
        # Simplified implementation
        return {"score": 0.8, "issues": []}
    
    def _check_color_consistency(
        self,
        current_slide: dict[str, Any],
        previous_slides: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Check color usage consistency."""
        # Simplified implementation
        return {"score": 0.8, "issues": []}
    
    def _check_font_consistency(
        self,
        current_slide: dict[str, Any],
        previous_slides: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Check font usage consistency."""
        # Simplified implementation
        return {"score": 0.8, "issues": []}
    
    def add_slide_to_history(self, slide: dict[str, Any]) -> None:
        """Add slide to history for consistency checking."""
        self.slide_history.append(slide)
