"""Tests for Unsplash web search client."""

from __future__ import annotations

from archium.infrastructure.images.web_search.unsplash import UnsplashClient


def test_unsplash_client_parses_search_results() -> None:
    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> dict:
        assert headers["Authorization"] == "Client-ID test-key"
        assert "query=modern+architecture" in url
        return {
            "results": [
                {
                    "user": {"name": "Chris"},
                    "links": {"html": "https://unsplash.com/photos/abc"},
                    "urls": {"regular": "https://images.unsplash.com/photo-abc?fm=jpg"},
                    "width": 1600,
                    "height": 900,
                }
            ]
        }

    client = UnsplashClient("test-key", fetch_json=fake_fetch)
    candidates = client.search("modern architecture")
    assert len(candidates) == 1
    assert candidates[0].download_url.startswith("https://images.unsplash.com/")
    assert "Chris" in candidates[0].attribution
