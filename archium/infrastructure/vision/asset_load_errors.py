"""Map asset image load failures to stable visual QA rule codes."""

from __future__ import annotations

from archium.domain.review_rules import ReviewRuleCode

try:
    from PIL import UnidentifiedImageError
except ImportError:  # pragma: no cover
    UnidentifiedImageError = type(  # type: ignore[misc, assignment]
        "UnidentifiedImageError",
        (OSError,),
        {},
    )


def rule_code_for_asset_load_error(exc: Exception) -> str:
    """Classify an image load failure for review issue creation."""
    if isinstance(exc, FileNotFoundError):
        return ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND
    if isinstance(exc, PermissionError):
        return ReviewRuleCode.VISUAL_ASSET_PERMISSION_DENIED
    if isinstance(exc, UnidentifiedImageError):
        return ReviewRuleCode.VISUAL_ASSET_FORMAT_UNSUPPORTED
    if isinstance(exc, OSError) and not isinstance(exc, FileNotFoundError):
        return ReviewRuleCode.VISUAL_ASSET_DECODE_FAILED
    return ReviewRuleCode.VISUAL_ASSET_UNREADABLE
