#!/usr/bin/env python3
"""Run the automated gate mapped to user-task Playbook A.

This is the repeatable CI/local command for Playbook A automation mapping in
``docs/user-task-playbooks.md``. It does **not** replace human rehearsal for
Beta/Stable tags.

Default suite (fast enough for a local gate):
  - tests/golden/regression
  - tests/golden/mission
  - tests/smoke/test_pptxgen_render.py

Optional ``--with-real-projects`` adds:
  - tests/e2e/real_projects -m real_project_acceptance
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_DEFAULT_TARGETS = [
    "tests/golden/regression",
    "tests/golden/mission",
    "tests/smoke/test_pptxgen_render.py",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-real-projects",
        action="store_true",
        help="Also run real-project acceptance (slower; needs fixtures).",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Extra args forwarded to pytest (after --).",
    )
    args = parser.parse_args(argv)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *_DEFAULT_TARGETS,
        "-v",
    ]
    if args.with_real_projects:
        cmd.extend(
            [
                "tests/e2e/real_projects",
                "-m",
                "real_project_acceptance",
            ]
        )
    if args.pytest_args:
        cmd.extend(args.pytest_args)

    env = os.environ.copy()
    env.setdefault("ARCHIUM_SMOKE_ARTIFACT_DIR", str(_ROOT / "tests" / "smoke" / "artifacts"))

    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=_ROOT, env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
