"""Local filesystem storage for project assets."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from uuid import UUID

from archium.config.settings import Settings, get_settings

_UNSAFE_FILENAME = re.compile(r"[\\/]+")


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


def sanitize_storage_filename(filename: str, *, fallback: str = "asset.bin") -> str:
    """Basename-only filename safe to join under a project directory."""
    text = (filename or "").strip().replace("\\", "/")
    name = Path(text).name
    name = _UNSAFE_FILENAME.sub("_", name)
    if not name or name in {".", ".."}:
        return fallback
    return name


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
        target_name = sanitize_storage_filename(
            filename or source_path.name,
            fallback=sanitize_storage_filename(source_path.name, fallback="upload.bin"),
        )
        destination = layout["sources"] / target_name
        destination = self._unique_destination(destination)
        self._assert_under(layout["sources"], destination)
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
        safe_name = sanitize_storage_filename(filename)
        if document_id is not None:
            asset_dir = layout["assets"] / str(document_id)
            asset_dir.mkdir(parents=True, exist_ok=True)
            destination = asset_dir / safe_name
            self._assert_under(asset_dir, destination)
        else:
            destination = layout["assets"] / safe_name
            self._assert_under(layout["assets"], destination)
        destination.write_bytes(data)
        return destination

    @staticmethod
    def _unique_destination(destination: Path) -> Path:
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while destination.exists():
            destination = destination.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
        return destination

    @staticmethod
    def _assert_under(root: Path, destination: Path) -> None:
        base = root.resolve()
        target = destination.resolve()
        if not target.is_relative_to(base):
            raise ValueError(f"refusing to write outside storage root: {destination}")
