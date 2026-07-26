# Showcase Case 001 — 医院更新汇报

Presentation Engine v0.3 **Phase 4** 杀手级 Demo 案例包。

| 项 | 值 |
|----|-----|
| 页数 | ~20 |
| 默认 Style Preset | `architecture_technical`（可选 `architecture_urban`） |
| Skill | `hospital-renovation-report` |
| 评分门 | 总分 ≥ 35 /50，且「美观」「专业度」均 ≥ 7 |

## 目录

| 文件 | 说明 |
|------|------|
| `manifest.json` | 案例元数据、Demo 导览、门禁 |
| `outline.json` | 20 页叙事骨架（CI 可跑） |
| `scorecard.template.json` | 投资人五维评分表（人工填写） |
| `fixtures/` | 小文本素材（可进 git） |
| `outputs/` | PPTX / PNG（**不进 git**） |

## CI Smoke（无 LLM / 无大二进制）

```bash
py -m scripts.showcase.run_case_001_smoke
py -m scripts.showcase.run_case_001_render --dry-run
# 或
py -m pytest tests/unit/visual/test_showcase_case_001.py -q
```

校验：outline → DeckComposition → **页主张（Page Director）** → **VisualConcept** → LayoutSolver 20 页 + `presentation_intelligence.json` + `page_claims.json`（无 Node）。

语法文档：[Architectural Presentation Grammar v1.0](../../../docs/visual/architectural-presentation-grammar-v1.md)（流线冲突 → `fragment_to_network`）。

气质对比（technical vs minimal，可测差值）：

```bash
py -m scripts.showcase.compare_case_001_presets
```

## 本地 PPTX（需 Node + pptxgenjs）

```bash
# 首次：cd archium/infrastructure/renderers/pptxgen && npm install
py -m scripts.showcase.run_case_001_render
# 可选气质：--style-preset architecture_urban
```

产物写入 `outputs/`（已 gitignore）：`presentation.pptx`、`layout_plans/`、`presentation.layout_instructions.json`。

路径：**LayoutSolver → render-plan.mjs**（非 Phase 8 DB 验收、非遗留 Spec fallback）。无真实照片时图位可能为空占位，正式 Demo 再挂本地素材。

## 人工评分

1. 打开 `outputs/presentation.pptx`，按 Demo 导览：封面 → 区位与交通 → 设计策略 → 效果表达。  
2. 复制 `scorecard.template.json` → `outputs/scorecard.filled.json` 填分。  
3. 评估门禁：

```bash
py -m scripts.showcase.evaluate_scorecard scripts/showcase/case_001_hospital/outputs/scorecard.filled.json
```

## 硬约束

- 不新增 Agent；走 Visual / Critic 既有服务。
- Showcase 本地导出走 LayoutPlan 主渲染路径（与正式 Studio RenderScene 同源 instruction deck）。
- Critic 只读，不静默改稿。
- 大二进制不进 git。
