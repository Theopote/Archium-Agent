"""Supplemental slide images resolved at export time."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FallbackImage:
    """Local image path plus optional web-search provenance."""

    path: Path
    generated: bool = True
    web_sourced: bool = False
    attribution: str | None = None
    source_url: str | None = None
    search_query: str | None = None
    provider: str | None = None
