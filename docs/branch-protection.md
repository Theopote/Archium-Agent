# Branch Protection for `master`

Archium 使用 GitHub Actions CI 作为合并门禁。本文说明如何在 `master` 上启用分支保护，以及如何用 CLI 批量配置。

## 前置条件

1. 你对 `Theopote/Archium-Agent` 拥有 **Admin** 权限。
2. CI workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) 已在 `master` 上至少成功运行一次，否则 GitHub Settings 里还无法搜索到 status check 名称。

### Required CI check 名称（当前 ci.yml jobs）

| Check name | 内容 | PR/push |
|------------|------|---------|
| `compatibility (3.11)` | Ruff + Mypy + unit + thin integration | ✅ |
| `compatibility (3.12)` | 同上 + config sync + Playbook F gate | ✅ |
| `quality-full` | Integration + benchmark + golden + PPTX smoke | ✅ |
| `layout pptx screenshot regression` | Composition golden + PPTX screenshot regression | ✅ |
| `architectural benchmark render pipeline` | Curated asset render + render pipeline tests | ✅ |
| `marp export smoke` | Marp + golden visual regression | ✅ |
| `alembic migration smoke` | DB migration smoke | ✅ |
| `streamlit startup smoke` | Streamlit + Canvas Editor build smoke | ✅ |
| `security audit` | Pip-audit + pip-licenses | ✅ |

> **Windows smoke** 和 **E2E benchmark nightly** 仅在定时/tag 触发，不强制为 PR 必过。

## Visual Change PR Gate

**所有**修改以下路径的改动**必须通过 PR 合并**，禁止直推 master：

- `archium/domain/visual/**`
- `archium/infrastructure/renderers/**`
- `archium/infrastructure/layout/**`（generators / solver / tokens）
- `archium/ui/studio/**` 及 Studio canvas editor
- `tests/benchmark/**` goldens / curated baselines
- `tests/golden/visual/**` screenshot / composition baselines

PR 必须填写 `.github/PULL_REQUEST_TEMPLATE.md` 中的 **Visual Change PR Gate** 清单。

### 最低合并要求

1. 以下 CI checks 全部绿勾：
   - `compatibility (3.11)` + `compatibility (3.12)`
   - `quality-full`
   - `layout pptx screenshot regression`
   - `architectural benchmark render pipeline`
2. PR 附 Before/After 拼图（关键页面 PNG 或 CI artifact 链接）
3. PPTX 截图（CI 产物或手动附图）
4. 受影响 LayoutFamily / variants 列表
5. Golden 变更声明（无变更 / 有意更新 / 新增）
6. 人工修订成本估计

## 方式一：GitHub Web UI（推荐）

1. 打开 <https://github.com/Theopote/Archium-Agent/settings/branches>
2. **Add branch protection rule**（或编辑已有 `master` 规则）
3. **Branch name pattern:** `master`
4. 启用：
   - ✅ **Require a pull request before merging**
   - ✅ **Require status checks to pass before merging**
   - ✅ **Require branches to be up to date before merging**
5. 在 **Status checks that are required** 中搜索并添加：
   - `compatibility (3.11)`
   - `compatibility (3.12)`
   - `quality-full`
   - `layout pptx screenshot regression`
   - `architectural benchmark render pipeline`
6. （推荐）**Do not allow bypassing the above settings**
7. 保存规则

## 方式二：GitHub CLI

安装并登录 [GitHub CLI](https://cli.github.com/)（需 Admin）：

```bash
gh auth login
```

在仓库根目录执行：

```bash
# Bash / Git Bash / WSL
./scripts/setup_branch_protection.sh

# Windows PowerShell
.\scripts\setup_branch_protection.ps1
```

脚本会为 `master` 设置：

- 必须通过五项核心 CI checks
- 合并前分支需与 `master` 同步（strict）
- 禁止 force push 与删除 `master`

> **注意：** 脚本使用 GitHub REST API 无法直接启用 "Require a pull request before merging"。脚本运行后，请在 Web UI 中手动勾选此选项。

若 status check 名称与脚本默认值不一致，可先查看最近一次 PR 的 checks 名称，再传入环境变量：

```bash
export ARCHIUM_CI_CHECKS='compatibility (3.11),compatibility (3.12),quality-full,layout pptx screenshot regression,architectural benchmark render pipeline'
./scripts/setup_branch_protection.sh
```

## 验证

1. 新建分支，故意引入 ruff 错误，开 PR → CI 应失败，且无法合并。
2. 修复后 CI 全绿 → 可以合并。
3. 确认直接推 master 被拒（若已启用 require PR）。

## 关于 Combined Status 与 Check Runs

GitHub Actions 结果通过 **Check Runs** API 上报，不会出现在传统 **Statuses** (combined status) API 中。因此 `gh api repos/.../commits/.../status` 返回空列表不代表 CI 未运行。

查看正确方法：

```bash
# Check Runs（推荐）
gh api "repos/Theopote/Archium-Agent/commits/<sha>/check-runs" --jq '.check_runs[] | {name, conclusion}'

# 或查看 Actions 页面
gh run list --limit 10
```

## 相关链接

- [CI workflow runs](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml)
- [PR template (Visual Change Gate)](.github/PULL_REQUEST_TEMPLATE.md)
