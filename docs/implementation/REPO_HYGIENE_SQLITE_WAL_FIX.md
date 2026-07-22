# 仓库卫生问题修复指南


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 问题描述

SQLite WAL (Write-Ahead Logging) 和 SHM (Shared Memory) 文件被错误地跟踪到 Git 版本控制中。

### 受影响的文件

```
data/database/archium.db-shm
data/database/archium.db-wal
```

### 问题影响

1. **版本控制污染**: 每次数据库操作都会产生差异
2. **仓库体积膨胀**: 临时文件被持续提交
3. **合并冲突**: 多人协作时容易产生无意义的冲突
4. **CI/CD 噪音**: 自动化流程中产生虚假变更

---

## 根本原因

`.gitignore` 配置不完整，只忽略了 `.db` 文件：

```gitignore
# 当前配置（不完整）
data/database/*.db
```

没有忽略 SQLite 的临时文件：
- `*.db-wal` - Write-Ahead Log
- `*.db-shm` - Shared Memory index

---

## 解决方案

### Step 1: 更新 `.gitignore`

已完成修改：

```gitignore
# Data (runtime)
data/database/*.db
data/database/*.db-wal
data/database/*.db-shm
*.db-wal
*.db-shm
data/projects/
data/chroma/
data/outputs/
output/
```

### Step 2: 从 Git index 移除已跟踪文件

**已执行**:
```bash
git rm --cached data/database/archium.db-shm
git rm --cached data/database/archium.db-wal
```

**输出**:
```
rm 'data/database/archium.db-shm'
rm 'data/database/archium.db-wal'
```

### Step 3: 提交更改

**遇到问题**: Git 锁文件权限问题

```
fatal: Unable to create '.git/index.lock': File exists.
```

**原因**: VM 环境中 `.git/index.lock` 权限受限

**解决方法**（需要在主机环境执行）:

```bash
# 在 C:\Users\navib\Desktop\development\Archium-Agent 目录
cd C:\Users\navib\Desktop\development\Archium-Agent

# 1. 移除锁文件（如果存在）
rm -f .git/index.lock

# 2. 暂存更改
git add .gitignore

# 3. 提交
git commit -m "chore: 忽略 SQLite WAL/SHM 文件以改善仓库卫生

- 添加 *.db-wal 和 *.db-shm 到 .gitignore
- 从 Git index 移除已跟踪的 WAL/SHM 文件
- 防止 SQLite 临时文件污染版本控制"
```

---

## 验证修复

提交后验证：

```bash
# 1. 确认 WAL/SHM 不再被跟踪
git ls-files | grep -E '\.(db-wal|db-shm)$'
# 应该没有输出

# 2. 确认被忽略
git check-ignore data/database/archium.db-wal
git check-ignore data/database/archium.db-shm
# 应该输出文件路径

# 3. 确认 git status 清洁
git status
# 不应该看到 .db-wal 或 .db-shm 文件
```

---

## 为什么需要忽略这些文件？

### SQLite WAL 模式

SQLite 默认使用 WAL (Write-Ahead Logging) 模式以提高并发性能：

```python
# archium/config/settings.py
database_sqlite_wal_enabled: bool = Field(
    default=True,
    description="Enable SQLite WAL journal mode..."
)
```

**WAL 模式产生的文件**:
- `archium.db` - 主数据库文件
- `archium.db-wal` - 写前日志（临时，运行时生成）
- `archium.db-shm` - 共享内存索引（临时，运行时生成）

### 临时文件的生命周期

```
1. 应用启动
   └─ 创建 .db-wal 和 .db-shm

2. 数据库操作
   └─ .db-wal 持续变化（记录写操作）

3. Checkpoint
   └─ WAL 内容合并回 .db

4. 应用关闭
   └─ .db-wal 和 .db-shm 被删除（或保留为空）
```

这些文件**不应该**被版本控制：
- 内容完全由运行时生成
- 不同开发者/环境会产生不同内容
- 合并这些文件没有意义

---

## 相关的仓库卫生最佳实践

### 数据库文件

```gitignore
# SQLite
*.db
*.db-wal
*.db-shm
*.db-journal

# PostgreSQL (如果本地测试)
pgdata/
```

### Python 缓存

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

### 运行时数据

```gitignore
data/projects/
data/chroma/
data/outputs/
output/
logs/
*.log
```

### IDE

```gitignore
.idea/
.vscode/
*.swp
.DS_Store
```

---

## 类似问题的预防

### Git Hooks

创建 `.git/hooks/pre-commit` 检查：

```bash
#!/bin/bash
# 检查是否有 WAL/SHM 文件被暂存
if git diff --cached --name-only | grep -qE '\.(db-wal|db-shm)$'; then
    echo "Error: SQLite WAL/SHM files should not be committed!"
    echo "Files found:"
    git diff --cached --name-only | grep -E '\.(db-wal|db-shm)$'
    exit 1
fi
```

### CI 检查

在 `.github/workflows/ci.yml` 添加：

```yaml
- name: Check for accidental SQLite temp files
  run: |
    if git ls-files | grep -qE '\.(db-wal|db-shm)$'; then
      echo "Error: SQLite temporary files found in repository"
      git ls-files | grep -E '\.(db-wal|db-shm)$'
      exit 1
    fi
```

---

## 当前状态

✅ `.gitignore` 已更新  
✅ 文件已从 Git index 移除  
⏳ 需要在主机环境提交更改  

---

## 手动操作清单

**在主机 PowerShell/CMD 中执行**:

```powershell
# 1. 进入项目目录
cd C:\Users\navib\Desktop\development\Archium-Agent

# 2. 检查当前状态
git status

# 3. 如果看到 index.lock 问题，移除它
del .git\index.lock

# 4. 暂存 .gitignore
git add .gitignore

# 5. 提交更改
git commit -m "chore: 忽略 SQLite WAL/SHM 文件以改善仓库卫生

- 添加 *.db-wal 和 *.db-shm 到 .gitignore
- 从 Git index 移除已跟踪的 WAL/SHM 文件
- 防止 SQLite 临时文件污染版本控制"

# 6. 验证
git ls-files | findstr /R "\.db-wal$ \.db-shm$"
# 应该没有输出
```

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)  
状态：待主机环境完成提交
