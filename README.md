# Archium Agent

[![CI](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Archium（阿基姆）是一款面向建筑师、规划师、设计院和建筑事务所的**智能汇报生产工具**。


它的目标不是简单地「让 AI 写一个 PPT」，而是：

> 读取建筑项目资料 → 理解项目事实和设计逻辑 → 根据汇报对象与目的组织叙事 → 生成可追溯、可编辑、可审核的汇报材料 → **按建筑表达目标编排版式（视觉编排）**。

## 版本与成熟度

| 项 | 值 |
|----|-----|
| **Current version** | v0.2-alpha.5 |
| **Architecture stage** | Stage 16+（视觉 QA、叙事拆页、CI smoke 已落地） |
| **Current sprint** | [v0.2 Beta Rehearsal](docs/v0.2-beta-rehearsal.md) → [发布决策](docs/v0.2-beta-release-decision.md) |
| **Stability status** | Alpha（**尚未**打 Beta 标签 — 见发布决策） |
| **Production readiness** | Not ready |

> Alpha 阶段功能可以演示和内部试用，但不保证 API、数据模型或输出格式的长期稳定；请勿直接用于生产交付。

## Quickstart

### 🐳 Docker 部署（推荐 · 一键启动）

**适合首次使用或希望快速体验的用户。**无需手动配置 Python 和 Node.js 环境。

```bash
git clone https://github.com/Theopote/Archium-Agent.git
cd Archium-Agent
cp .env.example .env               # 配置 LLM API Keys（可选）
docker-compose up -d               # 启动服务
# 访问 http://localhost:8501
```

**详细指南：** [Docker 快速启动](docs/deployment/docker-quickstart.md) · [5分钟快速测试](DOCKER_QUICK_TEST.md)

**NLP 子功能快速入门：** [`docs/guides/nlp-quickstart.md`](docs/guides/nlp-quickstart.md)

### 📦 传统部署

**v0.2 主路径**：安装 → 配置 → `archium`（或等价的 `streamlit run app.py`）。

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[full]"
cp .env.example .env               # Windows: copy .env.example .env
archium                            # 启动项目工作台（Streamlit UI）
```

**注意：** 原生 PPTX 导出需要 Node.js 18+ 并在 `archium/infrastructure/renderers/pptxgen` 运行 `npm install`。

| 路径 | 命令 | 说明 |
|------|------|------|
| **主路径** | `archium` | 安装后的默认命令，启动 v0.2 项目工作台 |
| 等价主路径 | `streamlit run app.py` | 与 `archium` 相同，适合已有 Streamlit 工作流的用户 |
| Legacy（高级） | `archium-legacy` 或 `python main.py` | v0.1 实验 CLI（文件整理 / 快速 PPT），**不是**主产品 |

开发者额外依赖：`pip install -e ".[full,dev]"`。Legacy CLI 与主产品共用 `[full]`（至少需 `[llm]`）；详见下文「Legacy 入口」。

**不再新增 Stage。** 当前冲刺是 [v0.2 Alpha Validation Sprint](docs/v0.2-alpha-validation-sprint.md)——用三个真实建筑 Golden Case 证明主链可用，而非继续扩展功能列表。Beta 范围冻结见 [docs/v0.2-beta-backlog.md](docs/v0.2-beta-backlog.md)。

### 完整主链

```
资料 → 事实
     →（推荐）项目任务：Mission → 澄清 → Workstream → Deliverable → 确认
     → Brief → Storyline → SlideSpec → 引用 → 素材
     →（可选）视觉编排：ArtDirection → VisualIntent → LayoutPlan → 校验/修复
     → 四层审核 + 视觉 QA → 修复 → JSON / 原生元素 PPTX / PDF
```

逻辑角色（Research / Narrative / Architecture / Composition / Layout / Render / Critic）与服务映射见 [`docs/architecture/pipeline-roles.md`](docs/architecture/pipeline-roles.md)——**角色 ≠ Agent 类**。

前置规划说明见 [`docs/project-mission-adaptive-planning.md`](docs/project-mission-adaptive-planning.md)。视觉编排说明见 [`docs/visual/README.md`](docs/visual/README.md)。工作台仍保留直接填 Brief 的快捷路径。

## Golden Case 验收（三层模型）

| 层 | 名称 | 说明 | CI |
|----|------|------|-----|
| **L1** | Deterministic workflow regression | Mock LLM + 内联文本，验证主链逻辑 | ✅ |
| **L2** | Real fixture acceptance | 脱敏真实资料 + 真实 parser + 缓存 LLM | ✅ |
| **L3** | Live model evaluation | 真实 API，评估输出质量 | ❌ 手动 |

L1 **不是**完整真实项目验收，而是固定 Mock 下的工作流回归。L2/L3 逐步覆盖 PDF 解析、复杂资料、模型波动与 PowerPoint 可打开性等。

| 案例 | 场景 | 验证重点 |
|------|------|----------|
| **Case A** | 医院老院区更新 | 多来源事实冲突、交通/功能汇报、证据层、决策型 Brief |
| **Case B** | 校园建筑改造 | 现状问题、分期实施、功能调整、对比/数据页面 |
| **Case D** | 20 页完整汇报 | 长 deck、PresentationSpec 导出 |
| **Case E** | 中文/空格路径 + 多格式 | PDF/DOCX/PPTX/低清 JPG 真实 parser、冲突数据 |
| **M1–M6** | 任务理解 / 自适应规划 | 重建、改造、环境提升、村庄更新、指标新建、专项咨询 |

```bash
pytest tests/golden/regression -v    # Layer 1（汇报主链）
pytest tests/golden/mission -v       # Layer 1b（Mission Planning M1–M6）
pytest tests/golden/fixtures -v      # Layer 2（含 case_e 路径压力）
pytest tests/golden -v               # 全部（不含 live_llm）
pytest tests/smoke -v                # PptxGen / Marp / Streamlit / Alembic smoke
pytest tests/smoke/test_pptxgen_render.py -v  # PptxGenJS 真实 Node 渲染（PresentationSpec）
pytest tests/smoke/test_layout_plan_pptx_render.py -v  # LayoutPlan → PPTX 执行路径
pytest tests/unit/visual tests/integration/visual tests/golden/visual/composition -q  # 视觉编排
```

跨平台说明见 [`docs/cross-platform-validation.md`](docs/cross-platform-validation.md) 与 Beta 支持矩阵 [`docs/beta-platform-support-matrix.md`](docs/beta-platform-support-matrix.md)。Windows 实机 smoke： nightly [`.github/workflows/windows-smoke.yml`](.github/workflows/windows-smoke.yml)。Real Project Validation 清单见 [`docs/real-project-validation-preparation.md`](docs/real-project-validation-preparation.md)。

## 能力矩阵

| 功能 | 已实现 | 有测试 | 已接主流程 | 可稳定使用 |
|------|:------:|:------:|:----------:|:----------:|
| 项目工作台（Streamlit UI） | ✅ | ✅ | ✅ | ⚠️ |
| **项目任务 / Mission Planning** | ✅ | ✅ | ✅ | ⚠️ |
| 动态 Workstream / DeliverablePlan | ✅ | ✅ | ✅ | ⚠️ |
| Mission → PresentationRequest 适配 | ✅ | ✅ | ✅ | ⚠️ |
| 文档导入（PDF/DOCX/PPTX/XLSX/图片） | ✅ | ✅ | ✅ | ⚠️ |
| 语义分块与资料片段编辑 | ✅ | ✅ | ✅ | ⚠️ |
| 向量检索（Chroma + Embedding） | ✅ | ⚠️ | ✅ | ⚠️ |
| LangGraph 多阶段工作流 | ✅ | ✅ | ✅ | ⚠️ |
| Brief / Storyline / SlideSpec 审核 | ✅ | ✅ | ✅ | ⚠️ |
| 统一修订历史（Brief / Storyline / SlideSpec lineage） | ✅ | ✅ | ✅ | ⚠️ |
| SlideSpec 字段 diff | ✅ | ✅ | ✅ | ⚠️ |
| JSON 导出 | ✅ | ✅ | ✅ | ⚠️ |
| Marp Markdown 导出 | ✅ | ✅ | ✅ | ⚠️ |
| PPTX 导出（Marp CLI） | ✅ | ⚠️ | ✅ | ❌ |
| 原生元素 PPTX 导出（PptxGenJS） | ✅ | ✅ | ✅ | ⚠️ |
| PresentationSpec JSON | ✅ | ✅ | ✅ | ⚠️ |
| PDF 导出（Marp CLI） | ✅ | ⚠️ | ✅ | ❌ |
| 幻灯片预览图（Marp `--images` PNG） | ✅ | ✅ | ✅ | ⚠️ |
| 项目事实账本（Fact Ledger） | ✅ | ✅ | ✅ | ⚠️ |
| 素材看板（Asset Board） | ✅ | ✅ | ✅ | ⚠️ |
| 四层质量审核（内容/证据/建筑/版面） | ✅ | ✅ | ✅ | ⚠️ |
| 视觉 QA（图像可读性 / 指北针 / 图例） | ✅ | ✅ | ✅ | ⚠️ |
| **建筑视觉编排（DesignSystem / ArtDirection / LayoutPlan）** | ✅ | ✅ | ✅ | ⚠️ |
| 视觉设计 UI（ArtDirection 审核 / 候选版式） | ✅ | ✅ | ✅ | ⚠️ |
| LayoutPlan → 原生 PPTX（execute-only） | ✅ | ✅ | ✅ | ⚠️ |
| 叙事感知拆页（SlideSplitPlan） | ✅ | ✅ | ✅ | ⚠️ |
| 拆页引用保护 | ✅ | ✅ | ✅ | ⚠️ |
| 拆页素材重匹配 | ✅ | ✅ | ✅ | ⚠️ |
| 质量审核与导出阻断 | ✅ | ✅ | ✅ | ⚠️ |
| Marp 导出 smoke（PPTX / PDF / PNG） | ✅ | ✅ | — | ⚠️ |
| Streamlit 启动 smoke | ✅ | ✅ | — | ⚠️ |
| Alembic migration smoke | ✅ | ✅ | — | ⚠️ |
| CLI 指令中心（`main.py` / `archium-legacy`） | ✅ | ⚠️ | — | ❌ |
| 遗留实验模块（文件整理） | ✅ | ⚠️ | — | ❌ |

图例：✅ 已满足 · ⚠️ 部分满足或依赖外部工具 · ❌ 未满足或不稳定

## 应用入口

| 入口 | 命令 | 地位 | 说明 |
|------|------|------|------|
| **主入口** | `archium` | v0.2 正式路径 | 安装后的默认命令；启动 Streamlit 项目工作台与结构化汇报管线 |
| **等价主入口** | `streamlit run app.py` | v0.2 正式路径 | 与 `archium` 相同，适合脚本或 IDE 直接调用 Streamlit |
| **Legacy CLI** | `archium-legacy` 或 `python main.py` | 遗留/实验 | v0.1 自然语言路由（文件整理、快速 PPT） |
| **库 API** | `archium/` 包内服务 | v0.2 核心 | `PlanningWorkflowService`、`PresentationWorkflowService`、`VisualWorkflowService`、`IngestionService` 等 |

`main.py` 与 `ppt_generator.py` 属于 **Legacy v0.1** 快速原型路径，**不等同**于项目工作台内的 Brief → Storyline → SlideSpec 主流程。

## 导出格式

主流程通过 `RenderResult` 统一返回导出路径：

```python
@dataclass
class RenderResult:
    json_path: Path | None
    markdown_path: Path | None
    spec_path: Path | None
    pptx_path: Path | None
    editable_pptx_path: Path | None
    pdf_path: Path | None
    preview_images: list[Path]
    warnings: list[str]
```

| 格式 | 主流程 | 实现 | 依赖 |
|------|:------:|------|------|
| **JSON** | ✅ | `JsonPresentationRenderer` | 无 |
| **PresentationSpec JSON** | ✅（可选） | `PptxGenPresentationRenderer.render()` | 无 |
| **Marp Markdown** | ✅ | `MarpPresentationRenderer.render()` | 无 |
| **PPTX（Marp）** | ✅（可选） | `MarpPresentationRenderer.export_pptx()` | Marp CLI |
| **PPTX（原生元素 · Legacy 模板）** | ✅（可选） | `PptxGenPresentationRenderer.export_pptx()` | Node.js + PptxGenJS |
| **PPTX（原生元素 · LayoutPlan）** | ✅（可选） | `export_pptx_from_layout_instructions()` | Node.js + `render-plan.mjs` |
| **PDF** | ✅（可选） | `MarpPresentationRenderer.export_pdf()` | Marp CLI |
| **预览图 PNG** | ✅（可选） | `MarpPresentationRenderer.export_preview_images()` | Marp CLI（`--images`） |

Marp 路径适合快速预览与降级导出。**LayoutPlan PPTX** 按视觉编排坐标执行（`render-plan.mjs`），不重选版式；详见 [`docs/visual/renderer.md`](docs/visual/renderer.md)。**Legacy 模板 PPTX** 仍通过 PresentationSpec → `layouts/*.mjs`，适合主汇报快捷导出，但**尚未**达到建筑事务所级母版系统（见「当前限制」）。PPTX / PDF / 预览图转换失败不会阻断 JSON 或 Markdown 导出，错误写入 `RenderResult.warnings` 或视觉工作流 `warnings`。

## 核心架构

```
Project → SourceDocument → ProjectFact
       → ProjectMission → Gaps/Questions → Workstream → DeliverablePlan
       → PresentationRequest → PresentationBrief
       → Storyline → SlideSpec[]
       →（视觉编排）DesignSystem / ArtDirection / VisualIntent / LayoutPlan
       → Render (JSON / Markdown / LayoutPlan-PPTX / Spec-PPTX / PDF)
```

- Mission Planning：[docs/project-mission-adaptive-planning.md](docs/project-mission-adaptive-planning.md)
- **汇报工作室**：[docs/studio-user-guide.md](docs/studio-user-guide.md)（主编辑界面）
- Visual Composition：[docs/visual/README.md](docs/visual/README.md) · [架构](docs/visual/architecture.md) · [视觉设计指南](docs/visual/user-guide.md)

## 项目目录

```
Archium-Agent/
├── app.py                  # Streamlit 前端（v0.2 主产品 UI）
├── main.py                 # Legacy v0.1 CLI（`archium-legacy`）
├── config.py               # 向后兼容配置 shim
├── archium/                # v0.2 核心包
│   ├── config/settings.py  # pydantic-settings
│   ├── domain/             # Pydantic 领域模型（含 domain/visual）
│   ├── application/        # ingestion、presentation、visual、workflow 等
│   ├── agents/             # Brief / Storyline / Slide 生成 Agent
│   ├── workflow/           # LangGraph（Planning / Presentation / Visual）
│   ├── ui/                 # Streamlit 页面与服务（含视觉设计）
│   ├── infrastructure/
│   │   ├── database/       # SQLAlchemy ORM + Repository
│   │   ├── document_parsers/
│   │   ├── layout/         # LayoutFamily Registry + 确定性 generators
│   │   ├── llm/
│   │   ├── renderers/      # JSON / Marp / PptxGenJS 导出
│   │   │   └── pptxgen/    # 原生元素 PPTX（主题 + 模板 + LayoutPlan 执行）
│   │   └── storage/
│   ├── prompts/            # 含 art_direction / visual_intent / layout_plan
│   ├── exceptions.py
│   └── logging.py
├── docs/
│   ├── studio-user-guide.md # 汇报工作室用户指南
│   └── visual/             # 建筑视觉编排文档
├── legacy/
├── data/
├── tests/
│   └── golden/
│       └── visual/
│           ├── baselines/          # Marp PNG regression
│           └── composition/        # LayoutPlan Golden V1–V3
└── pyproject.toml
```

### PptxGenJS 目录结构

```
archium/infrastructure/renderers/pptxgen/
├── render.mjs              # Legacy：PresentationSpec → PPTX
├── render-plan.mjs         # Visual：LayoutPlan instructions → PPTX
├── layout_plan_adapter.py  # LayoutPlan → instruction deck（Python）
├── design_token_adapter.py # DesignSystem → theme-like dict
├── core/
│   ├── theme.mjs           # 遗留命名主题
│   ├── geometry.mjs
│   ├── image-fit.mjs
│   ├── text-fit.mjs
│   └── validation.mjs
├── layouts/
│   ├── from-plan.mjs       # execute-only（按坐标放置）
│   ├── title.mjs           # Legacy 模板…
│   ├── comparison.mjs
│   ├── site-plan.mjs
│   ├── image-grid.mjs
│   └── data.mjs
└── components/
    ├── header.mjs
    ├── caption.mjs
    ├── citation.mjs
    ├── legend.mjs
    ├── north-arrow.mjs
    └── scale-bar.mjs
```

遗留命名主题：`minimal-light` · `minimal-dark` · `architecture-board` · `government-review` · `competition` · `technical-review`。视觉编排以 DesignSystem 为准，见 [`docs/visual/design-system.md`](docs/visual/design-system.md)。

## 安装

> 若你只想跑起来：**直接看文首 [Quickstart](#quickstart)**。本节补充 Python 版本、extras 组合与 Node/Marp 依赖。

### 🐳 Docker 部署（推荐）

使用 Docker 可以避免手动配置 Python、Node.js 等环境，实现一键部署：

```bash
# 前提条件：已安装 Docker Desktop
docker-compose up -d
```

**优势：**
- ✅ 无需安装 Python 3.11、Node.js 18
- ✅ 环境配置时间从 30-60 分钟缩短到 5 分钟
- ✅ 跨平台完全一致（Windows/macOS/Linux）
- ✅ 数据自动持久化（`./data` 目录）

**完整文档：**
- [Docker 快速启动指南](docs/deployment/docker-quickstart.md)
- [5分钟快速测试](DOCKER_QUICK_TEST.md)
- [完整测试清单](docs/deployment/docker-test-checklist.md)
- [跨平台优化方案](docs/deployment/CROSS_PLATFORM_OPTIMIZATION.md)

### 📦 传统部署

如果需要本地开发或自定义配置，可以使用传统方式安装。

### Python 版本

| 项 | 值 |
|----|-----|
| **requires-python** | `>=3.11` |
| **CI matrix** | 3.11、3.12（Ubuntu） |
| **mypy** | `python_version = 3.11`（与最低支持版本对齐） |

> **依赖说明：** optional extras 互不嵌套自引用。开发者安装 `pip install -e ".[full,dev]"`；普通用户安装 `pip install -e ".[full]"` 即可。模块化 extras（`ui`、`documents` 等）仍可按需单独组合。

PptxGenJS 原生 PPTX 还需 Node.js 20+，在 `archium/infrastructure/renderers/pptxgen` 运行 `npm install`。

### 开发者完整依赖

```powershell
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[full,dev]"
copy .env.example .env
```

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate
pip install -e ".[full,dev]"
cp .env.example .env
```

### 普通用户（仅运行工作台）

与 Quickstart 相同：`pip install -e ".[full]"`，然后 `archium`。

## 环境变量

所有开关的**默认值、环境变量名与说明**以 [`archium/config/settings.py`](archium/config/settings.py) 为唯一事实源。

| 产物 | 说明 |
|------|------|
| [`docs/configuration-reference.md`](docs/configuration-reference.md) | 按能力域分组的完整参考（`retrieval.*` / `review.*` / `repair.*` / `render.*` 等） |
| [`.env.example`](.env.example) | 可复制的环境变量模板（含默认值注释） |

以上文件由 `scripts/generate_config_docs.py` **自动生成**；CI 会校验与 `settings.py` 一致，请勿手工编辑。

```bash
python scripts/generate_config_docs.py        # 本地更新
python scripts/generate_config_docs.py --check  # CI 一致性检查
```

> **无 API Key 时应用可以正常启动**；只有执行 LLM 相关功能时才会提示未配置。  
> 常见误区：`BLOCK_EXPORT_ON_CRITICAL_REVIEW` 与 `SLIDE_REPAIR_ENABLED` 默认均为 **`false`**；`FACT_EXTRACTION_ENABLED` 默认为 **`true`**。以配置参考文档为准。

## 数据库初始化与迁移

项目存在两条建表/升级路径，**不要混用场景**：

| 路径 | 触发方式 | 适用场景 |
|------|----------|----------|
| **`init_database()`** | `streamlit run app.py` 首次启动时自动调用（见 `archium/ui/bootstrap.py`） | 本地全新 SQLite、clone 后空库快速跑通 |
| **Alembic 迁移** | 手动 `alembic upgrade head` | 已有数据库增量升级、生产/staging 部署、CI migration smoke |

### 什么时候必须用 Alembic？

- **生产或共享环境部署**：部署流程中应执行 `alembic upgrade head`，不要依赖 `create_all` 替代 schema 变更管理。
- **已有 `data/database/archium.db` 且仓库新增了 migration**（如 `002`–`008`）：必须 `alembic upgrade head` 才能补上新列/表；`init_database()` / `create_all` **不会**修改已有表结构。
- **Mission Planning 表**（`project_missions`、`knowledge_gaps`、`workstreams`、`deliverable_plans` 等）位于 revision `008_project_mission_planning`；说明见 [project-mission-adaptive-planning.md](docs/project-mission-adaptive-planning.md#5-数据库迁移)。
- **验证 migration 链**：`pytest tests/smoke/test_alembic_migration.py -v`

### 什么时候可以只用 `init_database()`？

- **全新 clone、数据库文件尚不存在**：直接 `streamlit run app.py`，启动时会自动建表。
- **pytest 等临时测试库**：测试自行 `create_all`，不依赖 Alembic。

> **双轨设计说明：** `001_initial_schema` 的 upgrade 为空操作——baseline 表由 `create_all` 创建；后续 revision 通过 Alembic 做增量变更。开发环境省心，生产环境可升级。

```bash
# 生产 / 已有库升级
alembic upgrade head

# 查看当前 revision
alembic current
```

## 运行

### 🐳 Docker 方式

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 访问应用
open http://localhost:8501
```

### 📦 传统方式

```bash
# 主入口（安装后默认命令）
archium

# 等价：直接调用 Streamlit
streamlit run app.py
```

### Legacy 入口（高级 / 实验）

v0.1 自然语言 CLI，**不是** v0.2 主产品。需 `pip install -e ".[full]"`（或至少 `[llm]`；PPT 导出另需 Marp CLI）。

```bash
archium-legacy
# 或
python main.py
```

## 测试

```bash
pytest
pytest tests/golden -v   # Golden Case 回归
ruff check archium tests
mypy archium

# 已有数据库升级 / migration smoke（详见上文「数据库初始化与迁移」）
alembic upgrade head
```

测试不依赖真实 API Key，使用临时目录，不会污染 `data/` 目录。

### CI 与分支保护

[![CI](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml)

仓库在 `push` / `pull_request` 时运行 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)（Python 3.11 / 3.12 matrix）：

| Status check（合并前必须通过） | 内容 |
|-------------------------------|------|
| `test (3.11)` | ruff、mypy、pytest |
| `test (3.12)` | ruff、mypy、pytest |

> 在 GitHub **Branch protection** 界面中，status check 可能显示为 `CI / test (3.11)` 形式（工作流名 + job 名）。勾选与 Python 版本对应的两个 job 即可。

**为 `master` 启用分支保护（仓库 Admin 一次性操作）：**

1. 打开 [Actions](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml) 确认至少有一次 **CI 已在 `master` 上跑绿**（否则 Settings 里还选不到 status check）。
2. GitHub → **Settings** → **Branches** → **Add branch protection rule**
3. **Branch name pattern:** `master`
4. 勾选 **Require status checks to pass before merging**
5. 勾选 **Require branches to be up to date before merging**（推荐）
6. 在 status checks 搜索并勾选 **`test (3.11)`** 与 **`test (3.12)`**（或带 `CI /` 前缀的同名项）
7. （推荐）勾选 **Require a pull request before merging**，**Do not allow bypassing the above settings**

完整说明与 `gh` CLI 脚本见 [`docs/branch-protection.md`](docs/branch-protection.md)。

本地等价命令：

```bash
pip install -e ".[full,dev]"
ruff check archium tests
mypy archium
pytest --cov=archium --cov-report=term-missing
```

## Marp 安装

PPTX / PDF 导出需要 [Marp CLI](https://github.com/marp-team/marp-cli)：

```bash
npm install -g @marp-team/marp-cli
marp --version
```

未安装 Marp 时，应用仍可启动；PPT 导出步骤会给出明确提示。

未安装 Marp 时，应用仍可启动并完成 JSON / Marp Markdown 导出；勾选 PPTX 或 PDF 时会在 `RenderResult.warnings` 中提示。

## 支持的文档格式

| 格式 | 导入 | 解析 | 分块 | 向量索引 |
|------|:----:|:----:|:----:|:--------:|
| PDF | ✅ | ✅ | ✅ | ⚠️（需启用检索） |
| DOCX | ✅ | ✅ | ✅ | ⚠️ |
| PPTX | ✅ | ✅ | ✅ | ⚠️ |
| XLSX | ✅ | ✅ | ✅ | ⚠️ |
| 图片 | ✅ | ✅ | — | — |

导入能力在 Stage 5 完成；语义分块与片段编辑在 Stage 10–11 增强。

## 数据保存位置

| 路径 | 用途 |
|------|------|
| `data/database/` | SQLite 数据库（Stage 3+） |
| `data/projects/` | 项目资料与资产 |
| `data/outputs/` | 生成的汇报文件 |
| `data/chroma/` | Chroma 向量索引（Stage 10） |

## 隐私说明

- API Key 不会写入日志或代码
- 上传文件内容不会完整记录到日志
- 所有数据默认保存在本地
- 使用第三方 LLM API 时，请遵守该服务商的数据与隐私条款；**不要**将未脱敏的客户机密资料发到公开 Issue

## 参与贡献

- 开发与 PR 流程：[CONTRIBUTING.md](CONTRIBUTING.md)
- 行为准则：[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 安全漏洞私下报告：[SECURITY.md](SECURITY.md)
- 第三方依赖许可说明：[NOTICE](NOTICE)

## License

本项目采用 [MIT License](LICENSE) 开源。

```
Copyright (c) 2026 Theopote and Archium contributors
```

你可以将本软件用于商业与非商业用途，前提是保留版权与许可声明。软件按「原样」提供，不附带担保。依赖包与生成产物的权属说明见 [NOTICE](NOTICE)。

## 当前限制

- 指令中心聊天记录仍保存在浏览器 Session 中，关闭页面后会丢失
- 项目工作台已支持项目持久化、资料导入、汇报生成与 Brief / Storyline / SlideSpec 审核编辑
- **项目任务**页支持自由描述 → 任务理解 → 澄清 → 工作路径 → 成果选择 → 进入汇报主链（见 Mission Planning 文档）
- 文档导入后按语义边界切分（段落合并、递归切分、重叠窗口），超长段落可选 Embedding 断点检测
- 工作台支持预览/编辑资料片段，保存后同步更新向量索引
- Brief、Storyline、SlideSpec 均支持基于 `lineage_id` 的统一修订历史；SlideSpec 另支持字段 diff 与 unified diff 对比
- 项目事实账本（Fact Ledger）支持标准键提取、冲突检测与人工确认；已确认事实优先注入生成上下文
- 素材看板（Asset Board）支持视觉需求扁平化视图、素材匹配、人工指定与确认
- **汇报工作室**页支持三栏浏览、NL 视觉编辑（8 意图）、内容适配（4 动作）与 PPTX 导出（见 [`docs/studio-user-guide.md`](docs/studio-user-guide.md)）
- **视觉设计**页支持 ArtDirection 审核、单页候选版式与预设重排（见 [`docs/visual/user-guide.md`](docs/visual/user-guide.md)）
- 四层质量审核：内容层、证据层、建筑专业层、版面层；严重问题可阻断导出
- 原生元素 PPTX 现有两条路径：
  - **LayoutPlan 执行路径**（视觉编排）：坐标来自 LayoutPlan，`render-plan.mjs` 只执行不重排
  - **PresentationSpec 模板路径**（主汇报快捷导出）：11 种硬编码布局模板
  - 以下能力尚未成熟：完整母版与占位符体系、可替换图片元数据、可编辑图例 / SVG 矢量保持、原生表格/图表编辑、组织品牌模板导入
- 驳回后可一键重新生成 Brief、Storyline 或 Slide 计划
- Marp 仍作为预览/降级路径
- PPTX / PDF 导出依赖 Marp CLI；原生元素 PPTX 需 Node.js 并在 `archium/infrastructure/renderers/pptxgen` 运行 `npm install`
- Round 1 视觉编排尚未覆盖：完整视觉语言模型审核、复杂约束求解、自动效果图生成；**LayoutPlan PPTX 截图级回归**已接入 CI（`tests/golden/visual/composition/test_pptx_screenshot_regression.py` + `scripts/update_layout_pptx_screenshot_baselines.py`），与 composition JSON fingerprint 互补
- 文件整理为实验性遗留功能

## 开发路线图

1. **Stage 1** — 工程基础（Settings、异常、日志、测试） ✅
2. **Stage 2** — Pydantic 领域模型 ✅
3. **Stage 3** — SQLAlchemy + Repository ✅
4. **Stage 4** — LLM 抽象层 ✅
5. **Stage 5** — 文档导入 ✅
6. **Stage 6** — 汇报中间管线 ✅
7. **Stage 7** — LangGraph 工作流 ✅
8. **Stage 8** — Marp 渲染迁移 ✅
9. **Stage 9** — Streamlit 项目工作台 UI ✅
10. **Stage 10** — 向量检索增强（Chroma + Embedding） ✅
11. **Stage 11** — 资料片段管理 + 引用溯源 ✅
12. **Stage 12** — 统一修订历史（Brief / Storyline / SlideSpec lineage + SlideSpec diff） ✅
13. **Stage 13** — 项目事实账本（Fact Ledger · 提取 / 冲突检测 / 人工确认） ✅
14. **Stage 14** — 素材看板（Asset Board · 匹配 / 指定 / 确认 / 裁剪标记） ✅
15. **Stage 15** — 四层质量审核（Content / Evidence / Architectural / Layout Reviewer） ✅
16. **Stage 16** — PresentationSpec → PptxGenJS 原生元素 PPTX ✅

### Architectural Visual Composition（Round 1，已落地骨架）

不另开 Stage 编号。能力说明与操作指南：[docs/visual/README.md](docs/visual/README.md)。

### v0.2 Alpha Validation Sprint（进行中）

不再称为 Stage 17。目标：**证明现有主链在真实建筑项目上可用**。  
验收清单与进度：[docs/v0.2-alpha-validation-sprint.md](docs/v0.2-alpha-validation-sprint.md)

> 主流程请使用 `PresentationWorkflowService.run()`。`PresentationService.run_pipeline()` 已在 **v0.2-beta 准备阶段移除**（原计划在 v0.3）。

## 遗留模块

以下模块属于 v0.1 实验性功能，将在后续阶段移入 `legacy/` 并与主汇报流程解耦：

- `file_manager.py` — AI 辅助文件整理（**CLI 中唯一会移动本地文件的路径**；执行前会展示分类方案并要求二次确认）
