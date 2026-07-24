"""Tests for web research search service."""

from __future__ import annotations

from archium.config.settings import Settings
from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.service import WebResearchSearchService


class _FakeProvider:
    provider_name = "fake"

    def __init__(self, hits: list[WebSearchResult]) -> None:
        self._hits = hits
        self.queries: list[str] = []

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        self.queries.append(query)
        return self._hits[:max_results]


def test_search_topics_deduplicates_by_url() -> None:
    provider = _FakeProvider(
        [
            WebSearchResult(title="A", url="https://example.org/a", snippet="one"),
            WebSearchResult(title="B", url="https://example.org/a", snippet="dup"),
        ]
    )
    settings = Settings(web_research_enabled=True)
    service = WebResearchSearchService(settings, providers=[provider])

    hits, name = service.search_topics(["topic one", "topic two"])

    assert name == "fake"
    assert len(hits) == 1
    assert provider.queries == ["topic one", "topic two"]


def test_search_topics_disabled_returns_empty() -> None:
    settings = Settings(web_research_enabled=False)
    service = WebResearchSearchService(settings, providers=[_FakeProvider([])])

    hits, name = service.search_topics(["topic"])

    assert hits == []
    assert name is None


def test_build_providers_prefers_session_tavily_key() -> None:
    settings = Settings(
        web_research_enabled=True,
        web_research_provider="tavily",
        tavily_api_key=None,
    )
    service = WebResearchSearchService(settings, session_tavily_api_key="session-tvly")

    providers = service._build_providers()

    assert len(providers) == 1
    assert providers[0].provider_name == "tavily"
