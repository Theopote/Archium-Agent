"""Deck-level narrative coherence checks beyond per-page visual QA."""

from __future__ import annotations

from archium.domain.deck_coherence import (
    DECK_CLOSING_WITHOUT_DECISION,
    DECK_DUPLICATE_KEY_POINT,
    DECK_DUPLICATE_MESSAGE,
    DECK_STRATEGY_WITHOUT_PROBLEM,
    DECK_WEAK_SECTION_EVIDENCE,
    DeckCoherenceFinding,
    DeckCoherenceReport,
)
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutIssueSeverity

_PROBLEM_CATEGORIES = frozenset({"problem", "现状", "issue", "background"})
_STRATEGY_CATEGORIES = frozenset({"strategy", "策略", "approach", "concept"})
_CLOSING_CATEGORIES = frozenset({"closing", "conclusion", "summary", "decision", "结语", "总结"})


class DeckCoherenceQAService:
    """Rule-based deck narrative QA — findings only, no numeric gate score."""

    def evaluate(
        self,
        slides: list[SlideSpec],
        *,
        outline: OutlinePlan | None = None,
        storyline: Storyline | None = None,
        manuscript: PresentationManuscript | None = None,
    ) -> DeckCoherenceReport:
        _ = storyline, manuscript  # reserved for future manuscript-aware rules
        findings: list[DeckCoherenceFinding] = []
        ordered = sorted(slides, key=lambda slide: slide.order)

        findings.extend(self._duplicate_messages(ordered))
        findings.extend(self._duplicate_key_points(ordered))
        if outline is not None:
            findings.extend(self._strategy_without_problem(outline))
            findings.extend(self._closing_without_decision(outline, ordered))
            findings.extend(self._weak_section_evidence(outline))

        return DeckCoherenceReport(slide_count=len(ordered), findings=findings)

    def _duplicate_messages(self, slides: list[SlideSpec]) -> list[DeckCoherenceFinding]:
        counts: dict[str, list[str]] = {}
        for slide in slides:
            message = slide.message.strip()
            if len(message) < 12:
                continue
            counts.setdefault(message, []).append(str(slide.id))
        findings: list[DeckCoherenceFinding] = []
        for message, slide_ids in counts.items():
            if len(slide_ids) < 2:
                continue
            findings.append(
                DeckCoherenceFinding(
                    rule_code=DECK_DUPLICATE_MESSAGE,
                    severity=LayoutIssueSeverity.WARNING,
                    message=f"核心观点在 {len(slide_ids)} 页重复：「{message[:40]}…」",
                    suggestion="区分各页论证角度，或合并重复页面。",
                    slide_ids=slide_ids,
                )
            )
        return findings

    def _duplicate_key_points(self, slides: list[SlideSpec]) -> list[DeckCoherenceFinding]:
        counts: dict[str, list[str]] = {}
        for slide in slides:
            for point in slide.key_points:
                text = point.strip()
                if len(text) < 8:
                    continue
                counts.setdefault(text, []).append(str(slide.id))
        findings: list[DeckCoherenceFinding] = []
        for point, slide_ids in counts.items():
            if len(slide_ids) < 2:
                continue
            findings.append(
                DeckCoherenceFinding(
                    rule_code=DECK_DUPLICATE_KEY_POINT,
                    severity=LayoutIssueSeverity.INFO,
                    message=f"要点「{point[:36]}…」在 {len(slide_ids)} 页重复出现",
                    suggestion="保留最强证据页，其余页改写或删除重复要点。",
                    slide_ids=slide_ids,
                )
            )
        return findings

    def _strategy_without_problem(self, outline: OutlinePlan) -> list[DeckCoherenceFinding]:
        categories = [section.category.strip().casefold() for section in outline.sections]
        has_problem = any(cat in _PROBLEM_CATEGORIES for cat in categories)
        strategy_sections = [
            section
            for section in outline.sections
            if section.category.strip().casefold() in _STRATEGY_CATEGORIES
        ]
        if has_problem or not strategy_sections:
            return []
        return [
            DeckCoherenceFinding(
                rule_code=DECK_STRATEGY_WITHOUT_PROBLEM,
                severity=LayoutIssueSeverity.WARNING,
                message="存在策略章节但未识别对应问题/现状章节",
                suggestion="在策略前补充问题诊断或现状分析章节。",
                section_ids=[section.id for section in strategy_sections],
            )
        ]

    def _closing_without_decision(
        self,
        outline: OutlinePlan,
        slides: list[SlideSpec],
    ) -> list[DeckCoherenceFinding]:
        closing_sections = [
            section
            for section in outline.sections
            if section.category.strip().casefold() in _CLOSING_CATEGORIES
        ]
        if not closing_sections:
            return []
        closing_ids = {section.id for section in closing_sections}
        closing_slides = [slide for slide in slides if slide.chapter_id in closing_ids]
        if not closing_slides:
            return []
        has_decision_language = any(
            any(
                token in (slide.message + " ".join(slide.key_points)).casefold()
                for token in ("建议", "决策", "请求", "批准", "推进", "实施")
            )
            for slide in closing_slides
        )
        if has_decision_language:
            return []
        return [
            DeckCoherenceFinding(
                rule_code=DECK_CLOSING_WITHOUT_DECISION,
                severity=LayoutIssueSeverity.WARNING,
                message="结语/决策章节缺少明确决策请求或行动建议",
                suggestion="在结尾页补充决策事项、下一步或请求支持的具体表述。",
                section_ids=list(closing_ids),
                slide_ids=[str(slide.id) for slide in closing_slides],
            )
        ]

    def _weak_section_evidence(self, outline: OutlinePlan) -> list[DeckCoherenceFinding]:
        findings: list[DeckCoherenceFinding] = []
        for section in outline.sections:
            if section.category.strip().casefold() not in _PROBLEM_CATEGORIES:
                continue
            if section.evidence_requirements:
                continue
            if not section.key_message.strip():
                continue
            findings.append(
                DeckCoherenceFinding(
                    rule_code=DECK_WEAK_SECTION_EVIDENCE,
                    severity=LayoutIssueSeverity.INFO,
                    message=f"章节「{section.title}」提出问题但缺少 evidence_requirements",
                    suggestion="补充可观测证据要求（照片、数据、规范条文等）。",
                    section_ids=[section.id],
                )
            )
        return findings
