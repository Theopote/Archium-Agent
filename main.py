"""Backward-compatible shim — use ``legacy.main`` or ``archium-legacy`` instead."""

from __future__ import annotations

import warnings

warnings.warn(
    "Root-level main.py is deprecated; use `legacy.main` or the `archium-legacy` CLI.",
    DeprecationWarning,
    stacklevel=2,
)

from legacy.main import *  # noqa: F403
