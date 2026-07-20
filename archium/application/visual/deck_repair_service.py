"""Map Deck QA findings to actionable Studio repair suggestions."""

from __future__ import annotations

import contextlib
from typing import Any
from uuid import UUID

from archium.domain.visual.deck_qa import (
    DECK_COMPOSITION_FAMILY_DEVIATION,
    DECK_COMPOSITION_INTENSITY_DRIFT,
    DECK_REPEATED_LAYOUT_FAMILY,
    DECK_WEAK_SECTION_TRANSITION,
    DeckQAFinding,
    DeckQAReport,
)
from archium.domain.visual.deck_repair import DeckRepairSuggestion
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutFamily


class DeckRepairService:
    """Convert Deck QA output into user-triggered slide repair actions."""

    def suggest_from_report(self, report: DeckQAReport | dict[str, Any]) -> list[DeckRepairSuggestion]:
        if isinstance(report, DeckQAReport):
            findings = list(report.findings)
        else:
            findings = [
                DeckQAFinding.model_validate(item)
                for item in list(report.get("findings") or [])
            ]
        suggestions: list[DeckRepairSuggestion] = []
        for finding in findings:
            suggestions.extend(self.suggest_from_finding(finding))
        return _dedupe_suggestions(suggestions)

    def suggest_from_finding(self, finding: DeckQAFinding) -> list[DeckRepairSuggestion]:
        slide_ids = _resolved_slide_ids(finding)
        if not slide_ids:
            return []

        if finding.rule_code == DECK_REPEATED_LAYOUT_FAMILY:
            return [
                _visual_suggestion(
                    finding=finding,
                    slide_id=slide_id,
                    intent=VisualEditIntent.CHANGE_LAYOUT,
                    label="切换版式类型",
                    reason="相邻页面版式类型重复，建议更换本页版式以增强节奏变化。",
                    params=_alternate_family_params(finding),
                )
                for slide_id in slide_ids[:2]
            ]

        if finding.rule_code == DECK_COMPOSITION_FAMILY_DEVIATION:
            family = finding.evidence.get("expected_family")
            params: dict[str, object] = {}
            if isinstance(family, str):
                with contextlib.suppress(ValueError):
                    params["layout_family"] = LayoutFamily(family)
            return [
                _visual_suggestion(
                    finding=finding,
                    slide_id=slide_id,
                    intent=VisualEditIntent.CHANGE_LAYOUT,
                    label="对齐节奏规划",
                    reason="本页版式与整套节奏规划偏差较大，建议切换到推荐版式类型。",
                    params=params,
                )
                for slide_id in slide_ids[:1]
            ]

        if finding.rule_code in {DECK_COMPOSITION_INTENSITY_DRIFT, DECK_WEAK_SECTION_TRANSITION}:
            return [
                _visual_suggestion(
                    finding=finding,
                    slide_id=slide_id,
                    intent=VisualEditIntent.INCREASE_WHITESPACE,
                    label="增加留白",
                    reason="本页视觉强度与章节过渡不匹配，建议疏朗排版或增强主视觉。",
                )
                for slide_id in slide_ids[:1]
            ]

        return [
            _visual_suggestion(
                finding=finding,
                slide_id=slide_ids[0],
                intent=VisualEditIntent.CHANGE_LAYOUT,
                label="重新排版",
                reason=finding.suggestion or finding.message,
            )
        ]


def _resolved_slide_ids(finding: DeckQAFinding) -> list[UUID]:
    resolved: list[UUID] = []
    for value in finding.slide_ids:
        slide_id = _parse_slide_id(value)
        if slide_id is not None:
            resolved.append(slide_id)
    return resolved


def _visual_suggestion(
    *,
    finding: DeckQAFinding,
    slide_id: UUID,
    intent: VisualEditIntent,
    label: str,
    reason: str,
    params: dict[str, object] | None = None,
) -> DeckRepairSuggestion:
    return DeckRepairSuggestion(
        rule_code=finding.rule_code,
        slide_id=slide_id,
        intent=intent.value,
        label=label,
        reason=reason,
        params=dict(params or {}),
    )


def _alternate_family_params(finding: DeckQAFinding) -> dict[str, object]:
    family_value = finding.evidence.get("family")
    if not isinstance(family_value, str):
        return {}
    try:
        current = LayoutFamily(family_value)
    except ValueError:
        return {}
    alternates = {
        LayoutFamily.HERO: LayoutFamily.DRAWING_FOCUS,
        LayoutFamily.DRAWING_FOCUS: LayoutFamily.HYBRID_CANVAS,
        LayoutFamily.TEXTUAL_ARGUMENT: LayoutFamily.STRATEGY_CARDS,
        LayoutFamily.EVIDENCE_BOARD: LayoutFamily.COMPARATIVE_MATRIX,
    }
    alternate = alternates.get(current, LayoutFamily.HYBRID_CANVAS)
    return {"layout_family": alternate}


def _parse_slide_id(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _dedupe_suggestions(items: list[DeckRepairSuggestion]) -> list[DeckRepairSuggestion]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[DeckRepairSuggestion] = []
    for item in items:
        key = (item.rule_code, str(item.slide_id), item.intent)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
