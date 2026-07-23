## 批次 3 Application：结论

Application 功能完整，但存在**同类结果多路径编排**（QA / 修复 / PPTX）与少数**分层倒置**。本轮先修了可立刻收敛的 P0。

### 本轮已修

| 项 | 动作 |
|----|------|
| `application → ui` | `presentation_has_visual_layout` 迁到 `application/visual/layout_readiness.py` |
| `SlideEditExecutionService` | 直接调 `VisualEditService` / `ContentAdaptationService`，不再经 UI |
| 死出口 | `VisualCompositionService` 移出公开 `__init__`，标 deprecated |
| 守卫 | `tests/unit/test_application_layering.py` |

### 体量画像

最大服务：`StudioCommandExecutor` (~1319)、`VisualEditService` (~1096)、`TemplateInduction` / `LayoutRepair` / `TransactionExecutor`（均 ~900+）。~109 个 `*Service`。

### 剩余 backlog

| ID | 级 | 问题 |
|----|----|------|
| A2 | P0/P1 | 双导出：`PresentationSpec` vs `RenderScene` |
| A3 | P0/P1 | 视觉编辑路径 `session.commit` 归属不一致（TransactionExecutor / StudioSceneEdit 各自提交） |
| A4 | P1 | QA 多栈（AutomatedReview / DeckQA / SceneSemantic / Critic） |
| A5 | P1 | 修复三路径（SlideSpec / LayoutPlan / RenderScene） |
| A6 | P1 | God stack：CommandExecutor + VisualEdit + TransactionExecutor |
| A7 | P2 | ORM `ProjectORM` 直读；`*_safe` 开独立 Session；死 `IconSelectionService` |

### 健康点

- Repository 默认 flush-only；工作流 checkpoint commit 有开关  
- `AutomatedReviewService` 拆到 `review/*` 较清晰  
- 内容 / 视觉 / 规划三条 LangGraph 边界明确  

---

下一步按总表是 **批次 4 Workflow**（状态机、暂停恢复、审批失效、路线分发）。若要先收双导出（A2），也可以插在 Workflow 之前。

[REDACTED]