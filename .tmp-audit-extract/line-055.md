## 批次 4 Workflow：结论

三条 LangGraph（Planning / Presentation / Visual）骨架健康；真正风险在**审批失效**、**门禁与 require 标志不一致**，以及 **checkpoint 并发**。

### 本轮已修

| 项 | 动作 |
|----|------|
| P0 计划审批失效 | 选择变更会使已批准的 `DeliverablePlan` → `DRAFT`（`invalidate_approval`） |
| P1 `pause_for_review` | brief/storyline 门禁现在尊重 `require_*_review`（与 outline/slides 一致） |
| P1 复用已有 brief/storyline | 跳过审核时自动 approve，避免脏 DRAFT 卡住后续 |

相关单测 / 集成测 13 passed。

### 结构速览

- **Planning**：interrupt 门（mission / clarification / plan）
- **Presentation**：统一 `pause_for_review`
- **Visual**：art_direction / layout_review
- **Slide recovery**：命令式服务，不是 LangGraph
- **双持久化**：SQLAlchemy `WorkflowRun` + LangGraph SqliteSaver

### 剩余 backlog

| ID | 级 | 问题 |
|----|----|------|
| W2 | P0 | 共享 Sqlite checkpoint + 后台 continue 并发竞态 |
| W3 | P1 | 非 interrupt 的 `resume()` 可能从 START 重跑 |
| W4 | P1 | 路由分叉：`GENERATE_FROM_PROJECT` 硬编码 vs 其它 route 旁路 |
| W5 | P1 | Plan 审批仍无 content hash（弱于 Mission） |
| W6 | P2 | 死 STEP_LABELS / 戏剧化 recovery 进度 / 死 route map 项 |

### 健康点

- Mission `approval_hash` 模型扎实  
- Outline → `CHANGES_PENDING` + 续跑校验清晰  
- Layout resume 会复验，拒绝静默导出无效 PPTX  
- `workflow/` 不依赖 UI（已有守卫测试）  

---

下一步按总表是 **批次 5 Database**（ORM / Repository / Mapper / 迁移 / 事务）。需要的话直接继续。

[REDACTED]