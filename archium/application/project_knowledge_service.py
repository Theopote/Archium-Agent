"""Unified project knowledge view — facts, statements, gaps, and isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from archium.application.knowledge_gap_detection import KnowledgeGapReport, detect_knowledge_gaps
from archium.application.knowledge_isolation import (
    fact_to_knowledge_item,
    filter_generation_facts,
    filter_generation_knowledge,
    is_reference_document,
)
from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import (
    DocumentPurpose,
    InformationOrigin,
    InformationReliability,
)
from archium.domain.fact import ProjectFact
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectKnowledgeRepository,
)


@dataclass
class KnowledgePanelSection:
    key: str
    title: str
    items: list[ProjectKnowledgeItem] = field(default_factory=list)


@dataclass
class ProjectKnowledgeView:
    project_id: UUID
    sections: list[KnowledgePanelSection] = field(default_factory=list)
    gap_report: KnowledgeGapReport | None = None

    @property
    def all_items(self) -> list[ProjectKnowledgeItem]:
        items: list[ProjectKnowledgeItem] = []
        for section in self.sections:
            items.extend(section.items)
        return items

    @property
    def generation_eligible_items(self) -> list[ProjectKnowledgeItem]:
        return filter_generation_knowledge(self.all_items)


class ProjectKnowledgeService:
    """Manage provenance-tracked project knowledge and generation eligibility."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._facts = FactRepository(session)
        self._knowledge = ProjectKnowledgeRepository(session)
        self._documents = DocumentRepository(session)

    def get_view(self, project_id: UUID) -> ProjectKnowledgeView:
        from archium.application.knowledge_gap_detection import resolve_required_fact_keys
        from archium.application.project_context_routing import skips_default_clarification
        from archium.infrastructure.database.repositories import ProjectRepository

        reference_doc_ids = self._reference_document_ids(project_id)
        fact_items = [
            fact_to_knowledge_item(
                fact,
                from_reference=self._fact_from_reference(fact, reference_doc_ids),
            )
            for fact in self._facts.list_by_project(project_id)
        ]
        stored_items = self._knowledge.list_by_project(project_id)
        combined = self._merge_fact_and_stored_items(fact_items, stored_items)
        sections = self._build_sections(combined)
        project = ProjectRepository(self._session).get_by_id(project_id)
        lightweight = (
            skips_default_clarification(self._session, project_id) if project else False
        )
        description = ""
        if project is not None and project.description:
            description = project.description
        facts = self._facts.list_by_project(project_id)
        required_keys = resolve_required_fact_keys(
            facts=facts,
            project_name=project.name if project else "",
            project_description=description,
            lightweight=lightweight,
        )
        gap_report = detect_knowledge_gaps(
            project_id,
            facts=facts,
            knowledge_items=combined,
            required_fact_keys=required_keys,
            lightweight_mode=lightweight,
        )
        return ProjectKnowledgeView(
            project_id=project_id,
            sections=sections,
            gap_report=gap_report,
        )

    def create_item(
        self,
        project_id: UUID,
        *,
        statement: str,
        origin: InformationOrigin,
        reliability: InformationReliability,
        source_citations: list[SourceCitation] | None = None,
        applies_to_current_project: bool = True,
        requires_user_confirmation: bool = False,
        category: str = "general",
        design_knowledge: DesignKnowledge | None = None,
    ) -> ProjectKnowledgeItem:
        if origin == InformationOrigin.REFERENCE_CASE:
            applies_to_current_project = False
        if origin == InformationOrigin.PUBLIC_RESEARCH and not source_citations:
            requires_user_confirmation = True
        if reliability == InformationReliability.INFERENCE:
            requires_user_confirmation = True

        item = ProjectKnowledgeItem(
            id=uuid4(),
            project_id=project_id,
            statement=statement.strip(),
            origin=origin,
            reliability=reliability,
            source_citations=source_citations or [],
            applies_to_current_project=applies_to_current_project,
            requires_user_confirmation=requires_user_confirmation,
            category=category,
            design_knowledge=design_knowledge,
        )
        created = self._knowledge.create(item)
        self._best_effort_vector_index(created)
        return created

    def confirm_item(self, item_id: UUID) -> ProjectKnowledgeItem:
        item = self._require_item(item_id)
        item.confirm()
        self._best_effort_link_architecture_case(item)
        self._best_effort_confirm_graph_edges(item)
        updated = self._knowledge.update(item)
        self._best_effort_vector_index(updated)
        self._best_effort_index_after_knowledge_change(
            updated.project_id,
            reason="knowledge_item_confirmed",
        )
        return updated

    def _best_effort_link_architecture_case(self, item: ProjectKnowledgeItem) -> None:
        """Phase B: link seed / project case or create draft from DesignKnowledge."""
        try:
            from archium.application.architecture_case_service import ArchitectureCaseService

            ArchitectureCaseService(self._session).ensure_from_knowledge_item(item)
        except Exception:
            return

    def _best_effort_confirm_graph_edges(self, item: ProjectKnowledgeItem) -> None:
        """Phase C: persist confirmed graph edges for precedent / linked fact."""
        try:
            from archium.application.knowledge_graph_service import KnowledgeGraphService

            KnowledgeGraphService(self._session).ensure_edges_from_knowledge_item(item)
        except Exception:
            return

    def reject_item(self, item_id: UUID) -> ProjectKnowledgeItem:
        item = self._require_item(item_id)
        item.reject()
        updated = self._knowledge.update(item)
        self._best_effort_remove_vector(updated)
        self._best_effort_index_after_knowledge_change(
            updated.project_id,
            reason="knowledge_item_rejected",
        )
        return updated

    def _best_effort_vector_index(self, item: ProjectKnowledgeItem) -> None:
        try:
            from archium.application.knowledge_vector_index import (
                best_effort_index_knowledge_item,
            )

            best_effort_index_knowledge_item(self._session, item)
        except Exception:
            return

    def _best_effort_remove_vector(self, item: ProjectKnowledgeItem) -> None:
        try:
            from archium.application.knowledge_vector_index import KnowledgeVectorIndexService

            KnowledgeVectorIndexService(self._session).remove_item(item.project_id, item.id)
        except Exception:
            return

    def _best_effort_index_after_knowledge_change(
        self,
        project_id: UUID,
        *,
        reason: str,
    ) -> None:
        """Refresh claim index after knowledge confirm/reject; never fail caller."""
        try:
            from archium.application.context import best_effort_reassess_knowledge

            best_effort_reassess_knowledge(
                self._session,
                project_id,
                reason=reason,
            )
        except Exception:
            return

    def update_item_statement(self, item_id: UUID, statement: str) -> ProjectKnowledgeItem:
        item = self._require_item(item_id)
        cleaned = statement.strip()
        if not cleaned:
            raise WorkflowError("Knowledge statement must not be empty")
        item.statement = cleaned
        item.touch()
        updated = self._knowledge.update(item)
        self._best_effort_vector_index(updated)
        return updated

    def set_document_purpose(self, document_id: UUID, purpose: DocumentPurpose) -> None:
        document = self._documents.get_document(document_id)
        if document is None:
            raise WorkflowError(f"Document {document_id} not found")
        metadata = dict(document.metadata)
        metadata["purpose"] = purpose.value
        document.metadata = metadata
        self._documents.update_document(document)

    def generation_eligible_facts(self, project_id: UUID) -> list[ProjectFact]:
        reference_doc_ids = self._reference_document_ids(project_id)
        facts = self._facts.list_by_project(project_id)
        return filter_generation_facts(
            facts,
            reference_document_ids=reference_doc_ids,
        )

    def generation_eligible_items(self, project_id: UUID) -> list[ProjectKnowledgeItem]:
        """Knowledge items safe for manuscript / design-stage consumption."""
        return self.get_view(project_id).generation_eligible_items

    def list_research_knowledge_items(
        self,
        project_id: UUID,
        *,
        pending_only: bool = True,
        limit: int = 5,
    ) -> list[ProjectKnowledgeItem]:
        """Return autonomous research items, newest first."""
        items = [
            item
            for item in self._knowledge.list_by_project(project_id)
            if item.category == "research"
            and (not pending_only or (not item.is_confirmed and not item.is_rejected))
        ]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items[: max(1, limit)]

    def list_confirmed_research_items(self, project_id: UUID) -> list[ProjectKnowledgeItem]:
        """Return confirmed research knowledge items (including after user confirmation)."""
        items = [
            item
            for item in self._knowledge.list_by_project(project_id)
            if item.category == "research" and item.is_confirmed
        ]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def _require_item(self, item_id: UUID) -> ProjectKnowledgeItem:
        item = self._knowledge.get_by_id(item_id)
        if item is None:
            raise WorkflowError(f"Knowledge item {item_id} not found")
        return item

    def _reference_document_ids(self, project_id: UUID) -> set[str]:
        documents = self._documents.list_by_project(project_id)
        return {
            str(doc.id)
            for doc in documents
            if is_reference_document(doc.metadata)
        }

    @staticmethod
    def _fact_from_reference(fact: ProjectFact, reference_doc_ids: set[str]) -> bool:
        if not fact.source_citations or not reference_doc_ids:
            return False
        return all(str(c.document_id) in reference_doc_ids for c in fact.source_citations)

    @staticmethod
    def _merge_fact_and_stored_items(
        fact_items: list[ProjectKnowledgeItem],
        stored_items: list[ProjectKnowledgeItem],
    ) -> list[ProjectKnowledgeItem]:
        linked = {item.linked_fact_id for item in stored_items if item.linked_fact_id}
        merged = list(stored_items)
        for item in fact_items:
            if item.linked_fact_id in linked or item.id in linked:
                continue
            merged.append(item)
        return merged

    @staticmethod
    def _build_sections(items: list[ProjectKnowledgeItem]) -> list[KnowledgePanelSection]:
        confirmed: list[ProjectKnowledgeItem] = []
        pending: list[ProjectKnowledgeItem] = []
        reference: list[ProjectKnowledgeItem] = []
        public: list[ProjectKnowledgeItem] = []
        inference: list[ProjectKnowledgeItem] = []
        conflict: list[ProjectKnowledgeItem] = []
        rejected: list[ProjectKnowledgeItem] = []

        for item in items:
            if item.is_rejected:
                rejected.append(item)
            elif item.reliability.value == "conflicting":
                conflict.append(item)
            elif item.is_reference_only:
                reference.append(item)
            elif item.origin == InformationOrigin.PUBLIC_RESEARCH:
                public.append(item)
            elif item.is_inference:
                inference.append(item)
            elif item.is_confirmed:
                confirmed.append(item)
            elif item.requires_user_confirmation:
                pending.append(item)
            else:
                confirmed.append(item)

        return [
            KnowledgePanelSection("confirmed", "已确认事实", confirmed),
            KnowledgePanelSection("pending", "待确认信息", pending),
            KnowledgePanelSection("gaps", "资料缺口", []),
            KnowledgePanelSection("public", "公开资料", public),
            KnowledgePanelSection("reference", "参考案例", reference),
            KnowledgePanelSection("conflict", "冲突信息", conflict),
            KnowledgePanelSection("inference", "系统推测", inference),
            KnowledgePanelSection("rejected", "已驳回", rejected),
        ]
