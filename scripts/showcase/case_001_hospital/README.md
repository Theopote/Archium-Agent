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
# 或
py -m pytest tests/unit/visual/test_showcase_case_001.py -q
```

校验：outline → DeckComposition 节奏（高潮预算、密度波形）+ 评分门契约。

## 本地完整 Demo（人工）

1. 将照片 / CAD 截图 / PDF 放到本机工作区（勿提交大文件）。
2. 上传资料包 → 选择 Style Preset → 一键生成汇报。
3. 固定导览：封面 → 区位与交通 → 设计策略 → 效果表达。
4. 将 PPTX 写入 `outputs/`（已 gitignore）。
5. 复制 `scorecard.template.json` → `outputs/scorecard.filled.json` 填分，用：

```bash
py -m scripts.showcase.evaluate_scorecard scripts/showcase/case_001_hospital/outputs/scorecard.filled.json
```

## 硬约束

- 不新增 Agent；走 Visual / Critic 既有服务。
- 主路径 RenderScene → PPTX，不走遗留 Spec fallback。
- Critic 只读，不静默改稿。
