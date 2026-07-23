# CI Security Audit

The `security-scan` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs **pip-audit** (Python env from `requirements/full-py312.lock`) and **npm audit** (PptxGenJS production deps).

Triage status and allowlist: [`docs/security/`](security/).

## Two-phase policy

| Phase | When | CI behavior |
|-------|------|-------------|
| **Observation** | Now → **2026-08-08** (UTC) | Full reports uploaded as artifacts; findings emit `::warning` but **do not fail** the job |
| **Enforcement** | From **2026-08-08**, or earlier if toggled | Non-allowlisted findings **fail** the job and block merge (once branch protection requires this check) |

Workflow knobs (top of `ci.yml`):

```yaml
env:
  SECURITY_AUDIT_ENFORCE: "false"          # set "true" to enforce before the date
  SECURITY_AUDIT_ENFORCE_AFTER: "2026-08-08"
```

**Do not wait until Aug 8:** complete the [triage checklist](security/AUDIT_TRIAGE_2026-07.md) by **2026-08-01**.

## Fail levels & allowlist

- **Python:** any `pip-audit` finding not listed in [`dependency-allowlist.json`](security/dependency-allowlist.json) (PyPI JSON often lacks severity, so we gate all reported vulns).
- **Node:** `npm audit --audit-level=high`.
- Allowlist entries require `id`/`aliases`, `risk_owner`, `expires_on`, and a short rationale. Expired entries are ignored.

Gate command:

```bash
python scripts/ci_security_audit_gate.py true pip
python scripts/ci_security_audit_gate.py true npm --omit=dev --prefix archium/infrastructure/renderers/pptxgen
```

## Artifacts

Each run uploads `security-audit-reports` (7-day retention), including allowlist snapshot and enforce outputs.

## Local reproduction

```bash
# Prefer a clean venv so local torch/setuptools pollution is not audited.
pip install "setuptools>=83.0.0"
pip install -r requirements/full-py312.lock
pip install -e ".[dev]" --constraint requirements/full-py312.lock
pip install "pip-audit>=2.8"
python scripts/ci_security_audit_gate.py false pip

cd archium/infrastructure/renderers/pptxgen && npm ci
python ../../../../scripts/ci_security_audit_gate.py false npm --omit=dev --prefix archium/infrastructure/renderers/pptxgen
```

`torch` is **not** in `requirements/*.lock`. If a developer env still reports torch CVEs, upgrade to `torch>=2.13.0` or uninstall it; do not allowlist it for CI.
