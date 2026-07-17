"""Helpers for visual requirement processing hints."""

from __future__ import annotations

from archium.domain.slide import VisualRequirement

_CROP_KEYWORDS = ("裁剪", "裁切", "crop", "截取")
_HIGHLIGHT_KEYWORDS = ("标注", "高亮", "highlight", "圈出", "箭头", "强调")


def infer_visual_processing_flags(requirement: VisualRequirement) -> None:
    """Infer crop/highlight flags from description and processing instructions."""
    text = " ".join(
        [requirement.description, *requirement.processing_instructions]
    ).lower()
    requirement.needs_crop = any(keyword in text for keyword in _CROP_KEYWORDS)
    requirement.needs_highlight = any(keyword in text for keyword in _HIGHLIGHT_KEYWORDS)
