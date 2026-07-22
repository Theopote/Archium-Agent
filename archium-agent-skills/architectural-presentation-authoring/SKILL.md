---
name: architectural-presentation-authoring
description: >-
  Authors and reviews architectural presentation decks with Archium hard rules
  for facts, drawings, evidence, metrics, and page pacing. Use when writing or
  editing slides, outlines, manuscripts, art direction, or when the user asks
  for architectural presentation standards.
---

# Architectural presentation authoring

## Hard rules（必须遵守）

一页一个中心结论；
项目事实优先；
图纸不得 cover；
参考案例不能冒充项目证据；
总平面必须保留指北针和比例尺；
策略必须回应前文问题；
指标必须有来源；
不允许连续大量同构卡片页。

## How to apply

1. **一页一个中心结论** — 每页标题/主文只承载一个可陈述的结论；次要信息降级为支撑点或移到下一页。
2. **项目事实优先** — 以 Fact Ledger / 已确认项目事实为真源；未知标为未知，禁止编造面积、投资、工期。
3. **图纸不得 cover** — Drawing / 总平面 / 平面 / 剖面：`contain` + 禁止裁切；见 `drawing-page-design`。
4. **参考案例不能冒充项目证据** — `asset_origin=reference_case` 必须标注「参考」；不得写成「本项目现状/成果」。
5. **总平面必须保留指北针和比例尺** — 缺失则阻断或明确列为必须修复项。
6. **策略必须回应前文问题** — 策略页显式回指问题页（编号或短标题）；禁止无问题的策略清单。
7. **指标必须有来源** — 每个关键指标附来源（事实键、文档页、计算说明）；无来源则降级为定性表述或删除。
8. **不允许连续大量同构卡片页** — 避免连续 3+ 页同结构 `strategy_cards` / 同构网格；穿插图纸、证据、对比或文字论述页。

## Workflow checklist

```
- [ ] 页面中心结论可一句话说清
- [ ] 事实来自账本或可追溯引用
- [ ] 图纸 fit = contain，无 cover/crop
- [ ] 参考素材已标注且未冒充项目
- [ ] 总平面含指北针 + 比例尺
- [ ] 策略 ↔ 前文问题一一对应
- [ ] 指标有来源
- [ ] 无连续大量同构卡片页
```

## Related skills

- Drawings → `drawing-page-design`
- Photo evidence → `photo-evidence-layout`
- Exec summary → `executive-summary-writing`
- Hospital / campus → `hospital-renovation-report` / `campus-renovation-report`
- Studio comments → `apply-studio-comments`
- QA pass → `visual-qa-review`

## Repo anchors

- Layout families: `docs/visual/layout-families.md`
- Design system image rules: `docs/visual/design-system.md`
- Fact / mission planning: `docs/project-mission-adaptive-planning.md`
