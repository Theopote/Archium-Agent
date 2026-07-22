# End-to-End Benchmark 实现总结


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 已完成的工作

### 1. 领域模型设计 ✅

**文件**: `archium/domain/visual/e2e_benchmark.py`

**核心数据结构**:

```python
# 输入定义
E2EBenchmarkCase - 端到端案例定义
E2EInputDocument - 输入文档
E2EInputAsset - 输入素材

# 期望标准
E2EExpectedOutcomes - 总体期望
E2EContentExpectation - 内容期望
E2EHeroAssetExpectation - 素材使用期望
E2ELayoutDistributionExpectation - 布局分布期望

# 评估结果
E2EBenchmarkResult - 单个案例结果
E2EContentCoverageResult - 内容覆盖度
E2EHeroAssetResult - 素材使用结果
E2ELayoutDistributionResult - 布局分布结果
E2EQualityMetrics - 质量指标
E2EBenchmarkSummary - 汇总统计
```

**关键特性**:
- 使用 Pydantic 进行数据验证
- 支持多维度期望标准
- 灵活的评估指标

### 2. 服务层实现 ✅

**文件**: `archium/application/visual/e2e_benchmark_service.py`

**核心功能**:

```python
class E2EBenchmarkService:
    def run_case(case) -> E2EBenchmarkResult:
        """执行单个端到端案例"""
        # 1. 导入文档和素材（IngestionService）
        # 2. 生成布局（VisualEditService，系统自主决策）
        # 3. 验证质量（ValidationService + DeckQAService）
        # 4. 检查期望标准
    
    def run_suite(cases) -> E2EBenchmarkSummary:
        """执行一组案例并生成汇总"""
```

**评估维度**:
- ✅ 内容覆盖度 (`_check_content_coverage`)
- ✅ Hero Asset 使用 (`_check_hero_assets`)
- ✅ 布局分布 (`_check_layout_distribution`)
- ✅ 质量指标 (`_compute_quality_metrics`)

### 3. 案例定义 ✅

**文件**: `E2E_BENCHMARK_CASES.md`

**5 个典型场景**:

1. **产品介绍**（图文并茂）
   - 投资路演 PPT
   - 预期：6-12 页，HERO_CONTENT 为主

2. **数据报告**（图表密集）
   - Q1 业绩报告
   - 预期：5-10 页，METRIC_GRID 为主

3. **项目提案**（结构化文本）
   - 管理层评审
   - 预期：8-15 页，TEXT_FOCUS 为主

4. **学术演讲**（概念图示）
   - 研究成果展示
   - 预期：10-18 页，图示 + 对比

5. **活动宣传**（视觉驱动）
   - 年会宣传
   - 预期：5-8 页，大图展示

**4 个边界案例**:
- 极少内容（3 行文字，无图）
- 极多内容（50 页，15 要点/页）
- 无素材（纯文字）
- 冲突素材（横竖图混合）

---

## 架构设计

### 双层 Benchmark 体系

```
┌─────────────────────────────────────────────────────────┐
│                    Archium Benchmark                     │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
    ┌─────────▼──────────┐    ┌────────▼─────────┐
    │   Layer A          │    │   Layer B        │
    │   Generator        │    │   End-to-End     │
    │   Benchmark        │    │   Benchmark      │
    └────────────────────┘    └──────────────────┘
              │                         │
    ┌─────────▼──────────┐    ┌────────▼─────────┐
    │ 已知正确输入       │    │ 真实混乱输入     │
    │ - LayoutFamily     │    │ - 原始文档       │
    │ - Variant          │    │ - 原始图片       │
    │ - Hero Asset       │    │ - 用户任务描述   │
    └────────────────────┘    └──────────────────┘
              │                         │
    ┌─────────▼──────────┐    ┌────────▼─────────┐
    │ 验证生成器质量     │    │ 验证产品能力     │
    │ - 布局合法性       │    │ - 内容选择       │
    │ - 设计规范         │    │ - 素材选择       │
    │ - 元素定位         │    │ - 布局决策       │
    └────────────────────┘    └──────────────────┘
              │                         │
    ┌─────────▼──────────┐    ┌────────▼─────────┐
    │ 快速（无 LLM）     │    │ 慢速（完整流程） │
    │ 适合 CI/CD         │    │ 适合周报         │
    │ 30 个案例          │    │ 5+4 个案例       │
    └────────────────────┘    └──────────────────┘
```

### 评估流程

```
E2E Benchmark 执行流程
═══════════════════════════════════════════════════════════

1. 输入准备
   ├─ 加载文档（PDF/Word/Excel）
   ├─ 加载图片素材
   └─ 解析用户任务描述

2. 系统自主处理 ⚠️ 不预先指定任何参数
   ├─ IngestionService 提取内容
   ├─ VisualIntentService 选择 LayoutFamily
   ├─ AssetSelectionService 选择素材
   └─ LayoutSolver 生成布局

3. 质量验证
   ├─ LayoutValidationService 规则检查
   └─ DeckQAService 整体评估

4. 期望对比
   ├─ 内容覆盖度检查
   │  ├─ 必需关键词 ✓
   │  ├─ 禁止关键词 ✗
   │  └─ 标题/要点数量 ✓
   ├─ Hero Asset 检查
   │  ├─ 优选标签使用 ✓
   │  ├─ 避免标签使用 ✗
   │  ├─ 使用率 ≥ 60%
   │  └─ 重用次数 ≤ 2
   ├─ 布局分布检查
   │  ├─ HERO_CONTENT: 3-5 页 ✓
   │  ├─ METRIC_GRID: 1-2 页 ✓
   │  └─ TEXT_FOCUS: 1-3 页 ✓
   └─ 质量指标检查
      ├─ 规则通过率 ≥ 90%
      ├─ 平均布局得分 ≥ 0.80
      └─ DeckQA 得分 ≥ 0.75

5. 结果输出
   ├─ E2EBenchmarkResult（单个案例）
   └─ E2EBenchmarkSummary（汇总统计）
```

---

## 与现有系统的集成

### 依赖的服务

```python
E2EBenchmarkService
├─ IngestionService           # 文档导入
├─ VisualEditService          # 布局生成
├─ LayoutValidationService    # 规则验证
├─ DeckQAService              # 整体评估
└─ PresentationRepository     # 数据访问
```

### 数据流

```
Input Files (PDF/Images)
         │
         ▼
  IngestionService
         │
         ├─ 提取文本
         ├─ 识别结构
         └─ 导入素材
         │
         ▼
   Presentation
         │
         ├─ Slides (内容)
         └─ Assets (素材)
         │
         ▼
  VisualEditService
         │
         ├─ VisualIntentService → 选择 LayoutFamily
         ├─ AssetSelectionService → 选择素材
         └─ LayoutSolver → 生成布局
         │
         ▼
    LayoutPlan
         │
         ├─ ValidationService → 规则检查
         └─ DeckQAService → 整体评估
         │
         ▼
 E2EBenchmarkResult
```

---

## 实施计划

### Phase 1：数据准备（未开始）

**目标**: 准备 5 个场景的测试数据

**任务**:
1. 创建目录结构
   ```
   benchmark_data/e2e/
   ├── product_intro/
   ├── data_report/
   ├── project_proposal/
   ├── academic_talk/
   └── event_promotion/
   ```

2. 准备文档
   - 产品介绍.pdf（10 页）
   - Q1业绩报告.xlsx（多表）
   - 项目提案书.docx（15 页）
   - 研究论文.pdf（20 页）
   - 年会策划方案.docx（5 页）

3. 准备图片
   - 每个场景 5-8 张图片
   - 标注语义标签（product/chart/photo 等）

4. 人工生成"黄金标准"
   - 使用 Archium 手动生成一次
   - 人工审核并调整
   - 作为期望标准的参考

**预计时间**: 1 周

### Phase 2：代码完善（未开始）

**目标**: 完善 E2EBenchmarkService 实现

**任务**:
1. 补充遗漏逻辑
   - `_check_hero_assets` 中的标签检查
   - 异常处理和错误恢复
   - 日志记录

2. 单元测试
   - 各个检查函数的独立测试
   - Mock 依赖服务

3. 集成测试
   - 使用小规模测试数据
   - 验证完整流程

**预计时间**: 1 周

### Phase 3：初始验证（未开始）

**目标**: 运行 5 个案例，获得基线数据

**任务**:
1. 执行 Benchmark
   ```python
   service = E2EBenchmarkService(session, benchmark_data_dir)
   cases = load_cases_from_json("e2e_cases.json")
   summary = service.run_suite(cases)
   ```

2. 分析结果
   - 哪些案例通过？
   - 哪些案例失败？
   - 失败原因是什么？

3. 调整标准
   - 如果期望过于严格，适当放宽
   - 如果系统确实存在问题，记录 bug

**预计时间**: 3 天

### Phase 4：持续集成（长期）

**目标**: 建立定期运行机制

**任务**:
1. 添加到 CI/CD
   - 每周运行一次（深度验证）
   - 生成趋势报告

2. 监控指标变化
   - Pass Rate 趋势
   - Quality Score 趋势
   - 常见失败原因

3. 扩展案例库
   - 新增真实用户案例
   - 新增失败场景回放
   - 定期更新期望标准

---

## 关键设计决策

### 1. 为什么不预先指定 LayoutFamily？

**Layer A（Generator Benchmark）**:
```python
# 预先指定 LayoutFamily
plan = solver.generate(
    layout_family=LayoutFamily.HERO_CONTENT,  # ✅ 已知正确答案
    context=context
)
```

**Layer B（E2E Benchmark）**:
```python
# 系统自主决策
intent = visual_intent_service.generate_for_slide(slide)
# ↓ intent.preferred_layout_families 由系统推断
plan = visual_edit_service.regenerate_layout(slide.id)
# ↓ 系统选择最合适的 LayoutFamily
```

**原因**: 真实场景中，用户不会告诉系统"用 HERO_CONTENT"，系统必须自己判断。

### 2. 为什么需要"期望标准"而非"黄金标准"？

**黄金标准**（精确匹配）:
```python
expected_layout_family = LayoutFamily.HERO_CONTENT
assert actual_layout_family == expected_layout_family  # ❌ 过于严格
```

**期望标准**（范围匹配）:
```python
expected_distribution = {
    LayoutFamily.HERO_CONTENT: (3, 5),  # 3-5 页
    LayoutFamily.METRIC_GRID: (1, 2),   # 1-2 页
}
# ✅ 允许合理变化
```

**原因**: 
- 相同输入可能有多个合理输出
- 系统更新后输出可能改进但不完全一致
- 避免"过拟合"单一输出

### 3. 为什么需要多维度评估？

单一指标容易误导：

```python
# ❌ 只看规则通过率
if rule_pass_rate >= 0.9:
    passed = True  # 但内容可能选错了

# ✅ 多维度综合评估
passed = (
    rule_pass_rate >= 0.9 AND
    content_coverage >= 0.8 AND
    hero_asset_correctness >= 0.7 AND
    layout_distribution_ok
)
```

**维度**:
- 布局合法性（规则）
- 内容正确性（关键词）
- 素材合理性（优选/避免）
- 分布合理性（布局族）
- 整体质量（DeckQA）

---

## 预期效果

### 短期（1-2 个月）

1. **建立基线**
   - 获得当前系统的 E2E 通过率
   - 识别主要问题领域

2. **暴露盲区**
   - 发现 Generator Benchmark 未覆盖的问题
   - 例如：内容选择不当、素材选择错误

3. **指导优化**
   - 明确需要改进的模块
   - 优先级排序

### 中期（3-6 个月）

1. **趋势监控**
   - 跟踪 Pass Rate 变化
   - 验证改进效果

2. **案例扩展**
   - 新增 10+ 真实场景
   - 覆盖更多边界情况

3. **自动化报告**
   - 每周生成趋势图
   - 自动识别退化

### 长期（6+ 个月）

1. **产品信心**
   - E2E Pass Rate > 80%
   - 覆盖主要使用场景

2. **用户案例库**
   - 收集真实失败案例
   - 转化为 Benchmark

3. **持续改进**
   - 根据 Benchmark 反馈迭代
   - 形成闭环

---

## 文件清单

### 新增文件

1. **领域模型**
   - `archium/domain/visual/e2e_benchmark.py` (200 行)
   - 定义所有数据结构

2. **服务层**
   - `archium/application/visual/e2e_benchmark_service.py` (400 行)
   - 实现执行和评估逻辑

3. **文档**
   - `BENCHMARK_OVERFITTING_ANALYSIS.md` (风险分析)
   - `E2E_BENCHMARK_CASES.md` (案例定义)
   - `E2E_BENCHMARK_IMPLEMENTATION_SUMMARY.md` (本文件)

### 待新增

4. **测试数据**
   - `benchmark_data/e2e/` 目录及内容

5. **配置文件**
   - `e2e_cases.json` (案例配置)

6. **测试脚本**
   - `tests/benchmark/test_e2e_benchmark.py`

---

## 总结

### 已完成 ✅

- ✅ E2E Benchmark 架构设计
- ✅ 领域模型实现
- ✅ 服务层骨架
- ✅ 5 个典型案例定义
- ✅ 4 个边界案例定义
- ✅ 评估维度设计
- ✅ 文档编写

### 待完成 ⏳

- ⏳ 准备测试数据
- ⏳ 完善服务实现
- ⏳ 编写单元测试
- ⏳ 初始验证运行
- ⏳ 集成到 CI/CD

### 关键价值

**避免过拟合**:
- Generator Benchmark: 100% 通过
- E2E Benchmark: ？% 通过（待验证）

两者结合才能全面评估产品能力。

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)
