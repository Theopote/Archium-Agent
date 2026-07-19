# Quality Gate Status (honest snapshot)

Last updated: 2026-07-20

This document states what is **proven by automation** vs what still requires **human rehearsal** or **real project delivery**.

## Architectural Slide Benchmark (30 cases)

| Gate | Status | Evidence |
|------|--------|----------|
| Layout rule quality | **Passed** | `rule_pass_rate = 1.0` (30/30) |
| Manual human visual review | **Not started** | `manual_human_review_count = 0` |
| Manual delivery acceptance | **Not started** | `manual_human_accepted_count = 0` |
| Placeholder reviews | 30 | `source=placeholder` in each `human_review.json` |
| Human quality gate | **Failed** | `human_quality_gate_passed = false` |

Report: `tests/benchmark/architectural_slides/reports/benchmark-summary.json`

**What automation proves:** geometry, overflow, hero sizing, whitespace rules, Deck QA scores.

**What automation does not prove:** information hierarchy, aesthetic finish, architect willingness to deliver, editability in practice.

**How to complete:** use Settings →「建筑幻灯片基准 · 人工视觉评审」or edit each case's `human_review.json` with `"source": "manual"`, `"reviewer"`, `"reviewed_at"`, and real scores.

## Real Project Acceptance (5 scenarios)

| Gate | Status | Evidence |
|------|--------|----------|
| Automated pipeline (content + visual) | **Runnable** | `pytest tests/e2e/real_projects -m real_project_acceptance` |
| Stored acceptance records | **Baseline only** | `tests/e2e/real_projects/records/*/acceptance_record.json` |
| Manual human rehearsal | **Not completed** | `human_metrics_source != studio_manual` on all records |
| Human rehearsal gate | **Failed** | `human_rehearsal_passed = false` |
| Verifiable real deliverables | **Not published** | no sanitized `files/<project_id>/` drop-ins; no signed-off PPTX/PDF bundle |

**What automation proves:** five desensitized scenarios can run end-to-end with mock LLM; slide/asset counts and layout validation metrics.

**What automation does not prove:** real client-ready decks, live edit time, export ratios from human sessions.

**How to complete:**

1. Add sanitized files under `tests/e2e/real_projects/files/<project_id>/`
2. Run live rehearsal; capture Studio manual reviews per slide
3. Re-run `UPDATE_REAL_PROJECT_ACCEPTANCE_RECORDS=1 python scripts/run_real_project_acceptance.py --update`
4. Set `human_metrics_source=studio_manual` and `human_rehearsal_passed=true` only after review

## Recent engineering focus (does not close human gates)

Recent work improved **wiring and honesty**, not human sign-off:

- E2E Benchmark M1–M5 (lite → content → visual → PPTX → nightly gate)
- Canvas preview / build reliability
- NLP composite transactions
- Project management service layer
- LLM structured output fixes
- Test and CI cleanup

None of the above substitutes for 30 manual benchmark reviews or five real-project rehearsal sign-offs.
