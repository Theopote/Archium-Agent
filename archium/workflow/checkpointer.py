"""LangGraph checkpoint persistence for presentation workflows."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

_CHECKPOINT_MODULES: list[tuple[str, str]] = [
    ("archium.application.chunk_models", "ProjectContextBundle"),
    ("archium.application.presentation_models", "PresentationRequest"),
    ("archium.domain.citation", "Citation"),
    ("archium.domain.document", "DocumentChunk"),
    ("archium.domain.enums", "ApprovalStatus"),
    ("archium.domain.enums", "AssetType"),
    ("archium.domain.enums", "DocumentType"),
    ("archium.domain.enums", "PresentationStatus"),
    ("archium.domain.enums", "PresentationType"),
    ("archium.domain.enums", "ProcessingStatus"),
    ("archium.domain.enums", "ProjectStatus"),
    ("archium.domain.enums", "ProjectType"),
    ("archium.domain.enums", "ReviewCategory"),
    ("archium.domain.enums", "ReviewSeverity"),
    ("archium.domain.enums", "ReviewStatus"),
    ("archium.domain.enums", "SlideStatus"),
    ("archium.domain.enums", "SlideType"),
    ("archium.domain.enums", "VerificationStatus"),
    ("archium.domain.enums", "VisualType"),
    ("archium.domain.fact", "ProjectFact"),
    ("archium.domain.presentation", "Chapter"),
    ("archium.domain.presentation", "Presentation"),
    ("archium.domain.presentation", "PresentationBrief"),
    ("archium.domain.presentation", "Storyline"),
    ("archium.domain.review", "ReviewIssue"),
    ("archium.domain.slide", "SlideSpec"),
    ("archium.domain.slide", "VisualRequirement"),
]


def create_workflow_checkpointer(db_path: Path) -> SqliteSaver:
    """Create a SQLite-backed LangGraph checkpointer with domain serde allowlist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    serde = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_MODULES)
    return SqliteSaver(conn, serde=serde)
