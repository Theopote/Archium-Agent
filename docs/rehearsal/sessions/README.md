# Beta Rehearsal Sessions

Place completed session data here: one folder per session, e.g. `2026-07-18-session1/`.

Required files (copy from [`../templates/`](../templates/)):

- `beta-edit-cost-sheet.csv`
- `beta-issue-triage.csv`

After a session:

```bash
python scripts/summarize_beta_rehearsal.py docs/rehearsal/sessions/2026-07-18-session1/ --output docs/rehearsal/sessions/2026-07-18-session1/summary.json
```

Update [`../v0.2-beta-release-decision.md`](../v0.2-beta-release-decision.md) when B10 is satisfied.
