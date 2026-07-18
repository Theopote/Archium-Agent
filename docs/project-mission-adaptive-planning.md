# Project Mission & Adaptive Planning

> **先理解这次任务是什么，再决定研究、分析与成果。**  
> 本能力插在现有「资料 → 事实 → Brief → Storyline → SlideSpec」主链**之前**，不依赖固定医院/寺庙/乡村模板。

相关实现：Steps 1–11（领域模型 → 持久化 → 服务 → LangGraph → UI → Golden M1–M6）。

---

## 1. 产品定位

建筑任务高度多样（重建、改造、环境提升、村庄更新、指标明确新建、专项咨询等）。**项目类型（ProjectType）只是背景，不能等同于任务性质（TaskNature），也不能直接决定工作流或汇报大纲。**

推荐主路径：

```
自由任务描述 + 项目资料
        ↓
ProjectMission（任务理解）
        ↓
KnowledgeGap / Assumption / ClarifyingQuestion
        ↓
Workstream（动态工作路径）
        ↓
DeliverablePlan（动态成果）
        ↓
用户确认
        ↓
PresentationRequest 适配
        ↓
Brief → Storyline → SlideSpec → 审核 → 导出
```

快捷路径（仍保留）：在「项目工作台」直接填写 Brief 表单跑汇报管线。

---

## 2. 用户指南（Streamlit）

### 入口

1. 启动：`archium` 或 `streamlit run app.py`
2. 侧边栏打开 **项目任务**
3. 选择已有项目（可先在「项目工作台」创建并导入资料）

### 六步体验

| 步骤 | 页面行为 | 系统动作 |
|------|----------|----------|
| 1. 描述任务 | 自由文本 + 可选示例 → **分析任务** | `PlanningWorkflowService.run` → 停在澄清闸门 |
| 2. 任务理解 | 分字段展示/编辑；澄清修订后需**显式批准** | `MissionPatch` / `approve_mission` |
| 3. 关键问题 | 回答 / 假设 / 暂不确定 / 不适用 | readiness → `continue_after_clarification` → mission_approval |
| 4. 工作路径 | 勾选能力卡片 | `WorkstreamPlanningService` 选型 |
| 5. 选择成果 | 必要项不可取消 | `DeliverablePlanningService` 选型 |
| 6. 开始执行 | 预览 PresentationRequest → 批准并生成汇报 | `approve_and_continue` → 适配 → Presentation 主链 |

页面刷新后可通过 `workflow_kind=planning` 的 WorkflowRun 恢复进度。

### 专业约束（产品规则）

- **不编造**面积、用地、高度、预算、规范条件；已确认 Fact Ledger 事实必须保留。
- 信息不足时产生 KnowledgeGap / 追问，而不是填假数。
- 未回答的**非阻塞**问题不全部卡住流程。
- Workstream **名称不会**机械变成汇报章节；最终章节由 Storyline 根据 Brief 生成。
- 专项咨询（如园区低碳）不得默认成「完整建筑设计方案 PPT」。

---

## 3. 架构与模块

| 层 | 路径 | 职责 |
|----|------|------|
| Domain | `archium/domain/project_mission.py` 等 | Mission / Gap / Assumption / Question / Workstream / Deliverable |
| Persistence | `mission_mappers.py` / `mission_repositories.py` / Alembic `008` | 7 张表 + cascade |
| Application | `project_mission_service.py`、`mission_parser.py`、`mission_validation_service.py`、`mission_clarification_service.py`、`workstream_planning_service.py`、`deliverable_planning_service.py`、`mission_to_presentation_request.py`、`planning_workflow_service.py` | 生成、解析、专业一致性校验、澄清、规划、适配、工作流门面 |
| Workflow | `planning_state.py` / `planning_nodes.py` / `planning_graph.py` | LangGraph + interrupt/resume |
| UI | `pages/project_mission.py` + `*_panel.py` + `planning_service.py` | 六步工作台 |
| Tests | `tests/unit/test_*mission*`、`tests/integration/test_planning_workflow.py`、`tests/golden/mission/` | 单元 / 闸门 / Golden M1–M6 |

### Planning Workflow 节点

```
load_project_context → analyze_task → validate_mission
  → await_user_clarification  ⟵ interrupt（clarification）
  → revise_mission → await_mission_approval ⟵ interrupt（mission_approval）
  → plan_workstreams → plan_deliverables
  → await_plan_approval       ⟵ interrupt（plan_approval）
  → prepare_presentation_request → finalize
```

- **职责分离**：`mission_parser` 负责 LLM draft → domain model（含事实账本防编造）；`MissionValidationService` 负责 domain model → 专业一致性（task_natures、scope 冲突、blocking gap、置信度与未知矛盾、专项咨询误判完整设计等）。`validate_mission` 节点调用后者，`errors` 失败流程，`warnings`/`suggestions` 写入状态。
- **批准 ≠ 继续**：领域层拆分 `approve_mission` / `approve_deliverable_plan` 与 `resume_after_mission_approval` / `resume_after_plan_approval`；UI 可用 facade `approve_mission_and_continue` / `approve_and_continue`。澄清 readiness 不能替代 Mission 批准 gate。
- Checkpoint：复用 `WorkflowCheckpointerManager`（SQLite）。
- **`PlanningSession`** 是规划主键；`WorkflowRun.presentation_id` **可空**，规划启动时**不**创建 Presentation。
- 仅当用户批准并启动已选 `PRESENTATION` 成果时，才由汇报管线创建真正的 Presentation，并写回 `PlanningSession.presentation_id`。

### Presentation 适配

`DeliverableExecutionRouter` 按成果类型路由：

| DeliverableType | 请求类型 | 当前自动生成 |
|-----------------|----------|--------------|
| `PRESENTATION` | `PresentationRequest` | 支持 |
| `REPORT` / `TECHNICAL_PROPOSAL` | `ReportRequest` | 规划完成，生成未支持 |
| `MEMO` | `MemoRequest` | 同上 |
| `CHECKLIST` | `ChecklistRequest` | 同上 |
| `CASE_STUDY` | `CaseStudyRequest` | 同上 |
| `WORK_PLAN` / roadmap | `WorkPlanRequest` | 同上 |

**禁止**将非 PPT 成果静默退化成 `PresentationRequest`。未支持类型显示：「该成果已完成规划，但当前版本尚未支持自动生成。」

`build_presentation_request(mission, deliverable, workstreams=..., user_overrides=...)` 仅接受 `PRESENTATION`：

| 来源 | → PresentationRequest |
|------|------------------------|
| `task_statement` | `purpose` |
| `decisions_required` | `decisions_required` |
| stakeholder concerns | `audience_concerns` |
| deliverable `content_scope` / `in_scope` | `required_sections` |
| `out_of_scope` | `excluded_topics` |
| design/research questions + 已选 workstreams | `user_notes`（生成上下文） |

---

## 4. 数据模型摘要

| 表 / 实体 | 说明 |
|-----------|------|
| `planning_sessions` | 规划会话主键（`current_mission_id` / `workflow_run_id` / 可选 `presentation_id`） |
| `project_missions` | 版本化任务理解（`lineage_id` + `version`） |
| `knowledge_gaps` | 知识缺口（含 `blocking`） |
| `project_assumptions` | 正式假设 |
| `clarifying_questions` | 用户追问（首轮建议 ≤5） |
| `design_questions` | 设计命题 |
| `workstreams` | 动态工作路径（可选中；含 `recommendation_reason`） |
| `deliverable_plans` | 成果计划；`deliverables` JSON + Pydantic 校验 |

关键枚举（节选）：`TaskNature`、`InterventionScale`、`ServiceDepth`、`ProjectDomain`、`WorkstreamType`、`DeliverableType`、`RevisionEntityType`（含 `MISSION` / `WORKSTREAM_PLAN` / `DELIVERABLE_PLAN` / `ASSUMPTION`）。

**命名注意：** Workstream ≠ LangGraph `WorkflowStep`。前者是业务工作路径，后者是编排步骤。

---

## 5. 数据库迁移

| 项 | 值 |
|----|-----|
| Head | `010_planning_session_decouple` |
| 009 | `workstreams.recommendation_reason` |
| 010 | `planning_sessions` + `workflow_runs.presentation_id` 可空 |
| 验证 | `pytest tests/smoke/test_alembic_migration.py -v` |

已有本地库升级：

```bash
alembic upgrade head
alembic current   # 应包含 010_planning_session_decouple
```

`init_database()` / `create_all` **不会**自动给旧库补新表；共享/生产环境必须跑 Alembic。

### Revision / 已知未知

- Mission / Workstream / DeliverablePlan 通过 `MissionHistoryService` 等写入统一 `entity_revisions`（`presentation_id` 可为空），`change_source` 使用通用 `RevisionSource`（`GENERATED` / `MANUAL_EDIT` / `REGENERATION` / `CLARIFICATION` / `APPROVAL` 等），不再复用 `SlideChangeSource` 命名。
- UI「关键问题」步展示五列：**已确认 / 推断 / 假设 / 冲突 / 待确认**，并支持缺口回答、按假设、暂缓，以及事实确认/驳回。
- 规划链路：`Project → PlanningSession → Mission → DeliverablePlan →`（仅 PRESENTATION）`Presentation`。

---

## 6. 开发者快速调用

```python
from archium.application.planning_workflow_service import PlanningWorkflowService
from archium.application.presentation_workflow_service import PresentationWorkflowService

planning = PlanningWorkflowService(session, llm, settings=settings)
result = planning.run(project_id, "自由任务描述…")
# …用户回答问题后…
result = planning.continue_after_clarification(result.workflow_run.id)
# …确认任务理解后（批准与继续可拆分）…
result = planning.approve_mission_and_continue(result.workflow_run.id)
# …调整 workstream/deliverable 后…
planning.approve_deliverable_plan(result.deliverable_plan.id)
result = planning.resume_after_plan_approval(result.workflow_run.id)
# 或 UI facade：result = planning.approve_and_continue(result.workflow_run.id)
bridge = planning.get_presentation_bridge(result.workflow_run.id)

presentation = PresentationWorkflowService(session, llm, settings=settings)
presentation.run(project_id, bridge.request, require_brief_review=True)
```

UI 门面：`archium/ui/planning_service.py`。

---

## 7. Golden Scenarios（M1–M6）

### Layer 1b — Mock regression（CI）

```bash
pytest tests/golden/mission -v -m regression
```

| Case | 场景 | 验证重点 |
|------|------|----------|
| M1 | 清凉寺重建 | reconstruction/research；历史/面积缺口；不编造面积 |
| M2 | 大学图书馆改造 | renovation/adaptive_reuse；不停业；汇报+分期路线图 |
| M3 | 医院环境提升 | 非新建；患者旅程；决策汇报 |
| M4 | 村庄更新 | 多主体；资源/居民/实施；反模板 |
| M5 | 消防站新建 | 保留明确指标；无「面积待确认」 |
| M6 | 园区绿色低碳专项 | consulting；排除施工图/设备选型/碳认证；报告非方案 PPT |

### Layer 3 — Live API + 人工评分（必做下一轮）

Mock 不能证明真实模型理解六种任务。用真实 API：

```powershell
$env:ARCHIUM_LIVE_LLM = "1"
py scripts/eval_mission_live.py
```

人工评分（满分 100，及格 ≥70）：任务性质 15 · 尺度与服务深度 10 · 事实忠实度 20 · 关键未知 15 · 澄清问题价值 15 · Workstream 15 · Deliverable 10。  
详见 `tests/golden/live/EVALUATION_CHECKLIST.md`。

规划闸门集成测试：`pytest tests/integration/test_planning_workflow.py -v`。

---

## 8. 验收清单

### 功能

- [x] 用户可自由描述任意建筑任务
- [x] 生成结构化 ProjectMission
- [x] 不依赖固定项目模板驱动大纲
- [x] 信息不足时生成 KnowledgeGap
- [x] 用户可回答问题或接受假设后继续
- [x] 动态 Workstream / DeliverablePlan
- [x] 用户批准后进入现有 Presentation 主链
- [x] 不破坏 Brief / Storyline / SlideSpec
- [x] 页面刷新可恢复规划状态
- [x] LangGraph interrupt / resume（澄清 + Mission 批准 + 成果批准；批准与继续分离）

### 专业

- [x] 不编造面积/用地/高度等（解析器反编造 + Golden）
- [x] TaskNature ≠ ProjectType
- [x] 专项咨询不误判为完整建筑设计（M6）
- [x] 设计问题表达条件、矛盾与目标
- [x] 工作范围 / 非范围可编辑
- [x] 非阻塞问题不全体阻塞

### 工程

- [x] 领域 / 仓库 / 服务 / 工作流 / UI facade 测试
- [x] Alembic `008` + migration smoke 指向 head
- [x] Checkpointer allowlist 含 mission 领域类型
- [ ] 完整 CI matrix / coverage 门禁以仓库当前 CI 配置为准（合并前请跑相关套件）

### 非目标（本轮明确不做）

医院/寺庙/消防站/村庄固定模板、自动 CAD/BIM/平面、通用搜索 Agent、完整规范/案例库、多租户/云端/权限、更多 PPT Theme/SlideType、替建筑师决定唯一方案。

---

## 9. 与 Beta Backlog 的关系

[v0.2-beta-backlog.md](v0.2-beta-backlog.md) 冻结的是 **Brief 主链** 验收 blocker。  
Mission Planning 是 PDF 要求的**前置规划层**，已作为独立能力交付：不替代 Beta Golden A/B/C，也不把固定模板重新引入产品。

推荐产品话术：

1. **项目任务**完成理解与成果确认  
2. 再进入 **项目工作台** 审核 Brief / Storyline / 导出  

成功标准（摘自规格）：用户确认任务理解与成果后，系统才进入 Brief、Storyline 和 SlideSpec。
