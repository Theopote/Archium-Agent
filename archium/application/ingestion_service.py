"""Document import and ingestion service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.retrieval_service import RetrievalService, create_retrieval_service
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import ProcessingStatus
from archium.exceptions import DocumentParseError
from archium.infrastructure.chunking.semantic import SemanticChunker
from archium.infrastructure.database.repositories import AssetRepository, DocumentRepository
from archium.infrastructure.document_parsers import (
    DocumentParser,
    default_parsers,
    get_parser_for_path,
)
from archium.infrastructure.document_parsers._utils import infer_document_type
from archium.infrastructure.document_parsers.base import ParsedDocument
from archium.infrastructure.embeddings.factory import create_embedding_provider
from archium.infrastructure.storage.local_storage import LocalProjectStorage, compute_file_hash
from archium.logging import get_logger

logger = get_logger(__name__, operation="ingestion")

_MIN_CHUNK_CHARS = 1


@dataclass
class ImportItemResult:
    """Result of importing a single file."""

    source_path: Path
    document: SourceDocument | None = None
    chunks: list[DocumentChunk] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    duplicate: bool = False
    skipped: bool = False
    error: str | None = None


class IngestionService:
    """Import project source files, parse them, and persist chunks/assets."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        parsers: list[DocumentParser] | None = None,
        retrieval: RetrievalService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session = session
        self._documents = DocumentRepository(session)
        self._assets = AssetRepository(session)
        self._storage = LocalProjectStorage(self._settings)
        self._parsers = parsers if parsers is not None else default_parsers()
        self._retrieval = retrieval

    def import_file(self, project_id: UUID, source_path: Path) -> ImportItemResult:
        """Import one file into a project."""
        source_path = source_path.expanduser().resolve()
        result = ImportItemResult(source_path=source_path)

        if not source_path.is_file():
            result.error = f"File not found: {source_path}"
            return result

        try:
            file_hash = compute_file_hash(source_path)
            existing = self._documents.get_by_hash(project_id, file_hash)
            if existing is not None:
                result.document = existing
                result.duplicate = True
                result.skipped = True
                logger.info("Skipped duplicate import for %s", source_path.name)
                return result

            stored_path = self._storage.copy_source_file(project_id, source_path)
            document = SourceDocument(
                project_id=project_id,
                filename=source_path.name,
                original_path=str(source_path),
                stored_path=str(stored_path),
                file_type=infer_document_type(source_path),
                file_hash=file_hash,
                size_bytes=source_path.stat().st_size,
            )
            document.mark_processing()
            document = self._documents.create_document(document)

            parsed = self._parse_file(stored_path)
            chunks = self._build_chunks(project_id, document.id, parsed)
            assets = self._persist_assets(project_id, document.id, parsed)

            saved_chunks: list[DocumentChunk] = []
            for chunk in chunks:
                saved_chunks.append(self._documents.create_chunk(chunk))

            self._index_chunks(project_id, document, saved_chunks)

            document.metadata = {
                **document.metadata,
                **parsed.metadata,
                "needs_ocr": parsed.needs_ocr,
                "chunk_count": len(saved_chunks),
                "asset_count": len(assets),
            }
            page_count = len(parsed.pages) if parsed.pages else None
            if parsed.needs_ocr and document.file_type.value == "pdf":
                document.processing_status = ProcessingStatus.NEEDS_OCR
                document = self._documents.update_document(document)
            else:
                document.mark_completed(page_count=page_count)
                document = self._documents.update_document(document)

            result.document = document
            result.chunks = saved_chunks
            result.assets = assets
            return result
        except Exception as exc:
            logger.exception("Import failed for %s", source_path)
            result.error = str(exc)
            if result.document is not None:
                result.document.mark_failed()
                self._documents.update_document(result.document)
            return result

    def import_files(self, project_id: UUID, source_paths: list[Path]) -> list[ImportItemResult]:
        """Import multiple files; failures on one file do not stop the batch."""
        results: list[ImportItemResult] = []
        for path in source_paths:
            results.append(self.import_file(project_id, path))
        return results

    def reparse_document(self, document_id: UUID) -> ImportItemResult:
        """Re-parse an existing stored document."""
        document = self._documents.get_document(document_id)
        if document is None:
            raise DocumentParseError(f"Document {document_id} not found")

        stored_path = Path(document.stored_path)
        result = ImportItemResult(source_path=stored_path, document=document)
        try:
            document.mark_processing()
            self._documents.update_document(document)
            self._retrieval_service().remove_document(document.project_id, document.id)
            self._documents.delete_chunks_for_document(document.id)

            parsed = self._parse_file(stored_path)
            chunks = self._build_chunks(document.project_id, document.id, parsed)
            assets = self._persist_assets(document.project_id, document.id, parsed)

            saved_chunks: list[DocumentChunk] = []
            for chunk in chunks:
                saved_chunks.append(self._documents.create_chunk(chunk))

            self._index_chunks(document.project_id, document, saved_chunks)

            document.metadata = {
                **document.metadata,
                **parsed.metadata,
                "needs_ocr": parsed.needs_ocr,
                "chunk_count": len(saved_chunks),
                "asset_count": len(assets),
            }
            page_count = len(parsed.pages) if parsed.pages else None
            if parsed.needs_ocr and document.file_type.value == "pdf":
                document.processing_status = ProcessingStatus.NEEDS_OCR
            else:
                document.mark_completed(page_count=page_count)
            result.document = self._documents.update_document(document)
            result.chunks = saved_chunks
            result.assets = assets
            return result
        except Exception as exc:
            result.error = str(exc)
            document.mark_failed()
            result.document = self._documents.update_document(document)
            return result

    def _parse_file(self, file_path: Path) -> ParsedDocument:
        parser = get_parser_for_path(file_path, self._parsers)
        return parser.parse(file_path)

    def _build_chunks(
        self,
        project_id: UUID,
        document_id: UUID,
        parsed: ParsedDocument,
    ) -> list[DocumentChunk]:
        if self._settings.semantic_chunking_enabled:
            return self._build_semantic_chunks(project_id, document_id, parsed)
        return self._build_page_chunks(project_id, document_id, parsed)

    def _build_semantic_chunks(
        self,
        project_id: UUID,
        document_id: UUID,
        parsed: ParsedDocument,
    ) -> list[DocumentChunk]:
        parts = SemanticChunker(
            self._settings,
            embedder=create_embedding_provider(self._settings),
        ).chunk_pages(
            parsed.pages,
            extra_metadata={"needs_ocr": parsed.needs_ocr},
        )
        return [
            DocumentChunk(
                project_id=project_id,
                document_id=document_id,
                content=part.content,
                page_number=part.page_number,
                section_title=part.section_title,
                content_type=part.content_type,
                chunk_index=index,
                metadata=part.metadata,
            )
            for index, part in enumerate(parts)
            if part.content.strip()
        ]

    def _build_page_chunks(
        self,
        project_id: UUID,
        document_id: UUID,
        parsed: ParsedDocument,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for index, page in enumerate(parsed.pages):
            text = page.text.strip()
            if len(text) < _MIN_CHUNK_CHARS:
                continue
            chunks.append(
                DocumentChunk(
                    project_id=project_id,
                    document_id=document_id,
                    content=text,
                    page_number=page.page_number,
                    section_title=page.section_title,
                    content_type=page.content_type,
                    chunk_index=index,
                    metadata={"needs_ocr": parsed.needs_ocr},
                )
            )
        return chunks

    def _persist_assets(
        self,
        project_id: UUID,
        document_id: UUID,
        parsed: ParsedDocument,
    ) -> list[Asset]:
        saved: list[Asset] = []
        for extracted in parsed.assets:
            try:
                path = self._storage.write_asset(
                    project_id,
                    filename=extracted.filename,
                    data=extracted.data,
                    document_id=document_id,
                )
                asset = Asset(
                    project_id=project_id,
                    document_id=document_id,
                    filename=extracted.filename,
                    path=str(path),
                    asset_type=extracted.asset_type,
                    width=extracted.width,
                    height=extracted.height,
                    page_number=extracted.page_number,
                    description=extracted.description,
                )
                saved.append(self._assets.create(asset))
            except Exception as exc:
                logger.warning("Failed to save asset %s: %s", extracted.filename, exc)
        return saved

    def _retrieval_service(self) -> RetrievalService:
        if self._retrieval is None:
            self._retrieval = create_retrieval_service(self._session, self._settings)
        return self._retrieval

    def _index_chunks(
        self,
        project_id: UUID,
        document: SourceDocument,
        chunks: list[DocumentChunk],
    ) -> None:
        if not chunks:
            return
        try:
            self._retrieval_service().index_chunks(
                project_id,
                chunks,
                document_name=document.filename,
            )
        except Exception as exc:
            logger.warning("Vector indexing failed for %s: %s", document.filename, exc)
