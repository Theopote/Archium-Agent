"""Visual Rhythm Engine — deck-level tension analysis and pacing suggestions.

Operates on the already-built DeckCompositionPlan (read-only).
Produces a RhythmReport with:
  - tension_curve: float[0..1] per slide (smoothed composite score)
  - page_roles: human-readable beat labels
  - findings: rule violations and suggestions
  - is_monotone: True when the deck lacks contrast
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    PacingRole,
    SlideCompositionDirective,
    density_to_score,
    intensity_to_score,
)
from archium.domain.visual.enums import DensityLevel


class BeatKind(StrEnum):
    OPENING = "opening"
    BREATH = "breath"          # low-tension buffer between peaks
    BUILD = "build"            # rising tension
    PEAK = "peak"              # climax / hero moment
    FALL = "fall"              # post-peak release
    ANALYSIS = "analysis"      # medium-tension informational
    TRANSITION = "transition"  # chapter boundary
    CLOSING = "closing"


_PACING_TO_BEAT: dict[PacingRole, BeatKind] = {
    PacingRole.OPENING: BeatKind.OPENING,
    PacingRole.SETUP: BeatKind.BUILD,
    PacingRole.EVIDENCE: BeatKind.ANALYSIS,
    PacingRole.ANALYSIS: BeatKind.ANALYSIS,
    PacingRole.PAUSE: BeatKind.BREATH,
    PacingRole.TRANSITION: BeatKind.TRANSITION,
    PacingRole.CLIMAX: BeatKind.PEAK,
    PacingRole.DECISION: BeatKind.FALL,
    PacingRole.CLOSING: BeatKind.CLOSING,
}


class RhythmFinding(DomainModel):
    rule_code: str
    slide_indices: list[int] = Field(default_factory=list)
    message: str
    suggestion: str = ""


class RhythmReport(DomainModel):
    """Read-only rhythm analysis for one DeckCompositionPlan."""

    slide_count: int
    tension_curve: list[float] = Field(default_factory=list)
    beat_kinds: list[BeatKind] = Field(default_factory=list)
    findings: list[RhythmFinding] = Field(default_factory=list)
    is_monotone: bool = False
    peak_positions: list[int] = Field(default_factory=list)
    breath_positions: list[int] = Field(default_factory=list)
    longest_flat_run: int = 0
    suggestions: list[str] = Field(default_factory=list)

    @property
    def finding_codes(self) -> list[str]:
        return [f.rule_code for f in self.findings]


RHYTHM_CONSECUTIVE_DIAGRAM = "RHYTHM.CONSECUTIVE_DIAGRAM"
RHYTHM_NO_BREATH_AFTER_PEAK = "RHYTHM.NO_BREATH_AFTER_PEAK"
RHYTHM_OPENING_NOT_SPACIOUS = "RHYTHM.OPENING_NOT_SPACIOUS"
RHYTHM_CLOSING_NOT_CALM = "RHYTHM.CLOSING_NOT_CALM"
RHYTHM_MONOTONE_DECK = "RHYTHM.MONOTONE_DECK"
RHYTHM_DOUBLE_PEAK_ADJACENT = "RHYTHM.DOUBLE_PEAK_ADJACENT"
RHYTHM_TEXT_OVERLOAD_RUN = "RHYTHM.TEXT_OVERLOAD_RUN"
RHYTHM_PEAK_MISSING = "RHYTHM.PEAK_MISSING"


def analyse_rhythm(plan: DeckCompositionPlan) -> RhythmReport:
    """Analyse deck rhythm and return a RhythmReport (pure, no mutation)."""
    directives = plan.slide_directives
    n = len(directives)
    if n == 0:
        return RhythmReport(slide_count=0, is_monotone=True)

    tension = _compute_tension_curve(directives, plan)
    beats = [_beat_for(d) for d in directives]
    findings: list[RhythmFinding] = []
    suggestions: list[str] = []

    # Rule 1: after 3+ consecutive analysis/diagram pages → insert hero.
    _check_consecutive_diagram(directives, beats, findings, suggestions)

    # Rule 2: peak immediately followed by another peak → double climax.
    _check_double_peak(beats, findings, suggestions)

    # Rule 3: peak not followed by breath within 2 pages.
    _check_breath_after_peak(beats, findings, suggestions)

    # Rule 4: opening page should be spacious.
    _check_opening_density(directives, findings, suggestions)

    # Rule 5: closing pages should be calm.
    _check_closing_density(directives, beats, findings, suggestions)

    # Rule 6: pure-text overload run.
    _check_text_overload(directives, findings, suggestions)

    # Rule 7: no peak at all → warn.
    peak_positions = [i for i, b in enumerate(beats) if b == BeatKind.PEAK]
    if not peak_positions and n >= 6:
        findings.append(
            RhythmFinding(
                rule_code=RHYTHM_PEAK_MISSING,
                message="全册无任何高潮（PEAK）页。",
                suggestion="在概念页或效果表达页设置至少一个 VisualIntensity.HERO 节点。",
            )
        )
        suggestions.append("建议在中部或后段设置高潮大图页。")

    # Monotone check: tension range < 0.3.
    t_range = max(tension) - min(tension) if tension else 0.0
    is_monotone = t_range < 0.20

    if is_monotone and n >= 5:
        findings.append(
            RhythmFinding(
                rule_code=RHYTHM_MONOTONE_DECK,
                message=f"全册张力区间 {t_range:.2f} < 0.20，节奏单调。",
                suggestion="增加视觉强页（HERO/CLIMAX）与留白页（PAUSE/TRANSITION）的对比。",
            )
        )
        suggestions.append("张力曲线需更多起伏：大图 → 缓冲 → 图纸 → 高潮。")

    breath_positions = [i for i, b in enumerate(beats) if b == BeatKind.BREATH]

    # Longest flat run (beats without PEAK or BREATH).
    flat_run = _longest_flat_run(beats)

    return RhythmReport(
        slide_count=n,
        tension_curve=tension,
        beat_kinds=beats,
        findings=findings,
        is_monotone=is_monotone,
        peak_positions=peak_positions,
        breath_positions=breath_positions,
        longest_flat_run=flat_run,
        suggestions=suggestions,
    )


def suggest_rhythm_edits(report: RhythmReport) -> list[str]:
    """Plain-language suggestions from a RhythmReport."""
    out = list(report.suggestions)
    for f in report.findings:
        if f.suggestion and f.suggestion not in out:
            out.append(f.suggestion)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_tension_curve(
    directives: list[SlideCompositionDirective],
    plan: DeckCompositionPlan,
) -> list[float]:
    """Composite tension = 0.6×intensity + 0.4×(1 - density_score)."""
    raw: list[float] = []
    for d in directives:
        i_score = intensity_to_score(d.visual_intensity)
        # spacious pages feel more tense visually; dense/compact pages feel more
        # analytical (lower tension). Invert density contribution.
        d_score = 1.0 - density_to_score(d.target_density)
        raw.append(round(0.6 * i_score + 0.4 * d_score, 3))

    # Smooth with a 3-point moving average (preserve endpoints).
    if len(raw) < 3:
        return raw
    smoothed = [raw[0]]
    for index in range(1, len(raw) - 1):
        smoothed.append(round((raw[index - 1] + raw[index] + raw[index + 1]) / 3, 3))
    smoothed.append(raw[-1])
    return smoothed


def _beat_for(d: SlideCompositionDirective) -> BeatKind:
    return _PACING_TO_BEAT.get(d.pacing_role, BeatKind.ANALYSIS)


_DIAGRAM_BEATS = {BeatKind.ANALYSIS, BeatKind.BUILD}
_DIAGRAM_FAMILIES_HINT = frozenset(["drawing_focus", "analytical_diagram", "evidence_board"])


def _is_diagram_page(d: SlideCompositionDirective, beat: BeatKind) -> bool:
    return beat in _DIAGRAM_BEATS or any(
        f.value in _DIAGRAM_FAMILIES_HINT for f in d.preferred_layout_families
    )


def _check_consecutive_diagram(
    directives: list[SlideCompositionDirective],
    beats: list[BeatKind],
    findings: list[RhythmFinding],
    suggestions: list[str],
) -> None:
    run: list[int] = []
    reported: set[int] = set()
    for i, (d, b) in enumerate(zip(directives, beats, strict=True)):
        if _is_diagram_page(d, b):
            run.append(i)
        else:
            if len(run) >= 3:
                start = run[0]
                if start not in reported:
                    reported.add(start)
                    findings.append(
                        RhythmFinding(
                            rule_code=RHYTHM_CONSECUTIVE_DIAGRAM,
                            slide_indices=list(run),
                            message=f"连续 {len(run)} 页分析/图纸页（idx {run[0]}–{run[-1]}）后无视觉强页。",
                            suggestion="在连续分析页后插入 hero 大图或 PAUSE 留白页。",
                        )
                    )
                    suggestions.append(
                        f"第 {run[-1]+1} 页后建议加入大图或留白页（连续 {len(run)} 页分析）。"
                    )
            run = []
    if len(run) >= 3:
        findings.append(
            RhythmFinding(
                rule_code=RHYTHM_CONSECUTIVE_DIAGRAM,
                slide_indices=list(run),
                message=f"末段连续 {len(run)} 页分析/图纸页。",
                suggestion="尾声段应以收束大图或留白页结束。",
            )
        )


def _check_double_peak(
    beats: list[BeatKind],
    findings: list[RhythmFinding],
    suggestions: list[str],
) -> None:
    for i in range(len(beats) - 1):
        if beats[i] == BeatKind.PEAK and beats[i + 1] == BeatKind.PEAK:
            findings.append(
                RhythmFinding(
                    rule_code=RHYTHM_DOUBLE_PEAK_ADJACENT,
                    slide_indices=[i, i + 1],
                    message=f"相邻两页均为 PEAK（idx {i}, {i+1}），高潮连排。",
                    suggestion="两个高潮页之间插入至少一页过渡或分析页。",
                )
            )
            suggestions.append(f"第 {i+2} 页前建议插入过渡页（两个高潮相邻）。")


def _check_breath_after_peak(
    beats: list[BeatKind],
    findings: list[RhythmFinding],
    suggestions: list[str],
) -> None:
    for i, beat in enumerate(beats):
        if beat != BeatKind.PEAK:
            continue
        window = beats[i + 1 : i + 3]
        if BeatKind.BREATH not in window and BeatKind.TRANSITION not in window:
            end = min(i + 3, len(beats))
            findings.append(
                RhythmFinding(
                    rule_code=RHYTHM_NO_BREATH_AFTER_PEAK,
                    slide_indices=[i],
                    message=f"PEAK 页（idx {i}）后 2 页内无 BREATH/TRANSITION。",
                    suggestion="高潮后安排一页留白或过渡页让观众「喘息」。",
                )
            )
            suggestions.append(f"第 {i+2} 页建议降低密度作为高潮后缓冲。")


def _check_opening_density(
    directives: list[SlideCompositionDirective],
    findings: list[RhythmFinding],
    suggestions: list[str],
) -> None:
    if directives and directives[0].target_density == DensityLevel.COMPACT:
        findings.append(
            RhythmFinding(
                rule_code=RHYTHM_OPENING_NOT_SPACIOUS,
                slide_indices=[0],
                message="首页密度为 COMPACT，开场压迫感过强。",
                suggestion="封面应设为 SPACIOUS，给观众建立语境的空间。",
            )
        )
        suggestions.append("建议封面使用 SPACIOUS 密度。")


def _check_closing_density(
    directives: list[SlideCompositionDirective],
    beats: list[BeatKind],
    findings: list[RhythmFinding],
    suggestions: list[str],
) -> None:
    closing = [
        i
        for i, b in enumerate(beats)
        if b == BeatKind.CLOSING
    ]
    for i in closing:
        if directives[i].target_density == DensityLevel.COMPACT:
            findings.append(
                RhythmFinding(
                    rule_code=RHYTHM_CLOSING_NOT_CALM,
                    slide_indices=[i],
                    message=f"结束页（idx {i}）密度为 COMPACT，收束感弱。",
                    suggestion="结尾页建议使用 SPACIOUS 或 BALANCED 密度。",
                )
            )
            suggestions.append(f"第 {i+1} 页（结尾）密度偏高，建议降低。")


def _check_text_overload(
    directives: list[SlideCompositionDirective],
    findings: list[RhythmFinding],
    suggestions: list[str],
) -> None:
    _TEXT_FAMILIES = frozenset(["textual_argument", "strategy_cards"])
    run: list[int] = []
    for i, d in enumerate(directives):
        is_text = all(f.value in _TEXT_FAMILIES for f in d.preferred_layout_families)
        if is_text:
            run.append(i)
        else:
            if len(run) >= 3:
                findings.append(
                    RhythmFinding(
                        rule_code=RHYTHM_TEXT_OVERLOAD_RUN,
                        slide_indices=list(run),
                        message=f"连续 {len(run)} 页纯文字（idx {run[0]}–{run[-1]}）。",
                        suggestion="纯文字段落内插入图纸/分析/视觉页打破文字密度。",
                    )
                )
                suggestions.append(
                    f"第 {run[0]+1}–{run[-1]+1} 页全为文字，建议中间插入一页视觉页。"
                )
            run = []
    if len(run) >= 3:
        findings.append(
            RhythmFinding(
                rule_code=RHYTHM_TEXT_OVERLOAD_RUN,
                slide_indices=list(run),
                message=f"末段连续 {len(run)} 页纯文字。",
                suggestion="尾声段补充一页图纸或大图收束。",
            )
        )


def _longest_flat_run(beats: list[BeatKind]) -> int:
    """Longest consecutive run without PEAK or BREATH."""
    max_run = current = 0
    for b in beats:
        if b not in (BeatKind.PEAK, BeatKind.BREATH, BeatKind.TRANSITION, BeatKind.CLOSING):
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run
