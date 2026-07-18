"""Loader for mission golden scenarios M1–M6."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class MissionGoldenCase:
    id: str
    name: str
    project_name: str
    project_type: ProjectType
    project_description: str
    task_description: str
    expectations: dict[str, Any]
    raw: dict[str, Any]


def list_mission_case_paths() -> list[Path]:
    return sorted(_CASES_DIR.glob("case_m*.json"))


def load_mission_case(path: Path) -> MissionGoldenCase:
    payload = json.loads(path.read_text(encoding="utf-8"))
    project = payload["project"]
    return MissionGoldenCase(
        id=str(payload["id"]),
        name=str(payload["name"]),
        project_name=str(project["name"]),
        project_type=ProjectType(str(project["project_type"])),
        project_description=str(project.get("description") or ""),
        task_description=str(payload["task_description"]),
        expectations=dict(payload.get("expectations") or {}),
        raw=payload,
    )


def _document_hash(case_id: str, index: int) -> str:
    return hashlib.sha256(f"{case_id}:{index}".encode()).hexdigest()


def seed_mission_case(session: Session, path: Path) -> tuple[MissionGoldenCase, Project]:
    case = load_mission_case(path)
    payload = case.raw
    project = ProjectRepository(session).create(
        Project(
            name=case.project_name,
            project_type=case.project_type,
            description=case.project_description or None,
        )
    )
    doc_repo = DocumentRepository(session)
    fact_repo = FactRepository(session)

    for index, document in enumerate(payload.get("documents") or []):
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

    for fact_data in payload.get("facts") or []:
        fact = ProjectFact(
            project_id=project.id,
            key=str(fact_data["key"]),
            label=str(fact_data["label"]),
            value=fact_data["value"],
            unit=fact_data.get("unit"),
            category=str(fact_data.get("category") or "metric"),
        )
        if fact_data.get("confirmed"):
            fact.confirm()
        fact_repo.create(fact)

    return case, project
