# 仓库根目录清理计划

## 问题诊断

### 当前根目录混乱状态

**Markdown 文件（30+ 个）**：
```
Archium项目审查报告.md
BENCHMARK_OVERFITTING_ANALYSIS.md
CANVAS_EDITOR_DELIVERY.md
CI_FIX_STATUS_FINAL.md
CI_FIX_SUMMARY.md
CONTENT_ADAPTATION_IMPROVEMENTS_SUMMARY.md
CONTENT_ADAPTATION_SAFETY_ANALYSIS.md
DECK_COMPOSITION_ANALYSIS.md
DECK_COMPOSITION_ARCHITECTURE.md
DECK_COMPOSITION_DELIVERY.md
DELIVERY_CHECKLIST.md
E2E_BENCHMARK_CASES.md
E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md
FINAL_OPTIMIZATION_RECORD.md
FINAL_PROJECT_SUMMARY.md
GIT_COMMIT_GUIDE.md
IMPLEMENTATION_SUMMARY.md
OPTIMIZATION_COMPLETE.md
QUICK_START.md
REPO_HYGIENE_SQLITE_WAL_FIX.md
RUFF_FIX_FINAL_RECOMMENDATION.md
RUFF_FIX_STRATEGY.md
STUDIO_INTERACTION_ROADMAP.md
THRESHOLD_HISTORY_ANALYSIS.md
优化总结.md
第二阶段优化总结.md
```

**Python 脚本（12 个）**：
```
demo_nlp_parsing.py
demo_nlp_parsing_fixed.py
file_manager.py
fix_ruff_errors.py
test_adaptation_safety_lite.py
test_brain.py
test_content_adaptation_safety.py
test_nlp_standalone.py
```

### 问题分析

#### 1. 重复和冗余
- `FINAL_*` 出现 3 次
- `SUMMARY` 出现 5 次
- `COMPLETE` 出现 1 次
- 中英文混杂（`优化总结.md`、`第二阶段优化总结.md`）

#### 2. 分类混乱
- **历史记录**：`CI_FIX_*`, `RUFF_FIX_*`, `OPTIMIZATION_*`, `DELIVERY_*`
- **架构文档**：`DECK_COMPOSITION_ARCHITECTURE.md`, `BENCHMARK_OVERFITTING_ANALYSIS.md`
- **用户指南**：`QUICK_START.md`, `GIT_COMMIT_GUIDE.md`
- **临时脚本**：`demo_*.py`, `test_*.py`, `fix_*.py`

#### 3. 维护者困惑
查看根目录时：
- ❓ 哪个是最新的总结？
- ❓ 哪些是历史文档？
- ❓ 哪些可以删除？
- ❓ 哪些是重要文档？

---

## 清理方案

### 目标目录结构

```
Archium-Agent/
├── README.md                    # ✅ 保留：项目入口
├── QUICK_START.md               # ✅ 保留：快速开始
├── CONTRIBUTING.md              # ✅ 保留：贡献指南
├── CODE_OF_CONDUCT.md           # ✅ 保留：行为准则
├── SECURITY.md                  # ✅ 保留：安全政策
├── LICENSE                      # ✅ 保留：许可证
├── NOTICE                       # ✅ 保留：版权声明
│
├── docs/                        # 📚 文档目录
│   ├── architecture/            # 架构设计文档
│   │   ├── deck-composition.md
│   │   ├── benchmark-system.md
│   │   └── content-adaptation.md
│   │
│   ├── guides/                  # 用户指南
│   │   ├── git-workflow.md
│   │   └── studio-interaction.md
│   │
│   └── internal/                # 内部文档
│       ├── history/             # 历史记录
│       │   ├── 2026-07-17-ci-fix.md
│       │   ├── 2026-07-18-ruff-cleanup.md
│       │   ├── 2026-07-19-content-safety.md
│       │   └── project-reviews/
│       │       └── 2026-07-15-review.md
│       │
│       └── analysis/            # 分析报告
│           ├── benchmark-overfitting.md
│           ├── threshold-history.md
│           └── repo-hygiene.md
│
└── scripts/                     # 工具脚本
    ├── maintenance/             # 维护脚本
    │   └── fix_ruff_errors.py
    │
    └── demos/                   # 演示脚本
        └── nlp_parsing_demo.py
```

---

## 迁移清单

### A. 核心文档（保留在根目录）

✅ **必须保留**：
- `README.md` - 项目入口
- `QUICK_START.md` - 快速开始
- `CONTRIBUTING.md` - 贡献指南
- `CODE_OF_CONDUCT.md` - 行为准则
- `SECURITY.md` - 安全政策
- `LICENSE` - 许可证
- `NOTICE` - 版权声明

### B. 架构文档 → `docs/architecture/`

```bash
mv BENCHMARK_OVERFITTING_ANALYSIS.md docs/architecture/benchmark-overfitting-analysis.md
mv DECK_COMPOSITION_ARCHITECTURE.md docs/architecture/deck-composition-architecture.md
mv CONTENT_ADAPTATION_SAFETY_ANALYSIS.md docs/architecture/content-adaptation-safety-analysis.md
mv E2E_BENCHMARK_CASES.md docs/architecture/e2e-benchmark-cases.md
mv E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md docs/architecture/e2e-benchmark-implementation.md
mv THRESHOLD_HISTORY_ANALYSIS.md docs/architecture/threshold-history-analysis.md
```

### C. 用户指南 → `docs/guides/`

```bash
mv GIT_COMMIT_GUIDE.md docs/guides/git-workflow.md
mv STUDIO_INTERACTION_ROADMAP.md docs/guides/studio-interaction-roadmap.md
```

### D. 历史记录 → `docs/internal/history/`

```bash
# CI 修复记录
mv CI_FIX_STATUS_FINAL.md docs/internal/history/2026-07-17-ci-fix-status.md
mv CI_FIX_SUMMARY.md docs/internal/history/2026-07-17-ci-fix-summary.md

# Ruff 清理记录
mv RUFF_FIX_FINAL_RECOMMENDATION.md docs/internal/history/2026-07-18-ruff-fix-recommendation.md
mv RUFF_FIX_STRATEGY.md docs/internal/history/2026-07-18-ruff-fix-strategy.md

# 功能交付记录
mv CANVAS_EDITOR_DELIVERY.md docs/internal/history/2026-07-18-canvas-editor-delivery.md
mv DECK_COMPOSITION_DELIVERY.md docs/internal/history/2026-07-18-deck-composition-delivery.md
mv DELIVERY_CHECKLIST.md docs/internal/history/delivery-checklist.md

# 优化记录
mv OPTIMIZATION_COMPLETE.md docs/internal/history/2026-07-18-optimization-complete.md
mv FINAL_OPTIMIZATION_RECORD.md docs/internal/history/2026-07-18-final-optimization-record.md
mv FINAL_PROJECT_SUMMARY.md docs/internal/history/2026-07-18-final-project-summary.md
mv IMPLEMENTATION_SUMMARY.md docs/internal/history/implementation-summary.md
mv 优化总结.md docs/internal/history/2026-07-optimization-summary-zh.md
mv 第二阶段优化总结.md docs/internal/history/2026-07-phase2-optimization-zh.md

# 项目审查
mv Archium项目审查报告.md docs/internal/history/project-reviews/2026-07-15-project-review-zh.md
```

### E. 分析报告 → `docs/internal/analysis/`

```bash
mv DECK_COMPOSITION_ANALYSIS.md docs/internal/analysis/deck-composition-analysis.md
mv CONTENT_ADAPTATION_IMPROVEMENTS_SUMMARY.md docs/internal/analysis/content-adaptation-improvements.md
mv REPO_HYGIENE_SQLITE_WAL_FIX.md docs/internal/analysis/repo-hygiene-sqlite-wal.md
```

### F. 维护脚本 → `scripts/maintenance/`

```bash
mv fix_ruff_errors.py scripts/maintenance/fix_ruff_errors.py
```

### G. 测试/演示脚本 → `scripts/demos/` 或删除

```bash
# 如果是临时测试文件，删除
rm demo_nlp_parsing.py
rm demo_nlp_parsing_fixed.py
rm test_adaptation_safety_lite.py
rm test_brain.py
rm test_content_adaptation_safety.py
rm test_nlp_standalone.py

# 或者移动到 scripts/demos/
mkdir -p scripts/demos
mv demo_nlp_parsing.py scripts/demos/
mv test_*.py scripts/demos/
```

### H. 临时文件 → 删除

```bash
# 如果是一次性脚本
rm file_manager.py  # 检查是否还需要
```

---

## 执行步骤

### Step 1: 创建目录结构

```bash
mkdir -p docs/architecture
mkdir -p docs/guides
mkdir -p docs/internal/history/project-reviews
mkdir -p docs/internal/analysis
mkdir -p scripts/maintenance
mkdir -p scripts/demos
```

### Step 2: 批量迁移

```bash
# 架构文档
mv BENCHMARK_OVERFITTING_ANALYSIS.md docs/architecture/benchmark-overfitting-analysis.md
mv DECK_COMPOSITION_ARCHITECTURE.md docs/architecture/deck-composition-architecture.md
mv CONTENT_ADAPTATION_SAFETY_ANALYSIS.md docs/architecture/content-adaptation-safety-analysis.md
mv E2E_BENCHMARK_CASES.md docs/architecture/e2e-benchmark-cases.md
mv E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md docs/architecture/e2e-benchmark-implementation.md
mv THRESHOLD_HISTORY_ANALYSIS.md docs/architecture/threshold-history-analysis.md

# 用户指南
mv GIT_COMMIT_GUIDE.md docs/guides/git-workflow.md
mv STUDIO_INTERACTION_ROADMAP.md docs/guides/studio-interaction-roadmap.md

# 历史记录（按日期命名）
mv CI_FIX_STATUS_FINAL.md docs/internal/history/2026-07-17-ci-fix-status.md
mv CI_FIX_SUMMARY.md docs/internal/history/2026-07-17-ci-fix-summary.md
mv RUFF_FIX_FINAL_RECOMMENDATION.md docs/internal/history/2026-07-18-ruff-fix-recommendation.md
mv RUFF_FIX_STRATEGY.md docs/internal/history/2026-07-18-ruff-fix-strategy.md
mv CANVAS_EDITOR_DELIVERY.md docs/internal/history/2026-07-18-canvas-editor-delivery.md
mv DECK_COMPOSITION_DELIVERY.md docs/internal/history/2026-07-18-deck-composition-delivery.md
mv DELIVERY_CHECKLIST.md docs/internal/history/delivery-checklist.md
mv OPTIMIZATION_COMPLETE.md docs/internal/history/2026-07-18-optimization-complete.md
mv FINAL_OPTIMIZATION_RECORD.md docs/internal/history/2026-07-18-final-optimization-record.md
mv FINAL_PROJECT_SUMMARY.md docs/internal/history/2026-07-18-final-project-summary.md
mv IMPLEMENTATION_SUMMARY.md docs/internal/history/implementation-summary.md
mv 优化总结.md docs/internal/history/2026-07-optimization-summary-zh.md
mv 第二阶段优化总结.md docs/internal/history/2026-07-phase2-optimization-zh.md
mv Archium项目审查报告.md docs/internal/history/project-reviews/2026-07-15-project-review-zh.md

# 分析报告
mv DECK_COMPOSITION_ANALYSIS.md docs/internal/analysis/deck-composition-analysis.md
mv CONTENT_ADAPTATION_IMPROVEMENTS_SUMMARY.md docs/internal/analysis/content-adaptation-improvements.md
mv REPO_HYGIENE_SQLITE_WAL_FIX.md docs/internal/analysis/repo-hygiene-sqlite-wal.md

# 脚本
mv fix_ruff_errors.py scripts/maintenance/fix_ruff_errors.py
```

### Step 3: 删除临时文件

```bash
# 临时测试脚本（如果不需要）
rm -f demo_nlp_parsing.py
rm -f demo_nlp_parsing_fixed.py
rm -f test_adaptation_safety_lite.py
rm -f test_brain.py
rm -f test_content_adaptation_safety.py
rm -f test_nlp_standalone.py
rm -f file_manager.py
```

### Step 4: 提交

```bash
git add docs/ scripts/
git add -u  # 添加删除操作
git commit -m "chore: 整理根目录文档结构以提升项目专业度

- 将架构文档移至 docs/architecture/
- 将用户指南移至 docs/guides/
- 将历史记录移至 docs/internal/history/（按日期命名）
- 将分析报告移至 docs/internal/analysis/
- 将维护脚本移至 scripts/maintenance/
- 删除临时测试文件
- 根目录仅保留核心文档（README、CONTRIBUTING 等）

改善前：根目录 30+ 个 .md 文件，难以导航
改善后：清晰的目录结构，降低维护者认知负担"
```

---

## 清理后的根目录

```
Archium-Agent/
├── README.md                 # 项目入口
├── QUICK_START.md           # 快速开始
├── CONTRIBUTING.md          # 贡献指南
├── CODE_OF_CONDUCT.md       # 行为准则
├── SECURITY.md              # 安全政策
├── LICENSE
├── NOTICE
├── app.py                   # 主应用
├── config.py
├── main.py
├── ppt_generator.py
├── alembic.ini
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── (其他配置文件)
```

**清爽、专业、易导航。**

---

## 命名规范

### 历史文档命名

```
格式: YYYY-MM-DD-<主题>-<类型>.md

示例:
✅ 2026-07-17-ci-fix-status.md
✅ 2026-07-18-ruff-fix-strategy.md
✅ 2026-07-19-content-safety-improvements.md

❌ FINAL_OPTIMIZATION_RECORD.md
❌ CI_FIX_STATUS_FINAL.md
```

**优点**：
- 时间排序清晰
- 避免 "FINAL" 陷阱（每次都觉得是最后一次）
- 易于检索

### 架构文档命名

```
格式: <主题>-<类型>.md

示例:
✅ benchmark-overfitting-analysis.md
✅ deck-composition-architecture.md
✅ e2e-benchmark-implementation.md

❌ BENCHMARK_OVERFITTING_ANALYSIS.md
❌ E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md
```

**优点**：
- 全小写，使用连字符（kebab-case）
- 符合 Web 和 URL 规范
- 避免大小写敏感问题

---

## 收益

### 1. 认知负担降低

**改善前**：
```bash
$ ls *.md
# 看到 30+ 个文件，不知道哪个重要
# 看到 FINAL、COMPLETE、SUMMARY，无法判断最新状态
```

**改善后**：
```bash
$ ls *.md
README.md  QUICK_START.md  CONTRIBUTING.md  ...
# 清晰，只有核心文档

$ ls docs/internal/history/
2026-07-17-ci-fix-status.md
2026-07-18-ruff-fix-strategy.md
2026-07-19-content-safety-improvements.md
# 按时间排序，一目了然
```

### 2. 项目专业度提升

清晰的文档结构传达：
- ✅ 项目有条理
- ✅ 维护者有经验
- ✅ 适合长期维护

混乱的根目录传达：
- ❌ 项目匆忙
- ❌ 缺乏规划
- ❌ 可能有技术债

### 3. 新贡献者友好

新人克隆仓库后：
- ✅ 快速找到 README 和 QUICK_START
- ✅ 不会被 30+ 个文件吓跑
- ✅ 需要历史信息时知道去哪里找

---

## 风险与注意事项

### 风险 1：断链接

如果其他文档有内部链接引用根目录文件：

```markdown
<!-- 旧链接 -->
[CI 修复](../CI_FIX_SUMMARY.md)

<!-- 需要更新为 -->
[CI 修复](../docs/internal/history/2026-07-17-ci-fix-summary.md)
```

**缓解措施**：
- 迁移后全局搜索断链接
- 更新所有引用

### 风险 2：丢失重要信息

**缓解措施**：
- 先 `git mv`，保留历史
- 不删除任何看起来重要的文件
- 审查后再删除临时文件

### 风险 3：Git 历史混乱

**缓解措施**：
- 使用 `git mv` 而非 `rm` + `add`
- 单次提交完成所有迁移
- 清晰的 commit message

---

## 执行时机

**建议**：在当前工作完成后的独立提交中执行

**原因**：
- 不与功能开发混合
- 便于 review
- 便于 revert（如果需要）

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)  
状态：待执行
