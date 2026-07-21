"""Backward-compatible shim — use ``legacy.file_manager`` instead."""

from __future__ import annotations

import warnings

warnings.warn(
    "Root-level file_manager.py is deprecated; use `legacy.file_manager`.",
    DeprecationWarning,
    stacklevel=2,
)

from legacy.file_manager import *  # noqa: F403
