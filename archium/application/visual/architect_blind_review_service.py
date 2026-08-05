"""VQ-008 Architect Blind Review — pack build, unseal metrics, Beta gate.

Does not invent passing scores. Empty / incomplete sessions fail closed.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from uuid import UUID, uuid4

from archium.domain.visual.architect_blind_review import (
    VQ008_DIMENSIONS,
    VQ008_EDIT_TIME_REDUCTION_RATE,
    VQ008_MEAN_VISUAL_SCORE,
    VQ008_MIN_REVIEWERS,
    VQ008_NEW_VS_OLD_WIN_RATE,
    VQ008_PROTOCOL_VERSION,
    VQ008_READY_OR_LIGHT_EDIT_RATE,
    BlindBallot,
    BlindReadiness,
    BlindReviewGateResult,
    BlindReviewMetrics,
    BlindReviewSession,
    BlindSourceKind,
    BlindStimulus,
    BlindTrial,
)

_LABELS = ("A", "B", "C")
_READY_SET = frozenset({BlindReadiness.READY, BlindReadiness.LIGHT_EDIT})


def build_blind_trial(
    *,
    case_id: str,
    title: str = "",
    legacy_asset: str | None = None,
    current_asset: str | None = None,
    reference_asset: str | None = None,
    page_kind: str = "",
    seed: int | None = None,
    include_reference: bool = True,
) -> BlindTrial:
    """Create one shuffled A/B/C trial; seal true sources on stimuli."""
    rng = random.Random(seed if seed is not None else hash(case_id) & 0xFFFFFFFF)
    stimuli = [
        BlindStimulus(
            label="?",  # filled after shuffle
            true_source=BlindSourceKind.ARCHIUM_LEGACY,
            case_id=case_id,
            asset_path=legacy_asset,
        ),
        BlindStimulus(
            label="?",
            true_source=BlindSourceKind.ARCHIUM_CURRENT,
            case_id=case_id,
            asset_path=current_asset,
        ),
    ]
    if include_reference:
        stimuli.append(
            BlindStimulus(
                label="?",
                true_source=BlindSourceKind.HUMAN_REFERENCE,
                case_id=case_id,
                asset_path=reference_asset,
            )
        )
    rng.shuffle(stimuli)
    labeled = [
        item.model_copy(update={"label": _LABELS[index]})
        for index, item in enumerate(stimuli)
    ]
    return BlindTrial(
        trial_id=f"trial:{case_id}",
        case_id=case_id,
        title=title or case_id,
        stimuli=labeled,
        page_kind=page_kind,
    )


def build_blind_session(
    *,
    cases: list[dict[str, object]],
    session_id: UUID | None = None,
    min_reviewers: int = VQ008_MIN_REVIEWERS,
    seed: int = 42,
) -> BlindReviewSession:
    """Build a sealed session from case descriptors.

    Each case dict supports keys: case_id, title, legacy_asset, current_asset,
    reference_asset, page_kind, include_reference.
    """
    trials: list[BlindTrial] = []
    for index, case in enumerate(cases):
        case_id = str(case.get("case_id") or f"case_{index + 1:03d}")
        trials.append(
            build_blind_trial(
                case_id=case_id,
                title=str(case.get("title") or case_id),
                legacy_asset=_opt_str(case.get("legacy_asset")),
                current_asset=_opt_str(case.get("current_asset")),
                reference_asset=_opt_str(case.get("reference_asset")),
                page_kind=str(case.get("page_kind") or ""),
                seed=seed + index,
                include_reference=bool(case.get("include_reference", True)),
            )
        )
    return BlindReviewSession(
        session_id=session_id or uuid4(),
        protocol_version=VQ008_PROTOCOL_VERSION,
        min_reviewers=min_reviewers,
        trials=trials,
    )


def reviewer_facing_pack(session: BlindReviewSession) -> dict[str, object]:
    """Export pack without true_source (safe to send to architects)."""
    trials = []
    for trial in session.trials:
        trials.append(
            {
                "trial_id": trial.trial_id,
                "case_id": trial.case_id,
                "title": trial.title,
                "page_kind": trial.page_kind,
                "stimuli": [
                    {
                        "label": s.label,
                        "asset_path": s.asset_path,
                        "notes": s.notes,
                    }
                    for s in trial.stimuli
                ],
            }
        )
    return {
        "protocol_version": session.protocol_version,
        "session_id": str(session.session_id),
        "title": session.title,
        "instructions": (
            "对各 trial 的 A/B/C 盲评：排序（最好→最差）、就绪度、"
            "视觉分（1–10）、估计改稿分钟。勿猜测来源。"
        ),
        "dimensions": list(VQ008_DIMENSIONS),
        "readiness_values": [item.value for item in BlindReadiness],
        "trials": trials,
    }


def sealed_key(session: BlindReviewSession) -> dict[str, object]:
    """Export label→source map (keep offline; never send to reviewers)."""
    return {
        "protocol_version": session.protocol_version,
        "session_id": str(session.session_id),
        "trials": {
            trial.trial_id: {s.label: s.true_source.value for s in trial.stimuli}
            for trial in session.trials
        },
    }


def compute_blind_metrics(session: BlindReviewSession) -> BlindReviewMetrics:
    """Unseal ballots against trial keys and compute VQ-008 metrics."""
    reviewers = session.reviewer_ids()
    metrics = BlindReviewMetrics(
        session_id=session.session_id,
        reviewer_count=len(reviewers),
        ballot_count=len(session.ballots),
        trial_count=len(session.trials),
    )

    new_vs_old_wins = 0
    new_vs_old_n = 0
    ready_hits = 0
    ready_n = 0
    scores: list[float] = []
    legacy_minutes: list[float] = []
    current_minutes: list[float] = []
    dim_accum: dict[str, list[float]] = {d: [] for d in VQ008_DIMENSIONS}

    for ballot in session.ballots:
        trial = session.trial_by_id(ballot.trial_id)
        if trial is None:
            continue
        label_current = trial.label_for_source(BlindSourceKind.ARCHIUM_CURRENT)
        label_legacy = trial.label_for_source(BlindSourceKind.ARCHIUM_LEGACY)
        if label_current is None or label_legacy is None:
            continue

        # New vs old preference from ranking / preferred.
        preferred = ballot.preferred_label or (
            ballot.ranking_labels[0] if ballot.ranking_labels else None
        )
        if preferred is not None:
            source = trial.source_for_label(preferred)
            if source in {
                BlindSourceKind.ARCHIUM_CURRENT,
                BlindSourceKind.ARCHIUM_LEGACY,
            }:
                new_vs_old_n += 1
                if source == BlindSourceKind.ARCHIUM_CURRENT:
                    new_vs_old_wins += 1
            elif preferred in ballot.ranking_labels and label_current in ballot.ranking_labels:
                # Prefer pairwise rank position when winner is reference.
                rank = {label: i for i, label in enumerate(ballot.ranking_labels)}
                if label_current in rank and label_legacy in rank:
                    new_vs_old_n += 1
                    if rank[label_current] < rank[label_legacy]:
                        new_vs_old_wins += 1

        readiness = ballot.readiness_by_label.get(label_current)
        if readiness is not None:
            ready_n += 1
            if readiness in _READY_SET:
                ready_hits += 1

        score = ballot.visual_score_by_label.get(label_current)
        if score is not None:
            scores.append(float(score))

        leg_m = ballot.edit_minutes_by_label.get(label_legacy)
        cur_m = ballot.edit_minutes_by_label.get(label_current)
        if leg_m is not None and cur_m is not None:
            legacy_minutes.append(float(leg_m))
            current_minutes.append(float(cur_m))

        dims = ballot.dimension_scores_by_label.get(label_current) or {}
        for key in VQ008_DIMENSIONS:
            if key in dims:
                dim_accum[key].append(float(dims[key]))

    metrics.new_vs_old_comparisons = new_vs_old_n
    metrics.new_vs_old_wins = new_vs_old_wins
    if new_vs_old_n:
        metrics.new_vs_old_win_rate = round(new_vs_old_wins / new_vs_old_n, 4)

    metrics.current_readiness_samples = ready_n
    metrics.current_ready_or_light = ready_hits
    if ready_n:
        metrics.ready_or_light_edit_rate = round(ready_hits / ready_n, 4)

    metrics.current_score_samples = len(scores)
    if scores:
        metrics.mean_visual_score_current = round(sum(scores) / len(scores), 3)

    metrics.edit_time_pairs = len(legacy_minutes)
    if legacy_minutes and current_minutes:
        mean_leg = sum(legacy_minutes) / len(legacy_minutes)
        mean_cur = sum(current_minutes) / len(current_minutes)
        metrics.mean_edit_minutes_legacy = round(mean_leg, 2)
        metrics.mean_edit_minutes_current = round(mean_cur, 2)
        if mean_leg > 0:
            metrics.edit_time_reduction_rate = round(
                max(0.0, (mean_leg - mean_cur) / mean_leg), 4
            )

    metrics.dimension_means_current = {
        key: round(sum(vals) / len(vals), 3)
        for key, vals in dim_accum.items()
        if vals
    }

    reasons = _threshold_reasons(metrics, min_reviewers=session.min_reviewers)
    metrics.reasons = reasons
    metrics.passed = not reasons
    return metrics


def evaluate_vq008_beta_gate(
    session: BlindReviewSession | None = None,
    *,
    metrics: BlindReviewMetrics | None = None,
) -> BlindReviewGateResult:
    """Beta hard gate: fail closed until all VQ-008 thresholds pass."""
    if metrics is None:
        if session is None:
            empty = BlindReviewMetrics(
                reasons=["no session or metrics provided"],
                passed=False,
            )
            return BlindReviewGateResult(
                passed=False,
                metrics=empty,
                blocking_reasons=list(empty.reasons),
                beta_allowed=False,
            )
        metrics = compute_blind_metrics(session)
    return BlindReviewGateResult(
        passed=metrics.passed,
        metrics=metrics,
        blocking_reasons=list(metrics.reasons),
        beta_allowed=metrics.passed,
    )


def load_session(path: str | Path) -> BlindReviewSession:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BlindReviewSession.model_validate(data)


def save_session(session: BlindReviewSession, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(session.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _threshold_reasons(
    metrics: BlindReviewMetrics,
    *,
    min_reviewers: int,
) -> list[str]:
    reasons: list[str] = []
    if metrics.reviewer_count < min_reviewers:
        reasons.append(
            f"reviewers {metrics.reviewer_count} < required {min_reviewers}"
        )
    if metrics.new_vs_old_comparisons <= 0:
        reasons.append("no new-vs-old comparisons unsealed")
    elif (
        metrics.new_vs_old_win_rate is None
        or metrics.new_vs_old_win_rate < VQ008_NEW_VS_OLD_WIN_RATE
    ):
        reasons.append(
            f"new_vs_old_win_rate {metrics.new_vs_old_win_rate} "
            f"< {VQ008_NEW_VS_OLD_WIN_RATE}"
        )
    if metrics.current_readiness_samples <= 0:
        reasons.append("no readiness samples for archium_current")
    elif (
        metrics.ready_or_light_edit_rate is None
        or metrics.ready_or_light_edit_rate < VQ008_READY_OR_LIGHT_EDIT_RATE
    ):
        reasons.append(
            f"ready_or_light_edit_rate {metrics.ready_or_light_edit_rate} "
            f"< {VQ008_READY_OR_LIGHT_EDIT_RATE}"
        )
    if metrics.current_score_samples <= 0:
        reasons.append("no visual scores for archium_current")
    elif (
        metrics.mean_visual_score_current is None
        or metrics.mean_visual_score_current < VQ008_MEAN_VISUAL_SCORE
    ):
        reasons.append(
            f"mean_visual_score_current {metrics.mean_visual_score_current} "
            f"< {VQ008_MEAN_VISUAL_SCORE}"
        )
    if metrics.edit_time_pairs <= 0:
        reasons.append("no edit-time pairs (legacy vs current)")
    elif (
        metrics.edit_time_reduction_rate is None
        or metrics.edit_time_reduction_rate < VQ008_EDIT_TIME_REDUCTION_RATE
    ):
        reasons.append(
            f"edit_time_reduction_rate {metrics.edit_time_reduction_rate} "
            f"< {VQ008_EDIT_TIME_REDUCTION_RATE}"
        )
    return reasons


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "build_blind_session",
    "build_blind_trial",
    "compute_blind_metrics",
    "evaluate_vq008_beta_gate",
    "load_session",
    "reviewer_facing_pack",
    "save_session",
    "sealed_key",
]
