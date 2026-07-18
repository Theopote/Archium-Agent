"""Pexels stock photo search client."""

from __future__ import annotations

import json
from typing import Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from archium.infrastructure.images.web_search.models import WebImageCandidate

SearchFetcher = Callable[[str, dict[str, str], float], dict]


class PexelsClient:
    """Minimal Pexels REST client for one-shot export fallbacks."""

    _BASE_URL = "https://api.pexels.com/v1/search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 15.0,
        fetch_json: SearchFetcher | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._fetch_json = fetch_json or self._default_fetch_json

    def search(self, query: str, *, per_page: int = 5) -> list[WebImageCandidate]:
        if not self._api_key:
            return []
        safe_query = quote_plus(query.strip() or "architecture")
        url = f"{self._BASE_URL}?query={safe_query}&per_page={max(1, min(per_page, 15))}"
        payload = self._fetch_json(
            url,
            {"Authorization": self._api_key},
            self._timeout,
        )
        photos = payload.get("photos")
        if not isinstance(photos, list):
            return []

        candidates: list[WebImageCandidate] = []
        for photo in photos:
            if not isinstance(photo, dict):
                continue
            src = photo.get("src")
            if not isinstance(src, dict):
                continue
            download_url = src.get("large2x") or src.get("large") or src.get("medium")
            page_url = photo.get("url")
            photographer = photo.get("photographer")
            if not isinstance(download_url, str) or not isinstance(page_url, str):
                continue
            photographer_name = photographer.strip() if isinstance(photographer, str) else "Unknown"
            attribution = f"Photo by {photographer_name} on Pexels"
            width = photo.get("width")
            height = photo.get("height")
            candidates.append(
                WebImageCandidate(
                    download_url=download_url,
                    page_url=page_url,
                    attribution=attribution,
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
            raise ValueError("Pexels response must be a JSON object")
        return data
