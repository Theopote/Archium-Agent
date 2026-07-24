#!/usr/bin/env python3
"""Scaffold a Playbook F (partial-knowledge) rehearsal session directory."""

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

_DEFAULT_SCENARIO = (
    "西安市某医院老院区改造，手头有一张老门诊楼照片、"
    "地址和一份旧院区介绍，甲方还没说清功能分区。"
)

_SESSION_META_TEMPLATE = {
    "session_id": "",
    "date": "",
    "playbook": "F",
    "status": "scheduled",
    "facilitator": "",
    "operator": "",
    "operator_is_non_developer": True,
    "llm_configured": None,
    "vision_image_enabled": None,
    "scenario_prompt": _DEFAULT_SCENARIO,
    "automated_gate": {
        "command": "python scripts/run_playbook_f_gate.py -q",
        "passed": False,
        "run_date": "",
        "commit": "",
    },
    "steps": {
        "F1": {"pass": None, "waived": False, "waive_reason": ""},
        "F2": {"pass": None, "waived": False, "waive_reason": ""},
        "F3": {"pass": None, "waived": False, "waive_reason": ""},
        "F4": {"pass": None, "waived": False, "waive_reason": ""},
        "F5": {"pass": None, "waived": False, "waive_reason": ""},
        "F6": {"pass": None, "waived": False, "waive_reason": ""},
        "F7": {"pass": None, "waived": False, "waive_reason": ""},
    },
    "overall_pass": False,
    "blockers": [],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session_id",
        help="Session folder name, e.g. 2026-07-25-playbook-f-1",
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
    for name in ("playbook-f-step-log.csv", "playbook-f-issues.csv"):
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
            "Reference paths from playbook-f-step-log.csv evidence_path column.\n",
            encoding="utf-8",
        )

    readme = session_dir / "README.txt"
    if not readme.exists() or args.force:
        readme.write_text(
            f"Playbook F session: {args.session_id}\n"
            "1. Follow docs/rehearsal/playbook-f-checklist.md\n"
            "2. Fill playbook-f-step-log.csv and playbook-f-issues.csv\n"
            "3. Update session-meta.json steps / overall_pass when done\n"
            "4. Do not commit evidence/ screenshots with PII\n",
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
        "  1. python scripts/run_playbook_f_gate.py -q\n"
        "  2. Open docs/rehearsal/playbook-f-checklist.md\n"
        "     Share docs/rehearsal/playbook-f-participant-guide.md with operator\n"
        "  3. archium → walk through F1–F7\n"
        f"  4. Mark session-meta.json overall_pass when F1–F5 are green"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
