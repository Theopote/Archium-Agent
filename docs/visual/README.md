# Architectural Visual Composition

建筑视觉编排与 Studio 场景编辑系统：让 Archium 回答「这些建筑内容应该如何被看见、理解、修改和交付？」。

## 文档索引

| 文档 | 内容 |
|------|------|
| [Studio User Guide](../studio-user-guide.md) | **汇报工作室** — 主编辑界面（浏览 / NL 编辑 / 导出） |
| [Architecture](architecture.md) | 分层、数据流、工作流与边界 |
| [Vision Intelligence Layer](../architecture/vision-intelligence-layer.md) | **战略缺口**：概念/图示/氛围生成（Visual 席位；非 Midjourney 套壳） |
| [Design System](design-system.md) | DesignSystem 令牌与默认预设 |
| [Layout Families](layout-families.md) | 10 个版式族、变体与 generator |
| [Renderer](renderer.md) | LayoutPlan → PptxGenJS 执行路径 |
| [User Guide](user-guide.md) | 工作室内视觉编排（ArtDirection / 候选版式 / 审核门） |

## 一句话

```
SlideSpec → VisualIntent → ArtDirection → LayoutPlan → Validate/Repair → Render
         ↘（战略规划）Vision Engine → ai_generated Asset → Studio / 非证据槽
```

LLM 只产出结构化意图与版式族选择；**坐标由确定性 generator 生成**。Renderer **执行** LayoutPlan，不重新决定版式。概念/分析示意生成见 [Vision Intelligence Layer](../architecture/vision-intelligence-layer.md)（未在当前 Visual Quality 冲刺内收口）。

## Round 1 已落地

| 能力 | 状态 |
|------|------|
| DesignSystem + 默认 `architecture-board` | ✅ |
| ArtDirection（生成 / 审核 / 再生） | ✅ |
| VisualIntent（规则 / LLM） | ✅ |
| LayoutFamily Registry（10 族） | ✅ |
| LayoutPlan generators（10 个） | ✅ |
| LayoutValidator + **Layout Quality Score**（几何/规则） | ✅ |
| Visual Workflow（可暂停 / 可恢复） | ✅ |
| 工作室视觉编排 UI | ✅ |
| LayoutPlan → 原生 PPTX（`render-plan.mjs`） | ✅ |
| Golden V1–V7（composition） | ✅ |
| Visual Critic heuristic_v0（只读 Visual Quality） | ✅ 初版 |
| Deck QA deck_heuristic_v0（跨页一致性） | ✅ 初版 |
| RenderScene 画布编辑（单选 / 多选 / 框选） | ✅ |
| 元素评论 → 提案 → QA → Revision | ✅ |
| 固定画布容量预算 / 内容适配 / 拆页建议 | ✅ |
| 图片衍生处理（原图不可变） | ✅ 初版 |
| 模板导入、归纳、发布与 Template Studio | ✅ 初版 |

## 当前边界

仍未提供自动建筑效果图生成、通用复杂约束求解器或与 PowerPoint 完全等价的自由编辑体验。当前图片处理是受证据策略约束的衍生管线，不是生成式修图；画布编辑写入 RenderScene 修订，而不是直接修改任意 PPTX 内部对象。

**Layout Quality Score** 主要覆盖结构与规则。`heuristic_v0` Visual Critic 提供只读视觉质量提示；确定性修复和需要确认的提案是两条不同路径。是否阻断导出由审核/导出策略决定，不能仅根据一个视觉分数推断。

## 与旧路径的关系

| 路径 | 用途 |
|------|------|
| **LayoutPlan → `render-plan.mjs`** | 视觉编排主路径（视觉工作流 / 工作室） |
| PresentationSpec → `layouts/*.mjs` | 遗留模板路径（主汇报导出仍可用） |
| Marp | 预览 / 降级 / 旧 visual regression |

## 快速验证

```bash
pytest tests/unit/visual -q
pytest tests/integration/visual -q
pytest tests/golden/visual/composition -q
pytest tests/smoke/test_layout_plan_pptx_render.py -q
```
