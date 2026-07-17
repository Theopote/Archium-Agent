# Branch Protection for `master`

Archium 使用 GitHub Actions CI 作为合并门禁。本文说明如何在 `master` 上启用分支保护，以及如何用 CLI 批量配置。

## 前置条件

1. 你对 `Theopote/Archium-Agent` 拥有 **Admin** 权限。
2. CI workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) 已在 `master` 上至少成功运行一次，否则 GitHub Settings 里还无法搜索到 status check 名称。

Status check 名称（job 显式命名后）：

| Check | Python |
|-------|--------|
| `test (3.11)` | 3.11 |
| `test (3.12)` | 3.12 |

在 Branch protection UI 中可能显示为 `CI / test (3.11)`（工作流名 `CI` + job 名）。

## 方式一：GitHub Web UI（推荐）

1. 打开 <https://github.com/Theopote/Archium-Agent/settings/branches>
2. **Add branch protection rule**（或编辑已有 `master` 规则）
3. **Branch name pattern:** `master`
4. 启用：
   - **Require a pull request before merging**（推荐；单人维护时可暂不勾选）
   - **Require status checks to pass before merging**
   - **Require branches to be up to date before merging**（推荐）
5. 在 **Status checks that are required** 中搜索并添加：
   - `test (3.11)` 或 `CI / test (3.11)`
   - `test (3.12)` 或 `CI / test (3.12)`
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

- 必须通过 `test (3.11)` 与 `test (3.12)`
- 合并前分支需与 `master` 同步（strict）
- 禁止 force push 与删除 `master`

若 status check 名称与脚本默认值不一致，可先查看最近一次 PR 的 checks 名称，再传入环境变量：

```bash
export ARCHIUM_CI_CHECKS='test (3.11),test (3.12)'
./scripts/setup_branch_protection.sh
```

## 验证

1. 新建分支，故意引入 ruff 错误，开 PR → CI 应失败，且无法合并。
2. 修复后 CI 双绿 → 可以合并（若启用了 PR 要求）。

## 相关链接

- [CI workflow runs](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml)
- [README — CI 与分支保护](../README.md#ci-与分支保护)
