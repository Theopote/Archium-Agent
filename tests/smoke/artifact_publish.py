"""Optional smoke-test artifact publishing for CI (not committed to Git)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def publish_smoke_artifact(source: Path, name: str) -> Path | None:
    """Copy ``source`` into ``ARCHIUM_SMOKE_ARTIFACT_DIR`` when set (CI only)."""
    artifact_root = os.environ.get("ARCHIUM_SMOKE_ARTIFACT_DIR")
    if not artifact_root:
        return None

    destination = Path(artifact_root) / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    else:
        destination.write_bytes(source.read_bytes())
    return destination
