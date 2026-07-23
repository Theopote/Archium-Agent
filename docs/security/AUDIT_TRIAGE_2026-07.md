# Dependency security triage (2026-07-23)

**Risk owner:** Archium maintainers  
**Enforcement date:** `SECURITY_AUDIT_ENFORCE_AFTER=2026-08-08` (CI auto-enforces on/after this UTC date)  
**Checkpoint:** complete triage + upgrades/allowlist by **2026-08-01** so `master` does not go red on Aug 8.

## Fail policy

When enforcement is on, CI fails on any **non-allowlisted** finding from:

| Gate | Scope | Tool |
|------|--------|------|
| Python | Installed env after `requirements/full-py312.lock` + editable | `pip-audit -f json` (all reported vulns; no reliable severity field from PyPI service) |
| Node | PptxGenJS production tree | `npm audit --audit-level=high --omit=dev` |

Allowlist file: [`dependency-allowlist.json`](dependency-allowlist.json)  
Gate: `python scripts/ci_security_audit_gate.py <enforce:true|false> pip|npm …`

## Current snapshot (lock-aligned, 2026-07-23)

Clean venv from `requirements/full-py312.lock` + editable: **1** finding (`chromadb` / CVE-2026-45829), covered by allowlist. Developer envs that also install `torch`/`setuptools` may report extra CVEs that are **not** in the product lock.

| Package | Status | Action taken |
|---------|--------|--------------|
| `pillow` | **Cleared** at `12.3.0` in `full-py31{1,2}.lock` | Floor `Pillow>=12.0`; locks recompiled |
| `chromadb` `1.5.9` | **Allowlisted** `GHSA-f4j7-r4q5-qw2c` / CVE-2026-45829 until 2026-10-01 | No newer PyPI release; product uses local `PersistentClient` only (no FastAPI HTTP server) |
| `setuptools` | **CI pin** `>=83.0.0` in `security-scan` + `build-system` | Fixes CVE-2026-59890; not a runtime lock pin |
| `torch` | **Not in product locks** | Local/dev pollution (e.g. torchvision); upgrade to `>=2.13.0` or uninstall if present outside CI |

`npm audit --omit=dev` (PptxGenJS): **0** vulnerabilities (2026-07-23).

## Allowlist rules

Only add an entry when:

1. No fixed release exists **or** upgrade is blocked by a documented compatibility issue.
2. `rationale`, `risk_owner`, and `expires_on` (≤ 90 days) are filled.
3. A follow-up issue/PR link is recorded in `ticket`.

Do **not** dump the current pillow/chromadb list into the allowlist without attempting upgrades first.

## Checklist before enforcement

- [x] Recompile `requirements/full-py311.lock` / `full-py312.lock` after Pillow/chromadb bumps
- [x] Green `python scripts/ci_security_audit_gate.py true pip` on a **clean lock install** (allowlist covers chromadb only)
- [x] Green npm gate locally (`found 0 vulnerabilities`, 2026-07-23)
- [x] Allowlist empty **or** every entry has expiry ≤ 2026-10-01 and an owner
- [ ] Branch protection requires `security audit` after flipping enforce
- [ ] Optional early flip: set `SECURITY_AUDIT_ENFORCE: "true"` once green
