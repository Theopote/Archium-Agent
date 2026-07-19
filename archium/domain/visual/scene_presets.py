"""Curated visual preference bundles for Presentation Studio scene presets."""

from __future__ import annotations

from archium.domain.visual.enums import (
    DecorationLevel,
    DensityLevel,
    DrawingDisplayMode,
    FormalityLevel,
    PresentationContext,
    VisualEmphasis,
    WhitespacePreference,
)
from archium.domain.visual.preferences import VisualPreferences

SCENE_PRESET_KEYS: tuple[str, ...] = (
    "client_review",
    "design_competition",
    "technical_report",
)

SCENE_PRESET_LABELS: dict[str, str] = {
    "client_review": "甲方方案汇报",
    "design_competition": "设计竞赛",
    "technical_report": "技术报告",
}

SCENE_PRESET_DESCRIPTIONS: dict[str, str] = {
    "client_review": "专业、图文平衡、中等密度、适度留白",
    "design_competition": "视觉强、图像优先、疏朗、高对比",
    "technical_report": "正式、信息优先、紧凑、图纸可读性高",
}


def scene_preset_preferences(key: str) -> VisualPreferences:
    """Return VisualPreferences for a curated scene preset key."""
    if key == "design_competition":
        return VisualPreferences(
            density=DensityLevel.SPACIOUS,
            visual_emphasis=VisualEmphasis.IMAGE,
            formality=FormalityLevel.PROFESSIONAL,
            decoration_level=DecorationLevel.MEDIUM,
            whitespace_preference=WhitespacePreference.GENEROUS,
            drawing_display_mode=DrawingDisplayMode.CLEAR,
            presentation_context=PresentationContext.DESIGN_COMPETITION,
        )
    if key == "technical_report":
        return VisualPreferences(
            density=DensityLevel.COMPACT,
            visual_emphasis=VisualEmphasis.TEXT,
            formality=FormalityLevel.FORMAL,
            decoration_level=DecorationLevel.LOW,
            whitespace_preference=WhitespacePreference.TIGHT,
            drawing_display_mode=DrawingDisplayMode.CLEAR,
            presentation_context=PresentationContext.TECHNICAL_REPORT,
        )
    return VisualPreferences(
        density=DensityLevel.BALANCED,
        visual_emphasis=VisualEmphasis.BALANCED,
        formality=FormalityLevel.PROFESSIONAL,
        decoration_level=DecorationLevel.LOW,
        whitespace_preference=WhitespacePreference.BALANCED,
        drawing_display_mode=DrawingDisplayMode.CLEAR,
        presentation_context=PresentationContext.CLIENT_REVIEW,
    )
