"""RhythmEngine — tension curve + pacing rule tests."""

from __future__ import annotations

from uuid import UUID

from archium.application.visual.showcase_case_001 import build_case_001_render_bundle
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    PacingRole,
    SlideCompositionDirective,
    VisualIntensity,
)
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.domain.visual.rhythm_engine import (
    RHYTHM_CONSECUTIVE_DIAGRAM,
    RHYTHM_DOUBLE_PEAK_ADJACENT,
    RHYTHM_MONOTONE_DECK,
    RHYTHM_NO_BREATH_AFTER_PEAK,
    RHYTHM_OPENING_NOT_SPACIOUS,
    BeatKind,
    analyse_rhythm,
    suggest_rhythm_edits,
)

_PID = UUID("aaaaaaaa-0000-4000-8000-000000000001")
_AID = UUID("aaaaaaaa-0000-4000-8000-000000000002")


def _directive(
    index: int,
    pacing: PacingRole,
    intensity: VisualIntensity = VisualIntensity.MEDIUM,
    density: DensityLevel = DensityLevel.BALANCED,
    families: list[LayoutFamily] | None = None,
) -> SlideCompositionDirective:
    sid = UUID(f"aaaaaaaa-0000-4000-8000-{index:012d}")
    return SlideCompositionDirective(
        slide_id=sid,
        slide_index=index,
        narrative_role="role",
        pacing_role=pacing,
        visual_intensity=intensity,
        target_density=density,
        preferred_layout_families=families or [LayoutFamily.HYBRID_CANVAS],
    )


def _minimal_plan(directives: list[SlideCompositionDirective]) -> DeckCompositionPlan:
    return DeckCompositionPlan(
        presentation_id=_PID,
        art_direction_id=_AID,
        composition_strategy="test",
        pacing_strategy="test",
        slide_directives=directives,
    )


def test_tension_curve_length_matches_slides() -> None:
    dirs = [_directive(i, PacingRole.EVIDENCE) for i in range(8)]
    plan = _minimal_plan(dirs)
    report = analyse_rhythm(plan)
    assert len(report.tension_curve) == 8
    assert all(0.0 <= v <= 1.0 for v in report.tension_curve)


def test_climax_page_has_highest_tension() -> None:
    dirs = [
        _directive(0, PacingRole.OPENING, VisualIntensity.LOW, DensityLevel.SPACIOUS),
        _directive(1, PacingRole.EVIDENCE, VisualIntensity.MEDIUM, DensityLevel.COMPACT),
        _directive(2, PacingRole.CLIMAX, VisualIntensity.HERO, DensityLevel.SPACIOUS),
        _directive(3, PacingRole.PAUSE, VisualIntensity.LOW, DensityLevel.SPACIOUS),
        _directive(4, PacingRole.CLOSING, VisualIntensity.LOW, DensityLevel.SPACIOUS),
    ]
    plan = _minimal_plan(dirs)
    report = analyse_rhythm(plan)
    assert BeatKind.PEAK in report.beat_kinds
    peak_idx = report.beat_kinds.index(BeatKind.PEAK)
    assert report.tension_curve[peak_idx] >= max(
        v for i, v in enumerate(report.tension_curve) if i != peak_idx
    ) - 0.05


def test_double_peak_adjacent_fires() -> None:
    dirs = [
        _directive(0, PacingRole.OPENING),
        _directive(1, PacingRole.CLIMAX, VisualIntensity.HERO),
        _directive(2, PacingRole.CLIMAX, VisualIntensity.HERO),
        _directive(3, PacingRole.CLOSING),
    ]
    report = analyse_rhythm(_minimal_plan(dirs))
    assert RHYTHM_DOUBLE_PEAK_ADJACENT in report.finding_codes


def test_no_breath_after_peak_fires() -> None:
    dirs = [
        _directive(0, PacingRole.OPENING),
        _directive(1, PacingRole.CLIMAX, VisualIntensity.HERO),
        _directive(2, PacingRole.EVIDENCE),
        _directive(3, PacingRole.EVIDENCE),
        _directive(4, PacingRole.CLOSING),
    ]
    report = analyse_rhythm(_minimal_plan(dirs))
    assert RHYTHM_NO_BREATH_AFTER_PEAK in report.finding_codes


def test_opening_compact_fires() -> None:
    dirs = [
        _directive(0, PacingRole.OPENING, density=DensityLevel.COMPACT),
        _directive(1, PacingRole.CLIMAX, VisualIntensity.HERO),
        _directive(2, PacingRole.CLOSING),
    ]
    report = analyse_rhythm(_minimal_plan(dirs))
    assert RHYTHM_OPENING_NOT_SPACIOUS in report.finding_codes


def test_consecutive_diagram_fires() -> None:
    dirs = [
        _directive(0, PacingRole.OPENING),
        _directive(1, PacingRole.EVIDENCE, families=[LayoutFamily.DRAWING_FOCUS]),
        _directive(2, PacingRole.EVIDENCE, families=[LayoutFamily.DRAWING_FOCUS]),
        _directive(3, PacingRole.ANALYSIS, families=[LayoutFamily.ANALYTICAL_DIAGRAM]),
        _directive(4, PacingRole.EVIDENCE, families=[LayoutFamily.DRAWING_FOCUS]),
        _directive(5, PacingRole.CLOSING),
    ]
    report = analyse_rhythm(_minimal_plan(dirs))
    assert RHYTHM_CONSECUTIVE_DIAGRAM in report.finding_codes


def test_monotone_deck_fires() -> None:
    # All EVIDENCE/MEDIUM/BALANCED → all tension values equal → range ≈ 0.
    dirs = [_directive(i, PacingRole.EVIDENCE) for i in range(8)]
    report = analyse_rhythm(_minimal_plan(dirs))
    assert report.is_monotone
    assert RHYTHM_MONOTONE_DECK in report.finding_codes


def test_good_rhythm_passes() -> None:
    dirs = [
        _directive(0, PacingRole.OPENING, VisualIntensity.LOW, DensityLevel.SPACIOUS),
        _directive(1, PacingRole.SETUP, VisualIntensity.MEDIUM, DensityLevel.BALANCED),
        _directive(2, PacingRole.EVIDENCE, VisualIntensity.MEDIUM, DensityLevel.COMPACT),
        _directive(3, PacingRole.PAUSE, VisualIntensity.LOW, DensityLevel.SPACIOUS),
        _directive(4, PacingRole.CLIMAX, VisualIntensity.HERO, DensityLevel.SPACIOUS),
        _directive(5, PacingRole.TRANSITION, VisualIntensity.LOW, DensityLevel.SPACIOUS),
        _directive(6, PacingRole.ANALYSIS, VisualIntensity.MEDIUM, DensityLevel.BALANCED),
        _directive(7, PacingRole.CLOSING, VisualIntensity.LOW, DensityLevel.SPACIOUS),
    ]
    report = analyse_rhythm(_minimal_plan(dirs))
    assert RHYTHM_DOUBLE_PEAK_ADJACENT not in report.finding_codes
    assert RHYTHM_OPENING_NOT_SPACIOUS not in report.finding_codes
    assert len(report.peak_positions) >= 1


def test_suggest_rhythm_edits_returns_strings() -> None:
    dirs = [_directive(i, PacingRole.EVIDENCE) for i in range(8)]
    report = analyse_rhythm(_minimal_plan(dirs))
    edits = suggest_rhythm_edits(report)
    assert isinstance(edits, list)
    assert all(isinstance(s, str) for s in edits)
    assert len(edits) >= 1


def test_case_001_rhythm_has_peaks_and_tension() -> None:
    bundle = build_case_001_render_bundle()
    report = analyse_rhythm(bundle.composition)
    assert report.slide_count == 20
    assert len(report.tension_curve) == 20
    assert len(report.peak_positions) >= 1
    assert not report.is_monotone, (
        f"Case 001 should not be monotone; tension range = "
        f"{max(report.tension_curve)-min(report.tension_curve):.3f}"
    )


def test_case_001_rhythm_finding_codes_are_strings() -> None:
    bundle = build_case_001_render_bundle()
    report = analyse_rhythm(bundle.composition)
    for code in report.finding_codes:
        assert code.startswith("RHYTHM.")
