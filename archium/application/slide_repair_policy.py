"""Graduated slide layout repair policy with protected-content guards."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field

from archium.domain.enums import SlideRepairTier
from archium.domain.presentation import Storyline
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_split import SlideSplitPlan

_MAX_KEY_POINTS = 5
_MAX_MESSAGE_LENGTH = 120
_MAX_BULLET_LENGTH = 40
_TEXT_DENSITY_THRESHOLD = 280

_NUMBER_WITH_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:公顷|平方米|m²|㎡|km|m|%|张|床|层|期|万|亿|吨|人次|辆|分钟|小时|年|月|日)"
)
_MEANINGFUL_NUMBER_RE = re.compile(r"\d{2,}(?:\.\d+)?")
_DECISION_RE = re.compile(r"(?:确认|决策|必须|要求|待确认|需决策|需确认)")
_RISK_RE = re.compile(r"(?:风险|隐患|拥堵|影响运营|安全事故|混行|延误|不足|超标)")
_PROJECT_RE = re.compile(r"(?:医院|院区|大楼|项目|门诊|住院|急诊|落客|车行|人行)")

_FILLER_PHRASES = ("相关", "有关", "方面", "整体", "进一步", "目前", "现有")


@dataclass
class LayoutRepairOutcome:
    """Result of applying tiered layout repair to one slide."""

    slide: SlideSpec
    changed: bool = False
    tier: SlideRepairTier | None = None
    removed_items: list[str] = field(default_factory=list)
    reason: str = ""
    split_slide: SlideSpec | None = None
    split_plan: SlideSplitPlan | None = None
    requires_manual_confirmation: bool = False
    involves_citation: bool = False
    involves_numbers: bool = False


def estimate_text_load(slide: SlideSpec) -> int:
    load = len(slide.message.strip())
    load += sum(len(point.strip()) for point in slide.key_points)
    load += len(slide.title.strip()) // 2
    return load


def extract_protected_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    tokens.update(match.group(0).strip() for match in _NUMBER_WITH_UNIT_RE.finditer(text))
    tokens.update(match.group(0).strip() for match in _MEANINGFUL_NUMBER_RE.finditer(text))
    for pattern in (_DECISION_RE, _RISK_RE, _PROJECT_RE):
        tokens.update(match.group(0).strip() for match in pattern.finditer(text))
    return {token for token in tokens if token}


def contains_protected_signal(text: str) -> bool:
    return bool(extract_protected_tokens(text.strip()))


def loses_protected_content(before: str, after: str) -> bool:
    before_tokens = extract_protected_tokens(before)
    if not before_tokens:
        return False
    after_tokens = extract_protected_tokens(after)
    return not before_tokens.issubset(after_tokens)


def slide_involves_citation(slide: SlideSpec) -> bool:
    return bool(slide.source_citations)


def slide_involves_numbers(slide: SlideSpec) -> bool:
    combined = " ".join([slide.message, *slide.key_points])
    return bool(_NUMBER_WITH_UNIT_RE.search(combined) or _MEANINGFUL_NUMBER_RE.search(combined))


def shorten_repetitive_expression(text: str) -> str:
    """Tier 1: collapse duplicated phrases without removing facts."""
    result = text.strip()
    result = _collapse_exact_repetitions(result)
    result = re.sub(r"(\S{2,8})\1+", r"\1", result)
    result = re.sub(r"[，,、；;]{2,}", "，", result)
    result = re.sub(r"。{2,}", "。", result)
    result = re.sub(r"\s{2,}", " ", result)
    for phrase in _FILLER_PHRASES:
        duplicate = phrase * 2
        while duplicate in result:
            result = result.replace(duplicate, phrase)
    return result.strip()


def _collapse_exact_repetitions(text: str) -> str:
    """If the entire string is repeated blocks, keep one copy."""
    stripped = text.strip()
    if len(stripped) < 6:
        return stripped
    for size in range(len(stripped) // 2, 2, -1):
        chunk = stripped[:size]
        if not chunk:
            continue
        if len(stripped) % len(chunk) == 0 and chunk * (len(stripped) // len(chunk)) == stripped:
            return chunk
    return stripped


def _truncate_text(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 1].rstrip() + "…"


def smart_shorten_text(text: str, limit: int) -> tuple[str, bool, str]:
    """Tier 2: rewrite/shorten text; return (result, applied, reason)."""
    original = text.strip()
    if len(original) <= limit:
        return original, True, "已在长度限制内"

    tier1 = shorten_repetitive_expression(original)
    if len(tier1) <= limit and not loses_protected_content(original, tier1):
        return tier1, True, "缩短重复表达"

    candidate = tier1
    for filler in _FILLER_PHRASES:
        if filler not in candidate:
            continue
        reduced = candidate.replace(filler, "")
        reduced = re.sub(r"\s{2,}", " ", reduced).strip()
        if len(reduced) <= limit and not loses_protected_content(original, reduced):
            return reduced, True, "改写并去除冗余修饰"

    if contains_protected_signal(original):
        return original, False, "包含数字/单位/决策/风险/项目条件，无法自动截断"

    truncated = _truncate_text(tier1, limit)
    if loses_protected_content(original, truncated):
        return original, False, "截断会丢失受保护信息"
    return truncated, True, "在安全前提下压缩表述"


def _removable_key_point_indices(points: list[str]) -> list[int]:
    return [index for index, point in enumerate(points) if not contains_protected_signal(point)]


def apply_tiered_layout_repair(
    slide: SlideSpec,
    *,
    storyline: Storyline | None = None,
    chapter_slide_count: int | None = None,
) -> LayoutRepairOutcome:
    """Apply tier 1→3 layout repair; defer to tier 4 when facts would be lost."""
    working = deepcopy(slide)
    before_message = working.message
    before_points = list(working.key_points)
    outcome = LayoutRepairOutcome(
        slide=working,
        involves_citation=slide_involves_citation(working),
        involves_numbers=slide_involves_numbers(working),
    )

    tier_used: SlideRepairTier | None = None
    reasons: list[str] = []

    # Tier 1 — shorten repetition on message and bullets
    new_message = shorten_repetitive_expression(working.message)
    new_points = [shorten_repetitive_expression(point) for point in working.key_points]
    if new_message != working.message or new_points != working.key_points:
        tier_used = SlideRepairTier.SHORTEN_REPETITION
        reasons.append("缩短重复表达")
        working.message = new_message
        working.key_points = new_points

    # Tier 2 — rewrite to fit length limits without dropping protected facts
    message, applied, msg_reason = smart_shorten_text(working.message, _MAX_MESSAGE_LENGTH)
    if applied and message != working.message:
        tier_used = SlideRepairTier.REWRITE
        reasons.append(msg_reason)
        working.message = message
    elif not applied and len(working.message.strip()) >= _MAX_MESSAGE_LENGTH:
        outcome.requires_manual_confirmation = True
        outcome.reason = msg_reason
        outcome.slide = slide
        outcome.tier = SlideRepairTier.USER_CONFIRMATION
        return outcome

    rewritten_points: list[str] = []
    for point in working.key_points:
        shortened, point_applied, point_reason = smart_shorten_text(point, _MAX_BULLET_LENGTH)
        if not point_applied and len(point.strip()) > _MAX_BULLET_LENGTH:
            outcome.requires_manual_confirmation = True
            outcome.reason = point_reason
            outcome.slide = slide
            outcome.tier = SlideRepairTier.USER_CONFIRMATION
            return outcome
        rewritten_points.append(shortened if point_applied else point)
        if point_applied and shortened != point and tier_used != SlideRepairTier.SHORTEN_REPETITION:
            tier_used = SlideRepairTier.REWRITE
            if point_reason not in reasons:
                reasons.append(point_reason)

    overflow_points: list[str] = []
    if len(rewritten_points) > _MAX_KEY_POINTS:
        overflow_points = rewritten_points[_MAX_KEY_POINTS:]
        rewritten_points = rewritten_points[:_MAX_KEY_POINTS]
        tier_used = SlideRepairTier.SPLIT
        reasons.append("要点超过 5 条，溢出内容将拆分到新页")
    working.key_points = rewritten_points

    # Tier 3 — split when density remains too high (never drop protected bullets)
    if estimate_text_load(working) > _TEXT_DENSITY_THRESHOLD and len(working.key_points) > 1:
        removable = _removable_key_point_indices(working.key_points)
        moved: list[str] = []
        if removable:
            move_index = removable[-1]
            moved = [working.key_points.pop(move_index)]
            tier_used = SlideRepairTier.SPLIT
            reasons.append("文本密度过高，将非关键要点拆分到新页")
            outcome.removed_items.append(f"要点（移至续页）: {moved[0]}")
        else:
            mid = max(1, len(working.key_points) // 2)
            moved = working.key_points[mid:]
            working.key_points = working.key_points[:mid]
            tier_used = SlideRepairTier.SPLIT
            reasons.append("文本密度过高，将部分要点拆分到新页")
            for point in moved:
                outcome.removed_items.append(f"要点（移至续页）: {point}")

        overflow_points.extend(moved)

    if overflow_points:
        if not tier_used:
            tier_used = SlideRepairTier.SPLIT
        if "要点超过 5 条" not in " ".join(reasons):
            reasons.append("溢出要点拆分到新页")
        split_reason = "；".join(reasons) if reasons else "版面拆分"
        from archium.application.slide_split_planner import build_split_plan

        plan = build_split_plan(
            slide,
            working,
            overflow_points,
            split_reason,
            storyline=storyline,
            chapter_slide_count=chapter_slide_count,
        )
        if plan.requires_human_approval:
            outcome.requires_manual_confirmation = True
            outcome.reason = "；".join(plan.validation_issues) or "拆页方案需人工确认"
            outcome.split_plan = plan
            outcome.tier = SlideRepairTier.USER_CONFIRMATION
            outcome.slide = slide
            return outcome
        outcome.split_plan = plan
        outcome.slide = plan.updated_source
        outcome.split_slide = plan.primary_continuation

    if before_message != working.message and not any(
        item.startswith("核心信息改写") for item in outcome.removed_items
    ):
        outcome.removed_items.append(f"核心信息改写: {before_message} → {working.message}")

    outcome.changed = (
        working.message != before_message
        or working.key_points != before_points
        or outcome.split_plan is not None
    )
    if outcome.changed and tier_used is not None:
        outcome.tier = tier_used
        outcome.reason = "；".join(reasons) if reasons else "版面修复"
    elif outcome.requires_manual_confirmation:
        outcome.tier = SlideRepairTier.USER_CONFIRMATION
    return outcome


def _build_split_slide(original: SlideSpec, moved_points: list[str]) -> SlideSpec:
    """Backward-compatible wrapper; prefer ``build_split_plan`` for full planning."""
    from archium.application.slide_split_planner import build_split_slide

    return build_split_slide(original, moved_points)


def insert_split_slide(slides: list[SlideSpec], split_slide: SlideSpec) -> list[SlideSpec]:
    """Bump orders and insert a split slide into the presentation list."""
    updated: list[SlideSpec] = []
    for item in slides:
        current = deepcopy(item)
        if current.order >= split_slide.order:
            current.order += 1
            current.logical_key = build_slide_logical_key(current.chapter_id, current.order)
        updated.append(current)
    updated.append(split_slide)
    return sorted(updated, key=lambda slide: slide.order)


def validate_llm_repair(
    before: SlideSpec,
    *,
    message: str,
    key_points: list[str],
) -> tuple[bool, str]:
    """Reject LLM repairs that silently drop protected content."""
    removed_points = [point for point in before.key_points if point not in key_points]
    for point in removed_points:
        if contains_protected_signal(point):
            return False, f"LLM 试图删除受保护要点: {point}"

    if loses_protected_content(before.message, message):
        return False, "LLM 改写丢失了核心数字或决策条件"

    combined_before = " ".join([before.message, *before.key_points])
    combined_after = " ".join([message, *key_points])
    if extract_protected_tokens(combined_before) - extract_protected_tokens(combined_after):
        return False, "LLM 输出缺少原文中的受保护信息"

    return True, ""
