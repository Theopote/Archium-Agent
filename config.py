"""Backward-compatible shim — use ``legacy.config`` or ``archium.config`` instead."""

from __future__ import annotations

import warnings

warnings.warn(
    "Root-level config.py is deprecated; use `legacy.config` or `archium.config.get_settings()`.",
    DeprecationWarning,
    stacklevel=2,
)

from legacy.config import *  # noqa: F403
