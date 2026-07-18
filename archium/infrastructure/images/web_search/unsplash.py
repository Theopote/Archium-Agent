"""Unsplash stock photo search client."""

from __future__ import annotations

import json
from typing import Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from archium.infrastructure.images.web_search.models import WebImageCandidate

SearchFetcher = Callable[[str, dict[str, str], float], dict]


class UnsplashClient:
    """Minimal Unsplash REST client used as a secondary provider."""

    _BASE_URL = "https://api.unsplash.com/search/photos"

    def __init__(
        self,
        access_key: str,
        *,
        timeout: float = 15.0,
        fetch_json: SearchFetcher | None = None,
    ) -> None:
        self._access_key = access_key.strip()
        self._timeout = timeout
        self._fetch_json = fetch_json or self._default_fetch_json

    def search(self, query: str, *, per_page: int = 5) -> list[WebImageCandidate]:
        if not self._access_key:
            return []
        safe_query = quote_plus(query.strip() or "architecture")
        url = f"{self._BASE_URL}?query={safe_query}&per_page={max(1, min(per_page, 15))}"
        payload = self._fetch_json(
            url,
            {"Authorization": f"Client-ID {self._access_key}"},
            self._timeout,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            return []

        candidates: list[WebImageCandidate] = []
        for photo in results:
            if not isinstance(photo, dict):
                continue
            urls = photo.get("urls")
            links = photo.get("links")
            user = photo.get("user")
            if not isinstance(urls, dict) or not isinstance(links, dict):
                continue
            download_url = urls.get("regular") or urls.get("full") or urls.get("small")
            page_url = links.get("html")
            if not isinstance(download_url, str) or not isinstance(page_url, str):
                continue
            photographer_name = "Unknown"
            if isinstance(user, dict):
                name = user.get("name")
                if isinstance(name, str) and name.strip():
                    photographer_name = name.strip()
            width = photo.get("width")
            height = photo.get("height")
            candidates.append(
                WebImageCandidate(
                    download_url=download_url,
                    page_url=page_url,
                    attribution=f"Photo by {photographer_name} on Unsplash",
                    width=width if isinstance(width, int) else None,
                    height=height if isinstance(height, int) else None,
                )
            )
        return candidates

    @staticmethod
    def _default_fetch_json(url: str, headers: dict[str, str], timeout: float) -> dict:
        request = Request(url, headers={**headers, "User-Agent": "Archium-Agent/1.0"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Unsplash response must be a JSON object")
        return data
