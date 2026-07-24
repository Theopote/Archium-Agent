"""Tests for Tavily web research client."""

from __future__ import annotations

import json

from archium.infrastructure.research.web_search.tavily import TavilyClient


def test_tavily_client_parses_search_results() -> None:
    captured: dict[str, object] = {}

    def fake_fetch(url: str, headers: dict[str, str], body: bytes, timeout: float) -> dict:
        captured["url"] = url
        captured["headers"] = headers
        payload = json.loads(body.decode("utf-8"))
        captured["payload"] = payload
        return {
            "results": [
                {
                    "title": "Rural cultural centers in China",
                    "url": "https://example.org/rural-cultural-center",
                    "content": "Case studies of village public space.",
                    "score": 0.91,
                }
            ]
        }

    client = TavilyClient("tvly-test", fetch_json=fake_fetch)
    hits = client.search("关中乡村公共文化空间", max_results=3)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["payload"]["api_key"] == "tvly-test"
    assert len(hits) == 1
    assert hits[0].url == "https://example.org/rural-cultural-center"
    assert "Case studies" in hits[0].snippet
    assert hits[0].score == 0.91


def test_tavily_client_returns_empty_without_api_key() -> None:
    client = TavilyClient("")
    assert client.search("architecture") == []
