"""Local filesystem storage for project assets."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import UUID

from archium.config.settings import Settings, get_settings


def compute_file_hash(file_path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Compute the SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class LocalProjectStorage:
    """Manage on-disk project directories and file copies."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def project_root(self, project_id: UUID) -> Path:
        return self._settings.project_storage_path / str(project_id)

    def ensure_project_layout(self, project_id: UUID) -> dict[str, Path]:
        """Create the standard project directory layout."""
        root = self.project_root(project_id)
        layout = {
            "root": root,
            "sources": root / "sources",
            "extracted": root / "extracted",
            "assets": root / "assets",
            "presentations": root / "presentations",
            "cache": root / "cache",
        }
        for path in layout.values():
            path.mkdir(parents=True, exist_ok=True)
        return layout

    def copy_source_file(
        self,
        project_id: UUID,
        source_path: Path,
        *,
        filename: str | None = None,
    ) -> Path:
        """Copy an uploaded file into the project sources directory."""
        layout = self.ensure_project_layout(project_id)
        target_name = filename or source_path.name
        destination = layout["sources"] / target_name
        if destination.exists():
            stem = destination.stem
            suffix = destination.suffix
            counter = 1
            while destination.exists():
                destination = layout["sources"] / f"{stem}_{counter}{suffix}"
                counter += 1
        shutil.copy2(source_path, destination)
        return destination

    def write_asset(
        self,
        project_id: UUID,
        *,
        filename: str,
        data: bytes,
        document_id: UUID | None = None,
    ) -> Path:
        """Write an extracted asset to the project assets directory."""
        layout = self.ensure_project_layout(project_id)
        if document_id is not None:
            asset_dir = layout["assets"] / str(document_id)
            asset_dir.mkdir(parents=True, exist_ok=True)
            destination = asset_dir / filename
        else:
            destination = layout["assets"] / filename
        destination.write_bytes(data)
        return destination
