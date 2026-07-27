#!/usr/bin/env python3
"""Scaffold a Playbook E (Studio HITL) rehearsal session directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES = _PROJECT_ROOT / "docs" / "templates"
_SESSIONS_ROOT = _PROJECT_ROOT / "docs" / "rehearsal" / "sessions"

_SESSION_META_TEMPLATE = {
    "session_id": "",
    "date": "",
    "playbook": "E",
    "status": "scheduled",
    "facilitator": "",
    "operator": "",
    "operator_is_non_developer": True,
    "llm_configured": None,
    "pptx_export_ready": None,
    "project_id": "",
    "project_name": "",
    "automated_gate": {
        "command": "python scripts/run_playbook_e_gate.py -q",
        "passed": False,
        "run_date": "",
        "commit": "",
    },
    "steps": {
        "E1": {"pass": None, "waived": False, "waive_reason": ""},
        "E2": {"pass": None, "waived": False, "waive_reason": ""},
        "E3": {"pass": None, "waived": False, "waive_reason": ""},
        "E4": {"pass": None, "waived": False, "waive_reason": ""},
        "E5": {"pass": None, "waived": False, "waive_reason": ""},
    },
    "overall_pass": False,
    "blockers": [],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session_id",
        help="Session folder name, e.g. 2026-07-27-playbook-e-1",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing templates in the session folder",
    )
    args = parser.parse_args(argv)

    session_dir = _SESSIONS_ROOT / args.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name in ("playbook-e-step-log.csv", "playbook-e-issues.csv"):
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
        meta["date"] = date.today().isoformat()
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        copied.append("session-meta.json")

    gitkeep = session_dir / "evidence"
    gitkeep.mkdir(exist_ok=True)
    evidence_readme = gitkeep / "README.txt"
    if not evidence_readme.exists() or args.force:
        evidence_readme.write_text(
            "Local screenshots only — do not commit sensitive client materials.\n"
            "Reference paths from playbook-e-step-log.csv evidence_path column.\n",
            encoding="utf-8",
        )

    readme = session_dir / "README.txt"
    if not readme.exists() or args.force:
        readme.write_text(
            f"Playbook E session: {args.session_id}\n"
            "1. Follow docs/rehearsal/playbook-e-checklist.md\n"
            "2. Fill playbook-e-step-log.csv and playbook-e-issues.csv\n"
            "3. Update session-meta.json steps / overall_pass when done\n"
            "4. Do not commit evidence/ screenshots with PII\n"
            "5. On pass: close UI-006 / ST-007 with link to this session\n",
            encoding="utf-8",
        )

    try:
        rel = session_dir.relative_to(_PROJECT_ROOT)
        print(f"Session directory: {rel}")
    except ValueError:
        print(f"Session directory: {session_dir}")

    if copied:
        print("Copied:", ", ".join(copied))
    print(
        "\nNext:\n"
        "  1. python scripts/run_playbook_e_gate.py -q\n"
        "  2. Open docs/rehearsal/playbook-e-checklist.md\n"
        "     Share docs/rehearsal/playbook-e-participant-guide.md with operator\n"
        "  3. archium → Studio → walk through E1–E5\n"
        f"  4. Mark session-meta.json overall_pass when E1–E5 are green"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
