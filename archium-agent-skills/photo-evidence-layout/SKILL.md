---
name: photo-evidence-layout
description: >-
  Lays out site photo evidence boards and issue grids with captions, numbering,
  and honest asset origins. Use when building evidence_board pages, site-issue
  photo grids, or distinguishing project photos from reference cases.
---

# Photo evidence layout

## Intent

现场问题 / 证据页：让读者**一眼看到问题与证据编号**，而不是相册拼贴。优先 `LayoutFamily.evidence_board`。

## Hard constraints

- 照片可用 **cover**（与图纸相反）；仍避免裁掉关键证据主体
- **参考案例不能冒充项目证据** — `asset_origin=reference_case` 必须标「参考」；项目现场用 `project_upload` 等真实来源
- 每张证据：**编号 + 短图注**（问题要点，非空泛形容词）
- 一页一个中心结论（例如「急诊流线交叉导致拥堵」）；照片服务于该结论

## Layout guidance

1. 网格有序（编号阅读顺序固定）；避免无序马赛克
2. 图注贴近对应照片；来源/拍摄信息可放次级字号
3. 问题页与后续策略页编号对齐（策略技能要求回应前文问题）
4. 局部 AI 编辑绑定具体 photo 节点，勿用「右边第二张」猜目标（见 `apply-studio-comments`）

## Checklist

```
- [ ] 中心结论明确
- [ ] 证据编号 + 图注齐全
- [ ] asset_origin 诚实（现场 vs 参考）
- [ ] 参考素材已标注
- [ ] 阅读顺序稳定
```

## Related

- Parent: `architectural-presentation-authoring`
- Studio node comments: `apply-studio-comments`
- Families: `docs/visual/layout-families.md`
