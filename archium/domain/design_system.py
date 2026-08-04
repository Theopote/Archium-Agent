"""Professional design system for architectural presentations.

This module defines the core design tokens and systems for creating
professional, visually consistent architectural presentations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ColorRole(str, Enum):
    """Color roles in the design system."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ACCENT = "accent"
    NEUTRAL = "neutral"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class ColorShade(str, Enum):
    """Color shade levels."""
    _50 = "50"
    _100 = "100"
    _200 = "200"
    _300 = "300"
    _400 = "400"
    _500 = "500"
    _600 = "600"
    _700 = "700"
    _800 = "800"
    _900 = "900"
    _950 = "950"


@dataclass
class ColorToken:
    """Individual color token with hex value and accessibility info."""
    hex_value: str
    name: str
    role: ColorRole
    shade: ColorShade
    contrast_ratio: float = 0.0  # WCAG contrast ratio
    is_accessible: bool = True
    
    def to_rgb(self) -> tuple[int, int, int]:
        """Convert hex to RGB tuple."""
        hex_value = self.hex_value.lstrip('#')
        channels = tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))
        return (channels[0], channels[1], channels[2])
    
    def to_css(self) -> str:
        """Convert to CSS color string."""
        return self.hex_value


@dataclass
class ColorPalette:
    """Complete color palette for a design theme."""
    name: str
    description: str
    primary: dict[ColorShade, ColorToken]
    secondary: dict[ColorShade, ColorToken]
    accent: dict[ColorShade, ColorToken]
    neutral: dict[ColorShade, ColorToken]
    semantic: dict[ColorRole, ColorToken]
    
    def get_color(self, role: ColorRole, shade: ColorShade = ColorShade._500) -> ColorToken:
        """Get a specific color from the palette."""
        if role == ColorRole.PRIMARY:
            return self.primary[shade]
        elif role == ColorRole.SECONDARY:
            return self.secondary[shade]
        elif role == ColorRole.ACCENT:
            return self.accent[shade]
        elif role == ColorRole.NEUTRAL:
            return self.neutral[shade]
        else:
            return self.semantic[role]
    
    def get_accessible_pair(self, background: ColorToken) -> ColorToken:
        """Get an accessible text color for the given background."""
        # Simple implementation - prefer darker colors on light backgrounds
        bg_luminance = self._get_luminance(background)
        if bg_luminance > 0.5:
            return self.neutral[ColorShade._900]
        else:
            return self.neutral[ColorShade._50]
    
    def _get_luminance(self, color: ColorToken) -> float:
        """Calculate relative luminance for accessibility."""
        red, green, blue = color.to_rgb()
        # Convert to linear RGB
        red_lin = self._linearize(red / 255)
        green_lin = self._linearize(green / 255)
        blue_lin = self._linearize(blue / 255)
        # Calculate luminance
        return 0.2126 * red_lin + 0.7152 * green_lin + 0.0722 * blue_lin
    
    def _linearize(self, value: float) -> float:
        """Linearize RGB value for luminance calculation."""
        if value <= 0.03928:
            return value / 12.92
        return float(((value + 0.055) / 1.055) ** 2.4)


class FontFamily(str, Enum):
    """Font family options."""
    SANS_SERIF = "sans_serif"
    SERIF = "serif"
    MONOSPACE = "monospace"
    DISPLAY = "display"


class FontWeight(str, Enum):
    """Font weight options."""
    THIN = "100"
    EXTRA_LIGHT = "200"
    LIGHT = "300"
    REGULAR = "400"
    MEDIUM = "500"
    SEMI_BOLD = "600"
    BOLD = "700"
    EXTRA_BOLD = "800"
    BLACK = "900"


class FontSize(str, Enum):
    """Font size tokens."""
    XS = "12px"
    SM = "14px"
    BASE = "16px"
    LG = "18px"
    XL = "20px"
    _2XL = "24px"
    _3XL = "30px"
    _4XL = "36px"
    _5XL = "48px"
    _6XL = "60px"
    _7XL = "72px"


@dataclass
class FontToken:
    """Font token with family, weight, size, and line height."""
    family: FontFamily
    weight: FontWeight
    size: FontSize
    line_height: float = 1.5
    letter_spacing: float = 0.0
    fallback: str = "system-ui, sans-serif"
    
    def to_css(self) -> str:
        """Convert to CSS font string."""
        weight_map = {
            FontWeight.THIN: "100",
            FontWeight.EXTRA_LIGHT: "200",
            FontWeight.LIGHT: "300",
            FontWeight.REGULAR: "400",
            FontWeight.MEDIUM: "500",
            FontWeight.SEMI_BOLD: "600",
            FontWeight.BOLD: "700",
            FontWeight.EXTRA_BOLD: "800",
            FontWeight.BLACK: "900",
        }
        
        family_map = {
            FontFamily.SANS_SERIF: "Inter, system-ui, sans-serif",
            FontFamily.SERIF: "Georgia, serif",
            FontFamily.MONOSPACE: "JetBrains Mono, monospace",
            FontFamily.DISPLAY: "Playfair Display, serif",
        }
        
        return (
            f"{weight_map[self.weight]} {self.size.value}/{self.line_height} "
            f"{family_map[self.family]}"
        )


def _nearest_font_size(size_px: int) -> FontSize:
    """Snap a computed pixel size to the nearest defined FontSize token."""
    candidates = sorted(
        ((int(token.value.rstrip("px")), token) for token in FontSize),
        key=lambda item: item[0],
    )
    return min(candidates, key=lambda item: abs(item[0] - size_px))[1]


@dataclass
class TypographyScale:
    """Typography scale with consistent sizing ratios."""
    name: str
    base_size: FontSize
    ratio: float = 1.25  # Perfect fourth ratio
    scale: dict[str, FontToken] = field(default_factory=dict)
    
    def generate_scale(self, base_token: FontToken) -> dict[str, FontToken]:
        """Generate typography scale from base token.

        Computed sizes are snapped to the nearest FontSize enum value so
        ratio-based steps never invent tokens outside the design system.
        """
        scale = {}
        sizes = [
            ("xs", -3),
            ("sm", -2),
            ("base", 0),
            ("lg", 1),
            ("xl", 2),
            ("2xl", 3),
            ("3xl", 4),
            ("4xl", 5),
            ("5xl", 6),
            ("6xl", 7),
        ]
        
        base_px = int(base_token.size.value.rstrip("px"))
        
        for name, steps in sizes:
            if steps < 0:
                size_px = int(base_px / (self.ratio ** abs(steps)))
            else:
                size_px = int(base_px * (self.ratio ** steps))
            
            scale[name] = FontToken(
                family=base_token.family,
                weight=base_token.weight,
                size=_nearest_font_size(size_px),
                line_height=base_token.line_height,
                letter_spacing=base_token.letter_spacing,
                fallback=base_token.fallback,
            )
        
        self.scale = scale
        return scale


class SpacingToken(str, Enum):
    """Spacing tokens based on 4px base unit."""
    _0 = "0px"
    _1 = "4px"
    _2 = "8px"
    _3 = "12px"
    _4 = "16px"
    _5 = "20px"
    _6 = "24px"
    _8 = "32px"
    _10 = "40px"
    _12 = "48px"
    _16 = "64px"
    _20 = "80px"
    _24 = "96px"
    _32 = "128px"


@dataclass
class SpacingScale:
    """Spacing scale based on consistent ratios."""
    base_unit: int = 4  # 4px base unit
    scale: dict[str, SpacingToken] = field(default_factory=dict)
    
    def generate_scale(self) -> dict[str, SpacingToken]:
        """Generate spacing scale."""
        scale = {
            "none": SpacingToken._0,
            "xs": SpacingToken._1,
            "sm": SpacingToken._2,
            "md": SpacingToken._3,
            "lg": SpacingToken._4,
            "xl": SpacingToken._5,
            "2xl": SpacingToken._6,
            "3xl": SpacingToken._8,
            "4xl": SpacingToken._10,
            "5xl": SpacingToken._12,
            "6xl": SpacingToken._16,
            "7xl": SpacingToken._20,
            "8xl": SpacingToken._24,
            "9xl": SpacingToken._32,
        }
        self.scale = scale
        return scale


@dataclass
class GridSystem:
    """Grid system for layout consistency."""
    columns: int = 12
    gutter: SpacingToken = SpacingToken._4
    max_width: str = "1200px"
    breakpoints: dict[str, int] = field(default_factory=lambda: {
        "sm": 640,
        "md": 768,
        "lg": 1024,
        "xl": 1280,
        "2xl": 1536,
    })
    
    def get_column_width(self, container_width: int) -> int:
        """Calculate column width based on container."""
        gutter_px = int(self.gutter.value.rstrip("px"))
        total_gutter = gutter_px * (self.columns - 1)
        return (container_width - total_gutter) // self.columns
    
    def get_span_width(self, span: int, container_width: int) -> int:
        """Get width for a specific column span."""
        column_width = self.get_column_width(container_width)
        gutter_px = int(self.gutter.value.rstrip("px"))
        return (column_width * span) + (gutter_px * (span - 1))


@dataclass
class ShadowToken:
    """Shadow token for elevation effects."""
    name: str
    x: str
    y: str
    blur: str
    spread: str
    color: str
    opacity: float = 1.0
    
    def to_css(self) -> str:
        """Convert to CSS box-shadow."""
        return f"{self.x} {self.y} {self.blur} {self.spread} rgba({self.color}, {self.opacity})"


@dataclass
class ShadowScale:
    """Shadow scale for elevation hierarchy."""
    shadows: dict[str, ShadowToken] = field(default_factory=dict)
    
    def generate_scale(self, base_color: str = "0,0,0") -> dict[str, ShadowToken]:
        """Generate shadow scale."""
        shadows = {
            "xs": ShadowToken("xs", "0px", "1px", "2px", "0px", base_color, 0.05),
            "sm": ShadowToken("sm", "0px", "1px", "3px", "0px", base_color, 0.1),
            "md": ShadowToken("md", "0px", "4px", "6px", "-1px", base_color, 0.1),
            "lg": ShadowToken("lg", "0px", "10px", "15px", "-3px", base_color, 0.1),
            "xl": ShadowToken("xl", "0px", "20px", "25px", "-5px", base_color, 0.1),
            "2xl": ShadowToken("2xl", "0px", "25px", "50px", "-12px", base_color, 0.25),
        }
        self.shadows = shadows
        return shadows


@dataclass
class BorderRadiusToken:
    """Border radius token for rounded corners."""
    name: str
    value: str
    
    def to_css(self) -> str:
        """Convert to CSS border-radius."""
        return self.value


@dataclass
class BorderRadiusScale:
    """Border radius scale for consistency."""
    radii: dict[str, BorderRadiusToken] = field(default_factory=dict)
    
    def generate_scale(self) -> dict[str, BorderRadiusToken]:
        """Generate border radius scale."""
        radii = {
            "none": BorderRadiusToken("none", "0px"),
            "sm": BorderRadiusToken("sm", "2px"),
            "md": BorderRadiusToken("md", "4px"),
            "lg": BorderRadiusToken("lg", "8px"),
            "xl": BorderRadiusToken("xl", "12px"),
            "2xl": BorderRadiusToken("2xl", "16px"),
            "full": BorderRadiusToken("full", "9999px"),
        }
        self.radii = radii
        return radii


@dataclass
class DesignSystem:
    """Complete design system combining all tokens."""
    name: str
    version: str
    description: str
    color_palette: ColorPalette
    typography: TypographyScale
    spacing: SpacingScale
    grid: GridSystem
    shadows: ShadowScale
    border_radius: BorderRadiusScale
    
    def to_dict(self) -> dict[str, Any]:
        """Convert design system to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "colors": {
                "palette": self.color_palette.name,
                "primary": {shade.value: color.hex_value for shade, color in self.color_palette.primary.items()},
                "secondary": {shade.value: color.hex_value for shade, color in self.color_palette.secondary.items()},
                "accent": {shade.value: color.hex_value for shade, color in self.color_palette.accent.items()},
                "neutral": {shade.value: color.hex_value for shade, color in self.color_palette.neutral.items()},
            },
            "typography": {
                "scale": {name: token.to_css() for name, token in self.typography.scale.items()},
            },
            "spacing": {
                "scale": {name: token.value for name, token in self.spacing.scale.items()},
            },
            "grid": {
                "columns": self.grid.columns,
                "gutter": self.grid.gutter.value,
                "max_width": self.grid.max_width,
            },
            "shadows": {
                "scale": {name: shadow.to_css() for name, shadow in self.shadows.shadows.items()},
            },
            "border_radius": {
                "scale": {name: radius.value for name, radius in self.border_radius.radii.items()},
            },
        }
    
    def validate_accessibility(self) -> list[str]:
        """Validate accessibility compliance (WCAG)."""
        issues = []
        
        # Check color contrast ratios
        for role, color in self.color_palette.semantic.items():
            if not color.is_accessible:
                issues.append(f"Color {role} does not meet WCAG contrast requirements")
        
        # Check font sizes for readability
        for name, token in self.typography.scale.items():
            size_px = int(token.size.value.rstrip("px"))
            if size_px < 12:
                issues.append(f"Typography {name} size {size_px}px is below minimum readable size")
        
        return issues


# Predefined professional color palettes for architectural presentations
def create_architecture_professional_palette() -> ColorPalette:
    """Create a professional color palette for architectural presentations."""
    
    # Primary - Deep blue (professional, trustworthy)
    primary_colors = {
        ColorShade._50: ColorToken("#F0F9FF", "Sky 50", ColorRole.PRIMARY, ColorShade._50),
        ColorShade._100: ColorToken("#E0F2FE", "Sky 100", ColorRole.PRIMARY, ColorShade._100),
        ColorShade._200: ColorToken("#BAE6FD", "Sky 200", ColorRole.PRIMARY, ColorShade._200),
        ColorShade._300: ColorToken("#7DD3FC", "Sky 300", ColorRole.PRIMARY, ColorShade._300),
        ColorShade._400: ColorToken("#38BDF8", "Sky 400", ColorRole.PRIMARY, ColorShade._400),
        ColorShade._500: ColorToken("#0EA5E9", "Sky 500", ColorRole.PRIMARY, ColorShade._500),
        ColorShade._600: ColorToken("#0284C7", "Sky 600", ColorRole.PRIMARY, ColorShade._600),
        ColorShade._700: ColorToken("#0369A1", "Sky 700", ColorRole.PRIMARY, ColorShade._700),
        ColorShade._800: ColorToken("#075985", "Sky 800", ColorRole.PRIMARY, ColorShade._800),
        ColorShade._900: ColorToken("#0C4A6E", "Sky 900", ColorRole.PRIMARY, ColorShade._900),
        ColorShade._950: ColorToken("#082F49", "Sky 950", ColorRole.PRIMARY, ColorShade._950),
    }
    
    # Secondary - Slate gray (neutral, sophisticated)
    secondary_colors = {
        ColorShade._50: ColorToken("#F8FAFC", "Slate 50", ColorRole.SECONDARY, ColorShade._50),
        ColorShade._100: ColorToken("#F1F5F9", "Slate 100", ColorRole.SECONDARY, ColorShade._100),
        ColorShade._200: ColorToken("#E2E8F0", "Slate 200", ColorRole.SECONDARY, ColorShade._200),
        ColorShade._300: ColorToken("#CBD5E1", "Slate 300", ColorRole.SECONDARY, ColorShade._300),
        ColorShade._400: ColorToken("#94A3B8", "Slate 400", ColorRole.SECONDARY, ColorShade._400),
        ColorShade._500: ColorToken("#64748B", "Slate 500", ColorRole.SECONDARY, ColorShade._500),
        ColorShade._600: ColorToken("#475569", "Slate 600", ColorRole.SECONDARY, ColorShade._600),
        ColorShade._700: ColorToken("#334155", "Slate 700", ColorRole.SECONDARY, ColorShade._700),
        ColorShade._800: ColorToken("#1E293B", "Slate 800", ColorRole.SECONDARY, ColorShade._800),
        ColorShade._900: ColorToken("#0F172A", "Slate 900", ColorRole.SECONDARY, ColorShade._900),
        ColorShade._950: ColorToken("#020617", "Slate 950", ColorRole.SECONDARY, ColorShade._950),
    }
    
    # Accent - Amber (warm, attention-grabbing)
    accent_colors = {
        ColorShade._50: ColorToken("#FFFBEB", "Amber 50", ColorRole.ACCENT, ColorShade._50),
        ColorShade._100: ColorToken("#FEF3C7", "Amber 100", ColorRole.ACCENT, ColorShade._100),
        ColorShade._200: ColorToken("#FDE68A", "Amber 200", ColorRole.ACCENT, ColorShade._200),
        ColorShade._300: ColorToken("#FCD34D", "Amber 300", ColorRole.ACCENT, ColorShade._300),
        ColorShade._400: ColorToken("#FBBF24", "Amber 400", ColorRole.ACCENT, ColorShade._400),
        ColorShade._500: ColorToken("#F59E0B", "Amber 500", ColorRole.ACCENT, ColorShade._500),
        ColorShade._600: ColorToken("#D97706", "Amber 600", ColorRole.ACCENT, ColorShade._600),
        ColorShade._700: ColorToken("#B45309", "Amber 700", ColorRole.ACCENT, ColorShade._700),
        ColorShade._800: ColorToken("#92400E", "Amber 800", ColorRole.ACCENT, ColorShade._800),
        ColorShade._900: ColorToken("#78350F", "Amber 900", ColorRole.ACCENT, ColorShade._900),
        ColorShade._950: ColorToken("#451A03", "Amber 950", ColorRole.ACCENT, ColorShade._950),
    }
    
    # Neutral - Gray scale
    neutral_colors = {
        ColorShade._50: ColorToken("#FAFAFA", "Gray 50", ColorRole.NEUTRAL, ColorShade._50),
        ColorShade._100: ColorToken("#F5F5F5", "Gray 100", ColorRole.NEUTRAL, ColorShade._100),
        ColorShade._200: ColorToken("#E5E5E5", "Gray 200", ColorRole.NEUTRAL, ColorShade._200),
        ColorShade._300: ColorToken("#D4D4D4", "Gray 300", ColorRole.NEUTRAL, ColorShade._300),
        ColorShade._400: ColorToken("#A3A3A3", "Gray 400", ColorRole.NEUTRAL, ColorShade._400),
        ColorShade._500: ColorToken("#737373", "Gray 500", ColorRole.NEUTRAL, ColorShade._500),
        ColorShade._600: ColorToken("#525252", "Gray 600", ColorRole.NEUTRAL, ColorShade._600),
        ColorShade._700: ColorToken("#404040", "Gray 700", ColorRole.NEUTRAL, ColorShade._700),
        ColorShade._800: ColorToken("#262626", "Gray 800", ColorRole.NEUTRAL, ColorShade._800),
        ColorShade._900: ColorToken("#171717", "Gray 900", ColorRole.NEUTRAL, ColorShade._900),
        ColorShade._950: ColorToken("#0A0A0A", "Gray 950", ColorRole.NEUTRAL, ColorShade._950),
    }
    
    # Semantic colors
    semantic_colors = {
        ColorRole.SUCCESS: ColorToken("#10B981", "Emerald 500", ColorRole.SUCCESS, ColorShade._500),
        ColorRole.WARNING: ColorToken("#F59E0B", "Amber 500", ColorRole.WARNING, ColorShade._500),
        ColorRole.ERROR: ColorToken("#EF4444", "Red 500", ColorRole.ERROR, ColorShade._500),
        ColorRole.INFO: ColorToken("#3B82F6", "Blue 500", ColorRole.INFO, ColorShade._500),
    }
    
    return ColorPalette(
        name="Architecture Professional",
        description="Professional color palette for architectural presentations",
        primary=primary_colors,
        secondary=secondary_colors,
        accent=accent_colors,
        neutral=neutral_colors,
        semantic=semantic_colors,
    )


def create_default_design_system() -> DesignSystem:
    """Create the default professional design system."""
    
    # Create color palette
    color_palette = create_architecture_professional_palette()
    
    # Create typography scale
    base_font = FontToken(
        family=FontFamily.SANS_SERIF,
        weight=FontWeight.REGULAR,
        size=FontSize.BASE,
        line_height=1.6,
        letter_spacing=0.0,
    )
    typography = TypographyScale(
        name="Professional Typography",
        base_size=FontSize.BASE,
        ratio=1.25,
    )
    typography.generate_scale(base_font)
    
    # Create spacing scale
    spacing = SpacingScale(base_unit=4)
    spacing.generate_scale()
    
    # Create grid system
    grid = GridSystem(
        columns=12,
        gutter=SpacingToken._4,
        max_width="1200px",
    )
    
    # Create shadow scale
    shadows = ShadowScale()
    shadows.generate_scale("0,0,0")
    
    # Create border radius scale
    border_radius = BorderRadiusScale()
    border_radius.generate_scale()
    
    return DesignSystem(
        name="Architecture Professional",
        version="1.0.0",
        description="Professional design system for architectural presentations",
        color_palette=color_palette,
        typography=typography,
        spacing=spacing,
        grid=grid,
        shadows=shadows,
        border_radius=border_radius,
    )
