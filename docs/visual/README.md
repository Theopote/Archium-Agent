# Architectural Visual Composition

建筑视觉编排系统（Round 1）：让 Archium 回答「这些建筑内容应该如何被看见、理解和记住？」。

## 文档索引

| 文档 | 内容 |
|------|------|
| [Architecture](architecture.md) | 分层、数据流、工作流与边界 |
| [Design System](design-system.md) | DesignSystem 令牌与默认预设 |
| [Layout Families](layout-families.md) | 10 个版式族、变体与 generator |
| [Renderer](renderer.md) | LayoutPlan → PptxGenJS 执行路径 |
| [User Guide](user-guide.md) | 视觉设计页操作指南 |

## 一句话

```
SlideSpec → VisualIntent → ArtDirection → LayoutPlan → Validate/Repair → Render
```

LLM 只产出结构化意图与版式族选择；**坐标由确定性 generator 生成**。Renderer **执行** LayoutPlan，不重新决定版式。

## Round 1 已落地

| 能力 | 状态 |
|------|------|
| DesignSystem + 默认 `architecture-board` | ✅ |
| ArtDirection（生成 / 审核 / 再生） | ✅ |
| VisualIntent（规则 / LLM） | ✅ |
| LayoutFamily Registry（10 族） | ✅ |
| LayoutPlan generators（10 个） | ✅ |
| LayoutValidator + 候选评分 | ✅ |
| Visual Workflow（可暂停 / 可恢复） | ✅ |
| 视觉设计 UI | ✅ |
| LayoutPlan → 原生 PPTX（`render-plan.mjs`） | ✅ |
| Golden V1–V7（composition） | ✅ |

## Round 1 明确不做

自动效果图生成、复杂约束求解器、完整视觉语言模型审核、拖拽式 PPT 编辑器、组织品牌模板导入等。详见任务书「非目标」。

## 与旧路径的关系

| 路径 | 用途 |
|------|------|
| **LayoutPlan → `render-plan.mjs`** | 视觉编排主路径（视觉工作流 / 视觉设计页） |
| PresentationSpec → `layouts/*.mjs` | 遗留模板路径（主汇报导出仍可用） |
| Marp | 预览 / 降级 / 旧 visual regression |

## 快速验证

```bash
pytest tests/unit/visual -q
pytest tests/integration/visual -q
pytest tests/golden/visual/composition -q
pytest tests/smoke/test_layout_plan_pptx_render.py -q
```
