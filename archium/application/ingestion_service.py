"""Document import and ingestion service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_vision_rag_service import AssetVisionRagResult, AssetVisionRagService
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
    visual_idea_seed_message: str | None = None


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

    def list_documents(self, project_id: UUID) -> list[SourceDocument]:
        return self._documents.list_by_project(project_id)

    def get_document(self, document_id: UUID) -> SourceDocument | None:
        return self._documents.get_document(document_id)

    def import_file(
        self,
        project_id: UUID,
        source_path: Path,
        *,
        actor_id: str | None = None,
    ) -> ImportItemResult:
        """Import one file into a project."""
        from archium.application.project_permission_gate import require_project_permission
        from archium.domain.access import ProjectPermission

        require_project_permission(
            self._session,
            project_id,
            ProjectPermission.EDIT,
            actor_id=actor_id,
        )
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

            vision_result = self._process_asset_vision_rag(
                project_id,
                document,
                assets,
                base_chunk_index=len(saved_chunks),
            )
            assets = vision_result.assets
            assets = self._analyze_assets_presentation_readiness(assets)
            for chunk in vision_result.chunks:
                saved_chunks.append(self._documents.create_chunk(chunk))

            ocr_chunks, ocr_ok = self._maybe_ocr_document_assets(
                project_id,
                document,
                assets,
                needs_ocr=parsed.needs_ocr,
                base_chunk_index=len(saved_chunks),
            )
            for chunk in ocr_chunks:
                saved_chunks.append(self._documents.create_chunk(chunk))

            self._extract_facts_at_ingest(project_id, document.filename, saved_chunks)
            self._index_chunks(project_id, document, saved_chunks)

            still_needs_ocr = bool(parsed.needs_ocr) and not ocr_ok
            document.metadata = {
                **document.metadata,
                **parsed.metadata,
                "needs_ocr": still_needs_ocr,
                "ocr_applied": ocr_ok,
                "chunk_count": len(saved_chunks),
                "asset_count": len(assets),
            }
            page_count = len(parsed.pages) if parsed.pages else None
            if still_needs_ocr and document.file_type.value in {"pdf", "image"}:
                document.processing_status = ProcessingStatus.NEEDS_OCR
                document = self._documents.update_document(document)
            else:
                document.mark_completed(page_count=page_count)
                document = self._documents.update_document(document)

            self._materialize_cad_spatial_facts(project_id, document, parsed.metadata)
            document = self._enqueue_analyze_after_ingest(project_id, document, stored_path)

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

    def _enqueue_analyze_after_ingest(
        self,
        project_id: UUID,
        document: SourceDocument,
        stored_path: Path,
    ) -> SourceDocument:
        """Queue durable document analysis after ingest (idempotent; best-effort)."""
        from archium.application.api.documents import DocumentsApi

        path = Path(stored_path)
        try:
            job = DocumentsApi(self._session).enqueue_analyze(
                project_id,
                path=str(path),
                document_id=document.id,
                filename=document.filename,
                idempotency_key=f"document_analyze:{document.id}",
            )
            document.metadata = {
                **dict(document.metadata or {}),
                "background_job_id": str(job.id),
                "analyze_queued": True,
                # Compat alias for older CAD ingest assertions.
                "cad_analyze_queued": True,
            }
            return self._documents.update_document(document)
        except Exception:
            logger.exception(
                "Failed to enqueue document analyze for %s", document.filename
            )
            return document

    def import_files(
        self,
        project_id: UUID,
        source_paths: list[Path],
        *,
        actor_id: str | None = None,
    ) -> list[ImportItemResult]:
        """Import multiple files; failures on one file do not stop the batch."""
        results: list[ImportItemResult] = []
        for path in source_paths:
            results.append(self.import_file(project_id, path, actor_id=actor_id))
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

            vision_result = self._process_asset_vision_rag(
                document.project_id,
                document,
                assets,
                base_chunk_index=len(saved_chunks),
            )
            assets = vision_result.assets
            assets = self._analyze_assets_presentation_readiness(assets)
            for chunk in vision_result.chunks:
                saved_chunks.append(self._documents.create_chunk(chunk))

            ocr_chunks, ocr_ok = self._maybe_ocr_document_assets(
                document.project_id,
                document,
                assets,
                needs_ocr=parsed.needs_ocr,
                base_chunk_index=len(saved_chunks),
            )
            for chunk in ocr_chunks:
                saved_chunks.append(self._documents.create_chunk(chunk))

            self._extract_facts_at_ingest(document.project_id, document.filename, saved_chunks)
            self._index_chunks(document.project_id, document, saved_chunks)

            still_needs_ocr = bool(parsed.needs_ocr) and not ocr_ok
            document.metadata = {
                **document.metadata,
                **parsed.metadata,
                "needs_ocr": still_needs_ocr,
                "ocr_applied": ocr_ok,
                "chunk_count": len(saved_chunks),
                "asset_count": len(assets),
            }
            page_count = len(parsed.pages) if parsed.pages else None
            if still_needs_ocr and document.file_type.value in {"pdf", "image"}:
                document.processing_status = ProcessingStatus.NEEDS_OCR
            else:
                document.mark_completed(page_count=page_count)
            result.document = self._documents.update_document(document)
            self._materialize_cad_spatial_facts(
                document.project_id, result.document, parsed.metadata
            )
            result.chunks = saved_chunks
            result.assets = assets
            return result
        except Exception as exc:
            result.error = str(exc)
            document.mark_failed()
            result.document = self._documents.update_document(document)
            return result

    def _materialize_cad_spatial_facts(
        self,
        project_id: UUID,
        document: SourceDocument,
        metadata: dict[str, object],
    ) -> None:
        if not metadata.get("cad_bim"):
            return
        try:
            from archium.application.cad_spatial_fact_materializer import (
                materialize_cad_spatial_facts,
            )

            materialize_cad_spatial_facts(
                self._session,
                project_id,
                document,
                metadata=metadata,
            )
        except Exception:
            logger.exception(
                "CAD spatial fact materialization failed for %s", document.filename
            )

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
            ).ensure_architectural_annotation()
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
                ).ensure_architectural_annotation()
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

    def _extract_facts_at_ingest(
        self,
        project_id: UUID,
        document_name: str,
        chunks: list[DocumentChunk],
    ) -> None:
        try:
            from archium.application.fact_extraction_service import FactExtractionService

            FactExtractionService(self._session, settings=self._settings).extract_from_document(
                project_id,
                document_name=document_name,
                chunks=chunks,
            )
        except Exception as exc:
            logger.warning("Parse-time fact extraction failed for %s: %s", document_name, exc)

    def _maybe_ocr_document_assets(
        self,
        project_id: UUID,
        document: SourceDocument,
        assets: list[Asset],
        *,
        needs_ocr: bool,
        base_chunk_index: int,
    ) -> tuple[list[DocumentChunk], bool]:
        """When needs_ocr, OCR image assets into ocr_text chunks (KN-005 / Topic 05).

        Idempotent on reparse because chunks are deleted before rebuild.
        Returns (chunks, ocr_succeeded).
        """
        if not needs_ocr or not assets:
            return [], False
        if not getattr(self._settings, "document_ocr_enabled", True):
            return [], False

        from archium.domain.enums import AssetType
        from archium.infrastructure.vision.ocr_text import (
            extract_text_from_image,
            is_meaningful_ocr_text,
            pytesseract_available,
        )

        if not pytesseract_available():
            logger.info(
                "OCR skipped for %s — pytesseract unavailable; status stays needs_ocr",
                document.filename,
            )
            return [], False

        indexable = {
            AssetType.IMAGE,
            AssetType.PHOTO,
            AssetType.DRAWING,
            AssetType.DIAGRAM,
        }
        chunks: list[DocumentChunk] = []
        for asset in assets:
            if asset.asset_type not in indexable:
                continue
            path = Path(asset.path)
            if not path.is_file():
                continue
            text = extract_text_from_image(path)
            if not is_meaningful_ocr_text(text):
                continue
            chunks.append(
                DocumentChunk(
                    project_id=project_id,
                    document_id=document.id,
                    content=text[:4000],
                    page_number=asset.page_number,
                    section_title=f"OCR · {asset.filename}",
                    content_type="ocr_text",
                    chunk_index=base_chunk_index + len(chunks),
                    metadata={
                        "asset_id": str(asset.id),
                        "ocr": True,
                        "ocr_engine": "pytesseract",
                        "needs_ocr": False,
                    },
                ).ensure_architectural_annotation()
            )

        if not chunks:
            logger.info("OCR produced no text for %s", document.filename)
            return [], False
        logger.info(
            "OCR materialized %s chunk(s) for %s",
            len(chunks),
            document.filename,
        )
        return chunks, True

    def _analyze_assets_presentation_readiness(
        self,
        assets: list[Asset],
    ) -> list[Asset]:
        from archium.application.asset_presentation_readiness_service import (
            analyze_and_cache_asset_presentation_readiness,
        )

        analyzed: list[Asset] = []
        for asset in assets:
            try:
                updated = analyze_and_cache_asset_presentation_readiness(
                    asset,
                    project_storage_root=self._settings.project_storage_path,
                )
                if updated.metadata != asset.metadata or updated != asset:
                    updated = self._assets.update(updated)
                analyzed.append(updated)
            except Exception as exc:
                logger.warning(
                    "Presentation readiness analysis failed for %s: %s",
                    asset.filename,
                    exc,
                )
                analyzed.append(asset)
        return analyzed

    def _process_asset_vision_rag(
        self,
        project_id: UUID,
        document: SourceDocument,
        assets: list[Asset],
        *,
        base_chunk_index: int,
    ) -> AssetVisionRagResult:
        try:
            return AssetVisionRagService(self._session, settings=self._settings).process_document_assets(
                project_id,
                document,
                assets,
                base_chunk_index=base_chunk_index,
            )
        except Exception as exc:
            logger.warning("Asset vision RAG failed for %s: %s", document.filename, exc)
            return AssetVisionRagResult(assets=assets, chunks=[])

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
