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

# Product visual-acceptance KPIs (architect edit cost).
KPI_KEEP_RATE_TARGET = 0.50
KPI_AVG_MINUTES_PER_SLIDE_TARGET = 3.0
KPI_SEVERE_LAYOUT_ERRORS_TARGET = 0
KPI_DECK_EDIT_MINUTES_TARGET = 45.0
KPI_EXPECTED_DECK_SLIDES = 20
KPI_SLIDE_COVERAGE_TARGET = 0.80


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"yes", "y", "true", "1"}


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


def _unique_slide_count(edit_rows: list[dict[str, str]]) -> int:
    """Count distinct slides; fall back to row count when index is missing."""
    keys: set[str] = set()
    for row in edit_rows:
        index = str(row.get("slide_index", "")).strip()
        title = str(row.get("slide_title", "")).strip()
        if index:
            keys.add(f"idx:{index}")
        elif title:
            keys.add(f"title:{title}")
        else:
            keys.add(f"row:{len(keys)}")
    return len(keys) if keys else 0


def compute_product_kpis(
    edit_rows: list[dict[str, str]],
    *,
    expected_deck_slides: int = KPI_EXPECTED_DECK_SLIDES,
) -> dict[str, object]:
    """Derive keep-rate / edit-cost KPIs from edit-cost sheet rows.

    Keep = distinct slide with total minutes_spent == 0 and no blocking_export.
    Severe layout error = layout category row with blocking_export=yes.
    """
    per_slide: dict[str, dict[str, object]] = {}
    severe_layout_errors = 0

    for i, row in enumerate(edit_rows):
        index = str(row.get("slide_index", "")).strip()
        title = str(row.get("slide_title", "")).strip()
        if index:
            key = f"idx:{index}"
        elif title:
            key = f"title:{title}"
        else:
            key = f"row:{i}"

        category = row.get("edit_category", "other").strip().lower()
        if category not in _EDIT_CATEGORIES:
            category = "other"
        try:
            minutes = float(row.get("minutes_spent", "0") or 0)
        except ValueError:
            minutes = 0.0
        blocking = _truthy(row.get("blocking_export"))

        bucket = per_slide.setdefault(
            key,
            {"minutes": 0.0, "blocking": False, "categories": set()},
        )
        bucket["minutes"] = float(bucket["minutes"]) + minutes
        bucket["blocking"] = bool(bucket["blocking"]) or blocking
        categories = bucket["categories"]
        assert isinstance(categories, set)
        categories.add(category)

        if category == "layout" and blocking:
            severe_layout_errors += 1

    slides_logged = len(per_slide)
    keep_slides = sum(
        1
        for data in per_slide.values()
        if float(data["minutes"]) == 0.0 and not bool(data["blocking"])
    )
    total_minutes = sum(float(data["minutes"]) for data in per_slide.values())
    keep_rate = round(keep_slides / slides_logged, 4) if slides_logged else 0.0
    avg_minutes = round(total_minutes / slides_logged, 2) if slides_logged else 0.0
    deck_minutes = round(total_minutes, 2)
    coverage = (
        round(slides_logged / expected_deck_slides, 4) if expected_deck_slides > 0 else 0.0
    )

    checks = {
        "keep_rate": keep_rate >= KPI_KEEP_RATE_TARGET,
        "avg_minutes_per_slide": avg_minutes <= KPI_AVG_MINUTES_PER_SLIDE_TARGET,
        "severe_layout_errors": severe_layout_errors <= KPI_SEVERE_LAYOUT_ERRORS_TARGET,
        "deck_edit_minutes": deck_minutes <= KPI_DECK_EDIT_MINUTES_TARGET,
        "slide_coverage": coverage >= KPI_SLIDE_COVERAGE_TARGET,
    }
    return {
        "keep_slides": keep_slides,
        "slides_logged_unique": slides_logged,
        "keep_rate": keep_rate,
        "avg_minutes_per_slide": avg_minutes,
        "severe_layout_errors": severe_layout_errors,
        "deck_edit_minutes": deck_minutes,
        "expected_deck_slides": expected_deck_slides,
        "slide_coverage": coverage,
        "targets": {
            "keep_rate": KPI_KEEP_RATE_TARGET,
            "avg_minutes_per_slide": KPI_AVG_MINUTES_PER_SLIDE_TARGET,
            "severe_layout_errors": KPI_SEVERE_LAYOUT_ERRORS_TARGET,
            "deck_edit_minutes": KPI_DECK_EDIT_MINUTES_TARGET,
            "slide_coverage": KPI_SLIDE_COVERAGE_TARGET,
        },
        "kpi_checks": checks,
        "kpi_pass": all(checks.values()) if slides_logged > 0 else False,
    }


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
        if _truthy(row.get("blocking_export")):
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
    expected_slides = int(meta.get("expected_deck_slides") or KPI_EXPECTED_DECK_SLIDES)
    product_kpis = compute_product_kpis(edit_rows, expected_deck_slides=expected_slides)
    return {
        "session_id": session_id,
        "session_dir": session_dir.as_posix(),
        "status": meta.get("status", ""),
        "playbook": meta.get("playbook", "A"),
        "non_dev_participants_declared": len(non_dev_from_meta),
        "edit_rows": len(edit_rows),
        "slides_logged": slide_count,
        "slides_logged_unique": _unique_slide_count(edit_rows),
        "total_edit_minutes": round(total_minutes, 2),
        "minutes_by_category": dict(minutes_by_category),
        "minutes_by_participant": dict(minutes_by_participant),
        "blocking_export_pages": blocking_pages,
        "issue_triage_counts": dict(triage_counts),
        "open_beta_blockers": open_beta_blockers,
        "product_kpis": product_kpis,
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

    # Aggregate product KPIs across sessions (sum minutes / unique slides).
    keep_slides = 0
    unique_slides = 0
    severe_layout = 0
    for summary in session_summaries:
        kpis = summary.get("product_kpis")
        if not isinstance(kpis, dict):
            continue
        keep_slides += int(kpis.get("keep_slides", 0) or 0)
        unique_slides += int(kpis.get("slides_logged_unique", 0) or 0)
        severe_layout += int(kpis.get("severe_layout_errors", 0) or 0)
    keep_rate = round(keep_slides / unique_slides, 4) if unique_slides else 0.0
    avg_minutes = round(total_minutes / unique_slides, 2) if unique_slides else 0.0
    coverage = (
        round(unique_slides / KPI_EXPECTED_DECK_SLIDES, 4) if unique_slides else 0.0
    )
    product_kpis = {
        "keep_slides": keep_slides,
        "slides_logged_unique": unique_slides,
        "keep_rate": keep_rate,
        "avg_minutes_per_slide": avg_minutes,
        "severe_layout_errors": severe_layout,
        "deck_edit_minutes": round(total_minutes, 2),
        "expected_deck_slides": KPI_EXPECTED_DECK_SLIDES,
        "slide_coverage": coverage,
        "targets": {
            "keep_rate": KPI_KEEP_RATE_TARGET,
            "avg_minutes_per_slide": KPI_AVG_MINUTES_PER_SLIDE_TARGET,
            "severe_layout_errors": KPI_SEVERE_LAYOUT_ERRORS_TARGET,
            "deck_edit_minutes": KPI_DECK_EDIT_MINUTES_TARGET,
            "slide_coverage": KPI_SLIDE_COVERAGE_TARGET,
        },
        "kpi_checks": {
            "keep_rate": keep_rate >= KPI_KEEP_RATE_TARGET,
            "avg_minutes_per_slide": avg_minutes <= KPI_AVG_MINUTES_PER_SLIDE_TARGET,
            "severe_layout_errors": severe_layout <= KPI_SEVERE_LAYOUT_ERRORS_TARGET,
            "deck_edit_minutes": total_minutes <= KPI_DECK_EDIT_MINUTES_TARGET,
            "slide_coverage": coverage >= KPI_SLIDE_COVERAGE_TARGET,
        },
    }
    product_kpis["kpi_pass"] = bool(unique_slides) and all(
        product_kpis["kpi_checks"].values()  # type: ignore[union-attr]
    )

    return {
        "sessions": session_summaries,
        "participants_non_dev": participants_non_dev,
        "total_edit_minutes": round(total_minutes, 2),
        "open_beta_blocker_count": len(open_blockers),
        "open_beta_blockers": open_blockers,
        "beta_ready_by_user_data": (
            participants_non_dev >= 1 and total_minutes > 0 and len(open_blockers) == 0
        ),
        "product_kpis": product_kpis,
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
