# Quality Gate Status (honest snapshot)

Last updated: 2026-07-21

This document states what is **proven by automation** vs what still requires **human rehearsal** or **real project delivery**.

## P0 portability / provenance (2026-07-21)

| Gate | Status | Evidence |
|------|--------|----------|
| RenderScene portable asset URIs | **Enforced** | `storage_uri` / `benchmark://` / `storage://` / `project://`; no machine absolutes in persisted scenes |
| Scene ↔ Manifest identity | **Enforced** | `validate_scene_manifest_consistency`: `scene_id`, `scene_hash`, pptx_render sidecar |
| Same-generation provenance | **Enforced** | `pptx_content_hash` + `output.pptx.meta.json` + screenshot sidecar; URI resolve; font state; post-render QA |
| Structured render evidence | **Enforced** | `screenshot_tools_available`, `pptx_screenshot_generated`, `pptx_screenshot_reused`, `pptx_screenshot_source_hash`, `render_attempt_id` |
| Human visual review on inconsistent artifacts | **Blocked** | consistency failure ⇒ treat `render_valid=false` |
| Formal human visual review requires fresh PPTX screenshot | **Enforced** | `pptx_screenshot_generated=true` required; `pptx_screenshot_reused=true` blocks formal scoring (dev preview only) |

Resolver: `archium/application/visual/asset_path_resolver.py` (`AssetPathResolver`).

## P0 repository hygiene (2026-07-21)

| Gate | Status | Evidence |
|------|--------|----------|
| Runtime DBs / Phase 8 dumps not on main | **Remediated** | `.data/` removed from Git index; `.gitignore` covers `.data/`, `data/`, `output/`, `*.db`, `*.sqlite`, `*.sqlite3` |
| Real-project run outputs | **CI artifacts / reviewed goldens only** | Do not commit full phase8/Studio run trees |

## RenderScene scope (honest — V1 only)

| Claim | Status |
|------|--------|
| RenderScene V1 最小节点闭环（Text / Image / Drawing / Shape） | **Done** (Phase 0–2 requirement) |
| 完整 RenderScene / Presenton 式全节点模型 | **Not done** — no TableNode / ChartNode / GroupNode / ContainerNode / IconNode / LineNode |
| 完整可编辑图表 | **Not done** — compiler maps `CHART` → `ImageNode`（可栅格化） |
| 完整可编辑表格 | **Not done** — compiler maps `TABLE` → `TextNode` |

**对外口径：** RenderScene V1 最小节点闭环完成。不得对外宣称「完整 RenderScene 已完成」或「完整可编辑图表和表格已完成」。

## Reference Style / ArtDirection → RenderScene (honest)

| Claim | Status |
|------|--------|
| ReferenceStyleProfile / ArtDirection 领域结构与 UI/服务存在 | **Yes** |
| Template Studio / 上游可影响 LayoutPlan 生成 | **Partial**（规划侧，非 Scene 编译） |
| `RenderSceneCompiler` 应用 ReferenceStyle / ArtDirection 视觉覆盖 | **Not passed** — 参数保留但未使用；Scene 仅应用 `DesignSystem` |
| 用户上传模板风格差异反映到 RenderScene | **Not passed**（经编译器路径） |

**对外口径：** 参考风格结构存在；**RenderScene 风格落地未通过**。不得把「Reference Style / Template Studio 已接入」说成 Scene 已吃到参考风格。

## Font system (2026-07-21)

| Claim | Status |
|------|--------|
| 中文节点存 resolved CJK family（默认 Microsoft YaHei） | **Enforced** via `scene_fonts.resolve_text_fonts` |
| `font_assets` 覆盖全部 typography roles | **Enforced** (`display`…`source`) |
| HTML / PNG / PPTX 共用 fallback chain | **Enforced** (`CJK_FALLBACK_CHAIN` / `LATIN_FALLBACK_CHAIN`) |
| `font_fallbacks` 识别 Arial→CJK 隐式替换 | **Enforced** via `detect_font_fallbacks` |
| 本机字体路径写入 Scene | **Forbidden**（仅 manifest 记录运行时替换） |

## Architectural Slide Benchmark (30 cases)

| Gate | Status | Evidence |
|------|--------|----------|
| Layout rule quality | **Passed** | `rule_pass_rate = 1.0` (30/30) |
| Manual human visual review | **Not started / blocked** | `manual_human_review_count = 0`; current goldens have `pptx_screenshot_reused=true` |
| Manual delivery acceptance | **Not started** | `manual_human_accepted_count = 0` |
| Placeholder reviews | 30 | `source=placeholder` in each `human_review.json` |
| Fresh PPTX screenshot for formal scoring | **Not met** | all 30 manifests: `pptx_screenshot_generated=false`, `pptx_screenshot_reused=true` |
| Human quality gate | **Failed** | `human_quality_gate_passed = false` |

Report: `tests/benchmark/architectural_slides/reports/benchmark-summary.json`

**What automation proves:** geometry, overflow, hero sizing, whitespace rules, Deck QA scores.

**What automation does not prove:** information hierarchy, aesthetic finish, architect willingness to deliver, editability in practice.

**How to complete:** regenerate each case's `pptx_render.png` via PowerPoint/LibreOffice (`pptx_screenshot_generated=true`), then use Settings →「建筑幻灯片基准 · 人工视觉评审」or edit each case's `human_review.json` with `"source": "manual"`, `"reviewer"`, `"reviewed_at"`, and real scores. UI defaults to `pptx_render.png` preview; visual score submit is disabled unless that preview mode is active **and** the screenshot was freshly generated.

## Phase 8 local runs ≠ formal real-project acceptance (honest)

本轮可生成两套约 20 页项目产物（Presentation / PPTX / Studio scene preview / Deck composition / QA reports）——这是**管线可跑通**的进步。

| Claim | Status |
|------|--------|
| Phase 8 端到端自动生成两套 20 页项目 | **Runnable**（本地 / CI 产物） |
| 产物落在 `.data/phase8`（运行时目录） | **Yes** — 不得当作仓库 Golden 或正式交付包 |
| 本机路径 / 自动生成数据 / 运行时 DB | **仍存在** — 不可移植、不可作为验收证据 |
| 有效人工视觉评分 | **Missing** |
| 真实修改时间（live edit cost） | **Missing** |
| 外部建筑师评价 | **Missing** |
| 最终交付结论 / 签收 | **Missing** |

**对外口径：** Phase 8 本地跑通 ≠ 正式真实项目验收。不得宣称「真实项目验收已完成」或把 `.data/phase8` 输出当作签收交付物。

## Real Project Acceptance (5 scenarios)

| Gate | Status | Evidence |
|------|--------|----------|
| Automated pipeline (content + visual) | **Runnable** | `pytest tests/e2e/real_projects -m real_project_acceptance` |
| Stored acceptance records | **Baseline only** | `tests/e2e/real_projects/records/*/acceptance_record.json` |
| Manual human rehearsal | **Not completed** | `human_metrics_source != studio_manual` on all records |
| Human rehearsal gate | **Failed** | `human_rehearsal_passed = false` |
| Verifiable real deliverables | **Not published** | no sanitized `files/<project_id>/` drop-ins; no signed-off PPTX/PDF bundle |
| Phase 8 `.data/phase8` dumps as acceptance | **Not accepted** | runtime only; see section above |

**What automation proves:** five desensitized scenarios can run end-to-end with mock LLM; slide/asset counts and layout validation metrics; Phase 8 can emit multi-slide decks locally.

**What automation does not prove:** real client-ready decks, live edit time, architect sign-off, portable sanitized deliverables, or final delivery conclusions.

**How to complete:**

1. Add sanitized files under `tests/e2e/real_projects/files/<project_id>/` (not `.data/phase8`)
2. Run live rehearsal; capture Studio manual reviews per slide + real edit time
3. Obtain external architect evaluation and a final delivery conclusion
4. Re-run `UPDATE_REAL_PROJECT_ACCEPTANCE_RECORDS=1 python scripts/run_real_project_acceptance.py --update`
5. Set `human_metrics_source=studio_manual` and `human_rehearsal_passed=true` only after review

## Recent engineering focus (does not close human gates)

Recent work improved **wiring and honesty**, not human sign-off:

- E2E Benchmark M1–M5 (lite → content → visual → PPTX → nightly gate)
- Canvas preview / build reliability
- NLP composite transactions
- Project management service layer
- LLM structured output fixes
- Test and CI cleanup
- Phase 8 local multi-slide generation (runtime under `.data/phase8` only)

None of the above substitutes for 30 manual benchmark reviews, five real-project rehearsal sign-offs, or treating Phase 8 dumps as formal acceptance.
