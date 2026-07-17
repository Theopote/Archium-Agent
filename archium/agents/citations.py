"""Citation resolution and auto-linking for slide generation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_models import ProjectContextBundle
from archium.application.retrieval_service import create_retrieval_service
from archium.config.settings import Settings, get_settings
from archium.domain.citation import Citation
from archium.domain.document import DocumentChunk
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import DocumentRepository
from archium.infrastructure.llm.presentation_schemas import CitationDraft


def citation_from_draft(
    item: CitationDraft,
    session: Session,
    *,
    document_names: dict[UUID, str] | None = None,
    context_chunks: list[DocumentChunk] | None = None,
) -> Citation:
    """Resolve a citation draft to a persisted domain citation."""
    repo = DocumentRepository(session)
    names = document_names or {}

    if item.chunk_id:
        chunk = repo.get_chunk(_parse_uuid(item.chunk_id))
        if chunk is not None:
            document = repo.get_document(chunk.document_id)
            return Citation(
                document_id=chunk.document_id,
                document_name=document.filename if document is not None else item.document_name,
                page_number=item.page_number or chunk.page_number,
                chunk_id=chunk.id,
                quote=item.quote or chunk.content[:200],
                confidence=item.confidence,
            )

    if item.quote and context_chunks:
        matched = _match_chunk_by_quote(item.quote, context_chunks)
        if matched is not None:
            return Citation(
                document_id=matched.document_id,
                document_name=names.get(matched.document_id, item.document_name),
                page_number=item.page_number or matched.page_number,
                chunk_id=matched.id,
                quote=item.quote,
                confidence=item.confidence,
            )

    document_id = _resolve_document_id(item.document_name, names)
    return Citation(
        document_id=document_id,
        document_name=item.document_name,
        page_number=item.page_number,
        quote=item.quote,
        confidence=item.confidence,
    )


def enrich_slide_citations(
    slide: SlideSpec,
    *,
    session: Session,
    project_id: UUID,
    context_bundle: ProjectContextBundle,
    settings: Settings | None = None,
) -> None:
    """Attach chunk_id to citations and auto-link slides without sources."""
    resolved_settings = settings or get_settings()
    names = context_bundle.document_names
    chunks = context_bundle.chunks

    for citation in slide.source_citations:
        if citation.chunk_id is not None:
            continue
        matched = _match_chunk_by_quote(citation.quote, chunks) if citation.quote else None
        if matched is None:
            continue
        citation.chunk_id = matched.id
        citation.document_id = matched.document_id
        citation.document_name = names.get(matched.document_id, citation.document_name)
        if citation.page_number is None:
            citation.page_number = matched.page_number

    if slide.source_citations:
        return

    query = " ".join(part for part in [slide.message, *slide.key_points] if part)
    if not query.strip():
        return

    retrieval = create_retrieval_service(session, resolved_settings)
    for hit in retrieval.search(project_id, query, top_k=2):
        chunk = DocumentRepository(session).get_chunk(hit.chunk_id)
        if chunk is None:
            continue
        slide.source_citations.append(
            Citation(
                document_id=chunk.document_id,
                document_name=names.get(chunk.document_id, "项目资料"),
                page_number=chunk.page_number,
                chunk_id=chunk.id,
                quote=hit.content[:200],
                confidence=min(max(hit.score, 0.0), 1.0),
            )
        )
        return


def _match_chunk_by_quote(quote: str | None, chunks: list[DocumentChunk]) -> DocumentChunk | None:
    if not quote:
        return None
    normalized = quote.strip()
    if not normalized:
        return None
    for chunk in chunks:
        if normalized in chunk.content:
            return chunk
    for chunk in chunks:
        if chunk.content[:80] in normalized or normalized[:80] in chunk.content:
            return chunk
    return None


def _resolve_document_id(document_name: str, names: dict[UUID, str]) -> UUID:
    for document_id, filename in names.items():
        if filename == document_name:
            return document_id
    from uuid import uuid4

    return uuid4()


def _parse_uuid(value: str) -> UUID:
    return UUID(value.strip())
