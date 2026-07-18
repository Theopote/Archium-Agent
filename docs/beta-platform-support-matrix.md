# Beta Platform Support Matrix

> **Primary platform:** Windows（建筑师主力环境 + Microsoft PowerPoint 终检）  
> **CI platforms:** Ubuntu Linux（默认 PR CI）+ `windows-latest`（nightly / RC smoke）

本矩阵区分 **自动化保证**（CI 或 nightly 会拦）与 **人工复核保证**（文档要求、但不自动化）。  
**不要假设三平台表现完全一致。**

## 图例

| 符号 | 含义 |
|------|------|
| **Auto** | 自动化测试覆盖；回归会失败 |
| **Auto†** | 部分自动化（结构/页数/路径）；非像素级或字体级 |
| **Manual** | 需人工在目标环境验证 |
| **N/A** | 非目标场景或无可行自动化 |

## 能力矩阵

| 能力 | Windows | macOS | Linux |
|------|:-------:|:-----:|:-----:|
| **主产品启动**（`archium` / Streamlit） | Auto† | Manual | Auto† |
| **Golden L1 工作流回归** | Auto† | Manual | **Auto**（PR CI 3.11/3.12） |
| **Golden L2 真实解析**（fixture） | Auto† | Manual | **Auto**（PR CI） |
| **配置单一事实源**（settings → docs） | **Auto** | **Auto** | **Auto**（PR CI） |
| **Alembic migration smoke** | Auto† | Manual | **Auto**（PR CI） |
| **PptxGen 原生 PPTX 结构**（页数/标题/notes） | **Auto**（[windows-smoke.yml](../.github/workflows/windows-smoke.yml) nightly） | Manual | **Auto**（PR CI `test_pptxgen_render`） |
| **PptxGen 输出到中文/空格路径** | **Auto**（Windows smoke） | Manual | Auto†（`case_e` parser，非 PPTX 写路径） |
| **LangGraph checkpoint 生命周期**（SQLite 可删） | **Auto**（Windows smoke） | Manual | Auto†（unit test，PR CI） |
| **Marp PNG 视觉回归** | Manual | Manual | **Auto**（PR CI `marp-export` job） |
| **Marp PPTX/PDF 导出 smoke** | Manual | Manual | **Auto**（PR CI） |
| **Unicode 资料导入**（PDF/DOCX/PPTX/JPG） | **Auto**（Windows smoke `case_e`） | Manual | Auto†（同测试，Linux runner） |
| **中文字体 / 排版像素级** | **Manual**（PowerPoint 打开 PPTX） | **Manual** | **N/A**（CI 字体降级，仅验证可打开） |
| **PowerPoint 可打开性 & 版式主观质量** | **Manual**（权威终检） | **Manual** | **N/A** |
| **Live LLM 输出质量（L3）** | Manual | Manual | Manual |
| **Discord / Legacy CLI** | Manual | Manual | Manual |

## 自动化入口

| 工作流 | 触发 | Runner | 覆盖 |
|--------|------|--------|------|
| [ci.yml](../.github/workflows/ci.yml) | 每个 PR / push | `ubuntu-latest` | ruff、mypy、pytest、Golden、PptxGen、Marp、Streamlit、Alembic |
| [windows-smoke.yml](../.github/workflows/windows-smoke.yml) | **每日 02:00 UTC**、`workflow_dispatch`、**`v*` tag push** | `windows-latest` | `tests/smoke/test_windows_platform.py` |

本地等价（Windows）：

```powershell
pytest tests/smoke/test_windows_platform.py -v
```

## 交付预期（Beta）

| 用户场景 | 最低保证 | 不保证 |
|----------|----------|--------|
| Windows + Office 交付 PPTX | 结构正确、中文路径可写、checkpoint 不锁库；**打开后版式需人工过目** | 与 CI Linux 渲染像素一致 |
| macOS 开发/演示 | 主链可跑通（Manual 验证清单） | 与 Windows PowerPoint 完全一致 |
| Linux 服务器/CI | 主链逻辑、导出链路、Golden 回归 | 中文字体、PowerPoint 行为 |

## 相关文档

- [cross-platform-validation.md](cross-platform-validation.md) — 已知平台差异与本地验证命令
- [tests/golden/README.md](../tests/golden/README.md) — Golden 三层验收
- [tests/golden/visual/README.md](../tests/golden/visual/README.md) — PNG 视觉基线（Linux CI）
