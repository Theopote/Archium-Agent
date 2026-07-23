"""Shared evidence + formal delivery readiness (Studio, deliver, flow gates)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.review.export_gating import export_blocking_open_issues
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import EvidenceAvailability
from archium.exceptions import WorkflowError


@dataclass(frozen=True)
class ProjectEvidenceStatus:
    availability: EvidenceAvailability
    document_count: int = 0

    @property
    def allows_formal_export(self) -> bool:
        return (
            self.availability == EvidenceAvailability.AVAILABLE
            and self.document_count > 0
        )

    @property
    def is_concept_draft(self) -> bool:
        return self.availability == EvidenceAvailability.MISSING

    @property
    def is_unknown(self) -> bool:
        return self.availability == EvidenceAvailability.UNKNOWN


@dataclass(frozen=True)
class DeliveryReadinessReport:
    """Unified readiness for formal export — single source for Studio + deliver."""

    evidence: ProjectEvidenceStatus
    pptx_ready: bool = False
    pdf_ready: bool = False
    export_blocker_count: int = 0
    review_blocker_count: int = 0
    deck_qa_blocker_count: int = 0
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def formal_delivery_ready(self) -> bool:
        return (
            self.pptx_ready
            and self.pdf_ready
            and self.evidence.allows_formal_export
            and self.export_blocker_count <= 0
        )

    @property
    def allows_formal_export(self) -> bool:
        return self.formal_delivery_ready


def resolve_project_evidence(session: Session, project_id: UUID) -> ProjectEvidenceStatus:
    from archium.infrastructure.database.repositories import DocumentRepository

    documents = DocumentRepository(session).list_by_project(project_id)
    count = len(documents)
    if count > 0:
        return ProjectEvidenceStatus(
            availability=EvidenceAvailability.AVAILABLE,
            document_count=count,
        )
    return ProjectEvidenceStatus(
        availability=EvidenceAvailability.MISSING,
        document_count=0,
    )


def resolve_project_evidence_safe(project_id: UUID) -> ProjectEvidenceStatus:
    from archium.infrastructure.database.session import get_session

    try:
        with get_session() as session:
            return resolve_project_evidence(session, project_id)
    except Exception:
        return ProjectEvidenceStatus(
            availability=EvidenceAvailability.UNKNOWN,
            document_count=0,
        )


def resolve_delivery_readiness(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID | None,
    deck_qa_report: dict | None = None,
) -> DeliveryReadinessReport:
    from archium.application.visual.layout_readiness import presentation_has_visual_layout

    evidence = resolve_project_evidence(session, project_id)
    pptx_ready = False
    pdf_ready = False
    review_blocker_count = 0
    deck_qa_blocker_count = 0
    blockers: list[str] = []

    if evidence.is_unknown:
        blockers.append("资料状态无法验证，禁止正式交付")
    elif evidence.is_concept_draft:
        blockers.append("概念草稿不可正式交付：请先绑定至少一份项目资料")

    if presentation_id is not None:
        pptx_ready = presentation_has_visual_layout(session, presentation_id)
        # PDF export compiles from the same layout/scene pipeline as PPTX today.
        pdf_ready = pptx_ready
        if not pptx_ready:
            blockers.append("版式未齐，无法正式导出 PPTX")
        if pptx_ready and not pdf_ready:
            blockers.append("PDF 导出准备度未满足")

        try:
            issues = PresentationReviewService(session).list_review_issues(presentation_id)
            review_blockers = export_blocking_open_issues(issues)
            review_blocker_count = len(review_blockers)
            for issue in review_blockers[:5]:
                blockers.append(f"[{issue.category.value}] {issue.title}")
        except Exception:
            blockers.append("质量检查状态无法验证")

    if isinstance(deck_qa_report, dict):
        deck_qa_blocker_count = int(deck_qa_report.get("blocker_count") or 0)
        if deck_qa_blocker_count > 0:
            blockers.append(f"Deck QA 仍有 {deck_qa_blocker_count} 个阻塞项")

    export_blocker_count = review_blocker_count + deck_qa_blocker_count

    return DeliveryReadinessReport(
        evidence=evidence,
        pptx_ready=pptx_ready,
        pdf_ready=pdf_ready,
        export_blocker_count=export_blocker_count,
        review_blocker_count=review_blocker_count,
        deck_qa_blocker_count=deck_qa_blocker_count,
        blockers=tuple(blockers),
    )


def resolve_delivery_readiness_safe(
    *,
    project_id: UUID,
    presentation_id: UUID | None,
    deck_qa_report: dict | None = None,
) -> DeliveryReadinessReport:
    from archium.infrastructure.database.session import get_session

    try:
        with get_session() as session:
            return resolve_delivery_readiness(
                session,
                project_id=project_id,
                presentation_id=presentation_id,
                deck_qa_report=deck_qa_report,
            )
    except Exception:
        evidence = ProjectEvidenceStatus(
            availability=EvidenceAvailability.UNKNOWN,
            document_count=0,
        )
        return DeliveryReadinessReport(
            evidence=evidence,
            blockers=("资料或准备度状态无法验证",),
        )


def assert_formal_export_allowed(
    report: DeliveryReadinessReport,
    *,
    export_format: str = "PPTX",
) -> None:
    """Fail-closed gate before any formal export action."""
    fmt = export_format.upper()
    if report.evidence.is_unknown:
        raise WorkflowError("资料状态无法验证，禁止正式导出。")
    if report.evidence.is_concept_draft:
        raise WorkflowError("概念草稿不可正式导出，请先绑定项目资料。")
    if fmt == "PDF" and not report.pdf_ready:
        raise WorkflowError("PDF 导出准备度未满足（需先完成全部页面版式）。")
    if fmt == "PPTX" and not report.pptx_ready:
        raise WorkflowError("PPTX 导出准备度未满足（需先完成全部页面版式）。")
    if report.export_blocker_count > 0:
        detail = report.blockers[0] if report.blockers else "存在阻塞项"
        raise WorkflowError(f"正式导出被阻止：{detail}")


def latest_presentation_revision_id(
    session: Session,
    presentation_id: UUID,
) -> UUID | None:
    """Best-effort link from export audit row to latest outline revision."""
    from archium.application.artifact_history_service import OutlineHistoryService
    from archium.infrastructure.database.repositories import PresentationRepository

    presentation = PresentationRepository(session).get_presentation(presentation_id)
    if presentation is None or presentation.current_outline_id is None:
        revisions = OutlineHistoryService(session).list_presentation_revisions(
            presentation_id
        )
        return revisions[0].id if revisions else None

    revisions = OutlineHistoryService(session).list_revisions(
        presentation.current_outline_id
    )
    if revisions:
        return revisions[0].id
    outline_revisions = OutlineHistoryService(session).list_presentation_revisions(
        presentation_id
    )
    return outline_revisions[0].id if outline_revisions else None
