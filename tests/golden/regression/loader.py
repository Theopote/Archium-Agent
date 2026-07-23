"""Layer 1: deterministic workflow regression case loader."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.presentation_models import PresentationRequest
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session

_CASES_DIR = Path(__file__).resolve().parent / "cases"


def _document_hash(case_id: str, index: int) -> str:
    return hashlib.sha256(f"{case_id}:{index}".encode()).hexdigest()


@dataclass(frozen=True)
class RegressionCase:
    id: str
    name: str
    project_name: str
    project_type: ProjectType
    request: PresentationRequest
    expectations: dict[str, Any]
    export_presentation_spec: bool


def list_regression_case_paths() -> list[Path]:
    return sorted(_CASES_DIR.glob("case_*.json"))


def load_regression_case(path: Path) -> RegressionCase:
    payload = json.loads(path.read_text(encoding="utf-8"))
    project = payload["project"]
    request_data = payload["request"]
    presentation_type = request_data.get("presentation_type", "client_review")
    from archium.domain.enums import PresentationType

    request = PresentationRequest(
        title=request_data["title"],
        audience=request_data["audience"],
        purpose=request_data["purpose"],
        duration_minutes=int(request_data.get("duration_minutes", 20)),
        target_slide_count=int(request_data.get("target_slide_count", 4)),
        core_message=request_data.get("core_message", ""),
        required_sections=list(request_data.get("required_sections", [])),
        presentation_type=PresentationType(presentation_type),
    )
    expectations = dict(payload.get("expectations", {}))
    export_spec = bool(expectations.pop("export_presentation_spec", False))
    return RegressionCase(
        id=str(payload["id"]),
        name=str(payload["name"]),
        project_name=str(project["name"]),
        project_type=ProjectType(str(project["project_type"])),
        request=request,
        expectations=expectations,
        export_presentation_spec=export_spec,
    )


def seed_regression_case(session: Session, path: Path) -> tuple[RegressionCase, Project]:
    """Seed DB with inline text chunks (no real file parsing)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    case = load_regression_case(path)
    project = ProjectRepository(session).create(
        Project(name=case.project_name, project_type=case.project_type)
    )
    doc_repo = DocumentRepository(session)
    fact_repo = FactRepository(session)

    for index, document in enumerate(payload.get("documents", [])):
        created = doc_repo.create_document(
            SourceDocument(
                project_id=project.id,
                filename=str(document["filename"]),
                original_path=f"/tmp/{document['filename']}",
                stored_path=f"/tmp/{document['filename']}",
                file_type=DocumentType.PDF,
                file_hash=_document_hash(case.id, index),
                size_bytes=1024,
                processing_status=ProcessingStatus.COMPLETED,
            )
        )
        doc_repo.create_chunk(
            DocumentChunk(
                document_id=created.id,
                project_id=project.id,
                chunk_index=0,
                content=str(document["content"]),
                page_number=1,
                section_title=str(document.get("section_title", "正文")),
            )
        )

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

    return case, project


def conflicting_fact_keys(session: Session, project_id: UUID) -> set[str]:
    from archium.domain.enums import VerificationStatus
    from archium.infrastructure.database.repositories import FactRepository

    facts = FactRepository(session).list_by_project(project_id)
    keys: set[str] = set()
    by_key: dict[str, set[str]] = {}
    for fact in facts:
        if fact.verification_status == VerificationStatus.CONFLICTED:
            keys.add(fact.key)
        by_key.setdefault(fact.key, set()).add(fact.value.strip())
    keys.update(key for key, values in by_key.items() if len(values) > 1)
    return keys


# Backward-compatible aliases for shared helpers
GoldenCase = RegressionCase
list_golden_case_paths = list_regression_case_paths
load_golden_case = load_regression_case
seed_golden_case = seed_regression_case
