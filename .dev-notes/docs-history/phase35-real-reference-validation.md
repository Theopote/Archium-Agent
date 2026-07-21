# Phase 3.5 Real Reference Deck Validation (local run)

Last run: 2026-07-21 (UTC)

## Source folder

`C:\Users\navib\Desktop\development\参考pptx`

| File (approx.) | Pages |
|----------------|-------|
| 老旧小区改造设计方案.pptx | 76 |
| 南京小西湖城市设计汇报.pptx | 76 |
| 现代简约小西湖… / 现代南京小西湖… | 205–208 |

Runner picks the **smallest** deck (76 pages) unless `--source` is set.

## Automated runs

### Run A — 28 pages (老旧小区改造设计方案, first 28)

- Workspace: `output/phase35-validation/phase35_20260721_073840/`
- **H1 页数/截图：PASS** (28 = 28 = 28 PNG)
- **H3 聚类：PASS** (15 content clusters)
- **H4 图纸：FAIL** (0 Drawing in first 28 pages — plans appear later)
- **H5 代表页：REVIEW** (7 clusters with anomaly/complexity penalty on rep)
- **H6/H7/H9：PASS**
- Auto gate: **NEEDS_REVIEW**

### Run B — 35 pages (same 76-page deck, includes slide 31 drawing)

- Workspace: `output/phase35-validation/phase35_20260721_074113/`
- **H1：PASS** (35 = 35 = 35 PNG)
- **H3：PASS** (19 content clusters)
- **H4：PASS** (1 Drawing on slide 31 — neighbor-text inference)
- **H5：REVIEW** (anomalous representative count > 0 — singleton clusters with parse/low-editability pages)
- Auto gate: **NEEDS_REVIEW**

Re-run checklist markdown + JSON live next to each run:

- `phase35_human_review_checklist.md`
- `phase35_validation_report.json`

## Human review checklist (fill in)

Open Run B workspace in **模板归纳复核** (`st.session_state.template_induction_workspace` = induction folder path).

| ID | Item | Auto (Run B) | Human | Notes |
|----|------|--------------|-------|-------|
| H1 | 页数 = 解析 = 截图 | PASS | ☐ | Open `slides/slide_*.png` |
| H2 | 功能页合理 | cover/content/closing detected | ☐ | No agenda/section in first 35? |
| H3 | ≥3 有意义内容聚类 | 19 clusters (many singletons) | ☐ | Merge obvious duplicates in UI |
| H4 | 图纸 → Drawing | slide_031 has DRAWING | ☐ | Spot-check PNG vs JSON |
| H5 | 异常页非代表页 | 7 flagged | ☐ | Re-pick rep for flagged clusters |
| H6 | 参考不进 Manuscript | reference_template only | ☐ | |
| H7 | 无绝对路径 | PASS | ☐ | |
| H8 | 聚类移动/合并/拆分 | UI shipped | ☐ | Manual test once |
| H9 | 重跑稳定 | PASS | ☐ | |

**Sign-off:** ☐ PASS  ☐ PASS_WITH_WARNINGS  ☐ NEEDS_REVIEW  ☐ BLOCKED

Reviewer: __________  Date: __________

## Commands

```powershell
cd C:\Users\navib\Desktop\development\Archium-Agent
py scripts/run_phase35_reference_validation.py --max-slides 28 --require-screenshots
py scripts/run_phase35_reference_validation.py --max-slides 35 --require-screenshots
py scripts/run_phase35_reference_validation.py --source "C:\Users\navib\Desktop\development\参考pptx\<file>.pptx" --max-slides 30
```

## Known gaps before formal Phase 3.5 PASS

1. First 28 pages of 老旧小区 deck are photo-heavy — drawing pages start ~31+.
2. Connected-components clustering yields many **singleton** content clusters on real deck (expected REVIEW, not BLOCKED).
3. Representative selector still picks low-editability singletons when no better member exists — human should re-pick in UI.
4. Full 76- or 205-page runs not executed (time/artifact size); sprint used 28–35 page subset.
