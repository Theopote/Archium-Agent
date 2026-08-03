"""Design system customization service for user preferences.

This module allows users to customize the design system for their specific needs,
including colors, typography, spacing, and other design tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID
from pathlib import Path
import json

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.design_system import (
    DesignSystem,
    create_default_design_system,
    ColorRole,
    ColorShade,
    FontFamily,
    FontWeight,
    FontSize,
    SpacingToken,
)
from archium.config.settings import Settings, get_settings


@dataclass
class CustomColorScheme:
    """Custom color scheme configuration."""
    primary: str = "#0EA5E9"
    secondary: str = "#64748B"
    accent: str = "#F59E0B"
    neutral: str = "#F1F5F9"
    success: str = "#10B981"
    warning: str = "#F59E0B"
    error: str = "#EF4444"
    info: str = "#3B82F6"
    
    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "neutral": self.neutral,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "info": self.info,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "CustomColorScheme":
        """Create from dictionary."""
        return cls(
            primary=data.get("primary", "#0EA5E9"),
            secondary=data.get("secondary", "#64748B"),
            accent=data.get("accent", "#F59E0B"),
            neutral=data.get("neutral", "#F1F5F9"),
            success=data.get("success", "#10B981"),
            warning=data.get("warning", "#F59E0B"),
            error=data.get("error", "#EF4444"),
            info=data.get("info", "#3B82F6"),
        )


@dataclass
class CustomTypography:
    """Custom typography configuration."""
    font_family: str = "Arial"
    heading_font: str = "Arial"
    body_font: str = "Arial"
    base_font_size: int = 14
    heading_scale: float = 1.25
    line_height: float = 1.5
    letter_spacing: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "font_family": self.font_family,
            "heading_font": self.heading_font,
            "body_font": self.body_font,
            "base_font_size": self.base_font_size,
            "heading_scale": self.heading_scale,
            "line_height": self.line_height,
            "letter_spacing": self.letter_spacing,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomTypography":
        """Create from dictionary."""
        return cls(
            font_family=data.get("font_family", "Arial"),
            heading_font=data.get("heading_font", "Arial"),
            body_font=data.get("body_font", "Arial"),
            base_font_size=data.get("base_font_size", 14),
            heading_scale=data.get("heading_scale", 1.25),
            line_height=data.get("line_height", 1.5),
            letter_spacing=data.get("letter_spacing", 0.0),
        )


@dataclass
class CustomSpacing:
    """Custom spacing configuration."""
    base_unit: int = 4
    scale_factor: float = 1.0
    tight_multiplier: float = 0.5
    normal_multiplier: float = 1.0
    relaxed_multiplier: float = 1.5
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_unit": self.base_unit,
            "scale_factor": self.scale_factor,
            "tight_multiplier": self.tight_multiplier,
            "normal_multiplier": self.normal_multiplier,
            "relaxed_multiplier": self.relaxed_multiplier,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomSpacing":
        """Create from dictionary."""
        return cls(
            base_unit=data.get("base_unit", 4),
            scale_factor=data.get("scale_factor", 1.0),
            tight_multiplier=data.get("tight_multiplier", 0.5),
            normal_multiplier=data.get("normal_multiplier", 1.0),
            relaxed_multiplier=data.get("relaxed_multiplier", 1.5),
        )


@dataclass
class CustomLayout:
    """Custom layout configuration."""
    grid_columns: int = 12
    gutter_size: int = 16
    max_content_width: int = 1200
    content_alignment: str = "left"
    vertical_alignment: str = "top"
    whitespace_preference: str = "medium"  # tight, medium, generous
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "grid_columns": self.grid_columns,
            "gutter_size": self.gutter_size,
            "max_content_width": self.max_content_width,
            "content_alignment": self.content_alignment,
            "vertical_alignment": self.vertical_alignment,
            "whitespace_preference": self.whitespace_preference,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomLayout":
        """Create from dictionary."""
        return cls(
            grid_columns=data.get("grid_columns", 12),
            gutter_size=data.get("gutter_size", 16),
            max_content_width=data.get("max_content_width", 1200),
            content_alignment=data.get("content_alignment", "left"),
            vertical_alignment=data.get("vertical_alignment", "top"),
            whitespace_preference=data.get("whitespace_preference", "medium"),
        )


@dataclass
class CustomDesignSystem:
    """Complete custom design system configuration."""
    name: str = "Custom Design System"
    description: str = "User-customized design system"
    colors: CustomColorScheme = field(default_factory=CustomColorScheme)
    typography: CustomTypography = field(default_factory=CustomTypography)
    spacing: CustomSpacing = field(default_factory=CustomSpacing)
    layout: CustomLayout = field(default_factory=CustomLayout)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "colors": self.colors.to_dict(),
            "typography": self.typography.to_dict(),
            "spacing": self.spacing.to_dict(),
            "layout": self.layout.to_dict(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomDesignSystem":
        """Create from dictionary."""
        return cls(
            name=data.get("name", "Custom Design System"),
            description=data.get("description", "User-customized design system"),
            colors=CustomColorScheme.from_dict(data.get("colors", {})),
            typography=CustomTypography.from_dict(data.get("typography", {})),
            spacing=CustomSpacing.from_dict(data.get("spacing", {})),
            layout=CustomLayout.from_dict(data.get("layout", {})),
            metadata=data.get("metadata", {}),
        )
    
    def apply_to_design_system(self, base_system: DesignSystem) -> DesignSystem:
        """Apply custom settings to a base design system."""
        # This would modify the base system with custom values
        # For now, return the base system as a placeholder
        return base_system


class DesignSystemCustomizationService:
    """Service for managing design system customizations."""
    
    def __init__(
        self,
        session: SessionLike,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._settings = settings or get_settings()
        self._custom_systems: dict[UUID, CustomDesignSystem] = {}
        self._default_system = create_default_design_system()
    
    def create_custom_system(
        self,
        project_id: UUID,
        name: str,
        custom_config: CustomDesignSystem,
    ) -> CustomDesignSystem:
        """Create a new custom design system for a project."""
        
        custom_config.name = name
        self._custom_systems[project_id] = custom_config
        
        return custom_config
    
    def get_custom_system(self, project_id: UUID) -> CustomDesignSystem | None:
        """Get custom design system for a project."""
        return self._custom_systems.get(project_id)
    
    def update_custom_system(
        self,
        project_id: UUID,
        updates: dict[str, Any],
    ) -> CustomDesignSystem:
        """Update custom design system for a project."""
        
        if project_id not in self._custom_systems:
            # Create default custom system if none exists
            self._custom_systems[project_id] = CustomDesignSystem()
        
        custom_system = self._custom_systems[project_id]
        
        # Update specific sections
        if "colors" in updates:
            custom_system.colors = CustomColorScheme.from_dict(updates["colors"])
        
        if "typography" in updates:
            custom_system.typography = CustomTypography.from_dict(updates["typography"])
        
        if "spacing" in updates:
            custom_system.spacing = CustomSpacing.from_dict(updates["spacing"])
        
        if "layout" in updates:
            custom_system.layout = CustomLayout.from_dict(updates["layout"])
        
        if "name" in updates:
            custom_system.name = updates["name"]
        
        if "description" in updates:
            custom_system.description = updates["description"]
        
        return custom_system
    
    def delete_custom_system(self, project_id: UUID) -> bool:
        """Delete custom design system for a project."""
        
        if project_id in self._custom_systems:
            del self._custom_systems[project_id]
            return True
        
        return False
    
    def export_custom_system(
        self,
        project_id: UUID,
        output_path: Path,
    ) -> Path:
        """Export custom design system to JSON file."""
        
        custom_system = self.get_custom_system(project_id)
        if custom_system is None:
            raise ValueError(f"No custom system found for project {project_id}")
        
        output_path.write_text(
            json.dumps(custom_system.to_dict(), indent=2),
            encoding='utf-8'
        )
        
        return output_path
    
    def import_custom_system(
        self,
        project_id: UUID,
        input_path: Path,
    ) -> CustomDesignSystem:
        """Import custom design system from JSON file."""
        
        data = json.loads(input_path.read_text(encoding='utf-8'))
        custom_system = CustomDesignSystem.from_dict(data)
        
        self._custom_systems[project_id] = custom_system
        
        return custom_system
    
    def validate_custom_system(self, custom_system: CustomDesignSystem) -> dict[str, Any]:
        """Validate custom design system configuration.
        
        Returns:
            Dictionary with validation results and any issues found
        """
        issues = []
        warnings = []
        
        # Validate color format
        for color_name, color_value in custom_system.colors.to_dict().items():
            if not color_value.startswith("#") or len(color_value) != 7:
                issues.append(f"Invalid color format for {color_name}: {color_value}")
        
        # Validate typography values
        if custom_system.typography.base_font_size < 10 or custom_system.typography.base_font_size > 24:
            warnings.append(f"Base font size {custom_system.typography.base_font_size} is outside recommended range (10-24)")
        
        if custom_system.typography.heading_scale < 1.0 or custom_system.typography.heading_scale > 2.0:
            warnings.append(f"Heading scale {custom_system.typography.heading_scale} is outside recommended range (1.0-2.0)")
        
        # Validate spacing values
        if custom_system.spacing.base_unit < 2 or custom_system.spacing.base_unit > 8:
            warnings.append(f"Base unit {custom_system.spacing.base_unit} is outside recommended range (2-8)")
        
        # Validate layout values
        if custom_system.layout.grid_columns < 6 or custom_system.layout.grid_columns > 24:
            issues.append(f"Grid columns {custom_system.layout.grid_columns} is outside valid range (6-24)")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }
    
    def get_preset_schemes(self) -> dict[str, CustomDesignSystem]:
        """Get predefined design system presets."""
        
        presets = {}
        
        # Professional preset
        presets["professional"] = CustomDesignSystem(
            name="Professional",
            description="Professional and conservative design",
            colors=CustomColorScheme(
                primary="#0EA5E9",
                secondary="#64748B",
                accent="#F59E0B",
            ),
            typography=CustomTypography(
                font_family="Arial",
                base_font_size=14,
                line_height=1.5,
            ),
            layout=CustomLayout(
                whitespace_preference="medium",
            ),
        )
        
        # Modern preset
        presets["modern"] = CustomDesignSystem(
            name="Modern",
            description="Modern and clean design",
            colors=CustomColorScheme(
                primary="#3B82F6",
                secondary="#6B7280",
                accent="#8B5CF6",
            ),
            typography=CustomTypography(
                font_family="Helvetica",
                base_font_size=16,
                line_height=1.6,
            ),
            layout=CustomLayout(
                whitespace_preference="generous",
            ),
        )
        
        # Creative preset
        presets["creative"] = CustomDesignSystem(
            name="Creative",
            description="Creative and bold design",
            colors=CustomColorScheme(
                primary="#EC4899",
                secondary="#8B5CF6",
                accent="#F59E0B",
            ),
            typography=CustomTypography(
                font_family="Georgia",
                base_font_size=15,
                line_height=1.4,
            ),
            layout=CustomLayout(
                whitespace_preference="generous",
            ),
        )
        
        # Minimal preset
        presets["minimal"] = CustomDesignSystem(
            name="Minimal",
            description="Minimal and clean design",
            colors=CustomColorScheme(
                primary="#000000",
                secondary="#333333",
                accent="#666666",
            ),
            typography=CustomTypography(
                font_family="Arial",
                base_font_size=13,
                line_height=1.7,
            ),
            layout=CustomLayout(
                whitespace_preference="generous",
            ),
        )
        
        return presets
    
    def apply_preset_to_project(
        self,
        project_id: UUID,
        preset_name: str,
    ) -> CustomDesignSystem:
        """Apply a preset design system to a project."""
        
        presets = self.get_preset_schemes()
        if preset_name not in presets:
            raise ValueError(f"Preset {preset_name} not found")
        
        preset = presets[preset_name]
        self._custom_systems[project_id] = preset
        
        return preset
    
    def get_design_system_for_project(
        self,
        project_id: UUID,
    ) -> DesignSystem:
        """Get the appropriate design system for a project.
        
        Returns custom system if available, otherwise default system.
        """
        custom_system = self.get_custom_system(project_id)
        
        if custom_system:
            # Apply custom settings to base system
            # For now, return default system
            # In full implementation, would merge custom settings
            return self._default_system
        
        return self._default_system
