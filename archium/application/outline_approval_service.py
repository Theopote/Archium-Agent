"""Approve OutlinePlan for the product-flow 大纲 confirm CTA."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ApprovalStatus
from archium.domain.outline import OutlinePlan
from archium.domain.outline_approval_record import OutlineApprovalRecord
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    OutlineApprovalRecordRepository,
    PresentationRepository,
)


@dataclass(frozen=True)
class OutlineApprovalResult:
    outline_id: UUID | None
    presentation_id: UUID | None
    approval_status: str
    approved_revision: int | None
    approved_at: datetime
    approved_by: str
    outline_hash: str
    message: str
    approval_record_id: UUID | None = None


def _outline_content_hash(outline: OutlinePlan) -> str:
    payload = {
        "title": outline.title,
        "thesis": outline.thesis,
        "audience": outline.audience,
        "purpose": outline.purpose,
        "target_slide_count": outline.target_slide_count,
        "sections": [section.model_dump(mode="json") for section in outline.sections],
        "page_intents": [intent.model_dump(mode="json") for intent in outline.page_intents],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def outline_ready_for_approval(outline: OutlinePlan) -> tuple[bool, list[str]]:
    """Structural gates for「确认大纲」— distinct from「确认任务」."""
    missing: list[str] = []
    if not outline.sections:
        missing.append("至少一个章节")
    if not outline.page_intents:
        missing.append("至少一个页面意图")
    if outline.target_slide_count < 1:
        missing.append("有效目标页数")
    if not (outline.thesis or "").strip():
        missing.append("中心任务 / 论点")
    return (not missing, missing)


class OutlineApprovalService:
    """Persist outline approval so「确认大纲」is not only a page switch."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._reviews = PresentationReviewService(session)
        self._approvals = OutlineApprovalRecordRepository(session)

    def approve_for_project(
        self,
        project_id: UUID,
        *,
        approved_by: str = "user",
        expected_revision: int | None = None,
        presentation_id: UUID | None = None,
    ) -> OutlineApprovalResult:
        presentations = self._presentations.list_by_project(project_id)
        if not presentations:
            raise WorkflowError("当前项目尚无汇报，无法确认大纲。请先生成大纲结构。")

        presentation = None
        if presentation_id is not None:
            presentation = next(
                (item for item in presentations if item.id == presentation_id),
                None,
            )
        if presentation is None:
            presentation = max(presentations, key=lambda item: item.updated_at)

        context = self._reviews.get_review_context(presentation.id)
        outline = context.outline if context is not None else None
        if outline is None:
            raise WorkflowError(
                "当前尚无 OutlinePlan，无法确认大纲。"
                "请先生成大纲结构，再统一确认。"
            )

        ready, missing = outline_ready_for_approval(outline)
        if not ready:
            raise WorkflowError(
                "大纲尚未就绪，无法确认：" + "；".join(missing) + "。"
            )

        if expected_revision is not None and outline.version != expected_revision:
            raise WorkflowError(
                f"大纲版本已变更（期望 v{expected_revision}，当前 v{outline.version}）。"
                "请刷新后重新确认。"
            )

        approved = self._reviews.approve_outline(outline.id)
        now = datetime.now(UTC)
        content_hash = _outline_content_hash(approved)
        self._approvals.supersede_active(approved.id, superseded_at=now)
        record = self._approvals.create(
            OutlineApprovalRecord(
                outline_id=approved.id,
                presentation_id=presentation.id,
                project_id=project_id,
                outline_revision=approved.version,
                outline_hash=content_hash,
                approved_by=approved_by,
                approved_at=now,
            )
        )
        return OutlineApprovalResult(
            outline_id=approved.id,
            presentation_id=presentation.id,
            approval_status=approved.approval_status.value,
            approved_revision=approved.version,
            approved_at=now,
            approved_by=approved_by,
            outline_hash=content_hash,
            approval_record_id=record.id,
            message=(
                f"大纲已确认（v{approved.version} · "
                f"{ApprovalStatus.APPROVED.value}）。"
            ),
        )

    def supersede_on_edit(self, outline_id: UUID) -> int:
        """Mark active approval rows superseded when outline content changes."""
        return self._approvals.supersede_active(outline_id)
