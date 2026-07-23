# Quality Gate Status (honest snapshot)


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
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
| Architectural Benchmark binaries are Goldens | **Governed (P1)** | See `tests/benchmark/architectural_slides/README.md` § Golden 二进制治理；`test_golden_binary_budget.py`；render script requires `--approve-goldens` (CI uses `--materialize-ci-samples`) |

## P2 asset fields — `storage_uri` vs `asset_path` (DOM-015 closed)

| Claim | Status |
|------|--------|
| Portable URI（`benchmark://` / `storage://` / `project://`）替代本机绝对路径 | **Done** |
| `resolved_path` 仅运行时、不写入 JSON | **Done** (`Field(exclude=True)`) |
| Schema v2：废弃持久化 `asset_path`，只存 `storage_uri` | **Done (DOM-015)** — `asset_path` 为内存别名（`exclude=True`）；读兼容旧 JSON |
| Renderer 使用已 resolve Scene（`resolved_path`） | **Done** — `AssetPathResolver.resolve_scene` 只填 `resolved_path`，不污染 `storage_uri` |

**对外口径：** 可移植 URI 已落地；新持久化 Scene 不再写入 `asset_path`。


| Claim | Status |
|------|--------|
| RenderScene V1 最小节点闭环（Text / Image / Drawing / Shape） | **Done** (Phase 0–2 requirement) |
| ChartNode / TableNode + dual export mode | **Partial** — nodes + `ChartExportMode` exist; not full chart/table effect depth |
| 完整 RenderScene / Presenton 式全节点模型 | **Not done** — no GroupNode / ContainerNode / Connector / Freeform |
| 深度原生 PowerPoint / ppt-master 级对象模型 | **Not done** — capability *map* exists; most depth inventory rows are empty |
| Connector / Preset Shape / Freeform / Group / Gradient / Pattern / Glow / Transition | **Not implemented** (see `POWERPOINT_NATIVE_DEPTH_INVENTORY`) |
| P0 Closure Cardinality (`one_to_one` / `one_to_many` / `many_to_one`) | **Done** — bake charts/tables plan multi-emissions; not treated as duplicate errors |
| P0 Workflow Route dispatch + preservation | **Partial** — `execute_fill_native_template` + router wired; FILL fingerprints are template-derived (not in-place OOXML yet) |
| P0 Capability Contract → export / manifest | **Done** — pre-export gate + closure + object-type → `DeckExportManifest` |
| P0 Artifact Ownership write entrypoints | **Done** — registered Import / Recovery / Restore / Fill / Reconcile / Delivery gates |
| P0 Structured PPTX spike (1 master / 3 layouts / title·body·picture·sldNum) | **Done** — `p0_structured_spike_spec` + OOXML smoke |

**对外口径：** RenderScene V1 最小节点闭环完成；图表/表格为可选双导出。不得对外宣称「完整 RenderScene」「深度原生 PowerPoint」或「与 PowerPoint / ppt-master 对象模型等价」。

## Reference Style / ArtDirection → RenderScene (honest) — P1 closed (deterministic overlay)

| Claim | Status |
|------|--------|
| ReferenceStyleProfile / ArtDirection 领域结构与 UI/服务存在 | **Yes** |
| Template Studio / Template matching 存在 | **Yes** |
| 上传参考后可识别颜色 / 字体 / 页面模式（上游） | **Partial**（抽取与匹配侧） |
| Template Studio / 上游可影响 LayoutPlan 生成 | **Partial**（规划侧，非 Scene 编译） |
| `RenderSceneCompiler` 应用 ReferenceStyle / ArtDirection 视觉覆盖 | **Passed (P1 deterministic)** — `style_overlay.apply_style_overlays`；可解析 hex / 字体 / 字号 / 色调启发写入 theme 与节点；持久化 DesignSystem 不改写 |
| 用户上传模板风格差异反映到 RenderScene | **Partial** — 可解析 cue 会进 Scene；自由文本 / 布局 cue 不改坐标 |
| ReferenceStyle `layout_cues` → LayoutPlan 候选偏好 | **Passed (deterministic)** — `layout_style_preference.derive_layout_style_preference` 映射 family/variant；参与候选生成排序与 `select_best` 打分 |

**影响：** Studio / 视觉修复工作流在编译 Scene 时会加载项目 ArtDirection 与 ReferenceStyleProfile，并覆盖 background/accent/title 等可解析令牌。Layout 规划会把 layout cues（如 full-bleed、photo grid、图纸主导）提升为 preferred families/variants。

**对外口径：** 参考风格 **已进入 RenderScene（确定性色/字覆盖）+ LayoutPlan 候选偏好**；不是完整品牌母版引擎，也不改写已生成坐标，只影响版式族/变体选择。

## Font system (2026-07-21)

| Claim | Status |
|------|--------|
| 中文节点存 resolved CJK family（默认 Microsoft YaHei） | **Enforced** via `scene_fonts.resolve_text_fonts` |
| `font_assets` 覆盖全部 typography roles | **Enforced** (`display`…`source`) |
| HTML / PNG / PPTX 共用 fallback chain | **Enforced** (`CJK_FALLBACK_CHAIN` / `LATIN_FALLBACK_CHAIN`) |
| `font_fallbacks` 识别 Arial→CJK 隐式替换 | **Enforced** via `detect_font_fallbacks` |
| 本机字体路径写入 Scene | **Forbidden**（仅 manifest 记录运行时替换） |

## Final verdict (2026-07-21) — engineering trust vs formal pass

**Solved this round (engineering credibility):**

- Portable asset URIs; scene ↔ PPTX ↔ screenshot identity / hash chain
- Structured render evidence; formal visual save blocked on reuse / inconsistency
- Repo hygiene for `.data/`; Golden binary governance
- Honest scope labels (RenderScene V1, ReferenceStyle not in compiler, Phase 8 ≠ acceptance)

**Remaining last layer before formal pass:**

`scene.json` → `output.pptx` → `pptx_render.png` must use a **freshly generated** screenshot
(`pptx_screenshot_generated=true`), not a reused historical PNG. Hash agreement alone is not enough.

Formal gate already **requires** `pptx_screenshot_generated=true` (item 2 done in code).

### Formal human gate mode (2026-07-21)

| Claim | Status |
|------|--------|
| 1–5 综合分 / 均分 ≥ 3.8 作为正式门禁 | **Retired** — experimental archive only |
| 问题驱动 `PASS` / `PASS_WITH_WARNINGS` / `NEEDS_REVIEW` / `BLOCKED` | **In force** |
| 人工异常复核（清单 + 可否汇报，非打分） | **UI default** — Settings 基准面板 |
| 人工查看价值 | **保留** — 抽查、发现未知问题、校准自动规则 |

**原则：** 人工判断仍然重要，但人工打分并不重要。

### Human review variance control (benchmark pages)

For low-visual-density pages (booth/text-heavy, near-single font/color, few architectural visuals),
reviewers must use a **type-aware pass/review rubric** instead of aesthetic micro-scoring:

- Do not auto-penalize “no architectural drawing/photo” when the page purpose is explanatory.
- De-emphasize color/font richness; prioritize structure clarity, readability, and narrative order.
- Prefer `PASS` / `NEEDS_REVIEW` judgment over fragile 1–5 differences on such pages.

### Next steps — only these three

1. **Regenerate screenshots** with Windows PowerPoint COM (or CI LibreOffice) for Goldens  
2. **Keep** formal quality gate on `pptx_screenshot_generated=true` (already enforced)  
3. **Pilot human exception review on 3 pages** (checklist + reporting_ready), then expand to 30

### Pilot trio (do first)

| Case | Covers | Fresh screenshot (this host) |
|------|--------|------------------------------|
| `case_001_site_plan` | 建筑图纸 | Regenerated via PowerPoint COM |
| `case_002_site_photos` | 多张现场照片 | Regenerated via PowerPoint COM |
| `case_006_project_hero` | 大图视觉页面 | Regenerated via PowerPoint COM |

Each pilot page must simultaneously satisfy:

- Fresh PPTX screenshot (`pptx_screenshot_generated=true`) — **done for pilot trio on this machine**
- Scene / PPTX / screenshot hash consistency — **pilot trio eligible**
- Human exception review (`source=manual`, problem checklist + reporting_ready) — **still required**
- PPTX editability review passed — **still required (human)**

Only then expand exception review / screenshot regen to all 30 pages.

```bash
# Regenerate pilot screenshots into Goldens (PowerPoint available on this host)
python scripts/render_architectural_benchmark_visuals.py --approve-goldens \
  --case case_001_site_plan \
  --case case_002_site_photos \
  --case case_006_project_hero
```

Then Settings →「建筑幻灯片基准 · 人工视觉评审」for those three only.

## Architectural Slide Benchmark (30 cases)

| Gate | Status | Evidence |
|------|--------|----------|
| Layout rule quality | **Passed** | `rule_pass_rate = 1.0` (30/30) |
| Provenance chain scene → PPTX → screenshot | **In place** | hashes + sidecars |
| Manual human exception review | **Not started** | no score averages; checklist + reporting_ready |
| Manual delivery acceptance | **Not started** | `manual_human_accepted_count = 0` |
| Placeholder reviews | 30 | `source=placeholder` in each `human_review.json` |
| Fresh PPTX screenshot for formal review | **Partial** | pilot 3: `generated=true`; remaining 27 still typically `reused=true` |
| Formal human gate (problem-driven) | **Failed** | needs ≥3 exception reviews; `human_quality_gate_passed = false` |
| Formal 1–5 average ≥ 3.8 | **Retired** | experimental only |

Report: `tests/benchmark/architectural_slides/reports/benchmark-summary.json`

**What automation proves:** geometry, overflow, hero sizing, whitespace rules, Deck QA scores, identity/hash chain.

**What automation does not prove:** Office-true fonts/overflow/layout, information hierarchy, aesthetic finish, architect willingness to deliver.

**How to complete:** follow **Next steps** (pilot 3 → then 30). Exception review submit stays disabled unless preview is `pptx_render.png` **and** `pptx_screenshot_generated=true`. Do **not** fill formal 1–5 averages.

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

## Template Induction Phase 0–3 (2026-07-21)

Architectural Template Induction sprint (PPTAgent-inspired, **not** a parallel PPT kernel).

### Phase 0 audit (summary)

| Bucket | Items |
|--------|--------|
| **A 可直接复用** | `DomainModel` / repos, `OutlinePlan`, `SlideSpec`, `RenderScene`, `ProjectKnowledge`, Semantic/Deck QA, Template Studio shell, asset origin literals, Streamlit review patterns |
| **B 需扩展** | `PptxStructureExtractor` → `ReferencePptxParser` + snapshots; `ArchitecturalTemplate` (later publish); `TemplateLayoutMatcher`; Outline ↔ Manuscript; Template Studio UI |
| **C 重复风险** | `TemplatePageType` / `LayoutFamily` / `VisualContentType` / `SlideType` — induction uses separate `FunctionalSlideType` + `ArchitecturalContentType` with explicit mapping later |
| **D 旧路径** | Legacy `main.py` / `ppt_generator.py` remain secondary; do not revive as induction kernel |
| **E 迁移** | `019_presentation_manuscripts` adds manuscripts + `outline_plans.manuscript_id` |

### Phase 1–3 delivered

| Capability | Status | Location |
|------------|--------|----------|
| PresentationManuscript (+ Fact/Evidence/Section) | **Done** | `archium/domain/presentation_manuscript.py` |
| Research → Manuscript → Outline | **Done** | `PresentationManuscriptService`, `outline_from_manuscript` |
| Reference PPT parse + snapshots | **Done** | `ReferencePptxParser`, `ReferenceSlideSnapshot` |
| Functional classification | **Done** | `FunctionalSlideClassifier` |
| Content clustering + representatives | **Done** | `ReferenceSlideClusterer`, `RepresentativeSlideSelector` |
| Artifact export (acceptance layout) | **Done** | `TemplateInductionService.export_artifacts` |
| Simple Review UI (corrections, not scores) | **Done** | `archium/ui/pages/template_induction.py` |
| Edit-based generation / Schema / Repair / Deck coherence | **Not in this round** | Phase 4+ |

**对外口径：** Phase 0–3 完成参考页归纳与复核；**不得**宣称 ArchitecturalContentSchema 发布、编辑式生成或 Scene 修复环已完成。

### Phase 2 parser hardening (closed)

| Defect | Status | Evidence |
|--------|--------|----------|
| Picture blob → `assets/slide_XXX/image_YYY.*` (`reference_template`) | **Done** | `ReferencePptxParser._extract_picture_asset` |
| Group recursive `children` | **Done** | `ReferenceElement.children` + `_parse_shape` depth≤6 |
| Placeholder typing | **Done** | `is_placeholder` / `MSO_SHAPE_TYPE.PLACEHOLDER` |
| Decoration uses `page_width * page_height` | **Done** | `_DECORATION_AREA_RATIO` on actual page area |
| Repeat chrome via structural signature (not `TextBox 1`) | **Done** | `_structural_signature` + `_mark_repeated_elements` |

Tests: `tests/unit/reference_ppt_parser/test_phase2_parser_fixes.py` (5 passed).

### Phase 3 classifier honesty (closed)

V1 is **rule-driven structural induction** (`classifier=rule_driven_structural_v1`), not full visual-semantic induction.

| Limitation | Mitigation |
|------------|------------|
| First page ≠ absolute COVER | `first-page prior`; disclaimer / dense opener can override; weak signals → `needs_review` |
| Sparse → SECTION_DIVIDER easy false positive | Always `needs_review`; confidence ≤ 0.54; large visual prefers CONTENT; neighbor flank is soft evidence only |
| Keyword / count heavy (not VLM) | Module docstring + evidence tag; screenshot / embedding deferred |

Tests: `tests/unit/functional_slide_classifier/` (incl. disclaimer, sparse review, large-visual content).

### Phase 3 clustering honesty (closed)

| Limitation | Mitigation |
|------------|------------|
| `layout_name` hard-bucket forever splits copies | Bucket by `content_type` only; `layout_name` soft penalty; signature excludes layout |
| Seed-only grouping lacks transitivity | Pairwise **connected components** (single-linkage) |
| Structural `covered` summed overlaps | Axis-aligned **rectangle union** clipped to page; coverage ∈ [0, 1] |

Tests: `tests/unit/reference_slide_clusterer/` (layout soft-merge, transitive chain, union coverage).

### Phase 3 representative selection — editability honesty (closed)

Overall selector quality is **good** (centrality, anomaly/complexity/parse penalties, rationale).

Editability is **heuristic V1.5**, not a full PPTX editability audit:

| Signal | Handled |
|--------|---------|
| Top-level placeholder / text / content-image slots | Yes — weighted credits |
| Group nesting | Yes — weak nested credit + group-root penalty |
| Master-like cross-page chrome | Yes — `repeats_across_pages` |
| Full-page background image | Yes — area + `hard_edit:full_page_background` |
| SmartArt / OLE / media | Yes — parser `hard_edit:*` tags |
| Lock flags / picture crop & effects | Yes — OOXML lock + blip effect cues |
| Truly safe rewrite in edit generator | **Not proven** — Phase 6 scope |

Tests: `tests/unit/representative_slide_selector/` (incl. `test_editability_scoring.py`).

### Phase 3.5 Real Reference Deck Validation Sprint (in progress)

| Item | Status | Notes |
|------|--------|-------|
| Manuscript citation gate | **Done** | `PresentationManuscriptService` |
| Drawing inference (neighbor text) | **Done** | `DrawingInferenceService` |
| Parser hardening (Group/Placeholder/Decoration/Signature) | **Done** | Phase 2 fixes |
| Full-page screenshots (LO/PPT env) | **Code done** | `@pytest.mark.requires_libreoffice` |
| Review UI cluster move / merge / split | **Done** | `induction_cluster_editor.py` + UI |
| Real 15–30 page deck + human sign-off | **Run done — human pending** | see `.dev-notes/docs-history/phase35-real-reference-validation.md` |

**Phase 3.5 阶段状态：`PASS_WITH_WARNINGS`**（工程门通过；真人结构复核签署未完成）。

Tests: `tests/unit/induction_cluster_editor/`; runner: `scripts/run_phase35_reference_validation.py`.

## Template Induction Phase 4 (2026-07-21)

**阶段状态：`IMPLEMENTED, HARDENING REQUIRED`**

开发放行：可继续开发、测试、人工修正 UI。  
正式发布放行：**有条件** — 须满足下方五项门槛，且发布门 `status == PASS`（`PASS_WITH_WARNINGS` 不写入 `published`）。

### 五项正式通过门槛

| # | 门槛 | 状态 |
|---|------|------|
| 1 | Run B 人工异常复核签署 | **未完成** — `.dev-notes/docs-history/phase35-real-reference-validation.md` |
| 2 | 代表页低置信分类阻止 Schema 发布 | **Done** — `REPRESENTATIVE_CLASSIFICATION_UNCONFIRMED` |
| 3 | Cluster-level Schema 统计（非仅代表页） | **Done** — `cluster_stats` + 分布边界 |
| 4 | 每 Schema 测试内容填充 | **Done** — 结构层 + `RenderScene` 编译；分层 QA（semantic/geometry/asset/drawing）+ 角色覆盖 |
| 5 | 至少一套真实建筑 PPT 模板成功发布 | **未完成** |

### 验收表（Phase 4 相关）

| 项目 | 结果 |
|------|------|
| Manuscript 引用门 | 通过 |
| ArchitecturalContentSchema 模型 | 通过 |
| Schema 自动提取 | 基本通过 |
| 建筑素材来源约束 | 通过 |
| Photo Analysis / Drawing Schema | 通过 |
| Schema 发布门 | 基本通过 |
| 代表页低置信阻塞 | **通过** |
| Cluster-level Schema 统计 | **通过** |
| 测试内容填充 | **通过** — 结构 + RenderScene 编译与分层 QA |
| Phase 4 开发放行 | **可以** |
| Phase 4 正式发布放行 | **有条件** |

| Capability | Status | Location |
|------------|--------|----------|
| ArchitecturalContentSchema / ContentRequirement / VisualRequirement / EvidenceRequirement | **Done** | `archium/domain/visual/architectural_content_schema.py` |
| Auto extract from representatives + cluster stats | **Done** | `ArchitecturalContentSchemaExtractor` |
| Induction confidence (classification × cluster × rep × slot support) | **Done** | `extract_from_slide` |
| Publish gate (`PASS` / `PASS_WITH_WARNINGS` / `BLOCKED`) | **Done** | `ArchitecturalContentSchemaPublishGate` |
| Representative `needs_review` → blocker; non-rep → warning | **Done** | publish gate |
| Structural + RenderScene test fill in publish gate | **Done** | `ArchitecturalContentSchemaTestFillService` |
| Formal publish (`published` only on `PASS`) | **Done** | `SchemaPublishReport.can_formally_publish` |
| Phase 3.5 human sign-off artifact + gate | **Done** | `Phase35HumanSignoff` · `PHASE35_HUMAN_SIGNOFF_REQUIRED` |
| Five-gate readiness report + CLI | **Done** | `template_publication_readiness.py` · `scripts/run_phase4_template_publication.py` |
| Review UI schema correction + publish attempt | **Done** | `template_induction.py` |
| Artifacts `content_schemas.json` / `schema_publish_report.json` | **Done** | `TemplateInductionService.export_artifacts` |
| Induction → `ArchitecturalTemplate` bridge | **Done** | `InductionArchitecturalTemplatePublisher` · `architectural_template.json` |
| Reference slide matching (WP I) | **Done (V1)** | `ReferenceSlideMatcher` · co-plan integration |
| Outline–Template co-planning / edit-based generation | **Co-plan Done / Edit Not** | Phase 5 co-plan; Phase 6 edit |

**对外口径：** 内容 Schema 可自动归纳并用于开发与测试；经人工修正且发布门 `PASS` 后方可标为正式发布模板。**不得**在未完成 Phase 3.5 真人签署前，将自动归纳结果对外宣称已验收。

Tests: `tests/unit/visual/test_architectural_content_schema.py`, `tests/unit/visual/test_template_publication_readiness.py`, `tests/unit/reference_slide_matcher/`.

## Template Induction Phase 5 (2026-07-21)

**阶段状态：`EXPERIMENTAL`**

Outline–Template co-planning (rule-driven V1) — **not** edit-based generation.  
在至少一套真实模板正式发布前，协同规划结果仅用于实验与 UI 验证，不得驱动真实交付物。

| Capability | Status | Location |
|------------|--------|----------|
| Template affinity (section ↔ schema) | **Done** | `OutlineTemplateCoPlanningService` |
| Content page planning (`estimated_slide_count`) | **Done** | `OutlineTemplateCompatibility` page slots |
| Compatibility / fallback routing | **Done** | `template_editing` / `free_composition` / `manual_required` |
| Unmatched schema/layout exposure | **Done** | `unmatched_schema_ids` / `unmatched_layout_ids` |
| Free Composition fallback | **Done** | weak/no match → `free_composition` |
| Artifact `outline_template_co_plan.json` | **Done** | `TemplateInductionService.co_plan_outline` |
| Review UI co-plan panel | **Done** | `template_induction.py` |
| Reference slide ranking (WP I) | **Done (V1)** | `ReferenceSlideMatcher` in co-plan when template has schemas |
| Reference slide edit-based generation | **Skeleton (V1)** | `ReferenceSlideEditingService.generate_scene` — structure copy + strip + fill; not production-ready |

**对外口径：** 大纲可与归纳 Schema 做亲和映射并暴露未匹配模板页；**不得**宣称参考页编辑式生成已生产可用、Scene Repair 或 Deck Coherence QA 已完成。

Tests: `tests/unit/outline_template_co_planning/`, `tests/unit/reference_slide_matcher/`, `tests/unit/reference_slide_editing/`.

## Template Induction Phase 6

**阶段状态：`SKELETON / EXPERIMENTAL`**

Reference slide edit-based generation — **骨架已落地**，可开发与单测；**正式接入生成管线仍暂缓**，待 Phase 4 正式通过（五项门槛 + 真实模板发布）后再推进完整实现。

| 项目 | 状态 |
|------|------|
| `ReferenceEditAction` 模型 | **Done (skeleton)** |
| `ReferenceSlideEditingService.generate_scene` | **Done (skeleton)** — 参考结构 → RenderScene；剥离 reference 文本/素材；绑定 SlideSpec + 项目 Asset |
| 参考素材泄漏防护 | **Done (skeleton)** — `remove_reference_asset` 动作 + 场景内无 `reference_template` URI |
| Co-plan / Studio 接线 | **Done (skeleton)** | `TemplateInductionService.execute_co_plan_template_editing` + Review UI |
| 全路径 RenderScene 渲染验收 | **Not proven** |

**不得**对外宣称「参考页编辑式生成已完成」或「可安全改写任意参考 slot」。

