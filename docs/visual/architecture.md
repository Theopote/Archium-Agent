# Visual Composition Architecture

## 分层

```
UI (Streamlit 视觉设计)
  └── archium/ui/visual_service.py          # facade，无布局算法
        └── VisualWorkflowService
              └── visual_graph (LangGraph)
                    ├── ArtDirection / VisualIntent / LayoutPlanning services
                    ├── LayoutValidator / LayoutRepair
                    └── render_presentation
                          └── PptxGenPresentationRenderer
                                └── render-plan.mjs  (execute-only)
```

| 层 | 职责 | 禁止 |
|----|------|------|
| `domain/visual` | DesignSystem、ArtDirection、VisualIntent、LayoutPlan、校验模型 | 渲染细节、Streamlit |
| `application/visual` | 生成、候选、**Layout Quality** 评分、修复、工作流编排 | 写死坐标、UI 控件 |
| `infrastructure/layout` | Family Registry、确定性 generators、几何与文本测量 | LLM 自由坐标 |
| `infrastructure/renderers/pptxgen` | Adapter + execute-only Node | 重选版式族 / 重算版心 |
| `workflow/visual_*` | 独立 Visual Composition 图 | 并入 PlanningWorkflow |
| `ui/*visual*` | 审核、选择候选、预设重排 | 布局业务逻辑 |

## 核心对象关系

```
DesignSystem (可复用令牌)
    ↑
ArtDirection (整套汇报视觉方向) ──► VisualIntent (单页意图)
                                       ↓
                                  LayoutPlan (元素 + 绝对坐标)
                                       ↓
                         RenderedSlideInstruction → PPTX
```

- **DesignSystem** 独立于 renderer。
- **ArtDirection** 独立于单页布局。
- **VisualIntent** 独立于 LayoutPlan（意图可换，计划可重算）。
- **LayoutPlan** 独立于 PptxGenJS（可序列化为 JSON 指令）。

## Visual Workflow

入口：`VisualWorkflowService.run()` / `continue_after_art_direction_approval()` /
`continue_after_layout_review()` / `resume()`。

默认步骤：

1. `load_presentation_context`
2. `ensure_design_system`
3. `generate_art_direction` → **审核门**（可关）
4. `generate_visual_intents`
5. `generate_layout_candidates` → `select_layout_plans`
6. `validate_layouts` ⇄ `repair_layouts`
7. 若仍有 ERROR/CRITICAL → `apply_safe_fallback` → 再校验
8. 仍失败 → **`await_layout_review`**（禁止静默导出）
9. `render_presentation`（仅 WARNING 可导出 PPTX；ERROR/CRITICAL 一律阻断 PPTX）
10. `finalize`

校验路由：

| 结果 | 去向 |
|------|------|
| 全部通过 | render |
| 仅 WARNING/INFO | render（带 warnings） |
| ERROR/CRITICAL 且未用尽修复轮 | repair |
| ERROR/CRITICAL 且未尝试 fallback | apply_safe_fallback |
| ERROR/CRITICAL 仍在 | await_layout_review |

工作流状态经 checkpointer 持久化；序列化会剥离 API Key。

## 持久化

Alembic：`011_visual_composition`。

表（JSON payload 仓储）：`design_systems`、`art_directions`、`visual_intents`、`layout_plans`。

`SlideSpec` 可选关联：`visual_intent_id`、`layout_plan_id`。

Revision 实体扩展：`DESIGN_SYSTEM` / `ART_DIRECTION` / `VISUAL_INTENT` / `LAYOUT_PLAN`。

## 关键服务接口

| 服务 | 关键方法 |
|------|----------|
| `ArtDirectionService` | `generate` / `update` / `approve` / `regenerate` / `get` |
| `VisualIntentService` | `generate_for_slide` |
| `LayoutPlanningService` | `generate_candidates` / `select_best` / `plan_for_slide` |
| `LayoutValidationService` | `validate` |
| `LayoutRepairService` | `repair` — auto-repairable rule codes。字号按 DesignSystem 实际 `font_size` 选最小合法更大 token，必要时用阈值内 `font_size_override`；文本溢出按邻接空白→减间距→微调→更小 token→换 variant/拆页 |
| `VisualCompositionService` | 薄编排：意图 → 候选 → 最佳计划 |
| `VisualWorkflowService` | `run` / `continue_after_art_direction_approval` / `continue_after_layout_review` / `resume` |
| `PptxGenPresentationRenderer` | `build_layout_instruction_deck` / `export_pptx_from_layout_instructions` |

## Layout Quality Score（非 Visual Quality）

`LayoutScore` / `LayoutQualityScore` 是 **Layout Quality Score**：由规则与几何推导，维度为 validity / readability / hierarchy / alignment / whitespace / asset usage / consistency。

它**不是**完整 Visual Quality Score，目前**不能**判断：

- 图片是否与观点匹配
- 页面是否“像建筑汇报”
- 主视觉表达力量、色彩协调
- 多页节奏、案例图统一尺度
- “不重叠但仍机械”的观感

下一阶段再增加 **screenshot-based Visual Critic**。候选选择与 golden `score_baseline` 均只约束 Layout Quality。

## 设计约束（不可违反）

1. 不用「医院模板 / 校园模板」等项目类型固定套版驱动排版。
2. LLM 不得自由发明全部坐标。
3. 图纸默认 `contain` + `crop_forbidden`；照片可用 `cover`。
4. 布局逻辑不进 Streamlit，也不进 PptxGen template 决策。
5. Visual graph 不与 PlanningWorkflow 合并。
