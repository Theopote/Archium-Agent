"""Shared UI labels for planned-but-unavailable options.

Team principle: any option that is registered or planned but not yet executable
must be marked at selection time (for example 「即将支持」), not only when a
workflow step fails at execution.
"""

from __future__ import annotations

COMING_SOON_SUFFIX = " · 即将支持"


def append_coming_soon_suffix(label: str) -> str:
    """Append the standard coming-soon marker once."""
    if COMING_SOON_SUFFIX in label:
        return label
    return f"{label}{COMING_SOON_SUFFIX}"


def format_availability_suffix(
    *,
    available: bool,
    available_label: str = "",
    coming_soon_label: str = "即将支持",
) -> str:
    """Return a short suffix for checkbox / select labels."""
    if available:
        return f" · {available_label}" if available_label else ""
    return f" · {coming_soon_label}"
