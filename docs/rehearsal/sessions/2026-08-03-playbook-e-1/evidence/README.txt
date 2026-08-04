Local evidence only — do not commit client-sensitive materials or large exports.

Never commit (gitignored):
- `*.pptx` / `*.pdf` (dry-run / browser / E5 exports)

Prefer keeping screenshots out of git when they contain client PII; text/JSON notes and
rehearsal scripts may stay tracked.

Regenerate PPTX by running scripts in this folder (`run_e_dry_run.py`,
`run_rehearsal_e2_e5.py`, etc.). Paths may also appear in
`playbook-e-step-log.csv` `evidence_path`.
