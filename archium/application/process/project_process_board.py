"""Build ProjectProcessBoard from existing process-owned entities (read-derived)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.enums import (
    KnowledgeItemStatus,
    PresentationStatus,
    VerificationStatus,
)
from archium.domain.process import (
    ProcessPointer,
    ProjectProcessBoard,
    ProjectProcessKind,
    ProjectProcessPhase,
)


def build_project_process_board(
    session: SessionLike,
    project_id: UUID,
) -> ProjectProcessBoard:
    """Derive process phases — does not persist; does not touch ProjectContext."""
    session = session_of(session)
    return ProjectProcessBoard(
        research=_research_pointer(session, project_id),
        design=_design_pointer(session, project_id),
        presentation=_presentation_pointer(session, project_id),
    )


def _research_pointer(session: SessionLike, project_id: UUID) -> ProcessPointer:
    session = session_of(session)
    from archium.infrastructure.database.repositories import (
        DocumentRepository,
        FactRepository,
        ProjectKnowledgeRepository,
    )

    docs = DocumentRepository(session).list_by_project(project_id)
    facts = FactRepository(session).list_by_project(project_id)
    items = ProjectKnowledgeRepository(session).list_by_project(project_id)

    active_facts = [
        f for f in facts if f.verification_status != VerificationStatus.REJECTED
    ]
    pending_facts = [f for f in active_facts if not f.is_confirmed]
    confirmed_facts = [f for f in active_facts if f.is_confirmed]
    research_items = [i for i in items if i.category == "research"]
    pending_research = [
        i
        for i in research_items
        if i.status not in {KnowledgeItemStatus.REJECTED, KnowledgeItemStatus.CONFIRMED}
        and not i.is_confirmed
    ]
    confirmed_research = [i for i in research_items if i.is_confirmed]

    now = datetime.now(UTC)
    if pending_facts or pending_research:
        label = "证据待确认"
        detail_bits = []
        if pending_facts:
            detail_bits.append(f"待确认事实 {len(pending_facts)}")
        if pending_research:
            detail_bits.append(f"待确认研究 {len(pending_research)}")
        return ProcessPointer(
            kind=ProjectProcessKind.RESEARCH,
            phase=ProjectProcessPhase.ACTIVE,
            label=label,
            detail="；".join(detail_bits),
            updated_at=now,
        )
    if docs or confirmed_facts or confirmed_research:
        return ProcessPointer(
            kind=ProjectProcessKind.RESEARCH,
            phase=ProjectProcessPhase.READY,
            label="资料与证据可用",
            detail=(
                f"文档 {len(docs)} · 已确认事实 {len(confirmed_facts)}"
                f" · 已确认研究 {len(confirmed_research)}"
            ),
            updated_at=now,
        )
    return ProcessPointer(
        kind=ProjectProcessKind.RESEARCH,
        phase=ProjectProcessPhase.IDLE,
        label="尚未进入研究",
        updated_at=now,
    )


def _design_pointer(session: SessionLike, project_id: UUID) -> ProcessPointer:
    session = session_of(session)
    from archium.application.process.design_process_pointer import build_design_pointer

    return build_design_pointer(session, project_id)


def _presentation_pointer(session: SessionLike, project_id: UUID) -> ProcessPointer:
    session = session_of(session)
    from archium.infrastructure.database.repositories import PresentationRepository

    presentations = PresentationRepository(session).list_by_project(project_id)
    now = datetime.now(UTC)
    if not presentations:
        return ProcessPointer(
            kind=ProjectProcessKind.PRESENTATION,
            phase=ProjectProcessPhase.IDLE,
            label="尚未创建汇报",
            updated_at=now,
        )
    latest = presentations[0]
    status = latest.status
    if status == PresentationStatus.EXPORTED:
        phase = ProjectProcessPhase.COMPLETE
        label = "已导出"
    elif status == PresentationStatus.APPROVED:
        phase = ProjectProcessPhase.READY
        label = "汇报已批准"
    elif status == PresentationStatus.REVIEW:
        phase = ProjectProcessPhase.BLOCKED
        label = "待审核"
    elif status in {PresentationStatus.DRAFT, PresentationStatus.IN_PROGRESS}:
        phase = ProjectProcessPhase.ACTIVE
        label = "汇报制作中"
    else:
        phase = ProjectProcessPhase.IDLE
        label = status.value
    return ProcessPointer(
        kind=ProjectProcessKind.PRESENTATION,
        phase=phase,
        active_id=latest.id,
        label=label,
        detail=(latest.title or "")[:80],
        updated_at=getattr(latest, "updated_at", now),
    )
