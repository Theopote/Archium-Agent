"""Models for text web search used in autonomous research."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    """One web page hit from a research-oriented search provider."""

    title: str
    url: str
    snippet: str
    score: float | None = None
