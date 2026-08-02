"""Professional visual elements library for architectural presentations.

This module defines icons, charts, and visual elements specifically designed
for architectural and planning presentations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from archium.domain.design_system import DesignSystem, create_default_design_system, ColorRole


class IconCategory(str, Enum):
    """Categories of architectural icons."""
    SITE_PLANNING = "site_planning"
    BUILDING_ELEMENTS = "building_elements"
    ANALYSIS = "analysis"
    SUSTAINABILITY = "sustainability"
    TRANSPORTATION = "transportation"
    LANDSCAPE = "landscape"
    STRUCTURAL = "structural"
    SERVICES = "services"
    FURNITURE = "furniture"
    SYMBOLS = "symbols"


class IconStyle(str, Enum):
    """Icon style options."""
    OUTLINE = "outline"
    FILLED = "filled"
    DUOTONE = "duotone"
    LINEAR = "linear"


@dataclass
class Icon:
    """Architectural icon definition."""
    id: str
    name: str
    category: IconCategory
    description: str
    svg_path: str  # SVG path data
    style: IconStyle = IconStyle.OUTLINE
    keywords: list[str] = field(default_factory=list)
    variants: dict[str, str] = field(default_factory=dict)  # Style variants
    
    def to_svg(self, size: int = 24, color: str = "#000000") -> str:
        """Generate SVG element for the icon."""
        return f'''
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="{self.svg_path}" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        '''
    
    def to_filled_svg(self, size: int = 24, color: str = "#000000") -> str:
        """Generate filled SVG element."""
        return f'''
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="{color}" xmlns="http://www.w3.org/2000/svg">
            <path d="{self.svg_path}"/>
        </svg>
        '''


class ChartType(str, Enum):
    """Types of charts for architectural data."""
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    PIE_CHART = "pie_chart"
    AREA_CHART = "area_chart"
    SCATTER_PLOT = "scatter_plot"
    HISTOGRAM = "histogram"
    STACKED_BAR = "stacked_bar"
    GROUPED_BAR = "grouped_bar"
    RADAR_CHART = "radar_chart"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    SANKEY = "sankey"


@dataclass
class ChartStyle:
    """Chart styling configuration."""
    color_palette: list[str]
    font_family: str = "sans-serif"
    show_grid: bool = True
    show_legend: bool = True
    animation_duration: int = 500
    border_radius: int = 4
    line_width: int = 2
    point_size: int = 4
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for charting libraries."""
        return {
            "colors": self.color_palette,
            "font": {"family": self.font_family},
            "grid": {"display": self.show_grid},
            "legend": {"display": self.show_legend},
            "animation": {"duration": self.animation_duration},
            "elements": {
                "rectangle": {"borderRadius": self.border_radius},
                "line": {"borderWidth": self.line_width},
                "point": {"radius": self.point_size},
            },
        }


@dataclass
class ChartTemplate:
    """Pre-configured chart template for specific data types."""
    id: str
    name: str
    chart_type: ChartType
    description: str
    style: ChartStyle
    data_requirements: dict[str, Any]
    example_data: dict[str, Any] = field(default_factory=dict)
    use_cases: list[str] = field(default_factory=list)
    
    def validate_data(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate if data matches template requirements."""
        errors = []
        
        for field, requirement in self.data_requirements.items():
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif requirement.get("type") == "array" and not isinstance(data[field], list):
                errors.append(f"Field {field} must be an array")
            elif requirement.get("type") == "number" and not isinstance(data[field], (int, float)):
                errors.append(f"Field {field} must be a number")
        
        return len(errors) == 0, errors


class DiagramType(str, Enum):
    """Types of architectural diagrams."""
    FLOOR_PLAN = "floor_plan"
    SITE_PLAN = "site_plan"
    ELEVATION = "elevation"
    SECTION = "section"
    AXONOMETRIC = "axonometric"
    PERSPECTIVE = "perspective"
    BLOCK_DIAGRAM = "block_diagram"
    FLOW_CHART = "flow_chart"
    NETWORK_DIAGRAM = "network_diagram"
    ORGANIZATION_CHART = "organization_chart"


@dataclass
class DiagramElement:
    """Standardized element for architectural diagrams."""
    id: str
    name: str
    diagram_type: DiagramType
    svg_definition: str
    default_color: str
    scale_factor: float = 1.0
    editable_properties: list[str] = field(default_factory=list)
    
    def to_svg(self, width: int = 100, height: int = 100, color: str = None) -> str:
        """Generate SVG for the diagram element."""
        fill_color = color or self.default_color
        return f'''
        <svg width="{width}" height="{height}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            {self.svg_definition}
        </svg>
        '''


class VisualElementType(str, Enum):
    """Types of visual elements."""
    ARROW = "arrow"
    CALLOUT = "callout"
    HIGHLIGHT = "highlight"
    DIMENSION_LINE = "dimension_line"
    GRID = "grid"
    SCALE_BAR = "scale_bar"
    NORTH_ARROW = "north_arrow"
    LEGEND = "legend"
    TITLE_BLOCK = "title_block"
    BORDER = "border"
    BACKGROUND = "background"


@dataclass
class VisualElement:
    """General visual element for presentations."""
    id: str
    name: str
    element_type: VisualElementType
    description: str
    svg_definition: str
    default_style: dict[str, Any] = field(default_factory=dict)
    customizable: bool = True
    style_properties: list[str] = field(default_factory=list)
    
    def apply_style(self, style: dict[str, Any]) -> str:
        """Apply custom styles to the element."""
        merged_style = {**self.default_style, **style}
        # Replace style placeholders in SVG
        styled_svg = self.svg_definition
        for prop, value in merged_style.items():
            styled_svg = styled_svg.replace(f"{{{prop}}}", str(value))
        return styled_svg


class VisualElementsLibrary:
    """Complete library of visual elements for architectural presentations."""
    
    def __init__(self, design_system: DesignSystem | None = None) -> None:
        self.design_system = design_system or create_default_design_system()
        self.icons: dict[str, Icon] = {}
        self.chart_templates: dict[str, ChartTemplate] = {}
        self.diagram_elements: dict[str, DiagramElement] = {}
        self.visual_elements: dict[str, VisualElement] = {}
        
        self._initialize_icons()
        self._initialize_chart_templates()
        self._initialize_diagram_elements()
        self._initialize_visual_elements()
    
    def _initialize_icons(self) -> None:
        """Initialize architectural icon library."""
        
        # Site planning icons
        self.icons["building"] = Icon(
            id="building",
            name="Building",
            category=IconCategory.SITE_PLANNING,
            description="Generic building icon",
            svg_path="M3 21h18M5 21V7l8-4 8 4v14M5 7l8-4 8 4M5 21V7l8-4 8 4v14",
            keywords=["architecture", "structure", "site"],
        )
        
        self.icons["site"] = Icon(
            id="site",
            name="Site Plan",
            category=IconCategory.SITE_PLANNING,
            description="Site plan icon",
            svg_path="M2 12h20M2 12l4-4m-4 4l4 4M22 12l-4-4m4 4l-4 4M12 2v20",
            keywords=["location", "map", "planning"],
        )
        
        self.icons["parking"] = Icon(
            id="parking",
            name="Parking",
            category=IconCategory.TRANSPORTATION,
            description="Parking icon",
            svg_path="M19 13v6h-3v-6h-3v6h-3v-6H7v6H4v-6H2v-2h20v2h-2zM7 2v3h3V2H7zm4 0v3h3V2h-3zm4 0v3h3V2h-3z",
            keywords=["car", "transport", "parking"],
        )
        
        self.icons["green_space"] = Icon(
            id="green_space",
            name="Green Space",
            category=IconCategory.LANDSCAPE,
            description="Green space/landscape icon",
            svg_path="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
            keywords=["landscape", "garden", "nature"],
        )
        
        self.icons["solar"] = Icon(
            id="solar",
            name="Solar Panel",
            category=IconCategory.SUSTAINABILITY,
            description="Solar panel/sustainability icon",
            svg_path="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 8a4 4 0 100 8 4 4 0 000-8z",
            keywords=["sustainability", "energy", "green"],
        )
        
        self.icons["water"] = Icon(
            id="water",
            name="Water",
            category=IconCategory.SERVICES,
            description="Water/services icon",
            svg_path="M12 2.69l5.66 5.66a8 8 0 11-11.31 0z",
            keywords=["water", "services", "utilities"],
        )
        
        # Analysis icons
        self.icons["analysis"] = Icon(
            id="analysis",
            name="Analysis",
            category=IconCategory.ANALYSIS,
            description="Analysis/research icon",
            svg_path="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
            keywords=["data", "statistics", "research"],
        )
        
        self.icons["compass"] = Icon(
            id="compass",
            name="Compass",
            category=IconCategory.SYMBOLS,
            description="Compass/orientation icon",
            svg_path="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
            keywords=["direction", "orientation", "navigation"],
        )
    
    def _initialize_chart_templates(self) -> None:
        """Initialize chart templates."""
        
        # Get colors from design system
        colors = [
            self.design_system.color_palette.get_color(ColorRole.PRIMARY).hex_value,
            self.design_system.color_palette.get_color(ColorRole.SECONDARY).hex_value,
            self.design_system.color_palette.get_color(ColorRole.ACCENT).hex_value,
            self.design_system.color_palette.get_color(ColorRole.SUCCESS).hex_value,
        ]
        
        base_style = ChartStyle(color_palette=colors)
        
        # Area analysis chart
        self.chart_templates["area_analysis"] = ChartTemplate(
            id="area_analysis",
            name="Area Analysis Chart",
            chart_type=ChartType.STACKED_BAR,
            description="Stacked bar chart for area analysis",
            style=base_style,
            data_requirements={
                "labels": {"type": "array", "description": "Area categories"},
                "datasets": {"type": "array", "description": "Data series"},
            },
            example_data={
                "labels": ["Residential", "Commercial", "Public", "Green"],
                "datasets": [
                    {"label": "Existing", "data": [30, 20, 15, 25]},
                    {"label": "Proposed", "data": [40, 25, 20, 30]},
                ],
            },
            use_cases=["Site analysis", "Program analysis", "Area breakdown"],
        )
        
        # Timeline chart
        self.chart_templates["timeline"] = ChartTemplate(
            id="timeline",
            name="Timeline Chart",
            chart_type=ChartType.GROUPED_BAR,
            description="Grouped bar chart for project timeline",
            style=base_style,
            data_requirements={
                "labels": {"type": "array", "description": "Time periods"},
                "datasets": {"type": "array", "description": "Project phases"},
            },
            example_data={
                "labels": ["Q1", "Q2", "Q3", "Q4"],
                "datasets": [
                    {"label": "Design", "data": [3, 2, 0, 0]},
                    {"label": "Construction", "data": [0, 1, 3, 2]},
                ],
            },
            use_cases=["Project scheduling", "Phasing", "Milestones"],
        )
        
        # Sustainability metrics
        self.chart_templates["sustainability"] = ChartTemplate(
            id="sustainability",
            name="Sustainability Metrics",
            chart_type=ChartType.RADAR_CHART,
            description="Radar chart for sustainability metrics",
            style=base_style,
            data_requirements={
                "labels": {"type": "array", "description": "Metric categories"},
                "datasets": {"type": "array", "description": "Metric values"},
            },
            example_data={
                "labels": ["Energy", "Water", "Materials", "Indoor Quality", "Innovation"],
                "datasets": [
                    {"label": "Current", "data": [70, 65, 80, 75, 60]},
                    {"label": "Target", "data": [85, 80, 90, 85, 75]},
                ],
            },
            use_cases=["LEED certification", "Green building", "Sustainability reporting"],
        )
    
    def _initialize_diagram_elements(self) -> None:
        """Initialize diagram elements."""
        
        # North arrow
        self.diagram_elements["north_arrow"] = DiagramElement(
            id="north_arrow",
            name="North Arrow",
            diagram_type=DiagramType.SITE_PLAN,
            svg_definition='<polygon points="50,10 90,90 50,70 10,90" fill="{color}" stroke="black" stroke-width="1"/>',
            default_color="#000000",
            editable_properties=["color", "size", "rotation"],
        )
        
        # Scale bar
        self.diagram_elements["scale_bar"] = DiagramElement(
            id="scale_bar",
            name="Scale Bar",
            diagram_type=DiagramType.SITE_PLAN,
            svg_definition='<rect x="10" y="45" width="80" height="10" fill="{color}" stroke="black" stroke-width="1"/><text x="50" y="85" text-anchor="middle" font-size="8">Scale</text>',
            default_color="#000000",
            editable_properties=["color", "length", "units"],
        )
        
        # Door symbol
        self.diagram_elements["door"] = DiagramElement(
            id="door",
            name="Door",
            diagram_type=DiagramType.FLOOR_PLAN,
            svg_definition='<path d="M10,50 L10,20 A30,30 0 0,1 40,50" fill="none" stroke="{color}" stroke-width="2"/><line x1="10" y1="50" x2="40" y2="50" stroke="{color}" stroke-width="2"/>',
            default_color="#000000",
            editable_properties=["color", "size", "swing_direction"],
        )
        
        # Window symbol
        self.diagram_elements["window"] = DiagramElement(
            id="window",
            name="Window",
            diagram_type=DiagramType.FLOOR_PLAN,
            svg_definition='<rect x="10" y="40" width="80" height="20" fill="none" stroke="{color}" stroke-width="2"/><line x1="50" y1="40" x2="50" y2="60" stroke="{color}" stroke-width="1"/>',
            default_color="#000000",
            editable_properties=["color", "size", "type"],
        )
    
    def _initialize_visual_elements(self) -> None:
        """Initialize general visual elements."""
        
        # Callout box
        self.visual_elements["callout"] = VisualElement(
            id="callout",
            name="Callout Box",
            element_type=VisualElementType.CALLOUT,
            description="Text callout box with pointer",
            svg_definition='<rect x="10" y="10" width="80" height="60" rx="4" fill="{background}" stroke="{border_color}" stroke-width="{border_width}"/><polygon points="50,70 45,80 55,80" fill="{background}" stroke="{border_color}" stroke-width="{border_width}"/>',
            default_style={
                "background": "#FFFFFF",
                "border_color": "#000000",
                "border_width": "2",
            },
            style_properties=["background", "border_color", "border_width"],
        )
        
        # Highlight box
        self.visual_elements["highlight"] = VisualElement(
            id="highlight",
            name="Highlight Box",
            element_type=VisualElementType.HIGHLIGHT,
            description="Highlight box for emphasis",
            svg_definition='<rect x="5" y="5" width="90" height="90" rx="8" fill="{color}" fill-opacity="{opacity}"/>',
            default_style={
                "color": "#FFEB3B",
                "opacity": "0.3",
            },
            style_properties=["color", "opacity"],
        )
        
        # Arrow pointer
        self.visual_elements["arrow"] = VisualElement(
            id="arrow",
            name="Arrow Pointer",
            element_type=VisualElementType.ARROW,
            description="Directional arrow",
            svg_definition='<line x1="10" y1="50" x2="90" y2="50" stroke="{color}" stroke-width="{width}" marker-end="url(#arrowhead)"/><defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="{color}"/></marker></defs>',
            default_style={
                "color": "#000000",
                "width": "2",
            },
            style_properties=["color", "width"],
        )
        
        # Title block
        self.visual_elements["title_block"] = VisualElement(
            id="title_block",
            name="Title Block",
            element_type=VisualElementType.TITLE_BLOCK,
            description="Standard title block for drawings",
            svg_definition='<rect x="60" y="70" width="35" height="25" fill="none" stroke="{color}" stroke-width="2"/><line x1="60" y1="80" x2="95" y2="80" stroke="{color}" stroke-width="1"/><line x1="60" y1="90" x2="95" y2="90" stroke="{color}" stroke-width="1"/>',
            default_style={
                "color": "#000000",
            },
            style_properties=["color"],
        )
    
    def get_icon(self, icon_id: str) -> Icon | None:
        """Get an icon by ID."""
        return self.icons.get(icon_id)
    
    def search_icons(self, query: str, category: IconCategory | None = None) -> list[Icon]:
        """Search icons by keyword and optionally category."""
        results = []
        query_lower = query.lower()
        
        for icon in self.icons.values():
            if category and icon.category != category:
                continue
            if (query_lower in icon.name.lower() or 
                any(query_lower in kw.lower() for kw in icon.keywords)):
                results.append(icon)
        
        return results
    
    def get_chart_template(self, template_id: str) -> ChartTemplate | None:
        """Get a chart template by ID."""
        return self.chart_templates.get(template_id)
    
    def get_diagram_element(self, element_id: str) -> DiagramElement | None:
        """Get a diagram element by ID."""
        return self.diagram_elements.get(element_id)
    
    def get_visual_element(self, element_id: str) -> VisualElement | None:
        """Get a visual element by ID."""
        return self.visual_elements.get(element_id)


# Global library instance
_visual_elements_library: VisualElementsLibrary | None = None


def get_visual_elements_library() -> VisualElementsLibrary:
    """Get the global visual elements library instance."""
    global _visual_elements_library
    if _visual_elements_library is None:
        _visual_elements_library = VisualElementsLibrary()
    return _visual_elements_library
