#!/usr/bin/env python3
"""Scaffold a Beta rehearsal session directory with CSV templates + meta."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES = _PROJECT_ROOT / "docs" / "templates"
_SESSIONS_ROOT = _PROJECT_ROOT / "docs" / "rehearsal" / "sessions"

_SESSION_META_TEMPLATE = {
    "session_id": "",
    "date": "",
    "facilitator": "",
    "project_label_redacted": "",
    "participants": [
        {
            "participant_id": "P1",
            "role": "",
            "is_non_developer": True,
            "notes": "",
        }
    ],
    "playbook": "A",
    "status": "scheduled",
    "b10_checklist": {
        "import_generate_edit_export": False,
        "edit_cost_coverage_gte_80pct": False,
        "critical_high_triaged": False,
        "summary_json_written": False,
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session_id",
        help="Session folder name, e.g. 2026-07-24-session1",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing CSV / meta templates in the session folder",
    )
    args = parser.parse_args(argv)

    session_dir = _SESSIONS_ROOT / args.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name in ("beta-edit-cost-sheet.csv", "beta-issue-triage.csv"):
        source = _TEMPLATES / name
        target = session_dir / name
        if target.exists() and not args.force:
            print(f"Skip (exists): {target}", file=sys.stderr)
            continue
        shutil.copy2(source, target)
        copied.append(name)

    meta_path = session_dir / "session-meta.json"
    if not meta_path.exists() or args.force:
        meta = dict(_SESSION_META_TEMPLATE)
        meta["session_id"] = args.session_id
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        copied.append("session-meta.json")

    readme = session_dir / "README.txt"
    if not readme.exists() or args.force:
        readme.write_text(
            f"Session: {args.session_id}\n"
            "1. Fill session-meta.json (non-dev participant role).\n"
            "2. Fill beta-edit-cost-sheet.csv and beta-issue-triage.csv during rehearsal.\n"
            f"3. python scripts/summarize_beta_rehearsal.py {session_dir.as_posix()}\n"
            "B10 requires a real non-developer participant — do not fabricate rows.\n",
            encoding="utf-8",
        )

    try:
        rel = session_dir.relative_to(_PROJECT_ROOT)
        print(f"Session directory: {rel}")
    except ValueError:
        print(f"Session directory: {session_dir}")

    if copied:
        print("Copied:", ", ".join(copied))
    try:
        display = session_dir.relative_to(_PROJECT_ROOT)
    except ValueError:
        display = session_dir
    print(
        "\nNext:\n"
        "  1. Open docs/v0.2-beta-rehearsal-facilitator-checklist.md\n"
        "  2. Share docs/v0.2-beta-rehearsal-participant-guide.md with users\n"
        "  3. Fill session-meta.json (is_non_developer=true)\n"
        f"  4. After session: python scripts/summarize_beta_rehearsal.py {display.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
