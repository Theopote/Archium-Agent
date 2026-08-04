"""Project fact ledger — list, confirm, and resolve structured project facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from archium.application.chunk_models import ProjectContextBundle
from archium.application.fact_extraction_service import FactExtractionService
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.enums import VerificationStatus
from archium.domain.fact import FactValue, ProjectFact
from archium.domain.fact_ledger import STANDARD_FACT_KEYS
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import FactRepository
from archium.infrastructure.llm.base import LLMProvider


@dataclass
class FactLedgerEntry:
    key: str
    label: str
    category: str
    fact: ProjectFact | None = None
    is_standard: bool = True


@dataclass
class FactLedgerView:
    project_id: UUID
    entries: list[FactLedgerEntry] = field(default_factory=list)
    extra_facts: list[ProjectFact] = field(default_factory=list)
    missing_standard_keys: list[str] = field(default_factory=list)
    conflict_count: int = 0
    pending_count: int = 0
    confirmed_count: int = 0


@dataclass(frozen=True)
class FactConfirmResult:
    """Result of confirming a fact, optionally with refreshed KnowledgeState."""

    fact: ProjectFact
    knowledge_summary: str | None = None
    understanding_summary: str | None = None


class FactLedgerService:
    """Manage the project fact ledger used before Brief / Storyline generation."""

    def __init__(
        self,
        session: SessionLike,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._facts = FactRepository(session)
        self._llm = llm
        self._settings = settings or get_settings()

    def get_ledger(self, project_id: UUID) -> FactLedgerView:
        from archium.application.knowledge_gap_detection import resolve_required_fact_keys
        from archium.application.project_context_routing import skips_default_clarification
        from archium.infrastructure.database.repositories import ProjectRepository

        facts = self._facts.list_by_project(project_id)
        by_key = {fact.key: fact for fact in facts}
        entries: list[FactLedgerEntry] = []
        missing: list[str] = []

        project = ProjectRepository(self._session).get_by_id(project_id)
        lightweight = (
            skips_default_clarification(self._session, project_id) if project else False
        )
        description = (project.description or "") if project is not None else ""
        required_keys = resolve_required_fact_keys(
            facts=facts,
            project_name=project.name if project is not None else "",
            project_description=description,
            lightweight=lightweight,
        )
        required_key_set = set(required_keys)

        known_project_name = (project.name or "").strip() if project is not None else ""
        for definition in STANDARD_FACT_KEYS:
            fact = by_key.get(definition.key)
            if definition.key in required_key_set and fact is None:
                # Project entity name already answers the identity fact key.
                if definition.key == "project_name" and known_project_name:
                    pass
                else:
                    missing.append(definition.key)
            entries.append(
                FactLedgerEntry(
                    key=definition.key,
                    label=definition.label,
                    category=definition.category,
                    fact=fact,
                )
            )

        standard_keys = {definition.key for definition in STANDARD_FACT_KEYS}
        extra_facts = [fact for fact in facts if fact.key not in standard_keys]

        active = [fact for fact in facts if fact.verification_status != VerificationStatus.REJECTED]
        return FactLedgerView(
            project_id=project_id,
            entries=entries,
            extra_facts=extra_facts,
            missing_standard_keys=missing,
            conflict_count=sum(
                1
                for fact in active
                if fact.verification_status == VerificationStatus.CONFLICTED
            ),
            pending_count=sum(
                1
                for fact in active
                if fact.verification_status in {VerificationStatus.EXTRACTED, VerificationStatus.INFERRED}
            ),
            confirmed_count=sum(1 for fact in active if fact.is_confirmed),
        )

    def extract_from_context(
        self,
        project_id: UUID,
        context_bundle: ProjectContextBundle | None,
    ) -> tuple[list[ProjectFact], int]:
        extractor = FactExtractionService(
            self._session,
            llm=self._llm,
            settings=self._settings,
        )
        return extractor.extract_from_context(project_id, context_bundle)

    def confirm_fact(self, fact_id: UUID) -> FactConfirmResult:
        fact = self._require_fact(fact_id)
        fact.confirm()
        fact.conflict_group = None
        updated = self._facts.update(fact)
        self._record_confirmed_fact_evidence(updated)
        summary, understanding = self._best_effort_reassess_after_confirm(
            updated.project_id,
            reason="fact_confirmed",
        )
        return FactConfirmResult(
            fact=updated,
            knowledge_summary=summary,
            understanding_summary=understanding,
        )

    def reject_fact(self, fact_id: UUID) -> ProjectFact:
        fact = self._require_fact(fact_id)
        fact.reject()
        updated = self._facts.update(fact)
        self._best_effort_reassess_after_confirm(
            updated.project_id,
            reason="fact_rejected",
        )
        return updated

    def update_fact(
        self,
        fact_id: UUID,
        *,
        value: FactValue,
        unit: str | None = None,
    ) -> ProjectFact:
        fact = self._require_fact(fact_id)
        fact.value = value
        if unit is not None:
            fact.unit = unit.strip() or None
        if fact.verification_status == VerificationStatus.CONFLICTED:
            fact.verification_status = VerificationStatus.EXTRACTED
        fact.conflict_group = None
        fact.touch()
        return self._facts.update(fact)

    def assign_conflict_group(self, fact_ids: list[UUID], *, group_id: str | None = None) -> None:
        group = group_id or str(uuid4())
        for fact_id in fact_ids:
            fact = self._require_fact(fact_id)
            fact.mark_conflicted()
            fact.conflict_group = group
            self._facts.update(fact)

    def _record_confirmed_fact_evidence(self, fact: ProjectFact) -> None:
        try:
            from archium.application.intent_evidence_helpers import (
                evidence_from_confirmed_fact,
                record_intent_evidence,
            )

            evidence = evidence_from_confirmed_fact(fact)
            unit = f" {fact.unit}" if fact.unit else ""
            record_intent_evidence(
                self._session,
                fact.project_id,
                evidence,
                summary=f"确认事实：{fact.label} = {fact.value}{unit}",
            )
        except Exception:
            # Provenance is best-effort; never block fact confirmation.
            return

    def _best_effort_reassess_after_confirm(
        self,
        project_id: UUID,
        *,
        reason: str = "fact_confirmed",
    ) -> tuple[str | None, str | None]:
        """Refresh KnowledgeState after a fact ledger change; never fail confirm."""
        from archium.application.context import best_effort_reassess_knowledge

        assessment = best_effort_reassess_knowledge(
            self._session,
            project_id,
            llm=self._llm,
            settings=self._settings,
            reason=reason,
        )
        if assessment is None:
            return None, None
        return (
            assessment.knowledge_state.summary_line(),
            assessment.understanding_summary.strip() or None,
        )
    def _require_fact(self, fact_id: UUID) -> ProjectFact:
        fact = self._facts.get_by_id(fact_id)
        if fact is None:
            raise WorkflowError(f"ProjectFact {fact_id} not found")
        return fact
