"""Repair individual slides based on automated review feedback."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import sanitize_slide_message
from archium.application.asset_matching_service import AssetMatchingService
from archium.application.slide_diff import slide_to_snapshot
from archium.application.slide_history_service import SlideHistoryService
from archium.application.slide_repair_policy import (
    apply_tiered_layout_repair,
    insert_split_slide,
    slide_involves_citation,
    slide_involves_numbers,
    validate_llm_repair,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import (
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
    SlideChangeSource,
    SlideRepairSource,
    SlideRepairTier,
)
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_repair import SlideRepairRecord
from archium.infrastructure.database.repositories import PresentationRepository, ReviewRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import SlideRepairDraft
from archium.logging import get_logger
from archium.prompts.slide_repair import (
    SLIDE_REPAIR_SYSTEM_PROMPT,
    build_slide_repair_user_prompt,
)

logger = get_logger(__name__, operation="slide_repair")

_MAX_KEY_POINTS = 5

_REPAIRABLE_CATEGORIES = {
    ReviewCategory.CONTENT,
    ReviewCategory.CITATION,
    ReviewCategory.LENGTH,
    ReviewCategory.CONSISTENCY,
}
_REPAIRABLE_SEVERITIES = {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH}


def has_repairable_open_issues(
    issues: list[ReviewIssue],
    settings: Settings,
) -> bool:
    """Return True when automated slide repair should run for open review issues."""
    if not settings.slide_repair_enabled:
        return False
    for issue in issues:
        if issue.status != ReviewStatus.OPEN:
            continue
        if issue.auto_fixable and issue.slide_id is not None:
            return True
        if (
            issue.slide_id is not None
            and issue.category in _REPAIRABLE_CATEGORIES
            and issue.severity in _REPAIRABLE_SEVERITIES
        ):
            return True
    return False


def split_affected_slide_ids(records: list[SlideRepairRecord]) -> set[UUID]:
    """Collect slide IDs that should be re-matched after page splits."""
    affected: set[UUID] = set()
    for record in records:
        if record.split_slide_id is None:
            continue
        affected.add(record.slide_id)
        affected.add(record.split_slide_id)
    return affected


class SlideRepairService:
    """LLM-assisted per-slide fixes for open review issues."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._reviews = ReviewRepository(session)
        self._history = SlideHistoryService(session)
        self._llm = llm
        self._settings = settings or get_settings()

    def repair_slides(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        issues: list[ReviewIssue],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        project_id: UUID | None = None,
    ) -> tuple[list[SlideSpec], int, list[SlideRepairRecord]]:
        """Repair slide-level issues and return updated slides, count, and audit records."""
        slides_by_id = {slide.id: slide for slide in slides}
        updated_slides = list(slides)
        repaired = 0
        records: list[SlideRepairRecord] = []

        rule_slides, rule_count, rule_records, pending_issues = self._apply_rule_repairs(
            presentation_id,
            updated_slides,
            slides_by_id,
            issues,
            storyline=storyline,
            brief=brief,
        )
        updated_slides = rule_slides
        slides_by_id = {slide.id: slide for slide in updated_slides}
        repaired += rule_count
        records.extend(rule_records)
        for pending in pending_issues:
            self._reviews.create(pending)

        if self._settings.slide_repair_enabled and self._llm is not None:
            open_issues = [issue for issue in issues if issue.status == ReviewStatus.OPEN]
            llm_slides, llm_count, llm_records, llm_pending = self._apply_llm_repairs(
                presentation_id,
                updated_slides,
                slides_by_id,
                open_issues,
                brief=brief,
            )
            updated_slides = llm_slides
            repaired += llm_count
            records.extend(llm_records)
            for pending in llm_pending:
                self._reviews.create(pending)

        updated_slides = self._rematch_assets_after_splits(
            updated_slides,
            records,
            project_id=project_id,
        )

        return updated_slides, repaired, records

    def _rematch_assets_after_splits(
        self,
        slides: list[SlideSpec],
        records: list[SlideRepairRecord],
        *,
        project_id: UUID | None,
    ) -> list[SlideSpec]:
        affected = split_affected_slide_ids(records)
        if not affected or project_id is None:
            return slides

        rematched, match_count = AssetMatchingService(self._session).rematch_slides_after_split(
            project_id,
            slides,
            affected,
        )
        if match_count:
            logger.info(
                "Re-matched %d visual asset(s) on %d slide(s) after page split",
                match_count,
                len(affected),
            )
        return rematched

    def _apply_rule_repairs(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        slides_by_id: dict[UUID, SlideSpec],
        issues: list[ReviewIssue],
        *,
        storyline: Storyline | None = None,
        brief: PresentationBrief | None = None,
    ) -> tuple[list[SlideSpec], int, list[SlideRepairRecord], list[ReviewIssue]]:
        """Deterministic graduated layout fixes for issues marked auto_fixable."""
        issues_by_slide: dict[UUID, list[ReviewIssue]] = {}
        for issue in issues:
            if issue.status != ReviewStatus.OPEN:
                continue
            if issue.slide_id is None or not issue.auto_fixable:
                continue
            issues_by_slide.setdefault(issue.slide_id, []).append(issue)

        if not issues_by_slide:
            return slides, 0, [], []

        repaired = 0
        records: list[SlideRepairRecord] = []
        pending_issues: list[ReviewIssue] = []
        current_slides = list(slides)

        for slide_id, slide_issues in issues_by_slide.items():
            slide = slides_by_id.get(slide_id)
            if slide is None:
                continue

            before_snapshot = slide_to_snapshot(slide)
            chapter_slide_count = sum(
                1 for item in current_slides if item.chapter_id == slide.chapter_id
            )
            outcome = apply_tiered_layout_repair(
                slide,
                storyline=storyline,
                chapter_slide_count=chapter_slide_count,
                llm=self._llm,
                settings=self._settings,
                brief=brief,
            )

            if outcome.requires_manual_confirmation:
                record = self._build_record(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    repair_source=SlideRepairSource.RULE,
                    tier=SlideRepairTier.USER_CONFIRMATION,
                    before=before_snapshot,
                    after=before_snapshot,
                    removed_items=[],
                    reason=outcome.reason or "需人工确认版面调整",
                    involves_citation=outcome.involves_citation,
                    involves_numbers=outcome.involves_numbers,
                    requires_manual_confirmation=True,
                    issue_ids=[issue.id for issue in slide_issues],
                )
                records.append(record)
                pending_issues.append(
                    self._manual_confirmation_issue(
                        presentation_id,
                        slide,
                        outcome.reason or "自动修复会丢失关键信息，需人工确认",
                    )
                )
                logger.info(
                    "Deferred rule repair for slide %s — manual confirmation required",
                    slide_id,
                )
                continue

            if not outcome.changed:
                continue

            saved = self._presentations.save_slide(outcome.slide)
            slides_by_id[slide_id] = saved
            current_slides = [
                saved if item.id == slide_id else slides_by_id.get(item.id, item)
                for item in current_slides
            ]

            split_slide = outcome.split_slide
            if split_slide is not None:
                for item in current_slides:
                    if item.id != slide_id and item.order >= split_slide.order:
                        bumped = item.model_copy(
                            update={
                                "order": item.order + 1,
                                "logical_key": build_slide_logical_key(
                                    item.chapter_id,
                                    item.order + 1,
                                ),
                            }
                        )
                        slides_by_id[bumped.id] = self._presentations.save_slide(bumped)
                split_saved = self._presentations.save_slide(split_slide)
                slides_by_id[split_saved.id] = split_saved
                current_slides = insert_split_slide(current_slides, split_saved)
                current_slides = [
                    slides_by_id.get(item.id, item) for item in current_slides
                ]

            after_snapshot = slide_to_snapshot(slides_by_id[slide_id])
            record = self._build_record(
                presentation_id=presentation_id,
                slide_id=slide_id,
                repair_source=SlideRepairSource.RULE,
                tier=outcome.tier or SlideRepairTier.SHORTEN_REPETITION,
                before=before_snapshot,
                after=after_snapshot,
                removed_items=outcome.removed_items,
                reason=outcome.reason,
                involves_citation=outcome.involves_citation,
                involves_numbers=outcome.involves_numbers,
                requires_manual_confirmation=False,
                split_slide_id=(
                    split_slide.id if split_slide is not None else None
                ),
                issue_ids=[issue.id for issue in slide_issues],
            )
            records.append(record)

            self._history.record_snapshot(
                slides_by_id[slide_id],
                SlideChangeSource.AUTO_REPAIR,
                note=record.reason,
            )
            if split_slide is not None and split_slide.id in slides_by_id:
                self._history.record_snapshot(
                    slides_by_id[split_slide.id],
                    SlideChangeSource.AUTO_REPAIR,
                    note="由版面拆分自动创建",
                )

            for issue in slide_issues:
                issue.resolve()
                self._reviews.update(issue)
            repaired += 1
            logger.info(
                "Rule-repaired slide %s for presentation %s (tier=%s)",
                slide_id,
                presentation_id,
                outcome.tier.value if outcome.tier else "unknown",
            )

        return current_slides, repaired, records, pending_issues

    def _apply_llm_repairs(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        slides_by_id: dict[UUID, SlideSpec],
        issues: list[ReviewIssue],
        *,
        brief: PresentationBrief | None,
    ) -> tuple[list[SlideSpec], int, list[SlideRepairRecord], list[ReviewIssue]]:
        issues_by_slide: dict[UUID, list[ReviewIssue]] = {}
        for issue in issues:
            if issue.slide_id is None:
                continue
            if issue.category not in _REPAIRABLE_CATEGORIES:
                continue
            if issue.severity not in _REPAIRABLE_SEVERITIES:
                continue
            issues_by_slide.setdefault(issue.slide_id, []).append(issue)

        if not issues_by_slide:
            return slides, 0, [], []

        brief_summary = (
            f"标题: {brief.title}\n核心信息: {brief.core_message}"
            if brief is not None
            else "无 Brief"
        )
        repaired = 0
        records: list[SlideRepairRecord] = []
        pending_issues: list[ReviewIssue] = []
        current_slides = list(slides)

        llm = self._llm
        if llm is None:
            return slides, 0, [], []

        for slide_id, slide_issues in issues_by_slide.items():
            slide = slides_by_id.get(slide_id)
            if slide is None:
                continue

            before_snapshot = slide_to_snapshot(slide)
            try:
                draft = llm.generate_structured(
                    LLMRequest(
                        system_prompt=SLIDE_REPAIR_SYSTEM_PROMPT,
                        user_prompt=build_slide_repair_user_prompt(
                            slide_summary=_slide_summary(slide),
                            issue_summary=_issue_summary(slide_issues),
                            brief_summary=brief_summary,
                        ),
                        model=self._settings.llm_model,
                        temperature=0.3,
                        json_mode=True,
                    ),
                    SlideRepairDraft,
                )
            except Exception as exc:
                logger.warning("Slide repair failed for slide %s: %s", slide_id, exc)
                continue

            candidate_message = sanitize_slide_message(draft.message)
            candidate_points = list(draft.key_points[:_MAX_KEY_POINTS])
            valid, reject_reason = validate_llm_repair(
                slide,
                message=candidate_message,
                key_points=candidate_points,
            )
            if not valid:
                records.append(
                    self._build_record(
                        presentation_id=presentation_id,
                        slide_id=slide_id,
                        repair_source=SlideRepairSource.LLM,
                        tier=SlideRepairTier.USER_CONFIRMATION,
                        before=before_snapshot,
                        after=before_snapshot,
                        removed_items=[],
                        reason=reject_reason,
                        involves_citation=slide_involves_citation(slide),
                        involves_numbers=slide_involves_numbers(slide),
                        requires_manual_confirmation=True,
                        issue_ids=[issue.id for issue in slide_issues],
                    )
                )
                pending_issues.append(
                    self._manual_confirmation_issue(presentation_id, slide, reject_reason)
                )
                continue

            slide.title = draft.title.strip() or slide.title
            slide.message = candidate_message
            slide.key_points = candidate_points
            saved = self._presentations.save_slide(slide)
            slides_by_id[slide_id] = saved
            current_slides = [
                saved if item.id == slide_id else slides_by_id.get(item.id, item)
                for item in current_slides
            ]

            after_snapshot = slide_to_snapshot(saved)
            before_points = _snapshot_key_points(before_snapshot)
            removed = [
                f"要点: {point}" for point in before_points if point not in candidate_points
            ]
            record = self._build_record(
                presentation_id=presentation_id,
                slide_id=slide_id,
                repair_source=SlideRepairSource.LLM,
                tier=SlideRepairTier.REWRITE,
                before=before_snapshot,
                after=after_snapshot,
                removed_items=removed,
                reason="LLM 改写以响应审核反馈",
                involves_citation=bool(saved.source_citations),
                involves_numbers=slide_involves_numbers(saved),
                requires_manual_confirmation=False,
                issue_ids=[issue.id for issue in slide_issues],
            )
            records.append(record)
            self._history.record_snapshot(
                saved,
                SlideChangeSource.AUTO_REPAIR,
                note=record.reason,
            )

            for issue in slide_issues:
                issue.resolve()
                self._reviews.update(issue)
            repaired += 1

        logger.info("LLM-repaired %d slide(s) for presentation %s", repaired, presentation_id)
        return current_slides, repaired, records, pending_issues

    def _build_record(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        repair_source: SlideRepairSource,
        tier: SlideRepairTier,
        before: dict[str, object],
        after: dict[str, object],
        removed_items: list[str],
        reason: str,
        involves_citation: bool,
        involves_numbers: bool,
        requires_manual_confirmation: bool,
        issue_ids: list[UUID],
        split_slide_id: UUID | None = None,
    ) -> SlideRepairRecord:
        return SlideRepairRecord(
            presentation_id=presentation_id,
            slide_id=slide_id,
            repair_source=repair_source,
            tier=tier,
            before_message=str(before.get("message", "")),
            after_message=str(after.get("message", "")),
            before_key_points=_snapshot_key_points(before),
            after_key_points=_snapshot_key_points(after),
            removed_items=removed_items,
            reason=reason,
            involves_citation=involves_citation,
            involves_numbers=involves_numbers,
            requires_manual_confirmation=requires_manual_confirmation,
            split_slide_id=split_slide_id,
            issue_ids=issue_ids,
        )

    def _manual_confirmation_issue(
        self,
        presentation_id: UUID,
        slide: SlideSpec,
        reason: str,
    ) -> ReviewIssue:
        return ReviewIssue(
            presentation_id=presentation_id,
            slide_id=slide.id,
            reviewer_layer=ReviewLayer.LAYOUT,
            category=ReviewCategory.LENGTH,
            severity=ReviewSeverity.HIGH,
            rule_code=ReviewRuleCode.LAYOUT_MANUAL_LAYOUT_CONFIRMATION,
            title="需人工确认版面调整",
            description=(
                f"第 {slide.order + 1} 页「{slide.title}」无法在不丢失关键信息的前提下自动压缩。"
                f"原因：{reason}"
            ),
            suggestion="请人工拆分页面、改写表述或确认可删除的内容。",
            auto_fixable=False,
        )


def _snapshot_key_points(snapshot: dict[str, object]) -> list[str]:
    raw = snapshot.get("key_points")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _slide_summary(slide: SlideSpec) -> str:
    points = "\n".join(f"- {point}" for point in slide.key_points) or "（无要点）"
    return (
        f"第 {slide.order + 1} 页\n"
        f"标题: {slide.title}\n"
        f"核心信息: {slide.message}\n"
        f"要点:\n{points}"
    )


def _issue_summary(issues: list[ReviewIssue]) -> str:
    return "\n".join(
        f"- [{issue.severity.value}] {issue.title}: {issue.description}"
        + (f"（建议：{issue.suggestion}）" if issue.suggestion else "")
        for issue in issues
    )
