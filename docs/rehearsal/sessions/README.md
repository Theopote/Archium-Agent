# Beta Rehearsal Sessions

Place completed session data here: one folder per session, e.g. `2026-07-24-session1/`.

Required files:

- `session-meta.json` — participant role + B10 checklist (`is_non_developer: true`)
- `beta-edit-cost-sheet.csv`
- `beta-issue-triage.csv`

Scaffold:

```bash
python scripts/new_beta_session.py 2026-07-24-session1
python scripts/summarize_beta_rehearsal.py docs/rehearsal/sessions/2026-07-24-session1/ --output docs/rehearsal/sessions/2026-07-24-session1/summary.json
```

**B10 cannot be closed by engineering alone** — a real non-developer must complete playbook A and fill the CSVs. Do not invent participant rows.

Update [`v0.2-beta-release-decision.md`](../../v0.2-beta-release-decision.md) when B10 is satisfied.
