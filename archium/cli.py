"""Archium v0.2 default CLI — launches the Streamlit project workspace."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Absolute path so Windows / non-repo cwd still target the same app.py.
_APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def main() -> None:
    """Launch Streamlit against ``app.py`` (thin wrapper → ``create_application``)."""
    try:
        import streamlit  # noqa: F401
    except ImportError as exc:
        print(
            "Archium requires the UI extra. Install with:\n"
            '  pip install -e ".[full]"',
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(_APP_PATH),
        *sys.argv[1:],
    ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
