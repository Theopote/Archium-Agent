"""Apply SlideSpec content adaptation actions for Presentation Studio."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.slide_history_service import SlideHistoryService
from archium.application.slide_repair_policy import (
    _MAX_BULLET_LENGTH,
    _MAX_MESSAGE_LENGTH,
    shorten_repetitive_expression,
    smart_shorten_text,
)
from archium.application.slide_split_planner import build_split_plan
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.content_adaptation import (
    ContentAdaptationAction,
    ContentAdaptationSuggestion,
    suggest_content_adaptations,
)
from archium.domain.enums import RevisionEntityType, RevisionSource, SlideStatus, SlideType
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_split import SlideSplitPlan
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.validation import LayoutValidationReport
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


@dataclass(frozen=True)
class ContentAdaptationResult:
    slide: SlideSpec
    action: ContentAdaptationAction
    created_slides: list[SlideSpec] = field(default_factory=list)
    split_plan: SlideSplitPlan | None = None
    replanned_slide_ids: list[UUID] = field(default_factory=list)
    message: str = ""


class ContentAdaptationService:
    """Shorten, bulletize, split, or promote slide content with revision tracking."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._history = SlideHistoryService(session)
        self._visual_edits = VisualEditService(session)

    def analyze(
        self,
        slide_id: UUID,
        *,
        layout_report: LayoutValidationReport | None = None,
    ) -> list[ContentAdaptationSuggestion]:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面 {slide_id} 不存在")
        return suggest_content_adaptations(slide, layout_report=layout_report)

    def apply(
        self,
        slide_id: UUID,
        action: ContentAdaptationAction | str,
        *,
        replan_visual: bool = True,
    ) -> ContentAdaptationResult:
        resolved = (
            action
            if isinstance(action, ContentAdaptationAction)
            else ContentAdaptationAction(str(action))
        )
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面 {slide_id} 不存在")

        self._history.record_snapshot(
            slide,
            RevisionSource.MANUAL_EDIT,
            note=f"content:{resolved.value}",
        )

        if resolved == ContentAdaptationAction.SHORTEN:
            result = self._apply_shorten(slide)
        elif resolved == ContentAdaptationAction.CONVERT_TO_BULLETS:
            result = self._apply_convert_to_bullets(slide)
        elif resolved == ContentAdaptationAction.SPLIT_SLIDE:
            result = self._apply_split(slide)
        elif resolved == ContentAdaptationAction.PROMOTE_KEY_MESSAGE:
            result = self._apply_promote_key_message(slide)
        else:
            raise WorkflowError(f"Unsupported content adaptation: {resolved}")

        if replan_visual:
            result = self._replan_affected_slides(result)

        return result

    def restore_at_revision(
        self,
        slide_id: UUID,
        revision_id: UUID,
        *,
        replan_visual: bool = True,
    ) -> ContentAdaptationResult:
        restored = self._history.restore_at_revision(revision_id)
        if restored.id != slide_id:
            raise WorkflowError("修订版本与当前页面不匹配。")
        result = ContentAdaptationResult(
            slide=restored,
            action=ContentAdaptationAction.SHORTEN,
            message="已恢复到所选内容版本。",
        )
        if replan_visual:
            result = self._replan_affected_slides(result)
        return result

    def list_content_revisions(self, slide_id: UUID) -> list[EntityRevision]:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            return []
        return [
            revision
            for revision in self._history.list_revisions(slide_id)
            if revision.entity_type == RevisionEntityType.SLIDE
            and (revision.note or "").startswith("content:")
        ]

    def restore_previous(
        self,
        slide_id: UUID,
        *,
        replan_visual: bool = True,
    ) -> ContentAdaptationResult:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面 {slide_id} 不存在")
        restored = self._history.restore_previous(slide_id)
        result = ContentAdaptationResult(
            slide=restored,
            action=ContentAdaptationAction.SHORTEN,
            message="已撤销上一步内容修改。",
        )
        if replan_visual:
            result = self._replan_affected_slides(result)
        return result

    def _apply_shorten(self, slide: SlideSpec) -> ContentAdaptationResult:
        updated = deepcopy(slide)
        message = shorten_repetitive_expression(updated.message)
        message, applied, reason = smart_shorten_text(message, _MAX_MESSAGE_LENGTH)
        if not applied and len(updated.message) > _MAX_MESSAGE_LENGTH:
            raise WorkflowError(reason or "无法在不丢失关键信息的前提下缩短核心信息。")

        points: list[str] = []
        for point in updated.key_points:
            shortened = shorten_repetitive_expression(point)
            new_point, point_applied, point_reason = smart_shorten_text(
                shortened,
                _MAX_BULLET_LENGTH,
            )
            if not point_applied and len(point) > _MAX_BULLET_LENGTH:
                raise WorkflowError(point_reason or "无法缩短要点。")
            points.append(new_point)

        updated.message = message
        updated.key_points = points
        updated.version += 1
        saved = self._presentations.save_slide(updated)
        return ContentAdaptationResult(
            slide=saved,
            action=ContentAdaptationAction.SHORTEN,
            message="已缩短页面文字。",
        )

    def _apply_convert_to_bullets(self, slide: SlideSpec) -> ContentAdaptationResult:
        updated = deepcopy(slide)
        if updated.key_points:
            summary, applied, reason = smart_shorten_text(updated.message, 72)
            if not applied:
                summary = shorten_repetitive_expression(updated.message)
                if len(summary) > 80:
                    summary = summary[:79].rstrip() + "…"
            updated.message = summary
        else:
            parts = _split_into_bullet_candidates(updated.message)
            if len(parts) < 2:
                raise WorkflowError("当前核心信息不足以拆成多条要点。")
            updated.key_points = parts[:5]
            lead, applied, _reason = smart_shorten_text(parts[0], _MAX_MESSAGE_LENGTH)
            updated.message = lead if applied else parts[0][: min(len(parts[0]), 80)]

        updated.version += 1
        saved = self._presentations.save_slide(updated)
        return ContentAdaptationResult(
            slide=saved,
            action=ContentAdaptationAction.CONVERT_TO_BULLETS,
            message="已将内容整理为要点列表。",
        )

    def _apply_promote_key_message(self, slide: SlideSpec) -> ContentAdaptationResult:
        updated = deepcopy(slide)
        promoted = updated.message.strip()
        if updated.key_points:
            promoted = max(updated.key_points, key=len).strip()
            updated.key_points = [point for point in updated.key_points if point.strip() != promoted]

        promoted, applied, reason = smart_shorten_text(promoted, _MAX_MESSAGE_LENGTH)
        if not applied and len(promoted) > _MAX_MESSAGE_LENGTH:
            raise WorkflowError(reason or "无法突出核心信息而不丢失关键内容。")

        updated.message = promoted
        updated.version += 1
        saved = self._presentations.save_slide(updated)
        return ContentAdaptationResult(
            slide=saved,
            action=ContentAdaptationAction.PROMOTE_KEY_MESSAGE,
            message="已将核心信息提升为页面主结论。",
        )

    def _apply_split(self, slide: SlideSpec) -> ContentAdaptationResult:
        if len(slide.key_points) < 2:
            raise WorkflowError("至少需要 2 条要点才能拆分页面。")

        updated_source = deepcopy(slide)
        mid = max(1, len(updated_source.key_points) // 2)
        moved = updated_source.key_points[mid:]
        updated_source.key_points = updated_source.key_points[:mid]
        updated_source.version += 1

        plan = build_split_plan(
            slide,
            updated_source,
            moved,
            "Studio 内容拆分",
        )
        if plan.requires_human_approval:
            detail = "；".join(plan.validation_issues) or "拆页方案需人工确认"
            raise WorkflowError(detail)

        saved_source = self._presentations.save_slide(plan.updated_source)
        continuation = plan.primary_continuation
        for item in self._presentations.list_slides(slide.presentation_id):
            if item.id != slide.id and item.order >= continuation.order:
                bumped = item.model_copy(
                    update={
                        "order": item.order + 1,
                        "logical_key": build_slide_logical_key(
                            item.chapter_id,
                            item.order + 1,
                        ),
                    }
                )
                self._presentations.save_slide(bumped)

        saved_continuation = self._presentations.save_slide(continuation)
        self._history.record_snapshot(
            saved_continuation,
            RevisionSource.MANUAL_EDIT,
            note="content:split_slide_created",
        )

        return ContentAdaptationResult(
            slide=saved_source,
            action=ContentAdaptationAction.SPLIT_SLIDE,
            created_slides=[saved_continuation],
            split_plan=plan,
            message=f"已拆分为 2 页：P{saved_source.order + 1} 与 P{saved_continuation.order + 1}。",
        )

    def _replan_affected_slides(self, result: ContentAdaptationResult) -> ContentAdaptationResult:
        replanned: list[UUID] = []
        slide_ids = [result.slide.id, *[slide.id for slide in result.created_slides]]
        preset = _visual_preset_for_action(result.action)
        for slide_id in slide_ids:
            try:
                if preset is not None:
                    self._visual_edits.apply_intent(slide_id, preset)
                else:
                    self._visual_edits.apply_intent(slide_id, VisualEditIntent.REDUCE_TEXT)
                replanned.append(slide_id)
            except WorkflowError:
                continue
        return ContentAdaptationResult(
            slide=result.slide,
            action=result.action,
            created_slides=list(result.created_slides),
            split_plan=result.split_plan,
            replanned_slide_ids=replanned,
            message=result.message,
        )


def _split_into_bullet_candidates(text: str) -> list[str]:
    stripped = text.strip()
    parts = [part.strip() for part in re.split(r"[。；;]\s*", stripped) if part.strip()]
    if len(parts) >= 2:
        return parts
    comma_parts = [part.strip() for part in re.split(r"[，,、]\s*", stripped) if len(part.strip()) >= 4]
    return comma_parts if len(comma_parts) >= 2 else parts


def _visual_preset_for_action(action: ContentAdaptationAction) -> VisualEditIntent | None:
    if action == ContentAdaptationAction.SHORTEN:
        return VisualEditIntent.REDUCE_TEXT
    if action == ContentAdaptationAction.CONVERT_TO_BULLETS:
        return VisualEditIntent.REDUCE_TEXT
    if action == ContentAdaptationAction.PROMOTE_KEY_MESSAGE:
        return VisualEditIntent.ENLARGE_HERO
    return None
