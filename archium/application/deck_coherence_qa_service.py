"""Deck-level narrative coherence checks beyond per-page visual QA."""

from __future__ import annotations

from archium.domain.deck_coherence import (
    DECK_CLOSING_WITHOUT_DECISION,
    DECK_DUPLICATE_KEY_POINT,
    DECK_DUPLICATE_MESSAGE,
    DECK_NO_ADVANCEMENT,
    DECK_RESOLUTION_UNSUPPORTED,
    DECK_STAGE_REGRESSION,
    DECK_STRATEGY_UNANCHORED,
    DECK_STRATEGY_WITHOUT_PROBLEM,
    DECK_WEAK_SECTION_EVIDENCE,
    DeckCoherenceFinding,
    DeckCoherenceReport,
)
from archium.domain.enums import NarrativeStage
from archium.domain.narrative_arc import (
    infer_narrative_stage,
    narrative_stage_rank,
)
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutIssueSeverity

_PROBLEM_CATEGORIES = frozenset({"problem", "现状", "issue", "background"})
_STRATEGY_CATEGORIES = frozenset({"strategy", "策略", "approach", "concept"})
_CLOSING_CATEGORIES = frozenset({"closing", "conclusion", "summary", "decision", "结语", "总结"})
_ANCHOR_STAGES = frozenset(
    {
        NarrativeStage.PROBLEM,
        NarrativeStage.EVIDENCE,
        NarrativeStage.TENSION,
    }
)
_STRATEGY_STAGES = frozenset(
    {
        NarrativeStage.STRATEGY,
        NarrativeStage.RESOLUTION,
    }
)
_CLOSING_STAGES = frozenset(
    {
        NarrativeStage.RESOLUTION,
        NarrativeStage.DECISION,
    }
)


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
        _ = manuscript  # reserved for manuscript-aware claim support checks
        findings: list[DeckCoherenceFinding] = []
        ordered = sorted(slides, key=lambda slide: slide.order)

        findings.extend(self._duplicate_messages(ordered))
        findings.extend(self._duplicate_key_points(ordered))
        if outline is not None:
            findings.extend(self._strategy_without_problem(outline))
            findings.extend(self._closing_without_decision(outline, ordered))
            findings.extend(self._weak_section_evidence(outline))
            findings.extend(self._no_advancement(outline))
            findings.extend(self._strategy_unanchored(outline))
            findings.extend(self._stage_regression(outline))
            findings.extend(self._resolution_unsupported(outline, storyline))

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
        stages = [_section_stage(section) for section in outline.sections]
        has_problem = any(stage in _ANCHOR_STAGES for stage in stages if stage is not None)
        if not has_problem:
            categories = [section.category.strip().casefold() for section in outline.sections]
            has_problem = any(cat in _PROBLEM_CATEGORIES for cat in categories)
        strategy_sections = [
            section
            for section in outline.sections
            if _section_stage(section) in _STRATEGY_STAGES
            or section.category.strip().casefold() in _STRATEGY_CATEGORIES
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
            if _section_stage(section) == NarrativeStage.DECISION
            or section.category.strip().casefold() in _CLOSING_CATEGORIES
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
            stage = _section_stage(section)
            is_problem = stage == NarrativeStage.PROBLEM or (
                section.category.strip().casefold() in _PROBLEM_CATEGORIES
            )
            if not is_problem:
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

    def _no_advancement(self, outline: OutlinePlan) -> list[DeckCoherenceFinding]:
        findings: list[DeckCoherenceFinding] = []
        ordered = sorted(outline.sections, key=lambda section: section.order)
        previous: OutlineSection | None = None
        for section in ordered:
            if previous is not None:
                prev_msg = previous.key_message.strip()
                curr_msg = section.key_message.strip()
                if prev_msg and curr_msg and prev_msg == curr_msg:
                    findings.append(
                        DeckCoherenceFinding(
                            rule_code=DECK_NO_ADVANCEMENT,
                            severity=LayoutIssueSeverity.WARNING,
                            message=(
                                f"章节「{section.title}」与上一章「{previous.title}」"
                                "关键结论相同，未推进论证"
                            ),
                            suggestion="改写 key_message，明确相对上一章推进了什么。",
                            section_ids=[previous.id, section.id],
                        )
                    )
            position = section.narrative_position
            if (
                position is not None
                and previous is not None
                and not position.advances_from_previous.strip()
            ):
                findings.append(
                    DeckCoherenceFinding(
                        rule_code=DECK_NO_ADVANCEMENT,
                        severity=LayoutIssueSeverity.INFO,
                        message=f"章节「{section.title}」缺少 advances_from_previous",
                        suggestion="说明相对上一章推进了哪一步论证。",
                        section_ids=[section.id],
                    )
                )
            previous = section
        return findings

    def _strategy_unanchored(self, outline: OutlinePlan) -> list[DeckCoherenceFinding]:
        ordered = sorted(outline.sections, key=lambda section: section.order)
        seen_anchor = False
        findings: list[DeckCoherenceFinding] = []
        for section in ordered:
            stage = _section_stage(section)
            if stage in _ANCHOR_STAGES:
                seen_anchor = True
            if stage in _STRATEGY_STAGES and not seen_anchor:
                findings.append(
                    DeckCoherenceFinding(
                        rule_code=DECK_STRATEGY_UNANCHORED,
                        severity=LayoutIssueSeverity.WARNING,
                        message=(
                            f"章节「{section.title}」进入策略/方案阶段，"
                            "但前文尚未建立问题或证据"
                        ),
                        suggestion="将策略章后移，或在此前补充 problem/evidence 章节。",
                        section_ids=[section.id],
                    )
                )
        return findings

    def _stage_regression(self, outline: OutlinePlan) -> list[DeckCoherenceFinding]:
        ordered = sorted(outline.sections, key=lambda section: section.order)
        findings: list[DeckCoherenceFinding] = []
        previous_rank: int | None = None
        previous_section: OutlineSection | None = None
        previous_stage: NarrativeStage | None = None
        for section in ordered:
            stage = _section_stage(section)
            if stage is None:
                continue
            rank = narrative_stage_rank(stage)
            if (
                previous_rank is not None
                and previous_section is not None
                and previous_stage is not None
                and previous_rank - rank >= 2
            ):
                findings.append(
                    DeckCoherenceFinding(
                        rule_code=DECK_STAGE_REGRESSION,
                        severity=LayoutIssueSeverity.WARNING,
                        message=(
                            f"章节「{section.title}」叙事阶段回退："
                            f"{previous_stage.value} → {stage.value}"
                        ),
                        suggestion="调整章节顺序，或重新标注 narrative_position.stage。",
                        section_ids=[previous_section.id, section.id],
                    )
                )
            previous_rank = rank
            previous_section = section
            previous_stage = stage
        return findings

    def _resolution_unsupported(
        self,
        outline: OutlinePlan,
        storyline: Storyline | None,
    ) -> list[DeckCoherenceFinding]:
        if storyline is None or storyline.narrative_arc is None:
            return []
        arc = storyline.narrative_arc
        ordered = sorted(outline.sections, key=lambda section: section.order)
        has_strategy = any(_section_stage(section) in _STRATEGY_STAGES for section in ordered)
        closing = [
            section
            for section in ordered
            if _section_stage(section) in _CLOSING_STAGES
        ]
        if not closing:
            return []
        if has_strategy or not arc.proposed_resolution.strip():
            return []
        return [
            DeckCoherenceFinding(
                rule_code=DECK_RESOLUTION_UNSUPPORTED,
                severity=LayoutIssueSeverity.WARNING,
                message="叙事弧线提出了解决方案，但大纲缺少 strategy/resolution 章节支撑结论",
                suggestion="补充策略或决议章节，使结尾决策有前文路径支撑。",
                section_ids=[section.id for section in closing],
            )
        ]


def _section_stage(section: OutlineSection) -> NarrativeStage | None:
    if section.narrative_position is not None:
        return section.narrative_position.stage
    return infer_narrative_stage(section.category)
