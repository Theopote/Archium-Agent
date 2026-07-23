# 当前系统架构

> 本文描述 v0.2.0a5 代码库的当前结构。历史阶段文档中的 Stage、Round 或 Phase 编号不是运行时架构版本。

## 产品入口

| 入口 | 实现 | 用途 |
|---|---|---|
| `archium` | `archium.cli:main` | 薄包装：`streamlit run app.py` |
| `streamlit run app.py` | `app.py` → `archium.bootstrap.create_application()` | 与 `archium` 同一 Streamlit shell |

启动时环境变量、日志、数据库与页面注册统一由 `archium.bootstrap` 完成（`.env` 固定读仓库根，不依赖进程 cwd）。`archium.ui.bootstrap` 仅保留样式 / 品牌与兼容用的 `init_app()`。

依赖：`full` extra 必须覆盖全部 runtime extras（测试守卫）；可复现安装用 `requirements/*.lock`（`uv` 生成）。Documentation URL 指向默认分支 `master`。CI 分层为 `compatibility`（3.11/3.12 unit+mypy）与 `quality-full`（3.12 integration/golden/render）；安全审计见 `docs/security/`（chromadb CVE 可 allowlist；`setuptools>=83` 在 security-scan）。能力完成度以 [发布等级矩阵](../release-capability-matrix.md) 为准；发版须过 [用户任务剧本 A–E](../user-task-playbooks.md)（剧本 A 自动化门禁：`scripts/run_playbook_a_gate.py`），不得仅凭模块测试宣称 Stable。

`legacy/` 保留在仓库中供开发者按需运行（`python -m legacy.main` / `python main.py`），**不**随 `archium-agent` 安装，**不**被 `archium.*` 导入，也不出现在主导航。**状态冻结**：不再接受功能修改；Ruff/Mypy/CI 不检查 `legacy/` 与根 shim。验收：`rg "from legacy|import legacy" archium` 必须为空。静态检查：`ignore_missing_imports = false`，仅对无 stub 的第三方包在 overrides 中忽略。

应用页面由 `archium/ui/app_navigation.py` 注册。当前页面覆盖项目、任务规划、生成工作区、Studio、视觉设计、页面恢复、模板归纳、模板库、模板 Studio、设置等能力。

## 主数据流

```text
Project + SourceDocument
  -> Chunk / ProjectFact / FactLedger / Asset
  -> ProjectMission -> Workstream -> DeliverablePlan
  -> PresentationBrief -> Storyline -> SlideSpec
  -> SlideDesignBrief -> VisualIntent -> LayoutPlan
  -> RenderScene -> Scene QA / Proposal / Revision
  -> JSON / Marp / editable PPTX / PDF / preview images
```

Studio 的编辑闭环不是直接覆写导出文件：

```text
画布选择或评论
  -> StudioCommand / ElementEditIntent
  -> SceneChangeProposal
  -> deterministic + semantic QA
  -> 接受或拒绝
  -> SceneRevision / history / undo
```

提案的 base/proposed 以独立 Scene 快照行持久化，接受后写回 live RenderScene 并同步 LayoutPlan；提案状态更新不得再覆写 live。UI `clear_proposal` 只清 session 缓存。Studio 几何编辑 / 修订恢复依赖外层 session 提交，服务内不再中途 `commit`。

评论固定到创建时的 Scene revision、hash 与节点快照；版本已变化时进入 `needs_rebase`，避免静默应用到错误节点。

## 分层与目录

| 层 | 目录 | 职责 |
|---|---|---|
| 领域模型 | `archium/domain/` | Pydantic 模型、枚举、不变量；视觉模型在 `domain/visual/`；**不**依赖 application / infrastructure / UI。自然语言解析器位于 `application/visual/`，domain 仅保留 `ParsedIntent` 等 DTO |
| 应用服务 | `archium/application/` | 用例编排、审核、版本、导出、视觉编辑和修复；**不**依赖 `archium.ui`（版式就绪判断见 `visual/layout_readiness.py`） |
| 工作流 | `archium/workflow/` | Planning、Presentation、Visual 的可暂停流程；审批门与 `require_*_review` 标志一致；成果选择变更会使 DeliverablePlan 审批失效；工作路径选择变更同样会使下游计划审批失效；Storyline 优先通过 PlanningSession 绑定 Mission 叙事模式 |
| 基础设施 | `archium/infrastructure/` | 数据库、解析、LLM、检索、布局、渲染、存储、视觉分析；Repository 封装 ORM，Application 不直接 import `models`。事实冲突组仅在检测到真实冲突时写入（alias:/key:/empty:），不同指标（如用地/建面）不共享 catalog 冲突组 |
| UI | `archium/ui/` | Streamlit 页面、Studio 面板和 canvas component。产品主路径为五段式 `materials → outline → generate → edit → deliver`；`edit` 嵌入 Studio。Studio 选区统一经 `set_studio_selection` 同步单选/多选 key。 |
| Agents/Prompts | `archium/agents/`、`archium/prompts/` | 结构化生成与提示词；不是全部业务逻辑所在层 |

## 视觉与编辑现状

- 固定画布先计算 `SlideCapacityBudget`。状态为 `fits`、`tight`、`overloaded`、`impossible`；超载后禁止继续缩小字体，改走内容适配或拆页。`CAPACITY.*` 警告会写入工作流 warnings；`CAPACITY.IMPOSSIBLE` 会硬阻断 layout candidates。
- 已批准 / 待确认的 `SlideDesignBrief` 会注入 `VisualIntent`（layout family、density、资产与图面策略）。Brief 中的 `photo_evidence_grid` 等别名归一为 `LayoutFamily` 枚举值（如 `evidence_board`）。
- Layout family generator 负责确定坐标；Renderer 只执行 LayoutPlan/RenderScene，不重新选择版式。
- Visual workflow 与 Studio 共用 `SceneCompilerChain` + `ImageDerivativeService` 编译 RenderScene；按 `layout_plan_id` 复用 scene id / version。`LayoutPlan.overflow_policy`（默认 WARN）映射为 TextNode `error`，使 `SEMANTIC.TEXT_OVERFLOW` 可被检出并修复。
- **导出 SSOT（DOM-003）：** 正式可编辑 PPTX 权威为 ``RenderScene`` → `presentation.pptx`。`PresentationSpec` 仅为由 `SlideSpec` 派生的遗留模板导出格式（兼容/测试），不再与 Scene 并列作为正式交付真相。无视觉版式时 **默认拒绝** Spec PPTX 回退；仅当 ``allow_legacy_presentation_spec_pptx_fallback=true`` 时才允许并写入警告。
- **几何 SSOT（DOM-011）：** 版式引擎写出的 LayoutPlan 为 `geometry_authority=layout_plan`；Studio / Scene 修复改几何后同步 Plan 并将权威切为 `render_scene`。此后 `ensure_scene_for_slide`（非 force）不得用 Plan 重编译覆盖 Scene。布局引擎再次改写 Plan 时经 `refresh_after_layout_edit` 收回权威为 `layout_plan` 再 force 重编译。
- **正式 Studio 交付物**为 RenderScene → `presentation.pptx`（导出前 `AssetPathResolver.resolve_scene`）。Visual workflow 在 compile/repair 后写入同名正式文件；Critic 截图绑定该文件（RP-003）。LayoutPlan 指令 JSON 为校验产物；可选 `export_layout_plan_validation_pptx=true` 时另写 `presentation.layout_plan.validation.pptx`（非正式交付）。
- Canvas 支持点击、Shift 多选、框选、文字/图片编辑，以及多选对齐、分布和等宽高。
- 元素评论支持作用域：`node`（单节点）、`node_and_references`、`selection`（多选）、`region`（包围盒区域）、`slide`（整页），并通过 Inbox 管理状态。
- 图片处理保存原图，`ImageTreatmentSpec` 生成不可变 derivative；项目图纸和证据照片只允许 `safe_normalize`，不能使用表达性统一处理（`presentation_unify`）。
- 字体资产、回退链与 Scene 语义 QA 共同检查潜在重排风险。
- 正式导出 readiness：以 ``IssueSeverity``（blocker/major/minor）为导出门禁权威（DOM-004）；`ReviewSeverity` / `LayoutIssueSeverity` 经 `domain.visual.severity` 桥接。ReviewIssue 导出门控认 gate BLOCKER，以及 gate MAJOR 且命中资产加载 / Scene 阻断规则码；内存 Scene semantic 用 BLOCKER；DeckQA `blocker_count` 仅计 Layout CRITICAL（→ BLOCKER）。提案接受后的 `qa_status`：blocker→`blocked`，major→`needs_review`。Post-render 截图缺失会发出 `POST_RENDER.IMAGE_NOT_LOADED`，不再静默跳过。
- **页类型权威（DOM-005）：** `SlideType` / `FunctionalSlideType` / `TemplatePageType` / Spec `layout` 字符串互不等价；交叉转换只经 `domain.visual.page_type_catalog`（co-plan、matcher、induction publisher、Spec layout 常量）。
- **布局族受控（DOM-006）：** Brief / RenderScene 的 `layout_family` 为 `LayoutFamily | None`；别名归一与非法拒绝经 `layout_family_normalize`（空表示未设）。Spec `layout` 仍是 DOM-005 模板 id，不是布局族。
- **工作流步骤（DOM-007）：** 阶段枚举 `Presentation` / `Planning` / `Visual` / `SlideRecovery`；LangGraph 图定义仅用字符串节点名；`WorkflowStep` 为由阶段合成的兼容词表（进度标签 / 角色映射）。

## 持久化与迁移

本地首次启动可由 `init_database()` 创建空 SQLite；已有数据库和共享环境必须使用 `alembic upgrade head`。Repository 和 mapper 位于 `archium/infrastructure/database/`。Scene、提案、评论、修订等编辑对象都应通过正式 repository/service 写入，不能只保存在 Streamlit session state。

## 外部依赖边界

- LLM/Embedding 通过配置和 provider factory 接入；无 Key 时应用可以启动，但生成能力会受限。
- PDF/DOCX/PPTX/XLSX/图片解析由可选 `documents` extra 提供。
- 原生 PPTX 使用 Node.js/PptxGenJS；PDF 与真实截图还可能需要 LibreOffice、PowerPoint 或相关转换工具。
- 所有配置字段以 `archium/config/settings.py` 为事实源，生成物见 [配置参考](../configuration-reference.md)。
- 凭证优先级：会话 → OS keyring（`archium-agent`）→ 环境变量。`storage://` / `project://` / `benchmark://` 解析必须落在 `project_storage` 或 benchmark 根目录内；资产写入文件名经 basename 净化。`FIELD_DOMAINS` 必须覆盖全部 Settings 字段。

## 测试分层

| 层 | 路径 / 标记 | CI |
|---|---|---|
| unit | `tests/unit`、`tests/ui`、`tests/domain`、`tests/spike`（路径自动标 `unit`） | `pytest -m unit` |
| integration | `tests/integration`、`tests/application` | `pytest -m "integration and not e2e"` |
| golden | `tests/golden/*`（按路径跑，不强制主 tier 标记） | regression / mission / fixtures / visual jobs |
| e2e / benchmark / smoke | 对应目录 | nightly 或专用 job |

集成 gate 的样例图用 `materialize_inline_image` 生成，不依赖 `tests/calibration` 语料二进制。

## 文档分层

- 现行入口：`README.md`、`docs/README.md`、`docs/architecture/current-system.md`、Studio / Visual 指南。
- 过程性会话与 `COMPLETE_*` / `FINAL_*` / `SESSION_SUMMARY_*` 归档到 `.dev-notes/docs-history/`，不进入产品导航。
- 配置事实源为 `Settings` + 生成脚本；禁止手改 `docs/configuration-reference.md` / `.env.example`。

## 架构契约锚点（机器可读）

> 下列列表由 `tests/unit/test_architecture_contracts.py` 校验，必须与 domain 枚举/策略一致。  
> 修改运行时代码时同步更新此处与上文叙述；禁止只改文档不改测试。

```arch-contract:capacity-status
fits
tight
overloaded
impossible
```

```arch-contract:element-comment-scope
node
node_and_references
selection
region
slide
```

```arch-contract:image-treatment-mode
none
safe_normalize
presentation_unify
document_scan
```

```arch-contract:evidence-asset-class
project_drawing
project_evidence_photo
```

```arch-contract:evidence-allowed-modes
none
safe_normalize
```

```arch-contract:overflow-policy-default
warn
```

```arch-contract:geometry-authority
layout_plan
render_scene
```

```arch-contract:formal-export-authority
render_scene
```

```arch-contract:legacy-spec-pptx-fallback-default
false
```

```arch-contract:formal-delivery-pptx-filename
presentation.pptx
```

```arch-contract:canvas-capabilities
marquee
shiftKey
set_studio_selection
```

```arch-contract:product-flow-stages
materials
outline
generate
edit
deliver
```

## 相关文档

- [文档中心](../README.md)
- [视觉架构](../visual/architecture.md)
- [Studio 用户指南](../studio-user-guide.md)
- [管线角色](pipeline-roles.md)
