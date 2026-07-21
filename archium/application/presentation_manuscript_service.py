"""Build and persist PresentationManuscript from project knowledge / research."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.domain.enums import InformationOrigin, KnowledgeItemStatus
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import (
    CitationReference,
    EvidenceItem,
    ManuscriptFact,
    ManuscriptSection,
    ManuscriptStatus,
    PresentationManuscript,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationManuscriptRepository,
    ProjectKnowledgeRepository,
)


def outline_plan_from_manuscript(
    manuscript: PresentationManuscript,
    *,
    brief: PresentationBrief | None = None,
    audience: str = "",
    purpose: str = "",
) -> OutlinePlan:
    """Map manuscript sections into an OutlinePlan (Outline reads Manuscript)."""
    if brief is None and manuscript.presentation_id is None:
        raise WorkflowError(
            "outline_from_manuscript 需要 PresentationBrief 或 presentation_id"
        )

    presentation_id = (
        brief.presentation_id if brief is not None else manuscript.presentation_id
    )
    assert presentation_id is not None

    sections = [
        OutlineSection(
            id=section.id,
            title=section.title,
            purpose=section.purpose,
            key_message=section.argument,
            estimated_slide_count=max(1, len(section.key_points) or 1),
            evidence_requirements=list(section.evidence_ids),
            required_assets=[],
            order=section.order,
            category="general",
        )
        for section in sorted(manuscript.sections, key=lambda s: s.order)
    ]
    if not sections:
        sections = [
            OutlineSection(
                id="sec-from-manuscript",
                title=manuscript.title,
                purpose="由 PresentationManuscript 生成",
                key_message=manuscript.narrative_thesis,
                estimated_slide_count=3,
                order=0,
            )
        ]

    return OutlinePlan(
        presentation_id=presentation_id,
        manuscript_id=manuscript.id,
        title=brief.title if brief else manuscript.title,
        thesis=manuscript.narrative_thesis,
        audience=brief.audience if brief else (audience or "未指定受众"),
        purpose=brief.purpose if brief else (purpose or manuscript.project_summary),
        target_slide_count=(
            brief.target_slide_count if brief else max(8, len(sections) * 2)
        ),
        sections=sections,
    )


class PresentationManuscriptService:
    """Research middle layer: ProjectKnowledge → Manuscript → OutlinePlan."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._manuscripts = PresentationManuscriptRepository(session)
        self._knowledge = ProjectKnowledgeRepository(session)

    def get(self, manuscript_id: UUID) -> PresentationManuscript | None:
        return self._manuscripts.get(manuscript_id)

    def list_for_project(self, project_id: UUID) -> list[PresentationManuscript]:
        return self._manuscripts.list_by_project(project_id)

    def save(self, manuscript: PresentationManuscript) -> PresentationManuscript:
        return self._manuscripts.save(manuscript)

    def build_from_knowledge(
        self,
        *,
        project_id: UUID,
        title: str,
        project_summary: str,
        narrative_thesis: str,
        knowledge_items: list[ProjectKnowledgeItem] | None = None,
        presentation_id: UUID | None = None,
        storyline: Storyline | None = None,
    ) -> PresentationManuscript:
        items = knowledge_items
        if items is None:
            items = self._knowledge.list_by_project(project_id)

        facts: list[ManuscriptFact] = []
        evidence: list[EvidenceItem] = []
        citations: list[CitationReference] = []
        unresolved: list[str] = []
        unsupported: list[str] = []
        missing: list[str] = []

        for item in items:
            if item.status == KnowledgeItemStatus.REJECTED:
                continue
            if item.is_reference_only:
                unsupported.append(
                    f"参考案例陈述未纳入项目事实：{item.statement[:80]}"
                )
                continue

            safe_citation_ids: list[str] = []
            for source in item.source_citations:
                if source.document_id is None:
                    missing.append(
                        f"知识条目缺少可追溯文档引用：{item.statement[:80]}"
                    )
                    continue
                citation_id = str(uuid4())
                safe_citation_ids.append(citation_id)
                citations.append(
                    CitationReference(
                        id=citation_id,
                        citation=source.to_citation(),
                        label=source.document_name,
                    )
                )

            if not safe_citation_ids and not item.source_citations:
                missing.append(f"知识条目无来源：{item.statement[:80]}")
                continue

            verified = (
                item.status == KnowledgeItemStatus.CONFIRMED
                or item.origin
                in {InformationOrigin.USER_UPLOAD, InformationOrigin.USER_CONFIRMED}
            )
            fact = ManuscriptFact(
                statement=item.statement,
                source_id=str(item.id),
                citation_ids=safe_citation_ids,
                confidence=1.0 if verified else 0.6,
                verified=verified,
                knowledge_item_id=item.id,
            )
            facts.append(fact)

            if item.requires_user_confirmation and not verified:
                unresolved.append(item.statement)

            evidence.append(
                EvidenceItem(
                    evidence_type="document_quote",
                    summary=item.statement,
                    source_id=str(item.id),
                    citation_id=safe_citation_ids[0] if safe_citation_ids else None,
                    confidence=fact.confidence,
                    verified=verified,
                    asset_origin="project_upload",
                )
            )

        sections = _sections_from_storyline(storyline) if storyline else []
        if not sections and facts:
            sections = [
                ManuscriptSection(
                    id="sec-overview",
                    title="项目概况与核心判断",
                    purpose="汇总已核实事实，支撑后续大纲",
                    argument=narrative_thesis,
                    key_points=[f.statement for f in facts[:5]],
                    fact_ids=[f.id for f in facts[:5]],
                    evidence_ids=[e.id for e in evidence[:5]],
                    recommended_slide_types=["text_argument", "metric_summary"],
                    order=0,
                )
            ]

        manuscript = PresentationManuscript(
            project_id=project_id,
            presentation_id=presentation_id,
            title=title.strip() or "未命名汇报手稿",
            project_summary=project_summary.strip() or title,
            narrative_thesis=narrative_thesis.strip() or project_summary,
            verified_facts=facts,
            sections=sections,
            evidence_catalog=evidence,
            citations=citations,
            unresolved_questions=unresolved,
            unsupported_claims=unsupported,
            missing_information=missing,
            status=ManuscriptStatus.DRAFT,
        )
        return self._manuscripts.save(manuscript)

    def outline_from_manuscript(
        self,
        manuscript: PresentationManuscript,
        *,
        brief: PresentationBrief | None = None,
        audience: str = "",
        purpose: str = "",
    ) -> OutlinePlan:
        return outline_plan_from_manuscript(
            manuscript,
            brief=brief,
            audience=audience,
            purpose=purpose,
        )


def _sections_from_storyline(storyline: Storyline) -> list[ManuscriptSection]:
    sections: list[ManuscriptSection] = []
    for chapter in sorted(storyline.chapters, key=lambda item: item.order):
        sections.append(
            ManuscriptSection(
                id=chapter.id,
                title=chapter.title,
                purpose=chapter.purpose,
                argument=chapter.key_message,
                key_points=[chapter.key_message],
                recommended_slide_types=["text_argument"],
                order=chapter.order,
            )
        )
    return sections
