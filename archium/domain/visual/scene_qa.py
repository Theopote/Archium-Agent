"""Scene-level and post-render QA check codes (WP H)."""

from __future__ import annotations


class SceneSemanticCheckCode:
    """Stable identifiers for RenderScene semantic checks."""

    DRAWING_COVER_MODE_FORBIDDEN = "SEMANTIC.DRAWING_COVER_MODE_FORBIDDEN"
    AI_IMAGE_PRESENTED_AS_REAL_PROJECT = "SEMANTIC.AI_IMAGE_PRESENTED_AS_REAL_PROJECT"
    STOCK_IMAGE_PRESENTED_AS_PROJECT = "SEMANTIC.STOCK_IMAGE_PRESENTED_AS_PROJECT"
    IMAGE_NOT_RENDERED = "SEMANTIC.IMAGE_NOT_RENDERED"
    FONT_TOO_SMALL = "SEMANTIC.FONT_TOO_SMALL"
    TEXT_OVERFLOW = "SEMANTIC.TEXT_OVERFLOW"
    CAPTION_MISSING = "SEMANTIC.CAPTION_MISSING"
    SCENE_PPTX_NODE_MISMATCH = "SEMANTIC.SCENE_PPTX_NODE_MISMATCH"
    FONT_FALLBACK_CHANGED_LAYOUT = "SEMANTIC.FONT_FALLBACK_CHANGED_LAYOUT"

    # Vocabulary aliases — same codes as slide-layer semantic QA (implemented there).
    BEFORE_AFTER_UNPAIRED = "SEMANTIC.BEFORE_AFTER_MISMATCH"
    PROJECT_PHOTO_WITHOUT_SOURCE = "SEMANTIC.PROJECT_ASSET_WITHOUT_SOURCE"


class PostRenderCheckCode:
    """Stable identifiers for screenshot-level visual checks."""

    BLANK_PAGE = "POST_RENDER.BLANK_PAGE"
    BLACK_BLOCK = "POST_RENDER.BLACK_BLOCK"
    IMAGE_NOT_LOADED = "POST_RENDER.IMAGE_NOT_LOADED"
    DUPLICATE_PAGE = "POST_RENDER.DUPLICATE_PAGE"
    ALL_PAGES_IDENTICAL = "POST_RENDER.ALL_PAGES_IDENTICAL"
    DRAWING_BLUR = "POST_RENDER.DRAWING_BLUR"
    SEVERE_STRETCH = "POST_RENDER.SEVERE_STRETCH"
    PNG_PPTX_DIFF = "POST_RENDER.PNG_PPTX_DIFF"


# Roles that may legitimately use non-project assets without "presented as real project" errors.
_REFERENCE_SEMANTIC_ROLES = frozenset(
    {
        "reference_case_photo",
        "reference",
        "citation",
        "public_research",
    }
)


def is_project_presentation_role(semantic_role: str) -> bool:
    """Return True when the node is presented as project evidence/photo."""
    role = (semantic_role or "").strip().lower()
    if not role:
        return True
    if role in _REFERENCE_SEMANTIC_ROLES:
        return False
    return not role.startswith("reference")
