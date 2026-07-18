"""Web image search result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebImageCandidate:
    """One remote image suitable for download."""

    download_url: str
    page_url: str
    attribution: str
    width: int | None = None
    height: int | None = None
