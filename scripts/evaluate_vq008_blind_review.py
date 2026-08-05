#!/usr/bin/env python3
"""Evaluate VQ-008 Architect Blind Review Beta gate from a session JSON.

Usage:
  py -3 scripts/evaluate_vq008_blind_review.py path/to/session.json
  py -3 scripts/evaluate_vq008_blind_review.py --scaffold out_dir

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
    build_blind_session,
    evaluate_vq008_beta_gate,
    load_session,
    reviewer_facing_pack,
    save_session,
    sealed_key,
)


def _scaffold(out_dir: Path) -> int:
    cases = [
        {
            "case_id": "demo_cover",
            "title": "封面（示例）",
            "legacy_asset": "assets/legacy/cover.png",
            "current_asset": "assets/current/cover.png",
            "reference_asset": "assets/reference/cover.png",
            "page_kind": "cover",
        },
        {
            "case_id": "demo_analysis",
            "title": "现状分析（示例）",
            "legacy_asset": "assets/legacy/analysis.png",
            "current_asset": "assets/current/analysis.png",
            "reference_asset": "assets/reference/analysis.png",
            "page_kind": "analysis",
        },
    ]
    session = build_blind_session(cases=cases, seed=42)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_session(session, out_dir / "session.sealed.json")
    (out_dir / "reviewer_pack.json").write_text(
        json.dumps(reviewer_facing_pack(session), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "sealed_key.json").write_text(
        json.dumps(sealed_key(session), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "README.txt").write_text(
        "1. 把 reviewer_pack.json + 截图发给 ≥5 名建筑师（勿发 sealed_key）。\n"
        "2. 收集 ballots 写回 session.sealed.json 的 ballots 数组。\n"
        "3. 运行: py -3 scripts/evaluate_vq008_blind_review.py session.sealed.json\n"
        "4. 仅当 exit 0 且 beta_allowed=true 时，VQ-008 视觉硬门才可清。\n",
        encoding="utf-8",
    )
    print(f"Scaffolded VQ-008 pack under {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", nargs="?", help="Path to BlindReviewSession JSON")
    parser.add_argument(
        "--scaffold",
        type=Path,
        help="Create an empty sealed session + reviewer pack in this directory",
    )
    args = parser.parse_args(argv)
    if args.scaffold is not None:
        return _scaffold(args.scaffold)
    if not args.session:
        parser.error("session path required (or use --scaffold)")
    session = load_session(args.session)
    gate = evaluate_vq008_beta_gate(session)
    payload = {
        "summary": gate.summary(),
        "passed": gate.passed,
        "beta_allowed": gate.beta_allowed,
        "blocking_reasons": gate.blocking_reasons,
        "metrics": gate.metrics.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if gate.beta_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
