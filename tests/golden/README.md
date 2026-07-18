# Three-Layer Acceptance Model

Part of the **[v0.2 Alpha Validation Sprint](../../docs/v0.2-alpha-validation-sprint.md)**.

| Layer | Name | LLM | Parsers | CI | Purpose |
|-------|------|-----|---------|-----|---------|
| **1** | Deterministic workflow regression | `MockLLMProvider` | Inline DB chunks | ✅ Always | 工作流 / DB / 导出结构 |
| **2** | Real fixture acceptance | Cached or mock LLM | Real `IngestionService` | ✅ When manifests present | 真实 PDF/DOCX/PPTX/图片解析 |
| **3** | Live model evaluation | Real API | Real | ❌ Manual only | 输出质量与模型波动 |

> Layer 1 是 **deterministic workflow regression cases**，不是完整的 **real architectural project acceptance**。Layer 2–3 才逐步逼近真实项目验收。

## Layer 1 — Regression (`regression/`)

Mock LLM + 预置文本块。验证主链逻辑：

- Workflow 状态 / 页数 / 四层 Review
- Fact conflict 检测
- PresentationSpec 布局
- 产物 manifest

```bash
pytest tests/golden/regression -v -m regression
```

## Layer 1b — Mission Golden (`mission/`)

Mission-first 规划链确定性场景（M1–M6）：自由任务描述 → Mission → Workstreams → Deliverables → PresentationRequest。

```bash
pytest tests/golden/mission -v -m regression
```

| Case | 场景 |
|------|------|
| M1 | 清凉寺重建（面积未知、历史研究） |
| M2 | 大学图书馆改造（不停业、分期） |
| M3 | 医院环境提升（非新建） |
| M4 | 村庄更新（多主体、反模板） |
| M5 | 消防站新建（指标保留） |
| M6 | 园区绿色低碳专项（非方案 PPT） |

## Layer 2 — Fixture Acceptance (`fixtures/`)

脱敏真实资料 → 真实 parser → 缓存或 mock LLM → 完整导出。

```bash
pytest tests/golden/fixtures -v -m fixture_acceptance
```

详见 [fixtures/README.md](fixtures/README.md)。

## Layer 3 — Live Model Evaluation (`live/`)

真实 LLM，手动或定期运行，**不进入默认 CI**：

```bash
set ARCHIUM_LIVE_LLM=1
pytest tests/golden/live -v -m live_llm
```

## 全部 Golden 测试

```bash
pytest tests/golden -v
```

产物：`tests/golden/artifacts/`（CI 上传为 workflow artifact）

## Visual regression（Layer 1 扩展）

在流程/结构 Golden 之上，对 **3 个关键 Case** 的 Marp PNG 预览建立视觉基线：

```bash
pytest tests/golden/visual -v -m visual_regression   # 需 Marp CLI
python scripts/update_visual_baselines.py            # 有意变更后刷新基线
```

详见 [visual/README.md](visual/README.md)。检测项：页数变化、标题缺失、布局大偏差、边距溢出——**非**像素级完全一致。
