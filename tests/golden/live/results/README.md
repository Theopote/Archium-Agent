# Live M1–M6 eval batch indexes

Batch JSON files written by `scripts/eval_mission_live.py --repeats 3`
land here (`{batch_id}.json`). Full scorecards remain under
`tests/golden/artifacts/live_mission/<run_id>/`.

Example:

```powershell
$env:ARCHIUM_LIVE_LLM = "1"
py scripts/eval_mission_live.py --repeats 3
```
