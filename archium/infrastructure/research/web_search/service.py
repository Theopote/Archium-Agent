"""Orchestrate web text search for autonomous research."""

from __future__ import annotations

from typing import Protocol

from archium.config.settings import Settings, get_settings
from archium.infrastructure.credentials.resolver import resolve_tavily_api_key
from archium.infrastructure.research.web_search.duckduckgo import DuckDuckGoClient
from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.tavily import TavilyClient


class WebResearchProvider(Protocol):
    provider_name: str

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]: ...


class _NamedProvider:
    def __init__(self, name: str, client: WebResearchProvider) -> None:
        self.provider_name = name
        self._client = client

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        return self._client.search(query, max_results=max_results)


class WebResearchSearchService:
    """Search the public web and return snippets for LLM-grounded synthesis."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session_tavily_api_key: str | None = None,
        providers: list[WebResearchProvider] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session_tavily_api_key = session_tavily_api_key
        self._providers = providers

    @property
    def enabled(self) -> bool:
        return self._settings.web_research_enabled

    @property
    def configured(self) -> bool:
        return bool(self._build_providers())

    def search_topics(self, topics: list[str]) -> tuple[list[WebSearchResult], str | None]:
        """Search each topic and return deduplicated hits plus provider name."""
        if not self.enabled:
            return [], None
        providers = self._build_providers()
        if not providers:
            return [], None

        provider = providers[0]
        seen_urls: set[str] = set()
        hits: list[WebSearchResult] = []
        for topic in topics:
            topic_hits = provider.search(
                topic,
                max_results=self._settings.web_research_max_results,
            )
            for hit in topic_hits:
                key = hit.url.strip().lower()
                if not key or key in seen_urls:
                    continue
                seen_urls.add(key)
                hits.append(hit)
        return hits, provider.provider_name

    def _build_providers(self) -> list[WebResearchProvider]:
        if self._providers is not None:
            return self._providers

        timeout = self._settings.web_research_timeout_seconds
        provider_name = (self._settings.web_research_provider or "tavily").strip().lower()

        tavily_key, _ = resolve_tavily_api_key(
            session_api_key=self._session_tavily_api_key,
            env_api_key=self._settings.tavily_api_key,
        )
        tavily_key = (tavily_key or "").strip()
        if provider_name == "tavily" and tavily_key:
            return [
                _NamedProvider(
                    "tavily",
                    TavilyClient(tavily_key, timeout=timeout),
                )
            ]

        if provider_name in {"tavily", "duckduckgo"}:
            return [
                _NamedProvider(
                    "duckduckgo",
                    DuckDuckGoClient(timeout=timeout),
                )
            ]

        if tavily_key:
            return [
                _NamedProvider(
                    "tavily",
                    TavilyClient(tavily_key, timeout=timeout),
                )
            ]
        return [
            _NamedProvider(
                "duckduckgo",
                DuckDuckGoClient(timeout=timeout),
            )
        ]
