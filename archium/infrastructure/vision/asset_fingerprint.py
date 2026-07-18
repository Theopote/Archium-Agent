"""Content fingerprint for visual QA cache invalidation."""

from __future__ import annotations

import hashlib
from pathlib import Path


def asset_content_hash(path: str | Path) -> str:
    """Return SHA-256 hex digest of the asset file bytes."""
    resolved = Path(path)
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
