---
name: visual-qa-review
description: >-
  Reviews architectural slides for visual and architectural QA blockers such as
  north arrow, drawing crop, overflow, isomorphic card runs, and evidence
  origin. Use when auditing decks, running visual QA, or deciding export gates.
---

# Visual QA review

## Severity

| Level | Meaning | Action |
|-------|---------|--------|
| Blocker | 不可导出 / 不可接受提案 | 必须修复 |
| Medium | 建筑表达风险 | 应修复后再汇报表态 |
| Suggestion | 可读性/美观 | 尽量改，可不阻断 |

## Blocker / high-priority checks

- 图纸使用 **cover** 或裁切关键图面信息
- 总平面缺失 **指北针** 或 **比例尺**
- 参考案例素材呈现为项目证据
- 文本溢出 / 预览渲染失败（Scene Proposal 不可接受）
- 素材无法加载 / 绑定失败（见 `VisualQAService` asset load codes）

## Medium / suggestion checks

- 未检测到图例区域（有色码流线时）
- 图纸文字密度过高、字号过小
- 连续大量同构卡片页（节奏问题）
- 指标无来源、策略未回指问题
- 主图不主导、留白失控、对齐混乱

## Review workflow

```
1. 列出本页 LayoutFamily + 中心结论
2. 跑硬规则（authoring + drawing/photo 专项）
3. 对照 Visual QA / architectural review 结果
4. 分类：Blocker / Medium / Suggestion
5. 给出可执行修复（优先 Studio Command / Proposal，勿静默改事实）
```

## Proposal gate

接受 `SceneChangeProposal` 前：

- 不得引入新的 Blocker
- 遵守 partial-edit：「只修改提到的部分」
- 预览渲染成功

## Related

- Rules: `architectural-presentation-authoring`
- Code: `archium/application/visual_qa_service.py`
- Architectural hints: `archium/application/review/architectural.py`
