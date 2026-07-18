# CI Security Audit

The `security-scan` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs **pip-audit** (Python deps from `pip install -e ".[full,dev]"`) and **npm audit** (PptxGenJS production deps).

## Two-phase policy

| Phase | When | CI behavior |
|-------|------|-------------|
| **Observation** | Now → **2026-08-08** (UTC) | Full reports uploaded as artifacts; high/critical findings emit `::warning` but **do not fail** the job |
| **Enforcement** | From **2026-08-08**, or earlier if toggled | high/critical findings **fail** the job and block merge (once branch protection requires this check) |

Workflow knobs (top of `ci.yml`):

```yaml
env:
  SECURITY_AUDIT_ENFORCE: "false"          # set "true" to enforce before the date
  SECURITY_AUDIT_ENFORCE_AFTER: "2026-08-08"
```

After the observation window, enforcement also turns on automatically when the run date is on or after `SECURITY_AUDIT_ENFORCE_AFTER`.

## What gets blocked

Only **high** and **critical** severities:

- Python: `pip-audit --min-severity high` (requires `pip-audit>=2.8`)
- npm: `npm audit --audit-level=high --omit=dev` (PptxGenJS tree)

Low/medium advisories stay in the full report artifact for triage but do not fail CI.

## Artifacts

Each run uploads `security-audit-reports` (7-day retention):

- `pip-audit-report.txt` — full pip-audit output (`--desc on`)
- `pip-audit-enforce.txt` — high/critical gate output
- `npm-audit-report.txt` — full npm audit
- `npm-audit-enforce.txt` — high/critical gate output

Download from the Actions run → **Artifacts** when investigating warnings during observation.

## Observation checklist (before flipping enforcement)

Run at least **2–3 weeks** of green main-branch CI and confirm:

1. No recurring high/critical hits that are accepted false positives (transitive deps with no fix, dev-only noise misclassified, etc.).
2. On-call knows how to read artifacts and open upgrade PRs within SLA.
3. Branch protection lists `security audit` as a required check **after** enforcement is enabled.

## Handling false positives

Prefer fixing or upgrading dependencies. If a finding is a documented accepted risk:

1. Record rationale in the PR that adds the ignore.
2. Python: `pip-audit --ignore-vuln GHSA-…` in the gate step (narrow, advisory-specific).
3. npm: `npm audit fix` or overrides in `package.json` / lockfile — avoid blanket `audit-level` downgrades.

Re-evaluate ignores quarterly; remove when upstream fixes land.

## Local reproduction

```bash
pip install -e ".[full,dev]"
pip install "pip-audit>=2.8"
pip-audit --desc on
pip-audit --min-severity high --desc on

cd archium/infrastructure/renderers/pptxgen
npm ci
npm audit --omit=dev
npm audit --omit=dev --audit-level=high

# Simulate CI gate (observation mode)
bash scripts/ci_security_audit_gate.sh false pip
bash scripts/ci_security_audit_gate.sh false npm --omit=dev --prefix archium/infrastructure/renderers/pptxgen
```
