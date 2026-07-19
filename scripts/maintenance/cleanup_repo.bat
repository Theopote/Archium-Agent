@echo off
REM 仓库根目录清理脚本
REM 执行前请确保：
REM 1. 当前工作目录是 Archium-Agent 根目录
REM 2. 没有未提交的重要更改
REM 3. 已备份重要文件

echo ========================================
echo Archium Agent 仓库清理脚本
echo ========================================
echo.

REM 移除 Git 锁文件（如果存在）
if exist .git\index.lock (
    echo [1/6] 移除 Git 锁文件...
    del /F .git\index.lock
) else (
    echo [1/6] Git 锁文件不存在，跳过
)
echo.

REM 创建目录结构
echo [2/6] 创建目录结构...
mkdir docs\architecture 2>nul
mkdir docs\guides 2>nul
mkdir docs\internal\history\project-reviews 2>nul
mkdir docs\internal\analysis 2>nul
mkdir scripts\maintenance 2>nul
mkdir scripts\demos 2>nul
echo 目录创建完成
echo.

REM 移动架构文档
echo [3/6] 迁移架构文档...
git mv BENCHMARK_OVERFITTING_ANALYSIS.md docs\architecture\benchmark-overfitting-analysis.md 2>nul
git mv DECK_COMPOSITION_ARCHITECTURE.md docs\architecture\deck-composition-architecture.md 2>nul
git mv CONTENT_ADAPTATION_SAFETY_ANALYSIS.md docs\architecture\content-adaptation-safety-analysis.md 2>nul
git mv E2E_BENCHMARK_CASES.md docs\architecture\e2e-benchmark-cases.md 2>nul
git mv E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md docs\architecture\e2e-benchmark-implementation.md 2>nul
git mv THRESHOLD_HISTORY_ANALYSIS.md docs\architecture\threshold-history-analysis.md 2>nul
echo 架构文档迁移完成
echo.

REM 移动用户指南
echo [4/6] 迁移用户指南...
git mv GIT_COMMIT_GUIDE.md docs\guides\git-workflow.md 2>nul
git mv STUDIO_INTERACTION_ROADMAP.md docs\guides\studio-interaction-roadmap.md 2>nul
echo 用户指南迁移完成
echo.

REM 移动历史记录
echo [5/6] 迁移历史记录...
git mv CI_FIX_STATUS_FINAL.md docs\internal\history\2026-07-17-ci-fix-status.md 2>nul
git mv CI_FIX_SUMMARY.md docs\internal\history\2026-07-17-ci-fix-summary.md 2>nul
git mv RUFF_FIX_FINAL_RECOMMENDATION.md docs\internal\history\2026-07-18-ruff-fix-recommendation.md 2>nul
git mv RUFF_FIX_STRATEGY.md docs\internal\history\2026-07-18-ruff-fix-strategy.md 2>nul
git mv CANVAS_EDITOR_DELIVERY.md docs\internal\history\2026-07-18-canvas-editor-delivery.md 2>nul
git mv DECK_COMPOSITION_DELIVERY.md docs\internal\history\2026-07-18-deck-composition-delivery.md 2>nul
git mv DELIVERY_CHECKLIST.md docs\internal\history\delivery-checklist.md 2>nul
git mv OPTIMIZATION_COMPLETE.md docs\internal\history\2026-07-18-optimization-complete.md 2>nul
git mv FINAL_OPTIMIZATION_RECORD.md docs\internal\history\2026-07-18-final-optimization-record.md 2>nul
git mv FINAL_PROJECT_SUMMARY.md docs\internal\history\2026-07-18-final-project-summary.md 2>nul
git mv IMPLEMENTATION_SUMMARY.md docs\internal\history\implementation-summary.md 2>nul
git mv 优化总结.md docs\internal\history\2026-07-optimization-summary-zh.md 2>nul
git mv 第二阶段优化总结.md docs\internal\history\2026-07-phase2-optimization-zh.md 2>nul
git mv Archium项目审查报告.md docs\internal\history\project-reviews\2026-07-15-project-review-zh.md 2>nul

REM 移动分析报告
git mv DECK_COMPOSITION_ANALYSIS.md docs\internal\analysis\deck-composition-analysis.md 2>nul
git mv CONTENT_ADAPTATION_IMPROVEMENTS_SUMMARY.md docs\internal\analysis\content-adaptation-improvements.md 2>nul
git mv REPO_HYGIENE_SQLITE_WAL_FIX.md docs\internal\analysis\repo-hygiene-sqlite-wal.md 2>nul
git mv REPO_CLEANUP_PLAN.md docs\internal\analysis\repo-cleanup-plan.md 2>nul

echo 历史记录和分析报告迁移完成
echo.

REM 移动脚本
echo [6/6] 迁移脚本文件...
git mv fix_ruff_errors.py scripts\maintenance\fix_ruff_errors.py 2>nul

REM 删除临时测试文件
if exist demo_nlp_parsing.py git rm demo_nlp_parsing.py 2>nul
if exist demo_nlp_parsing_fixed.py git rm demo_nlp_parsing_fixed.py 2>nul
if exist test_adaptation_safety_lite.py git rm test_adaptation_safety_lite.py 2>nul
if exist test_brain.py git rm test_brain.py 2>nul
if exist test_content_adaptation_safety.py git rm test_content_adaptation_safety.py 2>nul
if exist test_nlp_standalone.py git rm test_nlp_standalone.py 2>nul
if exist file_manager.py git rm file_manager.py 2>nul

echo 脚本迁移和临时文件删除完成
echo.

echo ========================================
echo 清理完成！
echo ========================================
echo.
echo 下一步：
echo 1. 检查变更: git status
echo 2. 确认无误后提交:
echo    git commit -m "chore: 整理根目录文档结构以提升项目专业度"
echo.
echo 清理后的根目录将只保留核心文档：
echo - README.md
echo - QUICK_START.md
echo - CONTRIBUTING.md
echo - CODE_OF_CONDUCT.md
echo - SECURITY.md
echo - LICENSE, NOTICE
echo.
pause
