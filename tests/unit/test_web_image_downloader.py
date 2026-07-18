"""Tests for remote image downloader."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.infrastructure.images.web_search.downloader import download_image, is_safe_https_url


def test_is_safe_https_url_allows_pexels_hosts() -> None:
    assert is_safe_https_url("https://images.pexels.com/photos/123.jpeg")
    assert is_safe_https_url("https://images.unsplash.com/photo-abc?fm=jpg")
    assert not is_safe_https_url("http://images.pexels.com/photos/123.jpeg")
    assert not is_safe_https_url("https://evil.example/photo.jpg")


def test_download_image_writes_payload(tmp_path: Path) -> None:
    payload = b"\xff\xd8\xff\xd9"

    def fake_fetch(url: str, timeout: float) -> bytes:
        assert url.startswith("https://images.pexels.com/")
        return payload

    dest = tmp_path / "web_image"
    saved = download_image(
        "https://images.pexels.com/photos/123.jpeg",
        dest,
        fetch_bytes=fake_fetch,
    )
    assert saved.exists()
    assert saved.read_bytes() == payload
    assert saved.suffix == ".jpeg"


def test_download_image_rejects_untrusted_host(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="untrusted"):
        download_image("https://example.com/photo.jpg", tmp_path / "x.jpg")
