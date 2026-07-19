# Real Project Acceptance Tests

Sprint Step 10 — five desensitized real-project acceptance scenarios (15–30 slides, 10+ assets).

## Scenarios

| Manifest | Scenario | Type |
|----------|----------|------|
| `project_001_new_building` | 新建建筑方案汇报 | mixed_use |
| `project_002_renovation` | 既有建筑改造 | urban_renewal |
| `project_003_hospital_school` | 医院/学校专项分析 | education |
| `project_004_government_client` | 政府/甲方决策汇报 | urban_design |
| `project_005_internal_review` | 内部设计评审 | office |

## Run

```bash
pytest tests/e2e/real_projects -v -m real_project_acceptance
```

## Update acceptance records

```bash
UPDATE_REAL_PROJECT_ACCEPTANCE_RECORDS=1 pytest tests/e2e/real_projects -v
python scripts/run_real_project_acceptance.py --update
```

Records are stored under `records/<project_id>/acceptance_record.json`.

Each record includes:

- **Automated metrics** — pipeline success, slide/asset counts, layout validation
- **`human_metrics_source`** — `none` | `layout_qa_derived` | `studio_manual`
- **`human_rehearsal_passed`** — `true` only after live Studio manual reviews

Manual fields (`major_edit_page_ratio`, `average_human_visual_score`, `user_edit_minutes`, etc.) remain **`null`** until a live rehearsal session with `source=manual` Studio reviews. Layout-derived scores are **not** written into acceptance records.

See also: `docs/QUALITY_GATE_STATUS.md`

## Drop-in real files

Optional sanitized files can replace inline fallbacks:

```text
tests/e2e/real_projects/files/<project_id>/...
```

Reference them from each manifest `files[]` entry (same pattern as Layer 2 fixture acceptance).
