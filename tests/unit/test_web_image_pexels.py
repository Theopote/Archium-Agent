"""Tests for Pexels web search client."""

from __future__ import annotations

from archium.infrastructure.images.web_search.pexels import PexelsClient


def test_pexels_client_parses_search_results() -> None:
    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> dict:
        assert headers["Authorization"] == "test-key"
        assert "query=modern+architecture" in url
        return {
            "photos": [
                {
                    "photographer": "Jane Doe",
                    "url": "https://www.pexels.com/photo/123/",
                    "width": 1200,
                    "height": 800,
                    "src": {
                        "large2x": "https://images.pexels.com/photos/123.jpeg",
                    },
                }
            ]
        }

    client = PexelsClient("test-key", fetch_json=fake_fetch)
    candidates = client.search("modern architecture")
    assert len(candidates) == 1
    assert candidates[0].download_url.endswith("123.jpeg")
    assert candidates[0].page_url.endswith("/123/")
    assert "Jane Doe" in candidates[0].attribution


def test_pexels_client_returns_empty_without_api_key() -> None:
    client = PexelsClient("")
    assert client.search("architecture") == []
