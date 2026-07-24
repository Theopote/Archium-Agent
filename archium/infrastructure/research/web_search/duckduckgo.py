"""DuckDuckGo HTML lite search client (no API key)."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from archium.infrastructure.research.web_search.models import WebSearchResult

HtmlFetcher = Callable[[str, dict[str, str], bytes, float], str]

_RESULT_BLOCK = re.compile(r'<div class="result results_links[^"]*".*?</div>\s*</div>', re.S)
_RESULT_LINK = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.S,
)
_RESULT_SNIPPET = re.compile(
    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
    re.S,
)


class DuckDuckGoClient:
    """Search DuckDuckGo HTML lite endpoint without third-party dependencies."""

    _SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        fetch_html: HtmlFetcher | None = None,
    ) -> None:
        self._timeout = timeout
        self._fetch_html = fetch_html or self._default_fetch_html

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        safe_query = query.strip() or "architecture research"
        body = f"q={quote_plus(safe_query)}&b=".encode("utf-8")
        page = self._fetch_html(
            self._SEARCH_URL,
            {"Content-Type": "application/x-www-form-urlencoded"},
            body,
            self._timeout,
        )
        hits: list[WebSearchResult] = []
        for block in _RESULT_BLOCK.findall(page):
            link_match = _RESULT_LINK.search(block)
            if link_match is None:
                continue
            href = _decode_ddg_url(link_match.group(1))
            title = _strip_tags(link_match.group(2))
            if not href or not title:
                continue
            snippet_match = _RESULT_SNIPPET.search(block)
            snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
            hits.append(WebSearchResult(title=title, url=href, snippet=snippet))
            if len(hits) >= max(1, min(max_results, 10)):
                break
        return hits

    @staticmethod
    def _default_fetch_html(url: str, headers: dict[str, str], body: bytes, timeout: float) -> str:
        request = Request(
            url,
            data=body,
            headers={
                **headers,
                "User-Agent": "Archium-Agent/1.0 (research)",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
        return raw.decode("utf-8", errors="replace")


def _decode_ddg_url(href: str) -> str:
    parsed = urlparse(href)
    if "uddg" in parse_qs(parsed.query):
        return unquote(parse_qs(parsed.query)["uddg"][0])
    if href.startswith("//"):
        return f"https:{href}"
    return href


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).strip()
