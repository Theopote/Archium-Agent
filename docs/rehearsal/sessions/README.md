# Beta Rehearsal Sessions

Place completed session data here: one folder per session, e.g. `2026-07-18-session1/`.

Required files (copy from [Beta rehearsal participant guide](../../v0.2-beta-rehearsal-participant-guide.md)):

- `beta-edit-cost-sheet.csv`
- `beta-issue-triage.csv`

After a session:

```bash
python scripts/new_beta_session.py <session_id>
python scripts/summarize_beta_rehearsal.py docs/rehearsal/sessions/<session_id>/ --output docs/rehearsal/sessions/<session_id>/summary.json
```

Update [`v0.2-beta-release-decision.md`](../../v0.2-beta-release-decision.md) when B10 is satisfied.
