"""Shared evidence + formal delivery readiness (Studio, deliver, flow gates)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.review.export_gating import export_blocking_open_issues
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import EvidenceAvailability
from archium.domain.export_verdict import ExportVerdict, ExportVerdictStatus
from archium.domain.slide_role import SlideRole
from archium.exceptions import WorkflowError


@dataclass(frozen=True)
class MaterialsExportReadiness:
    """Formal export materials gate (delivery BC — not IntentEvidence)."""

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


# KN-012 legacy alias — prefer MaterialsExportReadiness in new code.
ProjectEvidenceStatus = MaterialsExportReadiness


@dataclass(frozen=True)
class DeliveryReadinessReport:
    """Unified readiness for formal export — single source for Studio + deliver."""

    evidence: MaterialsExportReadiness
    pptx_ready: bool = False
    pdf_ready: bool = False
    export_blocker_count: int = 0
    review_blocker_count: int = 0
    deck_qa_blocker_count: int = 0
    citation_gap_count: int = 0
    blockers: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    critic_lines: tuple[str, ...] = field(default_factory=tuple)
    evidence_stacks: tuple[str, ...] = field(default_factory=tuple)

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

    def to_export_verdict(
        self,
        *,
        round_trip_status: str | None = None,
    ) -> ExportVerdict:
        status = ExportVerdictStatus.READY
        if not self.allows_formal_export:
            status = ExportVerdictStatus.BLOCKED
        elif self.warnings or self.critic_lines:
            status = ExportVerdictStatus.READY_WITH_WARNINGS
        if round_trip_status == "blocked":
            status = ExportVerdictStatus.BLOCKED
        stacks = self.evidence_stacks or ("materials_evidence",)
        return ExportVerdict(
            status=status,
            blockers=self.blockers,
            warnings=self.warnings,
            critic_lines=self.critic_lines,
            citation_gap_count=self.citation_gap_count,
            review_blocker_count=self.review_blocker_count,
            deck_qa_blocker_count=self.deck_qa_blocker_count,
            pptx_ready=self.pptx_ready,
            pdf_ready=self.pdf_ready,
            evidence_ok=self.evidence.allows_formal_export,
            round_trip_status=round_trip_status,
            evidence_stacks=stacks,
        )


_ANALYSIS_ROLES = frozenset(
    {
        SlideRole.PROBLEM_ANALYSIS,
        SlideRole.SITE_ANALYSIS,
        SlideRole.STRATEGY,
        SlideRole.SPATIAL_LOGIC,
        SlideRole.COMPARISON,
    }
)


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
    presentation_critique: dict | None = None,
) -> DeliveryReadinessReport:
    from archium.application.visual.layout_readiness import presentation_has_visual_layout

    evidence = resolve_project_evidence(session, project_id)
    pptx_ready = False
    pdf_ready = False
    review_blocker_count = 0
    deck_qa_blocker_count = 0
    citation_gap_count = 0
    blockers: list[str] = []
    warnings: list[str] = []
    critic_lines: list[str] = []
    stacks: list[str] = ["materials_evidence"]
    scene_hit = False

    if evidence.is_unknown:
        blockers.append("资料状态无法验证，禁止正式交付")
    elif evidence.is_concept_draft:
        blockers.append("概念草稿不可正式交付：请先绑定至少一份项目资料")

    if presentation_id is not None:
        pptx_ready = presentation_has_visual_layout(session, presentation_id)
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
            if review_blocker_count > 0:
                stacks.append("automated_review")
        except Exception:
            blockers.append("质量检查状态无法验证")
            stacks.append("automated_review")

        for message in _scene_export_blocker_messages(
            session,
            presentation_id=presentation_id,
            project_id=project_id,
        ):
            blockers.append(message)
            review_blocker_count += 1
            scene_hit = True
        if scene_hit:
            stacks.append("scene_semantic")

        citation_msgs = _citation_gap_messages(session, presentation_id)
        citation_gap_count = len(citation_msgs)
        blockers.extend(citation_msgs[:5])
        if citation_gap_count > 0:
            stacks.append("citation_gap")

    if isinstance(deck_qa_report, dict):
        deck_qa_blocker_count = int(deck_qa_report.get("blocker_count") or 0)
        stacks.append("deck_qa")
        if deck_qa_blocker_count > 0:
            blockers.append(f"Deck QA 仍有 {deck_qa_blocker_count} 个阻塞项")

    if isinstance(presentation_critique, dict):
        stacks.append("presentation_critic")
        for item in list(presentation_critique.get("missing_points") or [])[:3]:
            critic_lines.append(str(item))
        for item in list(presentation_critique.get("suggestions") or [])[:2]:
            warnings.append(str(item))

    export_blocker_count = (
        review_blocker_count + deck_qa_blocker_count + citation_gap_count
    )

    return DeliveryReadinessReport(
        evidence=evidence,
        pptx_ready=pptx_ready,
        pdf_ready=pdf_ready,
        export_blocker_count=export_blocker_count,
        review_blocker_count=review_blocker_count,
        deck_qa_blocker_count=deck_qa_blocker_count,
        citation_gap_count=citation_gap_count,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        critic_lines=tuple(critic_lines),
        evidence_stacks=tuple(dict.fromkeys(stacks)),
    )


def resolve_delivery_readiness_safe(
    *,
    project_id: UUID,
    presentation_id: UUID | None,
    deck_qa_report: dict | None = None,
    presentation_critique: dict | None = None,
) -> DeliveryReadinessReport:
    from archium.infrastructure.database.session import get_session

    try:
        with get_session() as session:
            return resolve_delivery_readiness(
                session,
                project_id=project_id,
                presentation_id=presentation_id,
                deck_qa_report=deck_qa_report,
                presentation_critique=presentation_critique,
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


def resolve_export_verdict(
    session: Session,
    *,
    project_id: UUID,
    presentation_id: UUID | None,
    deck_qa_report: dict | None = None,
    presentation_critique: dict | None = None,
    round_trip_status: str | None = None,
) -> ExportVerdict:
    """Single partner-facing verdict for Studio + Deliver."""
    report = resolve_delivery_readiness(
        session,
        project_id=project_id,
        presentation_id=presentation_id,
        deck_qa_report=deck_qa_report,
        presentation_critique=presentation_critique,
    )
    return report.to_export_verdict(round_trip_status=round_trip_status)


def resolve_export_verdict_safe(
    *,
    project_id: UUID,
    presentation_id: UUID | None,
    deck_qa_report: dict | None = None,
    presentation_critique: dict | None = None,
    round_trip_status: str | None = None,
) -> ExportVerdict:
    report = resolve_delivery_readiness_safe(
        project_id=project_id,
        presentation_id=presentation_id,
        deck_qa_report=deck_qa_report,
        presentation_critique=presentation_critique,
    )
    return report.to_export_verdict(round_trip_status=round_trip_status)


def assert_formal_export_allowed(
    report: DeliveryReadinessReport | ExportVerdict,
    *,
    export_format: str = "PPTX",
) -> None:
    """Fail-closed gate before any formal export action."""
    fmt = export_format.upper()
    if isinstance(report, ExportVerdict):
        if not report.allows_formal_export:
            detail = report.blockers[0] if report.blockers else "存在阻塞项"
            raise WorkflowError(f"正式导出被阻止：{detail}")
        if fmt == "PDF" and not report.pdf_ready:
            raise WorkflowError("PDF 导出准备度未满足（需先完成全部页面版式）。")
        if fmt == "PPTX" and not report.pptx_ready:
            raise WorkflowError("PPTX 导出准备度未满足（需先完成全部页面版式）。")
        if not report.evidence_ok:
            raise WorkflowError("概念草稿不可正式导出，请先绑定项目资料。")
        return

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


def citation_lines_for_slide(slide: object) -> list[str]:
    """Format SlideSpec.source_citations for PPTX citation blocks."""
    citations = getattr(slide, "source_citations", None) or []
    lines: list[str] = []
    for citation in citations[:6]:
        label = _citation_display_label(citation)
        if not label:
            continue
        page = getattr(citation, "page_number", None)
        quote = str(getattr(citation, "quote", "") or "").strip()
        bit = label
        if page:
            bit = f"{bit} p.{page}"
        if quote:
            bit = f"{bit} — {quote[:80]}"
        lines.append(bit)
    return lines


def _citation_display_label(citation: object) -> str:
    display = getattr(citation, "display_label", None)
    if callable(display):
        label = str(display() or "").strip()
        if label:
            return label
    name = str(getattr(citation, "document_name", "") or "").strip()
    if name:
        return name
    title = str(getattr(citation, "source_title", "") or "").strip()
    if title:
        return title
    url = str(getattr(citation, "url", "") or "").strip()
    if url:
        from urllib.parse import urlparse

        host = (urlparse(url).netloc or "").strip()
        return host or url[:60]
    return ""


def _citation_gap_messages(session: Session, presentation_id: UUID) -> list[str]:
    """Analysis pages must carry source citations / grammar evidence slots."""
    from archium.application.visual.visual_grammar_slots import missing_evidence_slots
    from archium.infrastructure.database.repositories import PresentationRepository

    messages: list[str] = []
    try:
        slides = PresentationRepository(session).list_slides(presentation_id)
    except Exception:
        return []
    for slide in slides:
        role = getattr(slide, "slide_role", None)
        order = int(getattr(slide, "order", 0) or 0) + 1
        title = str(getattr(slide, "title", "") or f"第{order}页")
        if role in _ANALYSIS_ROLES and not getattr(slide, "source_citations", None):
            messages.append(f"分析页「{title}」缺少来源引用（source_citations）")
        try:
            for slot in missing_evidence_slots(slide):
                messages.append(f"页「{title}」缺少证据槽：{slot.role}")
        except Exception:
            continue
        if len(messages) >= 8:
            break
    return messages


def _scene_export_blocker_messages(
    session: Session,
    *,
    presentation_id: UUID,
    project_id: UUID,
) -> list[str]:
    """In-memory Scene semantic blockers for formal export (no ReviewIssue spam).

    Resolves asset paths the same way formal PPTX export does, so stale
    ``asset_unresolved`` flags do not block when files are actually available.
    """
    try:
        from archium.application.visual.asset_path_resolver import (
            AssetPathResolveContext,
            AssetPathResolver,
        )
        from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
        from archium.config.settings import get_settings
        from archium.domain.visual.page_quality import IssueSeverity
        from archium.domain.visual.quality_issue_catalog import default_severity_for_auto_code
        from archium.infrastructure.database.repositories import PresentationRepository
        from archium.infrastructure.database.visual_repositories import RenderSceneRepository

        slides = PresentationRepository(session).list_slides(presentation_id)
        scenes_repo = RenderSceneRepository(session)
        scenes = []
        orders: dict[UUID, int] = {}
        for slide in slides:
            orders[slide.id] = slide.order
            if slide.layout_plan_id is None:
                continue
            scene = scenes_repo.get_by_layout_plan(slide.layout_plan_id)
            if scene is not None:
                scenes.append(scene)
        if not scenes:
            return []
        settings = get_settings()
        resolver = AssetPathResolver()
        resolve_ctx = AssetPathResolveContext(
            project_id=project_id,
            project_storage_root=settings.project_storage_path,
        )
        resolved_scenes = [
            resolver.resolve_scene(scene, resolve_ctx) for scene in scenes
        ]
        report = run_scene_semantic_qa(
            presentation_id,
            resolved_scenes,
            project_id=project_id,
            slide_orders=orders,
        )
        messages: list[str] = []
        for finding in report.findings:
            if default_severity_for_auto_code(finding.check_code) != IssueSeverity.BLOCKER:
                continue
            messages.append(f"[scene] {finding.title}")
            if len(messages) >= 5:
                break
        return messages
    except Exception:
        return []
