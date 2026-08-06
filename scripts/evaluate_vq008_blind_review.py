#!/usr/bin/env python3
"""Evaluate VQ-008 Architect Blind Review Beta gate from a session JSON.

Usage:
  py -3 scripts/evaluate_vq008_blind_review.py path/to/session.json
  py -3 scripts/evaluate_vq008_blind_review.py --scaffold out_dir
  py -3 scripts/evaluate_vq008_blind_review.py session.json --import-ballots r01.json
  py -3 scripts/evaluate_vq008_blind_review.py session.json --validate
  py -3 scripts/evaluate_vq008_blind_review.py session.json --ballot-template architect_01

Exit code 0 only when the Beta visual gate passes (all thresholds met).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archium.application.visual.architect_blind_review_service import (  # noqa: E402
    ballot_template_for_reviewer,
    evaluate_vq008_beta_gate,
    load_ballots,
    load_session,
    materialize_vq008_pack,
    merge_ballots,
    save_session,
    validate_session_ballots,
)


def _write_gate_report(gate, path: Path) -> None:
    payload = {
        "summary": gate.summary(),
        "passed": gate.passed,
        "beta_allowed": gate.beta_allowed,
        "blocking_reasons": gate.blocking_reasons,
        "metrics": gate.metrics.model_dump(mode="json"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", nargs="?", help="Path to BlindReviewSession JSON")
    parser.add_argument(
        "--scaffold",
        type=Path,
        help="Create sealed session + reviewer pack (default: 8-trial P0 pack)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="With --scaffold: use 2-trial demo pack instead of P0",
    )
    parser.add_argument(
        "--import-ballots",
        type=Path,
        action="append",
        default=[],
        metavar="PATH",
        help="Merge ballots from reviewer JSON into session (repeatable)",
    )
    parser.add_argument(
        "--replace-reviewer",
        action="store_true",
        help="With --import-ballots: overwrite existing ballots for same reviewer",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate ballots only; do not evaluate Beta gate",
    )
    parser.add_argument(
        "--ballot-template",
        metavar="REVIEWER_ID",
        help="Print empty ballot template JSON for one architect",
    )
    parser.add_argument(
        "--write-report",
        type=Path,
        help="Write gate evaluation JSON report to this path",
    )
    args = parser.parse_args(argv)

    if args.scaffold is not None:
        if args.demo:
            from archium.application.visual.architect_blind_review_service import (
                _demo_cases,
                build_blind_session,
                reviewer_facing_pack,
                save_session,
                sealed_key,
            )

            out_dir = args.scaffold
            session = build_blind_session(cases=_demo_cases(), seed=42)
            out_dir.mkdir(parents=True, exist_ok=True)
            save_session(session, out_dir / "session.sealed.json")
            (out_dir / "reviewer_pack.json").write_text(
                json.dumps(reviewer_facing_pack(session), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            (out_dir / "sealed_key.json").write_text(
                json.dumps(sealed_key(session), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            materialize_vq008_pack(args.scaffold, p0=True)
        print(f"Scaffolded VQ-008 pack under {args.scaffold}")
        return 0

    if not args.session:
        parser.error("session path required (or use --scaffold)")

    session = load_session(args.session)
    session_path = Path(args.session)

    if args.ballot_template:
        template = ballot_template_for_reviewer(session, args.ballot_template)
        print(json.dumps(template, ensure_ascii=False, indent=2))
        return 0

    for ballot_path in args.import_ballots:
        incoming = load_ballots(ballot_path)
        session = merge_ballots(
            session,
            incoming,
            replace_reviewer=args.replace_reviewer,
        )
        save_session(session, session_path)
        print(f"Imported {len(incoming)} ballot(s) from {ballot_path}")

    if args.validate:
        errors = validate_session_ballots(session)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
            return 2
        print(json.dumps({"valid": True, "ballot_count": len(session.ballots)}, indent=2))
        return 0

    ballot_errors = validate_session_ballots(session)
    gate = evaluate_vq008_beta_gate(session)
    payload = {
        "summary": gate.summary(),
        "passed": gate.passed,
        "beta_allowed": gate.beta_allowed,
        "blocking_reasons": gate.blocking_reasons,
        "ballot_validation_errors": ballot_errors,
        "metrics": gate.metrics.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.write_report:
        _write_gate_report(gate, args.write_report)
        print(f"Wrote report to {args.write_report}")
    if ballot_errors and not gate.beta_allowed:
        return 1
    return 0 if gate.beta_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
