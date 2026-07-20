#!/bin/bash
# 仓库文档整理脚本
# 将根目录散乱的 markdown 文件整理到合理的目录结构中

set -e

echo "======================================"
echo "仓库文档整理脚本"
echo "======================================"
echo ""

# 创建目标目录
echo "创建目录结构..."
mkdir -p .dev-notes/docs-history/sessions/2026-07-19
mkdir -p docs/analysis
mkdir -p docs/implementation
mkdir -p docs/delivery
mkdir -p docs/architecture
mkdir -p docs/guides

# 会话工作总结（历史工作记录，应归档到 .dev-notes）
echo "整理会话总结..."
mv -v 2026-07-19-work-summary.md .dev-notes/docs-history/sessions/2026-07-19/ 2>/dev/null || true
mv -v WORK_SUMMARY_2026-07-19_SESSION_RESUMED.md .dev-notes/docs-history/sessions/2026-07-19/ 2>/dev/null || true
mv -v SESSION_SUMMARY_E2E_FIX_COMPLETE.md .dev-notes/docs-history/sessions/2026-07-19/ 2>/dev/null || true
mv -v SESSION_INTEGRATION_FIXES_COMPLETE.md .dev-notes/docs-history/sessions/2026-07-19/ 2>/dev/null || true

# E2E Benchmark 相关
echo "整理 E2E Benchmark 文档..."
mv -v E2E_BENCHMARK_CASES.md docs/implementation/ 2>/dev/null || true
mv -v E2E_BENCHMARK_IMPLEMENTATION_ISSUES.md docs/analysis/ 2>/dev/null || true
mv -v E2E_BENCHMARK_FIX_SUMMARY.md docs/implementation/ 2>/dev/null || true
mv -v E2E_BENCHMARK_FIX_VERIFICATION.md docs/implementation/ 2>/dev/null || true
mv -v E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md docs/implementation/ 2>/dev/null || true
mv -v BENCHMARK_OVERFITTING_ANALYSIS.md docs/analysis/ 2>/dev/null || true
mv -v THRESHOLD_HISTORY_ANALYSIS.md docs/analysis/ 2>/dev/null || true

# Canvas Editor 相关
echo "整理 Canvas Editor 文档..."
mv -v CANVAS_EDITOR_DELIVERY.md docs/delivery/ 2>/dev/null || true
mv -v CANVAS_INTEGRATION_ANALYSIS.md docs/analysis/ 2>/dev/null || true
mv -v CANVAS_INTEGRATION_PHASE1_COMPLETE.md docs/implementation/ 2>/dev/null || true

# Enhanced Deck Composition 相关
echo "整理 Enhanced Deck Composition 文档..."
mv -v ENHANCED_DECK_COMPOSITION_FIX_COMPLETE.md docs/implementation/ 2>/dev/null || true
mv -v ENHANCED_DECK_COMPOSITION_INTEGRATION_ANALYSIS.md docs/analysis/ 2>/dev/null || true
mv -v DECK_COMPOSITION_ANALYSIS.md docs/analysis/ 2>/dev/null || true
mv -v DECK_COMPOSITION_ARCHITECTURE.md docs/architecture/ 2>/dev/null || true
mv -v DECK_COMPOSITION_DELIVERY.md docs/delivery/ 2>/dev/null || true

# Content Adaptation 相关
echo "整理 Content Adaptation 文档..."
mv -v CONTENT_ADAPTATION_IMPROVEMENTS_SUMMARY.md docs/implementation/ 2>/dev/null || true
mv -v CONTENT_ADAPTATION_SAFETY_ANALYSIS.md docs/analysis/ 2>/dev/null || true

# CI/Ruff 相关
echo "整理 CI 和 Ruff 文档..."
mv -v CI_FIX_STATUS_FINAL.md docs/implementation/ 2>/dev/null || true
mv -v CI_FIX_SUMMARY.md docs/implementation/ 2>/dev/null || true
mv -v RUFF_FIX_FINAL_RECOMMENDATION.md docs/guides/ 2>/dev/null || true
mv -v RUFF_FIX_STRATEGY.md docs/guides/ 2>/dev/null || true

# 仓库管理相关
echo "整理仓库管理文档..."
mv -v REPO_CLEANUP_PLAN.md docs/guides/ 2>/dev/null || true
mv -v REPO_HYGIENE_SQLITE_WAL_FIX.md docs/implementation/ 2>/dev/null || true
mv -v GIT_COMMIT_GUIDE.md docs/guides/ 2>/dev/null || true

# Human Review 相关
echo "整理 Human Review 文档..."
mv -v HUMAN_REVIEW_EXECUTION_PLAN.md docs/guides/ 2>/dev/null || true

# Studio 相关
echo "整理 Studio 文档..."
mv -v STUDIO_INTERACTION_ROADMAP.md docs/architecture/ 2>/dev/null || true

# 项目总结和交付文档
echo "整理项目总结文档..."
mv -v FINAL_PROJECT_SUMMARY.md docs/delivery/ 2>/dev/null || true
mv -v FINAL_OPTIMIZATION_RECORD.md docs/delivery/ 2>/dev/null || true
mv -v OPTIMIZATION_COMPLETE.md docs/delivery/ 2>/dev/null || true
mv -v IMPLEMENTATION_SUMMARY.md docs/delivery/ 2>/dev/null || true
mv -v DELIVERY_CHECKLIST.md docs/delivery/ 2>/dev/null || true

# 中文文档
echo "整理中文文档..."
mv -v Archium项目审查报告.md docs/analysis/ 2>/dev/null || true
mv -v 优化总结.md docs/delivery/ 2>/dev/null || true
mv -v 第二阶段优化总结.md docs/delivery/ 2>/dev/null || true

# 项目文档（保留在根目录）
echo ""
echo "保留在根目录的文档："
echo "  - README.md (项目主文档)"
echo "  - docs/guides/nlp-quickstart.md (NLP 快速入门)"
echo "  - CODE_OF_CONDUCT.md (行为准则)"
echo "  - CONTRIBUTING.md (贡献指南)"
echo "  - SECURITY.md (安全政策)"

echo ""
echo "======================================"
echo "整理完成！"
echo "======================================"
echo ""
echo "目录结构："
echo "  docs/"
echo "    ├── sessions/2026-07-19/  (今天的会话记录)"
echo "    ├── analysis/             (问题分析文档)"
echo "    ├── implementation/       (实现和修复文档)"
echo "    ├── delivery/             (交付和总结文档)"
echo "    ├── architecture/         (架构设计文档)"
echo "    └── guides/               (指南和计划文档)"
echo ""
echo "根目录保留 5 个项目级文档："
ls -1 *.md 2>/dev/null | wc -l
echo ""
