"""Structural validation for slide split plans before execution."""

from __future__ import annotations

import re

from archium.application.slide_repair_policy import contains_protected_signal
from archium.domain.presentation import Storyline
from archium.domain.slide import SlideSpec
from archium.domain.slide_split import GENERIC_CONTINUATION_MESSAGE, SlideSplitPlan, citation_key

_NUMERIC_EVIDENCE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|张|床|层|期|万|亿|吨|人次|辆|公顷|平方米|m²|㎡)"
    r"|\d{2,}(?:\.\d+)?"
)


def validate_split_plan(
    plan: SlideSplitPlan,
    *,
    original: SlideSpec | None = None,
    storyline: Storyline | None = None,
    chapter_slide_count: int | None = None,
) -> SlideSplitPlan:
    """Validate narrative structure; set ``requires_human_approval`` when checks fail."""
    issues: list[str] = []
    source = plan.updated_source
    continuations = plan.continuation_slides

    if source.id != plan.source_slide_id:
        issues.append("拆分计划的首页 ID 与 source_slide_id 不一致")

    for continuation in continuations:
        if not continuation.message.strip():
            issues.append(f"续页「{continuation.title}」缺少独立核心信息")
        elif (
            len(continuation.key_points) > 1
            and continuation.message == GENERIC_CONTINUATION_MESSAGE
        ):
            issues.append("续页使用占位核心信息，无法独立传达结论")

        if continuation.source_citations and not _content_needs_citations(continuation):
            issues.append("续页绑定了引用但内容无需证据支撑，可能导致结论与证据分离")

    if original is not None:
        moved_points = _moved_points(original, source, continuations)
        if original.source_citations and moved_points:
            issues.extend(
                _citation_separation_issues(
                    original,
                    source,
                    continuations,
                    plan.citation_mapping,
                    moved_points,
                )
            )

        if original.visual_requirements and plan.asset_mapping:
            unmapped = [
                index
                for index in range(len(original.visual_requirements))
                if index not in plan.asset_mapping
            ]
            if unmapped:
                issues.append("部分视觉素材未完成拆页映射，仍绑定旧页面")

        combined_points = source.key_points + [
            point for slide in continuations for point in slide.key_points
        ]
        if len(combined_points) != len(original.key_points):
            issues.append("拆页后要点总数与原文不一致，可能丢失或重复内容")

    if storyline is not None and original is not None:
        chapter = next(
            (item for item in storyline.chapters if item.id == original.chapter_id),
            None,
        )
        if chapter is not None and chapter_slide_count is not None:
            projected = chapter_slide_count + len(continuations)
            if projected > chapter.estimated_slide_count:
                issues.append(
                    f"拆页后章节「{chapter.title}」页数 ({projected}) "
                    f"超出 Storyline 预算 ({chapter.estimated_slide_count})"
                )

    for continuation in continuations:
        if continuation.title.endswith("（续）") and len(continuation.key_points) >= 3:
            issues.append(f"续页「{continuation.title}」标题缺少独立上下文")

    requires_human_approval = len(issues) > 0
    return plan.model_copy(
        update={
            "requires_human_approval": requires_human_approval,
            "validation_issues": issues,
        }
    )


def _content_needs_citations(slide: SlideSpec) -> bool:
    combined = " ".join([slide.message, *slide.key_points])
    return contains_protected_signal(combined)


def _citation_separation_issues(
    original: SlideSpec,
    source: SlideSpec,
    continuations: list[SlideSpec],
    citation_mapping: dict[str, UUID],
    moved_points: list[str],
) -> list[str]:
    """Flag when citations and their supporting content land on different pages."""
    if not original.source_citations:
        return []

    issues: list[str] = []
    continuation_ids = {slide.id for slide in continuations}
    moved_text = " ".join(moved_points)

    for index, citation in enumerate(original.source_citations):
        quote = citation.quote or ""
        if not quote:
            continue
        evidence_moved = quote in moved_text or any(quote in point for point in moved_points)
        if not evidence_moved:
            continue

        key = citation_key(citation.document_id, citation.chunk_id, index)
        target_id = citation_mapping.get(key)
        on_continuation = target_id in continuation_ids if target_id is not None else any(
            _citation_on_slide(citation, slide) for slide in continuations
        )
        if not on_continuation:
            issues.append("证据性要点已移至续页，但引用仍留在原页")
            return issues

    continuation_has_citations = any(slide.source_citations for slide in continuations)
    for point in moved_points:
        if not _point_has_numeric_evidence(point):
            continue
        if _point_supported_by_citations(
            point,
            [citation for slide in continuations for citation in slide.source_citations],
        ):
            continue
        if _point_supported_by_citations(point, source.source_citations):
            issues.append("证据性要点已移至续页，但引用仍留在原页")
            return issues
        if original.source_citations and not continuation_has_citations:
            issues.append("续页含证据性要点但未分配引用")
            return issues

    return issues


def _point_has_numeric_evidence(point: str) -> bool:
    return bool(_NUMERIC_EVIDENCE_RE.search(point))


def _point_supported_by_citations(point: str, citations: list) -> bool:
    for citation in citations:
        quote = citation.quote or ""
        if quote and (quote in point or point in quote):
            return True
    return False


def _citation_on_slide(citation, slide: SlideSpec) -> bool:
    for item in slide.source_citations:
        if citation.chunk_id is not None and item.chunk_id == citation.chunk_id:
            return True
        if item.document_id == citation.document_id and item.quote == citation.quote:
            return True
    return False


def _moved_points(
    _original: SlideSpec,
    _source: SlideSpec,
    continuations: list[SlideSpec],
) -> list[str]:
    return [point for slide in continuations for point in slide.key_points]
