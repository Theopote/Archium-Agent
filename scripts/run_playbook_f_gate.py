#!/usr/bin/env python3
"""Run automated gate for user-task Playbook F (partial knowledge projects).

Mapped in ``docs/user-task-playbooks.md``. Does not replace human F1–F7 rehearsal.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_DEFAULT_TARGETS = [
    "tests/integration/test_partial_knowledge_project_flow.py",
    "tests/unit/test_project_context.py",
    "tests/unit/test_project_context_routing.py",
    "tests/unit/test_knowledge_state_routing.py",
    "tests/unit/test_workspace_mode_service.py",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Extra args forwarded to pytest (after --).",
    )
    args = parser.parse_args(argv)

    cmd = [sys.executable, "-m", "pytest", *_DEFAULT_TARGETS, "-v"]
    if args.pytest_args:
        cmd.extend(args.pytest_args)

    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=_ROOT)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
