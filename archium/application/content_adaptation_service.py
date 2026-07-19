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
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_split import SlideSplitPlan
from archium.domain.studio_errors import StudioAssetReferenceError
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.element_lock import ElementLockedError
from archium.domain.visual.validation import LayoutValidationReport
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


@dataclass(frozen=True)
class AdaptationWarning:
    """记录内容调整过程中的警告信息"""
    action: ContentAdaptationAction
    message: str
    severity: str  # "info" | "warning" | "error"


@dataclass(frozen=True)
class ContentAdaptationResult:
    slide: SlideSpec
    action: ContentAdaptationAction
    created_slides: list[SlideSpec] = field(default_factory=list)
    split_plan: SlideSplitPlan | None = None
    replanned_slide_ids: list[UUID] = field(default_factory=list)
    message: str = ""
    warnings: list[AdaptationWarning] = field(default_factory=list)


class ContentAdaptationService:
    """Shorten, bulletize, split, or promote slide content with revision tracking."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._history = SlideHistoryService(session)
        self._visual_edits = VisualEditService(session)
        self._warnings: list[AdaptationWarning] = []

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
        self._warnings = []  # 重置警告列表
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

        # 将警告附加到结果中
        return ContentAdaptationResult(
            slide=result.slide,
            action=result.action,
            created_slides=result.created_slides,
            split_plan=result.split_plan,
            replanned_slide_ids=result.replanned_slide_ids,
            message=result.message,
            warnings=self._warnings,
        )

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
                    # 使用安全截断，而非硬截断
                    summary = self._safe_truncate(summary, max_length=80)
                    self._add_warning(
                        ContentAdaptationAction.CONVERT_TO_BULLETS,
                        f"摘要已自动压缩至 80 字符，请检查语义完整性。原因：{reason or '无法安全缩短'}",
                        severity="warning"
                    )
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
            # 使用智能评分选择最重要的要点，而非最长的
            promoted = self._select_most_important_point(
                updated.key_points,
                title=updated.title,
                message=updated.message
            )
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
            except (ElementLockedError, StudioAssetReferenceError):
                raise
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

    def _add_warning(
        self,
        action: ContentAdaptationAction,
        message: str,
        severity: str = "warning"
    ) -> None:
        """添加警告信息"""
        self._warnings.append(AdaptationWarning(
            action=action,
            message=message,
            severity=severity
        ))

    def _safe_truncate(self, text: str, max_length: int) -> str:
        """
        安全截断文本：优先在句子边界、逗号、空格处截断。
        避免破坏数值单位、专有名词、否定关系等语义结构。
        """
        if len(text) <= max_length:
            return text

        # 尝试在不同的分隔符处截断，优先级从高到低
        delimiters = [
            ("。", 1),  # 句号
            ("；", 1),  # 分号
            ("，", 1),  # 逗号
            ("、", 1),  # 顿号
            (" ", 1),   # 空格
        ]

        for delimiter, offset in delimiters:
            # 在 max_length 之前查找最后一个分隔符
            idx = text.rfind(delimiter, 0, max_length - 1)
            # 至少保留 70% 的内容，避免过度截断
            if idx > max_length * 0.7:
                return text[:idx + offset].rstrip() + "…"

        # 如果找不到合适的分隔符，尝试在词边界截断
        # 检查是否会截断数字单位（如 "15%", "100万"）
        truncate_pos = max_length - 1

        # 向前查找安全的截断点：不在数字或字母中间
        while truncate_pos > max_length * 0.7:
            char = text[truncate_pos] if truncate_pos < len(text) else ""
            prev_char = text[truncate_pos - 1] if truncate_pos > 0 else ""

            # 如果当前字符是数字、字母、百分号、货币符号，继续向前
            if char.isalnum() or char in "%$€¥万亿":
                truncate_pos -= 1
            # 如果前一个字符是数字，当前是单位，继续向前
            elif prev_char.isdigit() and char in "个件台套份次":
                truncate_pos -= 1
            else:
                break

        return text[:truncate_pos].rstrip() + "…"

    def _select_most_important_point(
        self,
        points: list[str],
        title: str = "",
        message: str = ""
    ) -> str:
        """
        基于多维度评分选择最重要的要点。
        不再简单使用 max(key=len)，而是考虑：
        1. 与标题的相关性
        2. 位置权重（首尾要点通常更重要）
        3. 结论性关键词
        4. 数据密度
        5. 长度（作为次要因素）
        """
        if not points:
            return ""

        if len(points) == 1:
            return points[0].strip()

        scored_points: list[tuple[float, str]] = []

        for idx, point in enumerate(points):
            score = self._calculate_importance_score(
                point=point,
                title=title,
                message=message,
                position=idx,
                total_count=len(points)
            )
            scored_points.append((score, point))

        # 选择得分最高的要点
        best_point = max(scored_points, key=lambda x: x[0])[1]
        return best_point.strip()

    def _calculate_importance_score(
        self,
        point: str,
        title: str,
        message: str,
        position: int,
        total_count: int
    ) -> float:
        """
        计算要点的重要性得分。

        评分维度：
        - 标题相关性：与标题关键词重叠越多越重要
        - 位置权重：第一个和最后一个要点通常更重要
        - 结论性关键词：包含总结性词汇（高权重）
        - 数据密度：包含具体数据和百分比（高权重）
        - 长度因素：强烈惩罚过长文本（避免选择冗长细节）
        """
        score = 0.0
        point_lower = point.lower()

        # 1. 标题相关性（权重：1.5，降低以避免过度匹配技术词汇）
        if title:
            title_words = set(self._tokenize_chinese(title.lower()))
            point_words = set(self._tokenize_chinese(point_lower))
            overlap = len(title_words & point_words)
            score += overlap * 1.5

        # 2. 位置权重（权重：2.0/3.0，降低以平衡其他因素）
        if position == 0:
            score += 2.0  # 首要点
        elif position == total_count - 1:
            score += 3.0  # 末要点（通常是结论）

        # 3. 结论性关键词（权重：8.0，提高以突出重要指标）
        conclusion_keywords = [
            "总结", "结论", "因此", "所以", "综上", "总之",
            "核心", "关键", "重点", "最", "首要",
            "ROI", "收益", "价值", "优势", "回本",
            "建议", "应该", "必须", "立即"
        ]
        for keyword in conclusion_keywords:
            if keyword in point:
                score += 8.0
                break

        # 4. 数据密度（权重：5.0，提高以重视量化指标）
        if re.search(r'\d+%', point):  # 百分比
            score += 5.0
        if re.search(r'\d+倍', point):  # 倍数
            score += 5.0
        if re.search(r'增长|降低|提升|减少|提高', point):  # 变化动词
            if re.search(r'\d+', point):  # 有数字支撑
                score += 3.0

        # 5. 长度因素（强烈惩罚过长文本）
        # 理想长度：8-35字符
        ideal_min = 8
        ideal_max = 35
        point_len = len(point)

        if ideal_min <= point_len <= ideal_max:
            score += 2.0  # 理想长度奖励
        elif point_len < ideal_min:
            # 过短扣分（但不会太严重）
            score -= (ideal_min - point_len) / ideal_min * 3.0
        else:
            # 过长严重扣分（避免选择冗长细节）
            penalty = (point_len - ideal_max) / 10.0
            score -= min(penalty, 8.0)  # 最多扣8分

        return score

    def _tokenize_chinese(self, text: str) -> list[str]:
        """
        简单的中文分词：提取2字以上的连续中文字符作为词。
        用于计算标题和要点的关键词重叠。
        """
        # 提取所有中文字符序列
        chinese_pattern = re.compile(r'[一-鿿]+')
        matches = chinese_pattern.findall(text)

        # 对于长词，也提取2-3字的子串
        tokens = []
        for match in matches:
            if len(match) >= 2:
                tokens.append(match)
                # 提取2字词
                for i in range(len(match) - 1):
                    tokens.append(match[i:i+2])

        return tokens


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
