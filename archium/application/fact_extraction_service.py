"""Extract structured ProjectFact records from document chunks and retrieved context."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.citations import citation_from_draft
from archium.application.chunk_models import ProjectContextBundle
from archium.application.fact_metric_extractor import ExtractedMetric, extract_metrics_from_chunks
from archium.application.fact_validation_service import _normalize_value
from archium.config.settings import Settings, get_settings
from archium.domain.citation import Citation
from archium.domain.document import DocumentChunk
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.fact_ledger import STANDARD_FACT_KEY_MAP, STANDARD_FACT_KEYS
from archium.infrastructure.database.repositories import FactRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import (
    CitationDraft,
    FactDraft,
    FactExtractionDraft,
)
from archium.logging import get_logger
from archium.prompts.fact_extraction import (
    FACT_EXTRACTION_SYSTEM_PROMPT,
    build_fact_extraction_user_prompt,
)

logger = get_logger(__name__, operation="fact_extraction")

UpsertAction = Literal["created", "updated", "merged", "skipped", "conflicted"]


class FactExtractionService:
    """Extract and merge project facts from parse-time chunks and workflow context."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._facts = FactRepository(session)
        self._llm = llm
        self._settings = settings or get_settings()

    def extract_from_document(
        self,
        project_id: UUID,
        *,
        document_name: str,
        chunks: list[DocumentChunk],
    ) -> int:
        """Parse-time rule extraction for strong metrics; returns newly created count."""
        if not chunks or not self._settings.fact_extraction_enabled:
            return 0

        created = 0
        for metric in extract_metrics_from_chunks(chunks):
            chunk = next((item for item in chunks if item.id == metric.chunk_id), None)
            if chunk is None:
                continue
            fact = self._metric_to_fact(project_id, metric, chunk, document_name)
            _, action = self._upsert_fact(fact)
            if action == "created":
                created += 1
        if created:
            logger.info(
                "Extracted %d metric fact(s) at ingest for project %s from %s",
                created,
                project_id,
                document_name,
            )
        return created

    def extract_from_context(
        self,
        project_id: UUID,
        context_bundle: ProjectContextBundle | None,
    ) -> tuple[list[ProjectFact], int]:
        """Rule pass on retrieved chunks, then LLM pass for remaining standard facts."""
        existing = self._facts.list_by_project(project_id)
        created = 0

        if context_bundle is not None and context_bundle.chunks:
            for metric in extract_metrics_from_chunks(context_bundle.chunks):
                chunk = next(
                    (item for item in context_bundle.chunks if item.id == metric.chunk_id),
                    None,
                )
                if chunk is None:
                    continue
                document_name = context_bundle.document_names.get(
                    chunk.document_id,
                    "项目资料",
                )
                fact = self._metric_to_fact(project_id, metric, chunk, document_name)
                _, action = self._upsert_fact(fact)
                if action == "created":
                    created += 1

        existing = self._facts.list_by_project(project_id)
        if context_bundle is None or not context_bundle.chunks:
            logger.info("No context chunks available for fact extraction on project %s", project_id)
            return existing, created

        if not self._settings.fact_extraction_enabled or self._llm is None:
            logger.info("LLM fact extraction disabled or unavailable for project %s", project_id)
            return existing, created

        known_keys = {fact.key for fact in existing}
        standard_keys = {definition.key for definition in STANDARD_FACT_KEYS}
        if known_keys >= standard_keys:
            logger.info("Standard fact keys already populated for project %s", project_id)
            return self._facts.list_by_project(project_id), created

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=FACT_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=build_fact_extraction_user_prompt(
                    project_context=context_bundle.text,
                    existing_keys=sorted(known_keys),
                ),
                model=self._settings.llm_model,
                temperature=0.2,
                json_mode=True,
            ),
            FactExtractionDraft,
        )

        for item in draft.facts:
            key = item.key.strip().lower().replace(" ", "_")
            if not key or key in known_keys:
                continue
            fact = self._draft_to_fact(project_id, item, context_bundle)
            stored, action = self._upsert_fact(fact)
            known_keys.add(stored.key)
            if action == "created":
                created += 1

        logger.info("Extracted %d new fact(s) for project %s", created, project_id)
        return self._facts.list_by_project(project_id), created

    def _metric_to_fact(
        self,
        project_id: UUID,
        metric: ExtractedMetric,
        chunk: DocumentChunk,
        document_name: str,
    ) -> ProjectFact:
        definition = STANDARD_FACT_KEY_MAP.get(metric.key)
        return ProjectFact(
            project_id=project_id,
            key=metric.key,
            label=metric.label,
            value=metric.value,
            unit=metric.unit,
            category=metric.category,
            confidence=metric.confidence,
            conflict_group=definition.conflict_group if definition else None,
            source_citations=[
                Citation(
                    document_id=chunk.document_id,
                    document_name=document_name,
                    page_number=chunk.page_number,
                    chunk_id=chunk.id,
                    quote=metric.quote,
                    confidence=metric.confidence,
                )
            ],
        )

    def _draft_to_fact(
        self,
        project_id: UUID,
        item: FactDraft,
        context_bundle: ProjectContextBundle,
    ) -> ProjectFact:
        key = item.key.strip().lower().replace(" ", "_")
        citations = []
        if item.chunk_id or item.quote:
            citations.append(
                citation_from_draft(
                    CitationDraft(
                        document_name="项目资料",
                        chunk_id=item.chunk_id,
                        quote=item.quote,
                        confidence=item.confidence,
                    ),
                    self._session,
                    document_names=context_bundle.document_names,
                    context_chunks=context_bundle.chunks,
                )
            )
        return ProjectFact(
            project_id=project_id,
            key=key,
            label=item.label.strip(),
            value=item.value.strip(),
            unit=item.unit.strip() if item.unit else None,
            category=item.category.strip() or "general",
            confidence=item.confidence,
            conflict_group=STANDARD_FACT_KEY_MAP[key].conflict_group
            if key in STANDARD_FACT_KEY_MAP
            else None,
            source_citations=citations,
        )

    def _upsert_fact(self, incoming: ProjectFact) -> tuple[ProjectFact, UpsertAction]:
        existing = self._facts.get_by_project_key(incoming.project_id, incoming.key)
        if existing is None:
            stored = self._facts.create(incoming)
            return stored, "created"

        if existing.is_confirmed:
            if _normalize_value(existing.value) == _normalize_value(incoming.value):
                merged = self._merge_citations(existing, incoming)
                if merged is not existing:
                    return self._facts.update(merged), "merged"
                return existing, "skipped"
            existing.mark_conflicted()
            existing.conflict_group = existing.conflict_group or incoming.conflict_group
            return self._facts.update(existing), "conflicted"

        if _normalize_value(existing.value) == _normalize_value(incoming.value):
            merged = self._merge_citations(existing, incoming)
            if merged is not existing:
                return self._facts.update(merged), "merged"
            return existing, "skipped"

        if incoming.confidence > existing.confidence:
            incoming.id = existing.id
            incoming.verification_status = VerificationStatus.EXTRACTED
            incoming.mark_conflicted()
            incoming.conflict_group = incoming.conflict_group or existing.conflict_group
            incoming.source_citations = self._combined_citations(existing, incoming)
            return self._facts.update(incoming), "updated"

        existing.mark_conflicted()
        existing.conflict_group = existing.conflict_group or incoming.conflict_group
        return self._facts.update(existing), "conflicted"

    @staticmethod
    def _merge_citations(existing: ProjectFact, incoming: ProjectFact) -> ProjectFact:
        combined = FactExtractionService._combined_citations(existing, incoming)
        if len(combined) == len(existing.source_citations):
            return existing
        existing.source_citations = combined
        existing.touch()
        return existing

    @staticmethod
    def _combined_citations(existing: ProjectFact, incoming: ProjectFact) -> list[Citation]:
        combined = list(existing.source_citations)
        seen = {
            (item.document_id, item.chunk_id, item.quote)
            for item in combined
        }
        for citation in incoming.source_citations:
            token = (citation.document_id, citation.chunk_id, citation.quote)
            if token in seen:
                continue
            combined.append(citation)
            seen.add(token)
        return combined
