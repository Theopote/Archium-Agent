"""Shim: icon usage policy helpers live in domain.visual."""

from archium.domain.visual.icon_usage import (
    accept_match,
    filter_icon_refs,
    icons_allowed_for_family,
    max_icons_for_family,
)

__all__ = [
    "accept_match",
    "filter_icon_refs",
    "icons_allowed_for_family",
    "max_icons_for_family",
]
