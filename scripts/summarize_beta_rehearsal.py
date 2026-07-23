#!/usr/bin/env python3
"""Aggregate Beta rehearsal CSVs into summary.json for release decision."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

_EDIT_CATEGORIES = frozenset(
    {"text", "layout", "image", "fact_citation", "structure", "export", "other"}
)
_TRIAGE_BUCKETS = frozenset({"beta_blocker", "post_beta_improvement", "future_idea"})


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row.get("session_id") and not str(row["session_id"]).startswith("#")
        ]


def _collect_session_dirs(root: Path) -> list[Path]:
    if (root / "beta-edit-cost-sheet.csv").exists():
        return [root]
    return sorted({path.parent for path in root.rglob("beta-edit-cost-sheet.csv")})


def summarize_session(session_dir: Path) -> dict[str, object]:
    edit_rows = _read_csv_rows(session_dir / "beta-edit-cost-sheet.csv")
    issue_rows = _read_csv_rows(session_dir / "beta-issue-triage.csv")
    meta = _read_session_meta(session_dir / "session-meta.json")

    minutes_by_category: Counter[str] = Counter()
    minutes_by_participant: Counter[str] = Counter()
    slide_count = 0
    blocking_pages = 0

    for row in edit_rows:
        category = row.get("edit_category", "other").strip().lower()
        if category not in _EDIT_CATEGORIES:
            category = "other"
        try:
            minutes = float(row.get("minutes_spent", "0") or 0)
        except ValueError:
            minutes = 0.0
        minutes_by_category[category] += minutes
        participant = row.get("participant_id", "unknown").strip()
        minutes_by_participant[participant] += minutes
        slide_count += 1
        if row.get("blocking_export", "").strip().lower() in {"yes", "y", "true", "1"}:
            blocking_pages += 1

    triage_counts: Counter[str] = Counter()
    open_beta_blockers: list[dict[str, str]] = []
    for row in issue_rows:
        bucket = row.get("triage_bucket", "future_idea").strip().lower()
        if bucket not in _TRIAGE_BUCKETS:
            bucket = "future_idea"
        triage_counts[bucket] += 1
        if bucket == "beta_blocker" and row.get("status", "open").strip().lower() == "open":
            open_beta_blockers.append(
                {
                    "issue_id": row.get("issue_id", ""),
                    "summary": row.get("summary", ""),
                    "severity": row.get("severity", ""),
                }
            )

    session_id = (
        str(meta.get("session_id") or "").strip()
        or (edit_rows[0]["session_id"] if edit_rows else session_dir.name)
    )
    total_minutes = sum(minutes_by_category.values())
    non_dev_from_meta = [
        p
        for p in meta.get("participants", [])
        if isinstance(p, dict) and p.get("is_non_developer") is True
    ]
    return {
        "session_id": session_id,
        "session_dir": session_dir.as_posix(),
        "status": meta.get("status", ""),
        "playbook": meta.get("playbook", "A"),
        "non_dev_participants_declared": len(non_dev_from_meta),
        "edit_rows": len(edit_rows),
        "slides_logged": slide_count,
        "total_edit_minutes": round(total_minutes, 2),
        "minutes_by_category": dict(minutes_by_category),
        "minutes_by_participant": dict(minutes_by_participant),
        "blocking_export_pages": blocking_pages,
        "issue_triage_counts": dict(triage_counts),
        "open_beta_blockers": open_beta_blockers,
    }


def _read_session_meta(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_root(root: Path) -> dict[str, object]:
    session_dirs = _collect_session_dirs(root)
    session_summaries = [summarize_session(path) for path in session_dirs]
    participants = {
        participant
        for summary in session_summaries
        for participant in summary.get("minutes_by_participant", {})
    }
    declared_non_dev = sum(
        int(summary.get("non_dev_participants_declared", 0) or 0)
        for summary in session_summaries
    )

    open_blockers: list[dict[str, str]] = []
    for summary in session_summaries:
        open_blockers.extend(summary.get("open_beta_blockers", []))

    total_minutes = sum(float(s.get("total_edit_minutes", 0)) for s in session_summaries)
    # Prefer edit-sheet participants; fall back to session-meta declarations.
    participants_non_dev = max(len(participants), declared_non_dev)
    return {
        "sessions": session_summaries,
        "participants_non_dev": participants_non_dev,
        "total_edit_minutes": round(total_minutes, 2),
        "open_beta_blocker_count": len(open_blockers),
        "open_beta_blockers": open_blockers,
        "beta_ready_by_user_data": (
            participants_non_dev >= 1 and total_minutes > 0 and len(open_blockers) == 0
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=Path("docs/rehearsal/sessions"),
        help="Session directory or parent containing session folders",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write summary JSON (default: stdout)",
    )
    args = parser.parse_args(argv)

    summary = summarize_root(args.root.resolve())
    payload = json.dumps(summary, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
