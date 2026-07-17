"""Unit tests for citation linking."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.agents.citations import citation_from_draft, enrich_slide_citations
from archium.application.chunk_models import ProjectContextBundle
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType, SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import DocumentRepository, PresentationRepository, ProjectRepository
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.llm.presentation_schemas import CitationDraft
from archium.infrastructure.vector.chroma_store import ChromaVectorStore
from sqlalchemy.orm import Session


def _seed_chunk(db_session: Session) -> tuple[DocumentChunk, dict[UUID, str]]:
    project = ProjectRepository(db_session).create(
        Project(name="引用测试", project_type=ProjectType.HEALTHCARE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="任务书.pdf",
            original_path="/tmp/任务书.pdf",
            stored_path="/tmp/任务书.pdf",
            file_type=DocumentType.PDF,
            file_hash="d" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    chunk = repo.create_chunk(
        DocumentChunk(
            project_id=project.id,
            document_id=document.id,
            content="老院区交通组织混乱，人车混行严重。",
            page_number=2,
            chunk_index=0,
        )
    )
    return chunk, {document.id: document.filename}


def test_citation_from_draft_resolves_chunk_id(db_session: Session) -> None:
    chunk, names = _seed_chunk(db_session)
    citation = citation_from_draft(
        CitationDraft(
            document_name="任务书.pdf",
            chunk_id=str(chunk.id),
            quote="交通组织混乱",
            page_number=2,
        ),
        db_session,
        document_names=names,
    )
    assert citation.chunk_id == chunk.id
    assert citation.document_id == chunk.document_id
    assert citation.page_number == 2


def test_citation_from_draft_matches_quote_in_context(db_session: Session) -> None:
    chunk, names = _seed_chunk(db_session)
    citation = citation_from_draft(
        CitationDraft(
            document_name="任务书.pdf",
            quote="交通组织混乱",
        ),
        db_session,
        document_names=names,
        context_chunks=[chunk],
    )
    assert citation.chunk_id == chunk.id


def test_enrich_slide_citations_auto_links_from_retrieval(
    db_session: Session,
    test_settings: object,
) -> None:
    chunk, names = _seed_chunk(db_session)
    store = ChromaVectorStore(test_settings.chroma_path)  # type: ignore[attr-defined]
    from archium.application.retrieval_service import RetrievalService

    RetrievalService(
        db_session,
        settings=test_settings,  # type: ignore[arg-type]
        embedder=MockEmbeddingProvider(),
        store=store,
    ).index_chunks(chunk.project_id, [chunk], document_name="任务书.pdf")

    project = ProjectRepository(db_session).get_by_id(chunk.project_id)
    assert project is not None
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    slide = SlideSpec(
        presentation_id=presentation.id,
        chapter_id="ch1",
        order=0,
        title="交通问题",
        message="老院区交通组织混乱，需要优化流线。",
        slide_type=SlideType.CONTENT,
        key_points=["人车混行"],
    )
    bundle = ProjectContextBundle(text="ctx", chunks=[chunk], document_names=names)
    enrich_slide_citations(
        slide,
        session=db_session,
        project_id=project.id,
        context_bundle=bundle,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert slide.source_citations
    assert slide.source_citations[0].chunk_id == chunk.id
