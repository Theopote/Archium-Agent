"""Direct parser tests for real-fixture edge cases (no workflow / no LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from archium.application.ingestion_service import IngestionService
from archium.domain.enums import ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository
from sqlalchemy.orm import Session
from tests.golden.fixtures.loader import seed_fixture_case

pytestmark = pytest.mark.fixture_acceptance

_MANIFEST = (
    Path(__file__).resolve().parent / "manifests" / "case_e_real_paths.fixture.json"
)


def test_real_parsers_handle_unicode_and_spaced_paths(
    db_session: Session,
    tmp_path: Path,
) -> None:
    case, project, imported_paths = seed_fixture_case(db_session, _MANIFEST, scratch_dir=tmp_path)

    assert case.id == "case_e_real_paths"
    assert any(ord(char) > 127 for char in str(imported_paths[0]))
    assert any(" " in str(path) for path in imported_paths)
    assert len(imported_paths) >= 4

    chunks = DocumentRepository(db_session).list_chunks_by_project(project.id)
    assert len(chunks) >= 3

    extensions = {path.suffix.lower() for path in imported_paths}
    assert extensions >= {".docx", ".pdf", ".pptx", ".jpg"}


def test_fixture_manifest_declares_conflict_facts() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    keys = {fact["key"] for fact in payload.get("facts", [])}
    assert {"site_area", "land_area"}.issubset(keys)


def test_low_resolution_image_imports(db_session: Session, tmp_path: Path) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="低清图片测试", project_type=ProjectType.HEALTHCARE)
    )
    from tests.golden.fixtures.loader import materialize_inline_image

    image_path = materialize_inline_image(
        tmp_path / "中文路径" / "现场 低清.jpg",
        {"width": 32, "height": 24},
    )
    result = IngestionService(db_session).import_file(project.id, image_path)
    assert not result.error
    assert not result.skipped

    chunks = DocumentRepository(db_session).list_chunks_by_project(project.id)
    assert len(chunks) >= 1
