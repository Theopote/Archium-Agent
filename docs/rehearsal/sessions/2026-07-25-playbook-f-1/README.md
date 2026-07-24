Playbook F session: 2026-07-25-playbook-f-1

## Summary

First F1–F5 rehearsal for partial-knowledge (Context Intelligence) flow.

| Item | Value |
|------|-------|
| Mode | Engineer service-layer dry-run (mock LLM) |
| UI walkthrough | No — Streamlit not exercised |
| Automated gate | PASS @ commit f456c7e |
| F1–F5 | PASS |
| F6–F7 | Waived |

## How this session was produced

```powershell
py -c "import runpy; runpy.run_path('scripts/run_playbook_f_rehearsal.py', run_name='__main__')" 2026-07-25-playbook-f-1 --force-scaffold
```

## Pending for full Context Intelligence sign-off

- Non-developer operator completes [playbook-f-participant-guide.md](../../playbook-f-participant-guide.md) in Streamlit with real LLM
- Optional F6 vision + F7 evidence gate

Evidence JSON under `evidence/` is safe to commit (standard scenario, no client PII).
