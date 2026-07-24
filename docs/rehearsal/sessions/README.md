# Beta Rehearsal Sessions

Place completed session data here: one folder per session, e.g. `2026-07-24-session1/`.

## Playbook A (Beta B10)

Required files:

- `session-meta.json` — participant role + B10 checklist (`is_non_developer: true`)
- `beta-edit-cost-sheet.csv`
- `beta-issue-triage.csv`

Scaffold:

```bash
python scripts/new_beta_session.py 2026-07-24-session1
python scripts/summarize_beta_rehearsal.py docs/rehearsal/sessions/2026-07-24-session1/ --output docs/rehearsal/sessions/2026-07-24-session1/summary.json
```

Facilitator guide: [v0.2-beta-rehearsal-facilitator-checklist.md](../v0.2-beta-rehearsal-facilitator-checklist.md)

**B10 cannot be closed by engineering alone** — a real non-developer must complete playbook A and fill the CSVs. Do not invent participant rows.

## Playbook F (Partial Knowledge / Context Intelligence)

Required files:

- `session-meta.json` — F1–F7 step pass flags + `overall_pass`
- `playbook-f-step-log.csv`
- `playbook-f-issues.csv` (if any)
- `evidence/` — local screenshots only; **do not commit** client-sensitive images

Scaffold:

```bash
python scripts/run_playbook_f_gate.py -q
python scripts/new_playbook_f_session.py 2026-07-25-playbook-f-1
python scripts/run_playbook_f_rehearsal.py 2026-07-25-playbook-f-1   # optional engineer dry-run
```

Facilitator guide: [playbook-f-checklist.md](../rehearsal/playbook-f-checklist.md)  
Participant guide (share with operator): [playbook-f-participant-guide.md](../rehearsal/playbook-f-participant-guide.md)

Update [`v0.2-beta-release-decision.md`](../../v0.2-beta-release-decision.md) when B10 is satisfied.
