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

## Current snapshot (local, 2026-07-23)

`pip-audit` against the developer env reported **24** advisories in **4** packages (not yet all pinned to the lockfile set):

| Package | Example IDs | Proposed action | Owner | Due |
|---------|-------------|-----------------|-------|-----|
| `pillow` 12.2.0 | CVE-2026-54059 / GHSA-8v84-… (many) | Bump floor + recompile locks | maintainers | 2026-08-01 |
| `chromadb` 1.5.5+ | CVE-2026-45829 / GHSA-f4j7-… | Upgrade chromadb or document accepted risk | maintainers | 2026-08-01 |
| `setuptools` | CVE-2026-59890 | Ensure CI uses patched setuptools (build tool) | maintainers | 2026-08-01 |
| `torch` (transitive) | CVE-2025-3000 | Confirm whether needed at runtime; upgrade or exclude | maintainers | 2026-08-01 |

`npm audit --omit=dev` (PptxGenJS): **0** vulnerabilities (2026-07-23).

## Allowlist rules

Only add an entry when:

1. No fixed release exists **or** upgrade is blocked by a documented compatibility issue.
2. `rationale`, `risk_owner`, and `expires_on` (≤ 90 days) are filled.
3. A follow-up issue/PR link is recorded in `ticket`.

Do **not** dump the current pillow/chromadb list into the allowlist without attempting upgrades first.

## Checklist before enforcement

- [ ] Recompile `requirements/full-py311.lock` / `full-py312.lock` after Pillow/chromadb bumps
- [ ] Green `python scripts/ci_security_audit_gate.py true pip` locally
- [ ] Green npm gate locally
- [ ] Allowlist empty **or** every entry has expiry ≤ 2026-10-01 and an owner
- [ ] Branch protection requires `security audit` after flipping enforce
- [ ] Optional early flip: set `SECURITY_AUDIT_ENFORCE: "true"` once green
