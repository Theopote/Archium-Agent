"""Tavily web search client for autonomous research."""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.request import Request, urlopen

from archium.infrastructure.research.web_search.models import WebSearchResult

SearchFetcher = Callable[[str, dict[str, str], bytes, float], dict]


class TavilyClient:
    """Minimal Tavily REST client."""

    _SEARCH_URL = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 20.0,
        fetch_json: SearchFetcher | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._fetch_json = fetch_json or self._default_fetch_json

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        if not self._api_key:
            return []
        payload = self._fetch_json(
            self._SEARCH_URL,
            {"Content-Type": "application/json"},
            json.dumps(
                {
                    "api_key": self._api_key,
                    "query": query.strip() or "architecture research",
                    "search_depth": "basic",
                    "include_answer": False,
                    "max_results": max(1, min(max_results, 10)),
                }
            ).encode("utf-8"),
            self._timeout,
        )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            return []

        hits: list[WebSearchResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            url = item.get("url")
            content = item.get("content")
            if not isinstance(title, str) or not isinstance(url, str):
                continue
            snippet = content.strip() if isinstance(content, str) else ""
            score_value = item.get("score")
            score = float(score_value) if isinstance(score_value, (int, float)) else None
            hits.append(
                WebSearchResult(
                    title=title.strip(),
                    url=url.strip(),
                    snippet=snippet,
                    score=score,
                )
            )
        return hits

    @staticmethod
    def _default_fetch_json(url: str, headers: dict[str, str], body: bytes, timeout: float) -> dict:
        request = Request(
            url,
            data=body,
            headers={**headers, "User-Agent": "Archium-Agent/1.0"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Tavily response must be a JSON object")
        return data
