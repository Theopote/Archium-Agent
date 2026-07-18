#!/usr/bin/env bash
# Gate CI on high/critical dependency vulnerabilities.
# Usage: ci_security_audit_gate.sh <enforce:true|false> <pip|npm> [extra args...]

set -euo pipefail

enforce="${1:-false}"
target="${2:-}"
shift 2

case "$target" in
  pip)
    set +e
    pip-audit --min-severity high --desc on "$@" 2>&1 | tee -a pip-audit-enforce.txt
    code=$?
    set -e
    ;;
  npm)
    set +e
    npm audit --audit-level=high "$@" 2>&1 | tee -a npm-audit-enforce.txt
    code=$?
    set -e
    ;;
  *)
    echo "Unknown target: $target (expected pip or npm)" >&2
    exit 2
    ;;
esac

if [ "$code" -eq 0 ]; then
  exit 0
fi

if [ "$enforce" = "true" ]; then
  echo "::error::High/critical $target vulnerabilities must be resolved before merge."
  exit "$code"
fi

echo "::warning title=Security observation period::High/critical $target vulnerabilities detected. CI remains green until enforcement; see docs/ci-security-audit.md."
exit 0
