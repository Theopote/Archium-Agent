# Architectural Slide Visual Benchmark

真实建筑汇报页面的视觉质量基准库（**30 页**）。

本目录下的 PPTX / PNG / Scene 等是**经评审的 Golden Benchmark**（允许提交），**不是** `.data/phase8` 一类运行时垃圾。必须按下方治理规则更新，否则每次重渲染都会产生大批无避免的二进制 diff。

汇总状态与**试点三页 → 再扩 30**计划见 [`docs/QUALITY_GATE_STATUS.md`](../../../docs/QUALITY_GATE_STATUS.md) § Final verdict。

---

## Golden 二进制治理（P1）

### 哪些是 Golden（允许提交）

| 类别 | 路径 / 文件 | 说明 |
|------|-------------|------|
| Case 定义 | `case_catalog.py`、`input.json`、`notes.md` | 源真相；手工维护 |
| Layout 几何指纹 | `layout_plan.json`、`validation_report.json`、`score_baseline.json`、`slide_spec.json`、`visual_intent.json`、`deck_qa_report.json` | Layout Geometry Golden |
| 线框预览 | `wireframe.png`、`preview.png`（legacy 别名） | Layout 几何预览；**不是**正式视觉评分对象 |
| Rendered Visual Golden | `scene.json`、`scene_preview.png`、`output.pptx`、`output.pptx.meta.json`、`pptx_render.png`、`pptx_render.meta.json`、`final_render.png`、`render_manifest.json` | Scene / PPTX / 截图同源证据 |
| 素材 | `assets/*` | 脱敏/占位或已审查的案例素材 |
| 人工评审 | `human_review.json`、`editability_review.json`、`layout_qa_review.json` | 评审记录；基线脚本不覆盖已有 manual |
| 报告 | `reports/benchmark-summary.json`、`benchmark-report.html` | 由脚本/pytest 会话钩子再生 |

**明确不是 Golden、禁止当交付证据：**

- `.data/phase8/**`、Studio 运行时目录、本机绝对路径产物
- 仅 `pptx_screenshot_reused=true`、未本轮重新截图的截图（开发预览可用，**正式人工视觉门禁不接受**）

### 哪些允许提交 vs 必须走更新流程

| 变更类型 | 可否直接 `git add` | 要求 |
|----------|-------------------|------|
| 改 `input.json` / catalog / 代码后的**预期**漂移 | 否 → 先走更新脚本 | 见「如何更新」 |
| 刷新 30 页 `output.pptx` / `pptx_render.png` / `scene.json` | 否 → 显式写库 + 人工确认 | 大批二进制；PR 须说明原因 |
| 只改 `human_review.json`（manual） | 是 | 填 `reviewer` / `reviewed_at` / `source=manual` |
| 改 README / 报告逻辑 | 是 | 无二进制预算问题 |

### 由脚本生成（不要手改二进制）

| 产物 | 生成方式 |
|------|----------|
| Layout JSON + wireframe/preview | `UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1` + `python scripts/update_architectural_benchmark_baselines.py` 或同环境 pytest |
| Scene / PPTX / pptx_render / final_render / sidecars / manifest | 同上，或 `python scripts/render_architectural_benchmark_visuals.py --write-goldens` |
| `reports/*` | 基线更新后会话钩子，或 `python scripts/build_architectural_benchmark_report.py` |
| 便携 URI 归一化 | `python scripts/normalize_benchmark_scene_uris.py`（改 `scene.json` + manifest；仍属 Golden 变更） |

`final_render.png` 与 `pptx_render.png` 常为同内容别名；更新时两者应一并提交，避免只改其一。

### 如何更新

**Layout + 全量 Rendered Visual（默认整库刷新）：**

```bash
python scripts/update_architectural_benchmark_baselines.py
# 等价：
# UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1 pytest tests/benchmark/architectural_slides -v
```

**仅重渲 Scene / PPTX / 截图（不改 layout 指纹）：**

```bash
python scripts/render_architectural_benchmark_visuals.py --write-goldens
python scripts/render_architectural_benchmark_visuals.py --write-goldens --case case_002_site_photos
```

未加 `--write-goldens` 时脚本**拒绝**写入已提交的 case 目录（防止普通本地跑刷爆 Git）。

**正式视觉用新鲜截图（推荐在有 PowerPoint/LibreOffice 的机器上）：**

```bash
# 须 screenshot_tools_available；目标 manifest.pptx_screenshot_generated=true
python scripts/render_architectural_benchmark_visuals.py --write-goldens
```

### 更新需要什么人工确认

提交含二进制 Golden 的 PR 前，作者须确认：

1. **意图**：为何重渲（编译器/字体/素材/布局变更），而非「顺手跑了脚本」。
2. **范围**：`git status` / diff 统计 — 预期约 N 个 case ×（pptx + png + json）；禁止夹带 `.data/`、DB、无关 phase8。
3. **抽样目视**：至少打开 3 页 `pptx_render.png`（含变更最大的 case）与对应 `output.pptx`。
4. **截图证据**：若宣称可人工视觉评审，manifest 须为 `pptx_screenshot_generated=true`（不得仅 `reused=true`）。
5. **评审作废**：渲染语义变化后，相关 `human_review.json` 应作废或重评（见 `scripts/invalidate_benchmark_human_reviews.py`）。
6. **预算**：通过下方二进制大小上限（或在 PR 中说明超限例外）。

### 如何避免普通测试覆盖 Golden

| 机制 | 行为 |
|------|------|
| `assert_or_update_case_baseline` | 仅当 `UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1` 时写盘；平时只比对指纹 |
| `test_render_benchmark_visual_artifacts_*` | 写入 **`tmp_path`**，不碰仓库 case 目录 |
| `render_architectural_benchmark_visuals.py` | 默认拒绝写 Golden；须 `--write-goldens` |
| CI 普通 / PR 测试 | **不得**设置 `UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1` |
| 本地调试 | 用 `tmp_path` 或复制 case 到沙箱目录再渲染 |

### 二进制大小上限

当前量级（约）：全库 PNG+PPTX ≈ **6 MB**；单 case 二进制峰值 ≈ **0.3 MB**（占位素材）。素材升级后会增大，故设软/硬上限：

| 范围 | 软上限（PR 须说明） | 硬上限（默认禁止合入） |
|------|---------------------|------------------------|
| 单文件 `*.png`（含 wireframe / scene_preview / pptx_render / final_render） | 500 KB | 2 MB |
| 单文件 `output.pptx` | 1 MB | 5 MB |
| 单 case 全部 `*.png` + `output.pptx` | 2 MB | 8 MB |
| 30 case 合计 `*.png` + `output.pptx` | 30 MB | 80 MB |

预算由 `test_golden_binary_budget.py` 校验硬上限；软上限靠 PR 自检。超硬上限须先缩图/压缩素材或拆分资产策略，并更新本表。

---

## 目录结构（单 Case）

| 文件 | 用途 |
|------|------|
| `input.json` | 页面任务、分类、预期 LayoutFamily、素材清单 |
| `assets/` | 占位或真实输入素材 |
| `slide_spec.json` | 页面内容指纹 |
| `visual_intent.json` | 视觉意图指纹 |
| `layout_plan.json` | 版式几何指纹 |
| `validation_report.json` | 规则校验结果 |
| `deck_qa_report.json` | 单页 Deck QA 摘要 |
| `score_baseline.json` | Layout Quality 分数基线 |
| `wireframe.png` / `preview.png` | Layout 线框 |
| `scene.json` / `scene_preview.png` | RenderScene Golden |
| `output.pptx` (+ `.meta.json`) | 可编辑 PPTX + 内容哈希 sidecar |
| `pptx_render.png` (+ `.meta.json`) / `final_render.png` | PPTX 截图（正式视觉评分对象） |
| `render_manifest.json` | 渲染有效性与截图证据 |
| `human_review.json` | 人工 9 维评分（手动填写；基线更新时不覆盖） |
| `layout_qa_review.json` | 可选：layout QA 派生（非人工） |
| `notes.md` | 问题与修复记录 |

## Case 目录

Case 定义集中在 `case_catalog.py`（30 条 `CaseCatalogEntry`），`case_registry.py` 负责通用构建逻辑。

| 范围 | 分类 | LayoutFamily 覆盖 |
|------|------|-------------------|
| `case_001`–`005` | A1–A5 各 1 页 | 图纸 / 照片 / 案例 / 数据 / 文字 |
| `case_006`–`008` | A2/A5 | `hero`（3 variants） |
| `case_009`–`011` | A4/A5 | `process_narrative` |
| `case_012`–`014` | A1 | `analytical_diagram` |
| `case_015`–`017` | A4/A5 | `strategy_cards` |
| `case_018`–`020` | A1/A2/A3 | `hybrid_canvas` |
| `case_021`–`022` | A1 | `drawing_focus`（补充 variant） |
| `case_023`–`024` | A2 | `evidence_board`（补充 variant） |
| `case_025`–`026` | A3 | `comparative_matrix`（补充 variant） |
| `case_027`–`028` | A4 | `metric_dashboard`（补充 variant） |
| `case_029`–`030` | A5 | `textual_argument`（补充 variant） |

每个 LayoutFamily 至少 3 个 Case；A1–A5 五类均有覆盖。

## 运行（只读比对，不写 Golden）

```bash
pytest tests/benchmark/architectural_slides -v
pytest tests/benchmark/architectural_slides -v -m architectural_benchmark
```

## 报告

```bash
python scripts/build_architectural_benchmark_report.py
```

输出：`tests/benchmark/architectural_slides/reports/benchmark-report.html` 与 `benchmark-summary.json`

### CI 质量门禁（P0）

`test_benchmark_summary_report_is_current_and_consistent` 会检查：

- `benchmark-summary.json` / `benchmark-report.html` 存在
- summary 生成时间不早于各 case artifact
- `case_count` 与 30 个 case 目录一致
- 每个 case 的 `rule_passed` / `layout_score` 与 live build 及 summary 一致
- `rule_pass_rate >= 1.0`（正式 layout 规则门槛）
- **占位/派生人工评审不得 `accepted=true`**（仅 `source=manual` 可标记可交付）

当前状态：**30 页 layout 规则质量已通过；人工视觉质量验收未通过**（`manual_human_accepted_count=0`，`human_quality_gate_passed=false`）。占位评审在报告中显示为 **待人工评审**，不会展示 4.0 占位分。

## 人工评分

### 三轮验收流程（推荐）

1. **第一轮**：项目作者逐页真实审阅 30 页（设置 → 建筑幻灯片基准 · 人工视觉评审）
2. **第二轮**：另请一位建筑师复核其中 10 页
3. **第三轮**：争议页修改后复评

正式视觉评分对象为 **`pptx_render.png`**，且须 `pptx_screenshot_generated=true`。

### 必填字段（`source=manual`）

| 字段 | 说明 |
|------|------|
| `reviewer` | 评审人 |
| `reviewed_at` | 评审时间（ISO 8601） |
| `source` | 必须为 `manual` |
| 9 维分数 | `information_hierarchy` … `editability`（1–5） |
| `major_problems` / `minor_problems` | 问题列表 |
| `accepted` | 是否可交付（仅 manual 可设为 true） |
| `reviewer_notes` | 评审备注 |

在 Streamlit **设置** 页「建筑幻灯片基准 · 人工视觉评审」面板中查看 `pptx_render.png` 并保存；或直接编辑各 Case 的 `human_review.json`。加权门槛默认 **3.5/5**。

**设置页评审面板：** 总览 / 筛选 / 导航 / 评审人记忆 / 保存后可选刷新报告。

使用 `UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1` 时**不会覆盖**已有 `human_review.json`；缺失时写入占位模板。

严格模式（CI 可选）：

```bash
STRICT_BENCHMARK_HUMAN_REVIEW=1 pytest tests/benchmark/architectural_slides -v
```

## 与 V1–V7 Golden 的区别

- V1–V7（`tests/golden/`）：LayoutFamily 几何与渲染回归
- Architectural Benchmark：真实建筑页面任务 + 分类体系 + 人工视觉评分 + 整套报告；二进制须按本节治理
