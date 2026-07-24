"""Web text search for autonomous research."""

from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.service import WebResearchSearchService

__all__ = ["WebResearchSearchService", "WebSearchResult"]
