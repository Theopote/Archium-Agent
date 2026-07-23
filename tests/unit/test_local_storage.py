"""Tests for local project storage path confinement."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.config.settings import Settings
from archium.infrastructure.storage.local_storage import (
    LocalProjectStorage,
    sanitize_storage_filename,
)


def test_sanitize_storage_filename_strips_path_segments() -> None:
    assert sanitize_storage_filename("../../etc/passwd") == "passwd"
    assert sanitize_storage_filename(r"..\..\secret.bin") == "secret.bin"
    assert sanitize_storage_filename("..") == "asset.bin"
    assert sanitize_storage_filename("") == "asset.bin"


def test_write_asset_rejects_escaped_filename(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, project_storage_path=tmp_path / "projects")
    storage = LocalProjectStorage(settings)
    project_id = uuid4()
    path = storage.write_asset(
        project_id,
        filename="../escape.png",
        data=b"png",
    )
    assert path.name == "escape.png"
    assert path.resolve().is_relative_to(storage.project_root(project_id).resolve())
    assert not (tmp_path / "escape.png").exists()


def test_copy_source_file_uses_basename_only(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, project_storage_path=tmp_path / "projects")
    storage = LocalProjectStorage(settings)
    project_id = uuid4()
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"%PDF")
    destination = storage.copy_source_file(
        project_id,
        source,
        filename="../../evil.pdf",
    )
    assert destination.name == "evil.pdf"
    assert destination.resolve().is_relative_to(
        (storage.project_root(project_id) / "sources").resolve()
    )


def test_write_asset_document_subdir_stays_confined(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, project_storage_path=tmp_path / "projects")
    storage = LocalProjectStorage(settings)
    project_id = uuid4()
    document_id = uuid4()
    path = storage.write_asset(
        project_id,
        filename="a/b/c.png",
        data=b"x",
        document_id=document_id,
    )
    assert path.name == "c.png"
    asset_root = storage.project_root(project_id) / "assets" / str(document_id)
    assert path.resolve().is_relative_to(asset_root.resolve())
