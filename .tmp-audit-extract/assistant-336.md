## 问题 8–11 已落地

### 问题 8：CI 分层
- **`compatibility`（3.11/3.12）**：Ruff/config（仅 3.12）、mypy、unit、薄 integration（ingestion + presentation + import smoke）
- **`quality-full`（仅 3.12）**：全量 integration、coverage gate、benchmark、golden、PptxGen smoke + Node/字体

### 问题 9：Golden 命令语义
- CI：`--materialize-ci-samples`（临时样本，不表示批准基线）
- 正式更新：`--approve-goldens`
- `--write-goldens` 保留为 deprecated 别名

### 问题 10：安全审计预备（距 8/8 约两周）
- `docs/security/AUDIT_TRIAGE_2026-07.md`：当前发现、Owner、**2026-08-01** 检查点
- `docs/security/dependency-allowlist.json`：空白名单 + 到期规则（先升级，再允许）
- 新门禁：`scripts/ci_security_audit_gate.py`（适配无 `--min-severity` 的 pip-audit）
- `Pillow>=12.0`，锁文件已到 **pillow==12.3.0**
- 仍需在 8/1 前处理 chromadb / setuptools / torch 等剩余项，否则 8/8 强制阻断会红

### 问题 11：安装成本
- **migration-smoke**：只用 `base.lock` + alembic/pytest（无 Chroma/OpenAI/Node）
- compatibility 不再装 Node/LibreOffice
- 重活集中在 quality-full / screenshot / benchmark jobs

相关单测 `7 passed`。未提交。