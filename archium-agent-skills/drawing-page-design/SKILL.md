---
name: drawing-page-design
description: >-
  Designs architectural drawing-focused slides (site plans, floor plans,
  sections) with contain fit, no crop, north arrow, and scale bar. Use when
  editing drawing pages, drawing_focus layouts, or north-arrow / readability
  issues.
---

# Drawing page design

## Intent

图纸页目标是**可读的技术图面**，不是装饰海报。优先 `LayoutFamily.drawing_focus`。

## Hard constraints

- Fit：**contain**；`crop_forbidden` — 图纸不得 cover、不得裁切图面关键信息
- 总平面：**指北针 + 比例尺** 必须保留（或页面明确北向与比例标注）
- 图例：流线/分区用色必须有图例或等价说明
- 主图面积：图纸应占页面主导视觉权重；辅助正文可压缩，不可挤占图面到不可读
- 锁定：用户锁定的图纸几何/身份不得在局部编辑中被静默改掉

## Layout guidance

1. 一页一图（或主图 + 少量 callout）；多图时保证每张仍可读
2. 标题 = 本页中心结论（建筑判断），不是文件名
3. 标注字号不得低于可读阈值；宁拆页勿糊字
4. 提高可读性时走 Studio `IncreaseDrawingReadability` / 提案流程，勿直接 cover

## Checklist

```
- [ ] contain，无 cover/crop
- [ ] 指北针 / 北向
- [ ] 比例尺或比例标注
- [ ] 图例（若用色编码）
- [ ] 图纸为主视觉，正文为辅
- [ ] 中心结论清晰
```

## Related

- Parent rules: `architectural-presentation-authoring`
- QA: `visual-qa-review`
- Families: `docs/visual/layout-families.md`
