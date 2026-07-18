# Layer 3: Live Model Evaluation

Manual or scheduled runs only. **Not part of default CI.**

## Presentation pipeline (legacy checklist)

See [EVALUATION_CHECKLIST.md](EVALUATION_CHECKLIST.md) for Brief / Storyline / export checks.

## Mission planning — M1–M6 (required next step)

Mock golden cases prove parser / persistence / workflow / bridge. They **do not** prove a real model understands the six tasks. Run a live API pass and score by hand.

### Run

```powershell
# PowerShell
$env:ARCHIUM_LIVE_LLM = "1"
py scripts/eval_mission_live.py
py scripts/eval_mission_live.py --case case_m1_temple
py scripts/eval_mission_live.py --case m6

# or pytest
pytest tests/golden/live/test_live_mission_evaluation.py -v -m live_llm
```

Requires `.env` API keys (`GEMINI_API_KEY` / `LLM_API_KEY`) and a non-mock `llm_provider`.

Artifacts: `tests/golden/artifacts/live_mission/<run_id>/<case_id>/`

| File | Purpose |
|------|---------|
| `result.json` | Full mission / gaps / workstreams / deliverables dump |
| `scorecard.json` | Machine-readable score scaffold |
| `SCORECARD.md` | Human scoring sheet |
| `../SUMMARY.md` | Run index |

### Human rubric (100 pts)

| 指标 | 分值 |
|------|------|
| 任务性质判断 | 15 |
| 尺度与服务深度 | 10 |
| 事实忠实度 | 20 |
| 关键未知识别 | 15 |
| 澄清问题价值 | 15 |
| Workstream 合理性 | 15 |
| Deliverable 合理性 | 10 |

**及格线：单 case ≥ 70。** Critical 自动标记（编造指标 / 专项误判完整设计）出现时，即使总分及格也须复盘。

### 特别观察

- 是否编造面积
- 是否把专项咨询误判成建筑方案
- 是否生成太多无价值问题
- 是否把项目类型当成固定模板
- 是否过度扩大任务范围
- 是否遗漏关键利益相关方

自动启发式会预填 `auto_flags`；人工仍须在 `SCORECARD.md` 勾选并打分。
