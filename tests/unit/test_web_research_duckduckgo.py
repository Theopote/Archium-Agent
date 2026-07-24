"""Tests for DuckDuckGo HTML web research client."""

from __future__ import annotations

from archium.infrastructure.research.web_search.duckduckgo import DuckDuckGoClient


def test_duckduckgo_client_parses_html_results() -> None:
    sample_html = """
    <div class="result results_links results_links_deep web-result">
      <div class="links_main links_deep result__body">
        <h2 class="result__title">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fspace">
            Village Public Space Study
          </a>
        </h2>
        <a class="result__snippet" href="#">
          Overview of rural cultural buildings in northern China.
        </a>
      </div>
    </div>
    """

    def fake_fetch(url: str, headers: dict[str, str], body: bytes, timeout: float) -> str:
        assert url.endswith("/html/")
        assert b"q=" in body
        return sample_html

    client = DuckDuckGoClient(fetch_html=fake_fetch)
    hits = client.search("乡村文化建筑", max_results=2)

    assert len(hits) == 1
    assert hits[0].title == "Village Public Space Study"
    assert hits[0].url == "https://example.org/space"
    assert "rural cultural" in hits[0].snippet
