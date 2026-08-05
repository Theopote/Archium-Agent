"""VQ-008 Architect Blind Review unit tests — fail-closed Beta gate."""

from __future__ import annotations

from archium.application.visual.architect_blind_review_service import (
    build_blind_session,
    compute_blind_metrics,
    evaluate_vq008_beta_gate,
    reviewer_facing_pack,
    sealed_key,
)
from archium.domain.visual.architect_blind_review import (
    VQ008_MEAN_VISUAL_SCORE,
    VQ008_MIN_REVIEWERS,
    VQ008_NEW_VS_OLD_WIN_RATE,
    BlindBallot,
    BlindReadiness,
    BlindSourceKind,
)


def _cases() -> list[dict[str, object]]:
    return [
        {
            "case_id": "cover_01",
            "title": "封面",
            "legacy_asset": "legacy/cover.png",
            "current_asset": "current/cover.png",
            "reference_asset": "ref/cover.png",
            "page_kind": "cover",
        },
        {
            "case_id": "analysis_01",
            "title": "现状分析",
            "legacy_asset": "legacy/analysis.png",
            "current_asset": "current/analysis.png",
            "reference_asset": "ref/analysis.png",
            "page_kind": "analysis",
        },
    ]


def _ballot_for(
    session,
    *,
    reviewer: str,
    prefer_current: bool = True,
    ready: BlindReadiness = BlindReadiness.READY,
    score: float = 8.0,
    legacy_minutes: float = 40.0,
    current_minutes: float = 15.0,
) -> list[BlindBallot]:
    ballots: list[BlindBallot] = []
    for trial in session.trials:
        label_cur = trial.label_for_source(BlindSourceKind.ARCHIUM_CURRENT)
        label_leg = trial.label_for_source(BlindSourceKind.ARCHIUM_LEGACY)
        label_ref = trial.label_for_source(BlindSourceKind.HUMAN_REFERENCE)
        assert label_cur and label_leg
        if prefer_current:
            ranking = [label_cur, label_ref or label_leg, label_leg]
        else:
            ranking = [label_leg, label_ref or label_cur, label_cur]
        # Deduplicate if no reference
        ranking = list(dict.fromkeys(ranking))
        ballots.append(
            BlindBallot(
                reviewer_id=reviewer,
                trial_id=trial.trial_id,
                ranking_labels=ranking,
                preferred_label=ranking[0],
                readiness_by_label={
                    label_cur: ready,
                    label_leg: BlindReadiness.HEAVY_EDIT,
                    **(
                        {label_ref: BlindReadiness.READY}
                        if label_ref
                        else {}
                    ),
                },
                visual_score_by_label={
                    label_cur: score,
                    label_leg: 5.0,
                    **({label_ref: 9.0} if label_ref else {}),
                },
                edit_minutes_by_label={
                    label_cur: current_minutes,
                    label_leg: legacy_minutes,
                    **({label_ref: 5.0} if label_ref else {}),
                },
            )
        )
    return ballots


def test_reviewer_pack_hides_true_source() -> None:
    session = build_blind_session(cases=_cases(), seed=7)
    pack = reviewer_facing_pack(session)
    blob = str(pack)
    assert "archium_legacy" not in blob
    assert "archium_current" not in blob
    assert "true_source" not in blob
    key = sealed_key(session)
    assert "archium_current" in str(key)
    for trial in session.trials:
        labels = {s.label for s in trial.stimuli}
        assert labels == {"A", "B", "C"}


def test_empty_session_fails_beta_gate() -> None:
    session = build_blind_session(cases=_cases())
    gate = evaluate_vq008_beta_gate(session)
    assert gate.passed is False
    assert gate.beta_allowed is False
    assert any("reviewers" in r for r in gate.blocking_reasons)


def test_legacy_preferred_fails_win_rate() -> None:
    session = build_blind_session(cases=_cases(), seed=1)
    ballots: list[BlindBallot] = []
    for i in range(VQ008_MIN_REVIEWERS):
        ballots.extend(
            _ballot_for(
                session,
                reviewer=f"architect_{i}",
                prefer_current=False,
                score=8.5,
                current_minutes=10,
                legacy_minutes=40,
            )
        )
    session = session.model_copy(update={"ballots": ballots})
    metrics = compute_blind_metrics(session)
    assert metrics.reviewer_count >= VQ008_MIN_REVIEWERS
    assert metrics.new_vs_old_win_rate is not None
    assert metrics.new_vs_old_win_rate < VQ008_NEW_VS_OLD_WIN_RATE
    gate = evaluate_vq008_beta_gate(metrics=metrics)
    assert gate.beta_allowed is False
    assert any("win_rate" in r for r in gate.blocking_reasons)


def test_passing_synthetic_campaign_clears_gate() -> None:
    session = build_blind_session(cases=_cases(), seed=3)
    ballots: list[BlindBallot] = []
    for i in range(VQ008_MIN_REVIEWERS):
        ballots.extend(
            _ballot_for(
                session,
                reviewer=f"architect_{i}",
                prefer_current=True,
                ready=BlindReadiness.LIGHT_EDIT if i == 0 else BlindReadiness.READY,
                score=7.5,
                legacy_minutes=50.0,
                current_minutes=20.0,  # 60% reduction
            )
        )
    session = session.model_copy(update={"ballots": ballots})
    gate = evaluate_vq008_beta_gate(session)
    assert gate.metrics.mean_visual_score_current is not None
    assert gate.metrics.mean_visual_score_current >= VQ008_MEAN_VISUAL_SCORE
    assert gate.metrics.new_vs_old_win_rate == 1.0
    assert gate.metrics.edit_time_reduction_rate is not None
    assert gate.metrics.edit_time_reduction_rate >= 0.5
    assert gate.passed is True
    assert gate.beta_allowed is True
    assert "PASSED" in gate.summary()


def test_low_score_blocks_even_if_wins() -> None:
    session = build_blind_session(cases=_cases(), seed=9)
    ballots: list[BlindBallot] = []
    for i in range(VQ008_MIN_REVIEWERS):
        ballots.extend(
            _ballot_for(
                session,
                reviewer=f"architect_{i}",
                prefer_current=True,
                score=6.0,  # below 7.0
                legacy_minutes=40,
                current_minutes=10,
            )
        )
    session = session.model_copy(update={"ballots": ballots})
    gate = evaluate_vq008_beta_gate(session)
    assert gate.beta_allowed is False
    assert any("mean_visual_score" in r for r in gate.blocking_reasons)
