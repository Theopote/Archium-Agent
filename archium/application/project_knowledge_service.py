"""Unified project knowledge view — facts, statements, gaps, and isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.knowledge_gap_detection import KnowledgeGapReport, detect_knowledge_gaps
from archium.application.knowledge_isolation import (
    fact_to_knowledge_item,
    filter_generation_facts,
    filter_generation_knowledge,
    is_reference_document,
)
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

    def __init__(self, session: Session) -> None:
        self._session = session
        self._facts = FactRepository(session)
        self._knowledge = ProjectKnowledgeRepository(session)
        self._documents = DocumentRepository(session)

    def get_view(self, project_id: UUID) -> ProjectKnowledgeView:
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
        gap_report = detect_knowledge_gaps(
            project_id,
            facts=self._facts.list_by_project(project_id),
            knowledge_items=combined,
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
        )
        return self._knowledge.create(item)

    def confirm_item(self, item_id: UUID) -> ProjectKnowledgeItem:
        item = self._require_item(item_id)
        item.confirm()
        return self._knowledge.update(item)

    def reject_item(self, item_id: UUID) -> ProjectKnowledgeItem:
        item = self._require_item(item_id)
        item.reject()
        return self._knowledge.update(item)

    def update_item_statement(self, item_id: UUID, statement: str) -> ProjectKnowledgeItem:
        item = self._require_item(item_id)
        cleaned = statement.strip()
        if not cleaned:
            raise WorkflowError("Knowledge statement must not be empty")
        item.statement = cleaned
        item.touch()
        return self._knowledge.update(item)

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
