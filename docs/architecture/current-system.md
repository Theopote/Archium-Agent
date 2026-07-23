# 当前系统架构

> 本文描述 v0.2.0a5 代码库的当前结构。历史阶段文档中的 Stage、Round 或 Phase 编号不是运行时架构版本。

## 产品入口

| 入口 | 实现 | 用途 |
|---|---|---|
| `archium` | `archium.cli:main` | 启动 Streamlit 主产品 |
| `streamlit run app.py` | `app.py` | 与 `archium` 等价的开发入口 |

`legacy/` 保留在仓库中供开发者按需运行（`python -m legacy.main` / `python main.py`），**不**随 `archium-agent` 安装，**不**被 `archium.*` 导入，也不出现在主导航。验收：`rg "from legacy|import legacy" archium` 必须为空。

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

评论固定到创建时的 Scene revision、hash 与节点快照；版本已变化时进入 `needs_rebase`，避免静默应用到错误节点。

## 分层与目录

| 层 | 目录 | 职责 |
|---|---|---|
| 领域模型 | `archium/domain/` | Pydantic 模型、枚举、不变量；视觉模型在 `domain/visual/` |
| 应用服务 | `archium/application/` | 用例编排、审核、版本、导出、视觉编辑和修复 |
| 工作流 | `archium/workflow/` | Planning、Presentation、Visual 的可暂停流程 |
| 基础设施 | `archium/infrastructure/` | 数据库、解析、LLM、检索、布局、渲染、存储、视觉分析 |
| UI | `archium/ui/` | Streamlit 页面、Studio 面板和 canvas component |
| Agents/Prompts | `archium/agents/`、`archium/prompts/` | 结构化生成与提示词；不是全部业务逻辑所在层 |

## 视觉与编辑现状

- 固定画布先计算 `SlideCapacityBudget`。状态为 `fits`、`tight`、`overloaded`、`impossible`；超载后禁止继续缩小字体，改走内容适配或拆页。
- Layout family generator 负责确定坐标；Renderer 只执行 LayoutPlan/RenderScene，不重新选择版式。
- Canvas 支持点击、Shift 多选、框选、文字/图片编辑，以及多选对齐、分布和等宽高。
- 元素评论支持单节点、多选、包围盒区域和整页作用域，并通过 Inbox 管理状态。
- 图片处理保存原图，`ImageTreatmentSpec` 生成不可变 derivative；项目图纸和证据照片只允许 `safe_normalize`，不能使用表达性统一处理。
- 字体资产、回退链与 Scene 语义 QA 共同检查潜在重排风险。

## 持久化与迁移

本地首次启动可由 `init_database()` 创建空 SQLite；已有数据库和共享环境必须使用 `alembic upgrade head`。Repository 和 mapper 位于 `archium/infrastructure/database/`。Scene、提案、评论、修订等编辑对象都应通过正式 repository/service 写入，不能只保存在 Streamlit session state。

## 外部依赖边界

- LLM/Embedding 通过配置和 provider factory 接入；无 Key 时应用可以启动，但生成能力会受限。
- PDF/DOCX/PPTX/XLSX/图片解析由可选 `documents` extra 提供。
- 原生 PPTX 使用 Node.js/PptxGenJS；PDF 与真实截图还可能需要 LibreOffice、PowerPoint 或相关转换工具。
- 所有配置字段以 `archium/config/settings.py` 为事实源，生成物见 [配置参考](../configuration-reference.md)。

## 相关文档

- [文档中心](../README.md)
- [视觉架构](../visual/architecture.md)
- [Studio 用户指南](../studio-user-guide.md)
- [管线角色](pipeline-roles.md)
