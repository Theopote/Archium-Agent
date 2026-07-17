"""Layer 2: real fixture acceptance case loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archium.application.ingestion_service import IngestionService
from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import ProjectType
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from sqlalchemy.orm import Session

_MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"
_FILES_DIR = Path(__file__).resolve().parent / "files"


@dataclass(frozen=True)
class FixtureCase:
    id: str
    name: str
    project_name: str
    project_type: ProjectType
    request: PresentationRequest
    expectations: dict[str, Any]
    export_presentation_spec: bool
    source_files: tuple[Path, ...]


def list_fixture_manifest_paths() -> list[Path]:
    return sorted(_MANIFESTS_DIR.glob("*.fixture.json"))


def load_fixture_case(path: Path) -> FixtureCase:
    payload = json.loads(path.read_text(encoding="utf-8"))
    project = payload["project"]
    request_data = payload["request"]
    from archium.domain.enums import PresentationType

    request = PresentationRequest(
        title=request_data["title"],
        audience=request_data["audience"],
        purpose=request_data["purpose"],
        duration_minutes=int(request_data.get("duration_minutes", 20)),
        target_slide_count=int(request_data.get("target_slide_count", 4)),
        core_message=request_data.get("core_message", ""),
        required_sections=list(request_data.get("required_sections", [])),
        presentation_type=PresentationType(request_data.get("presentation_type", "client_review")),
    )
    expectations = dict(payload.get("expectations", {}))
    export_spec = bool(expectations.pop("export_presentation_spec", False))

    source_files: list[Path] = []
    for entry in payload.get("files", []):
        relative = Path(str(entry["relative_path"]))
        resolved = (_FILES_DIR / relative).resolve()
        required = bool(entry.get("required", False))
        if resolved.is_file():
            source_files.append(resolved)
        elif required:
            raise FileNotFoundError(f"Required fixture file missing: {resolved}")

    return FixtureCase(
        id=str(payload["id"]),
        name=str(payload["name"]),
        project_name=str(project["name"]),
        project_type=ProjectType(str(project["project_type"])),
        request=request,
        expectations=expectations,
        export_presentation_spec=export_spec,
        source_files=tuple(source_files),
    )


def materialize_inline_docx(path: Path, payload: dict[str, Any]) -> Path | None:
    """Create a DOCX from manifest inline paragraphs when bundled files are absent."""
    inline = payload.get("inline_docx")
    if inline is None:
        return None
    from docx import Document

    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    for paragraph in inline.get("paragraphs", []):
        document.add_paragraph(str(paragraph))
    document.save(path)
    return path


def seed_fixture_case(
    session: Session,
    path: Path,
    *,
    scratch_dir: Path,
) -> tuple[FixtureCase, Project, list[Path]]:
    """Import real files through IngestionService (real parsers)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    case = load_fixture_case(path)
    project = ProjectRepository(session).create(
        Project(name=case.project_name, project_type=case.project_type)
    )

    imported_paths: list[Path] = list(case.source_files)
    if not imported_paths:
        inline = payload.get("inline_docx")
        if inline is not None:
            generated = scratch_dir / str(inline.get("filename", "inline.docx"))
            materialize_inline_docx(generated, payload)
            imported_paths = [generated]

    if not imported_paths:
        raise FileNotFoundError(
            f"Fixture {case.id} has no source files and no inline_docx fallback"
        )

    ingestion = IngestionService(session)
    for source_path in imported_paths:
        result = ingestion.import_file(project.id, source_path)
        if result.error:
            raise RuntimeError(f"Fixture import failed for {source_path.name}: {result.error}")
        if result.skipped:
            raise RuntimeError(f"Fixture import skipped for {source_path.name}")

    fact_repo = FactRepository(session)
    for fact in payload.get("facts", []):
        fact_repo.create(
            ProjectFact(
                project_id=project.id,
                key=str(fact["key"]),
                label=str(fact["label"]),
                value=str(fact["value"]),
                conflict_group=fact.get("conflict_group"),
            )
        )

    return case, project, imported_paths


def fixture_files_dir() -> Path:
    return _FILES_DIR
