"""Load and seed real-project acceptance manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archium.application.ingestion_service import IngestionService
from archium.application.presentation_models import PresentationRequest
from archium.application.project_acceptance_service import RealProjectManifest
from archium.domain.enums import ProjectType, VisualType
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.domain.project_acceptance import RealProjectScenario
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from archium.infrastructure.renderers.diagram_generator import generate_fallback_diagram
from sqlalchemy.orm import Session

from tests.golden.fixtures.loader import (
    materialize_inline_fallbacks,
    resolve_fixture_scratch_dir,
)

_MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"


@dataclass(frozen=True)
class LoadedRealProjectCase:
    manifest: RealProjectManifest
    request: PresentationRequest
    raw: dict[str, Any]


def list_manifest_paths() -> list[Path]:
    return sorted(_MANIFESTS_DIR.glob("project_*.json"))


def load_manifest(path: Path) -> LoadedRealProjectCase:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request_data = payload["request"]
    from archium.domain.enums import PresentationType

    request = PresentationRequest(
        title=request_data["title"],
        audience=request_data["audience"],
        purpose=request_data["purpose"],
        duration_minutes=int(request_data.get("duration_minutes", 30)),
        target_slide_count=int(request_data.get("target_slide_count", 20)),
        core_message=request_data.get("core_message", ""),
        required_sections=list(request_data.get("required_sections", [])),
        presentation_type=PresentationType(request_data.get("presentation_type", "client_review")),
    )
    expectations = dict(payload.get("expectations", {}))
    manifest = RealProjectManifest(
        project_id=str(payload["id"]),
        scenario=RealProjectScenario(str(payload["scenario"])),
        title=str(payload["name"]),
        expectations=expectations,
    )
    return LoadedRealProjectCase(manifest=manifest, request=request, raw=payload)


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
_DOCUMENT_SUFFIXES = {".docx", ".pdf", ".xlsx", ".pptx", ".doc", ".xls", ".ppt"}


def resolve_manifest_files(payload: dict[str, Any]) -> list[Path]:
    """Resolve drop-in files under tests/e2e/real_projects/files/."""
    files_dir = Path(__file__).resolve().parent / "files"
    paths: list[Path] = []
    for entry in payload.get("files", []):
        relative = Path(str(entry["relative_path"]))
        resolved = (files_dir / relative).resolve()
        if resolved.is_file():
            paths.append(resolved)
        elif bool(entry.get("required", False)):
            msg = f"Required real-project file missing: {resolved}"
            raise FileNotFoundError(msg)
    return paths


def _paths_include_images(paths: list[Path]) -> bool:
    return any(path.suffix.lower() in _IMAGE_SUFFIXES for path in paths)


def _paths_include_documents(paths: list[Path]) -> bool:
    return any(path.suffix.lower() in _DOCUMENT_SUFFIXES for path in paths)


def materialize_inline_assets(payload: dict[str, Any], scratch_dir: Path) -> list[Path]:
    """Create placeholder PNG assets declared in inline_assets."""
    base_dir = resolve_fixture_scratch_dir(payload, scratch_dir)
    assets_dir = base_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    min_assets = int(payload.get("expectations", {}).get("min_assets", 10))
    entries = list(payload.get("inline_assets", []))
    while len(entries) < min_assets:
        index = len(entries) + 1
        entries.append(
            {
                "filename": f"asset_{index:02d}.png",
                "label": f"项目素材 {index}",
                "visual_type": "diagram",
            }
        )
    paths: list[Path] = []
    for index, entry in enumerate(entries, start=1):
        filename = str(entry.get("filename", f"asset_{index:02d}.png"))
        label = str(entry.get("label", f"素材 {index}"))
        visual_type = VisualType(str(entry.get("visual_type", "diagram")))
        output_path = assets_dir / filename
        if not output_path.exists():
            generate_fallback_diagram(
                output_path,
                title=label,
                visual_type=visual_type,
                description=label,
                key_points=[label],
                message=label,
            )
        paths.append(output_path)
    return paths


def seed_real_project_case(
    session: Session,
    path: Path,
    *,
    scratch_dir: Path,
) -> tuple[LoadedRealProjectCase, Project, list[Path]]:
    """Import documents/assets and facts for one acceptance scenario."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    loaded = load_manifest(path)
    project = ProjectRepository(session).create(
        Project(
            name=str(payload["project"]["name"]),
            project_type=ProjectType(str(payload["project"]["project_type"])),
        )
    )

    file_paths = resolve_manifest_files(payload)
    imported_paths: list[Path] = []
    if not file_paths or not _paths_include_documents(file_paths):
        imported_paths.extend(materialize_inline_fallbacks(payload, scratch_dir))
    if not file_paths or not _paths_include_images(file_paths):
        imported_paths.extend(materialize_inline_assets(payload, scratch_dir))
    imported_paths.extend(file_paths)

    if len(imported_paths) < int(loaded.manifest.expectations.get("min_assets", 10)):
        msg = (
            f"{loaded.manifest.project_id} must materialize at least "
            f"{loaded.manifest.expectations.get('min_assets', 10)} import paths"
        )
        raise RuntimeError(msg)

    ingestion = IngestionService(session)
    for source_path in imported_paths:
        result = ingestion.import_file(project.id, source_path)
        if result.error:
            raise RuntimeError(f"Import failed for {source_path.name}: {result.error}")
        if result.skipped and not result.duplicate:
            raise RuntimeError(f"Import skipped for {source_path.name}")

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

    return loaded, project, imported_paths
