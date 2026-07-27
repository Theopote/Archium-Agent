#!/usr/bin/env python3
"""Run automated gate for user-task Playbook E (Studio HITL).

Mapped in ``docs/user-task-playbooks.md``. Does not replace human E1–E5 rehearsal.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Service/command coverage for select → geometry → undo → studio chain.
# Human browser clicks (UI-006) are still required to close the playbook.
_DEFAULT_TARGETS = [
    "tests/unit/ui/test_ui_selection_contracts.py",
    "tests/unit/ui/test_undo_stack.py",
    "tests/application/test_scene_undo_service.py",
    "tests/unit/visual/test_studio_geometry_commands.py",
    "tests/integration/studio/test_studio_e2e_smoke.py",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Pass -q to pytest.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Extra args forwarded to pytest (e.g. -- -k undo).",
    )
    args = parser.parse_args(argv)

    extra = list(args.pytest_args)
    if extra and extra[0] == "--":
        extra = extra[1:]

    cmd = [sys.executable, "-m", "pytest", *_DEFAULT_TARGETS, "-v"]
    if args.quiet:
        cmd.append("-q")
    if extra:
        cmd.extend(extra)

    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=_ROOT)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
