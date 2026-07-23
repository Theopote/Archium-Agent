#!/usr/bin/env python3
"""CI security audit gate with JSON allowlist support.

Usage:
  python scripts/ci_security_audit_gate.py <true|false> pip
  python scripts/ci_security_audit_gate.py <true|false> npm --omit=dev --prefix PATH
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_ALLOWLIST = _ROOT / "docs" / "security" / "dependency-allowlist.json"


def _load_allowlist() -> set[str]:
    if not _ALLOWLIST.is_file():
        return set()
    payload = json.loads(_ALLOWLIST.read_text(encoding="utf-8"))
    today = date.today()
    allowed: set[str] = set()
    for entry in payload.get("entries") or []:
        expires = str(entry.get("expires_on") or "").strip()
        if expires:
            try:
                if date.fromisoformat(expires) < today:
                    continue
            except ValueError:
                continue
        for key in ("id", "aliases"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                allowed.add(value.strip())
            elif isinstance(value, list):
                allowed.update(str(item).strip() for item in value if str(item).strip())
    return allowed


def _pip_findings() -> list[dict[str, Any]]:
    report = _ROOT / "pip-audit-enforce.json"
    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "-f",
        "json",
        "--desc",
        "on",
        "-o",
        str(report),
    ]
    proc = subprocess.run(cmd, cwd=_ROOT, capture_output=True, text=True)
    # pip-audit exits non-zero when vulns exist; still parse the JSON file.
    text = report.read_text(encoding="utf-8") if report.is_file() else (proc.stdout or "[]")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode or 1) from exc
    # Keep a human-readable copy for artifacts.
    readable = _ROOT / "pip-audit-enforce.txt"
    lines: list[str] = []
    findings: list[dict[str, Any]] = []
    deps = payload.get("dependencies", payload if isinstance(payload, list) else [])
    for dep in deps:
        for vuln in dep.get("vulns") or []:
            item = {
                "package": dep.get("name"),
                "version": dep.get("version"),
                "id": vuln.get("id"),
                "aliases": list(vuln.get("aliases") or []),
            }
            findings.append(item)
            lines.append(
                f"{item['package']}=={item['version']} {item['id']} aliases={item['aliases']}"
            )
    readable.write_text("\n".join(lines) + ("\n" if lines else "No findings.\n"), encoding="utf-8")
    print(readable.read_text(encoding="utf-8"), end="")
    return findings


def _npm_findings(extra_args: list[str]) -> tuple[int, str]:
    cmd = ["npm", "audit", "--audit-level=high", *extra_args]
    proc = subprocess.run(cmd, cwd=_ROOT, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    path = _ROOT / "npm-audit-enforce.txt"
    path.write_text(out, encoding="utf-8")
    print(out, end="")
    return proc.returncode, out


def _filter_pip(findings: list[dict[str, Any]], allowed: set[str]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for item in findings:
        ids = {str(item.get("id") or "")}
        ids.update(str(alias) for alias in item.get("aliases") or [])
        ids.discard("")
        if ids & allowed:
            continue
        blocked.append(item)
    return blocked


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    enforce = argv[0].lower() == "true"
    target = argv[1]
    extra = argv[2:]
    allowed = _load_allowlist()

    if target == "pip":
        findings = _pip_findings()
        blocked = _filter_pip(findings, allowed)
        if not blocked:
            return 0
        print(f"Blocked findings ({len(blocked)}):", file=sys.stderr)
        for item in blocked:
            print(f"  - {item}", file=sys.stderr)
        if enforce:
            print(
                "::error::High/critical Python dependency vulnerabilities must be "
                "resolved or allowlisted (see docs/security/).",
                file=sys.stderr,
            )
            return 1
        print(
            "::warning title=Security observation period::Python audit findings "
            "detected; CI stays green until enforcement. See docs/ci-security-audit.md.",
            file=sys.stderr,
        )
        return 0

    if target == "npm":
        code, _out = _npm_findings(extra)
        if code == 0:
            return 0
        if enforce:
            print(
                "::error::High/critical npm vulnerabilities must be resolved before merge.",
                file=sys.stderr,
            )
            return code
        print(
            "::warning title=Security observation period::npm audit findings detected; "
            "CI stays green until enforcement. See docs/ci-security-audit.md.",
            file=sys.stderr,
        )
        return 0

    print(f"Unknown target: {target}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
