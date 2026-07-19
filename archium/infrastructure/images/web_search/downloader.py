"""Download remote images to local export storage."""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_DEFAULT_MAX_BYTES = 10_000_000
_ALLOWED_DOWNLOAD_HOST_SUFFIXES = (
    ".pexels.com",
    "pexels.com",
    "images.pexels.com",
    ".unsplash.com",
    "unsplash.com",
    "images.unsplash.com",
    "plus.unsplash.com",
)


def is_safe_https_url(url: str) -> bool:
    """Return True when the URL is HTTPS and targets an allowed host."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    host = parsed.hostname
    if host is None:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local):
        return False
    lowered = host.lower()
    return any(
        lowered == suffix.removeprefix(".") or lowered.endswith(suffix)
        for suffix in _ALLOWED_DOWNLOAD_HOST_SUFFIXES
    )


def download_image(
    url: str,
    dest: Path,
    *,
    timeout: float = 15.0,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    fetch_bytes: Callable[[str, float], bytes] | None = None,
) -> Path:
    """Download an image when the URL passes HTTPS host checks."""
    if not is_safe_https_url(url):
        raise ValueError(f"Refusing to download from untrusted URL: {url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = fetch_bytes(url, timeout) if fetch_bytes is not None else _fetch_bytes(url, timeout)
    if len(payload) > max_bytes:
        raise ValueError(f"Remote image exceeds size limit ({max_bytes} bytes)")
    if not payload:
        raise ValueError("Remote image payload is empty")

    suffix = _guess_suffix(url, payload)
    if dest.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        dest = dest.with_suffix(suffix)

    dest.write_bytes(payload)
    return dest


def _fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "Archium-Agent/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        content_type = response.headers.get("Content-Type", "")
        if content_type and not content_type.startswith("image/"):
            raise ValueError(f"Unexpected content type: {content_type}")
        return cast(bytes, response.read())


def _guess_suffix(url: str, payload: bytes) -> str:
    path_suffix = Path(urlparse(url).path).suffix.lower()
    if path_suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return path_suffix
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"
