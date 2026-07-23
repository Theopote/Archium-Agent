"""Backward-compatible shim — prefer ``python -m legacy.main`` from a repo checkout."""

from __future__ import annotations

import warnings

warnings.warn(
    "Root-level main.py is deprecated; use `python -m legacy.main` from the repo root.",
    DeprecationWarning,
    stacklevel=2,
)

from legacy.main import *  # noqa: F403
