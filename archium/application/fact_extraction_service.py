"""Extract structured ProjectFact records from retrieved context."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.citations import citation_from_draft
from archium.application.chunk_models import ProjectContextBundle
from archium.config.settings import Settings, get_settings
from archium.domain.fact import ProjectFact
from archium.infrastructure.database.repositories import FactRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import CitationDraft, FactExtractionDraft
from archium.logging import get_logger
from archium.prompts.fact_extraction import (
    FACT_EXTRACTION_SYSTEM_PROMPT,
    build_fact_extraction_user_prompt,
)

logger = get_logger(__name__, operation="fact_extraction")


class FactExtractionService:
    """LLM-assisted extraction of project facts from document chunks."""

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

    def extract_from_context(
        self,
        project_id: UUID,
        context_bundle: ProjectContextBundle | None,
    ) -> tuple[list[ProjectFact], int]:
        """Return project facts and the number newly persisted in this pass."""
        existing = self._facts.list_by_project(project_id)
        if existing:
            logger.info("Project %s already has %d fact(s); skipping extraction", project_id, len(existing))
            return existing, 0

        if context_bundle is None or not context_bundle.chunks:
            logger.info("No context chunks available for fact extraction on project %s", project_id)
            return existing, 0

        if not self._settings.fact_extraction_enabled or self._llm is None:
            logger.info("Fact extraction disabled or LLM unavailable for project %s", project_id)
            return existing, 0

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=FACT_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=build_fact_extraction_user_prompt(project_context=context_bundle.text),
                model=self._settings.llm_model,
                temperature=0.2,
                json_mode=True,
            ),
            FactExtractionDraft,
        )

        known_keys = {fact.key for fact in existing}
        created = 0
        for item in draft.facts:
            key = item.key.strip().lower().replace(" ", "_")
            if not key or key in known_keys:
                continue
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
            fact = ProjectFact(
                project_id=project_id,
                key=key,
                label=item.label.strip(),
                value=item.value.strip(),
                unit=item.unit.strip() if item.unit else None,
                category=item.category.strip() or "general",
                confidence=item.confidence,
                source_citations=citations,
            )
            stored = self._facts.create(fact)
            existing.append(stored)
            known_keys.add(key)
            created += 1

        logger.info("Extracted %d new fact(s) for project %s", created, project_id)
        return existing, created
