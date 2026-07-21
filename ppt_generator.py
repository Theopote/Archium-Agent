"""Backward-compatible shim — use ``legacy.ppt_generator`` instead."""

from __future__ import annotations

import warnings

warnings.warn(
    "Root-level ppt_generator.py is deprecated; use `legacy.ppt_generator`.",
    DeprecationWarning,
    stacklevel=2,
)

from legacy.ppt_generator import *  # noqa: F403
