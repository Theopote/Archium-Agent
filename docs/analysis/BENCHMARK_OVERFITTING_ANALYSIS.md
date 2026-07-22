# Benchmark 过拟合风险分析


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 问题描述

当前 Benchmark 显示 **30 个案例 100% 通过规则验证**，多数评分达到 1.0。

这是进步，但也存在**过拟合测试集**的风险。

---

## 当前 Benchmark 的特点

### 确定性构建

`BenchmarkService.build_case()` 接收以下**预先指定的输入**：

```python
@dataclass(frozen=True)
class BenchmarkCaseBuildRequest:
    definition: BenchmarkCaseDefinition
    design_system: DesignSystem
    title: str
    message: str
    visual_requirements: list[VisualRequirement]
    content: BenchmarkSlideContent | None = None  # ← 关键
```

**BenchmarkSlideContent 包含**：

```python
@dataclass(frozen=True)
class BenchmarkSlideContent:
    key_points: list[str] | None = None
    metrics: list[str] | None = None
    captions: list[str] | None = None
    insight: str | None = None
    hero_asset_id: UUID | None = None  # ← 预先指定
    supporting_asset_ids: list[UUID] | None = None  # ← 预先指定
    dominant_content_type: VisualContentType | None = None
    preferred_layout_families: list[LayoutFamily] | None = None  # ← 预先指定
    drawing_hero: bool = False
```

### 关键代码（第 109-119 行）

```python
content_override = request.content
if content_override is not None:
    if content_override.dominant_content_type is not None:
        intent.dominant_content_type = content_override.dominant_content_type
    if content_override.preferred_layout_families is not None:
        intent.preferred_layout_families = list(
            content_override.preferred_layout_families
        )
    if content_override.hero_asset_id is not None:
        intent.hero_asset_id = content_override.hero_asset_id
    if content_override.supporting_asset_ids is not None:
        intent.supporting_asset_ids = list(content_override.supporting_asset_ids)
```

**关键：第 130 行**

```python
plan = self._solver.generate(definition.expected_layout_family, context)
                              # ↑ 预先知道正确的 LayoutFamily
```

---

## 这验证了什么？

### ✅ 当前 Benchmark 验证的能力

**Layer A: Generator Benchmark（生成器基准）**

给定：
- ✅ 正确的 `LayoutFamily`（如 `HERO_CONTENT`）
- ✅ 正确的 `Variant`（如 `split_hero_left`）
- ✅ 正确的素材 ID（`hero_asset_id`, `supporting_asset_ids`）
- ✅ 正确的内容结构（`key_points`, `metrics`）

验证：
- 生成器能否产生**合法的布局**
- 布局是否符合**设计规范**
- 元素是否**位置正确、尺寸合理**

**这是重要的，但还不够。**

---

## 这没有验证什么？

### ❌ 当前 Benchmark 未验证的能力

**Layer B: End-to-End Benchmark（端到端基准）**

真实场景：
- ❌ 用户提供原始任务（"做一个产品介绍 PPT"）
- ❌ 用户上传原始文件（PDF、Word、Excel）
- ❌ 系统需要自主决策：
  - 选择哪些内容作为标题/核心信息/要点
  - 选择哪些图片作为 hero asset
  - 选择哪个 `LayoutFamily`
  - 选择哪个 `Variant`
  - 如何分配素材到页面

**当前 Benchmark 绕过了这些决策。**

---

## 风险：误判系统能力

### 场景 1：理想输入 vs 真实输入

**Benchmark 输入（确定性）**：
```python
BenchmarkSlideContent(
    key_points=["收入增长 45%", "成本降低 30%", "客户满意度提升"],
    hero_asset_id=UUID("12345678-..."),  # 已知最佳图片
    preferred_layout_families=[LayoutFamily.HERO_CONTENT],
    dominant_content_type=VisualContentType.DATA_VISUAL,
)
```

**真实输入（混乱）**：
```python
# 用户上传 50 页 PDF，包含：
# - 大段文字
# - 10 张图表
# - 5 张照片
# - 3 个表格
# Archium 需要自己：
# 1. 提取关键信息 → key_points
# 2. 选择最佳图片 → hero_asset_id
# 3. 判断内容类型 → dominant_content_type
# 4. 选择布局族 → preferred_layout_families
```

### 场景 2：规则通过率的误导

**当前结果**：30/30 通过 = 100%

**可能的原因**：
1. ✅ 生成器真的变好了（好事）
2. ⚠️ Benchmark 案例被设计得刚好适配生成器
3. ⚠️ 规则阈值被放宽了
4. ⚠️ 所有输入都是"理想场景"

**问题**：无法区分这 4 种情况。

---

## 类比：考试与实战

### 当前 Benchmark = 开卷考试

- 题目：生成一个 `HERO_CONTENT` 布局
- 提供：正确的 hero 图片、正确的要点、正确的 Variant
- 验证：生成的布局是否合法

**这像是告诉学生"第3题用勾股定理"。**

### 需要的 Benchmark = 闭卷考试

- 题目：用户上传了产品介绍文档，生成 PPT
- 提供：原始 PDF、原始图片文件夹
- 验证：
  - 是否选对了关键信息
  - 是否选对了图片
  - 是否选对了布局
  - 生成的页面是否合法

**这才是真实产品能力。**

---

## 建议：建立两层 Benchmark 体系

### Layer A: Generator Benchmark（已有）

**目的**：回归测试，验证生成器质量

**特点**：
- 确定性输入
- 预先指定 LayoutFamily、Variant、素材
- 快速执行（无 LLM）
- 适合 CI/CD

**保留价值**：
- 防止生成器退化
- 验证设计规范遵守
- 快速定位布局 bug

**局限性**：
- 不验证内容选择能力
- 不验证素材选择能力
- 不验证 LayoutFamily 选择能力

---

### Layer B: End-to-End Benchmark（需新增）

**目的**：产品能力基准，验证端到端质量

**特点**：
- 真实任务输入（"制作产品介绍 PPT"）
- 真实文件输入（PDF、图片文件夹）
- 不预先指定任何决策
- 调用完整 Archium 流程

**验证内容**：

#### 1. 内容理解与提取
```python
# 输入：50 页产品介绍 PDF
# 验证：
# - 是否提取了正确的标题
# - 是否识别了核心信息
# - 是否正确分段为多个页面
```

#### 2. 素材选择
```python
# 输入：20 张图片（产品图、团队照、图表）
# 验证：
# - hero asset 是否选对（产品图 > 团队照）
# - supporting assets 是否相关
# - 是否避免了重复使用
```

#### 3. 布局决策
```python
# 验证：
# - LayoutFamily 选择是否合理
#   （数据密集页 → METRIC_GRID，产品介绍 → HERO_CONTENT）
# - Variant 选择是否合理
#   （hero 图横构图 → split_hero_left，竖构图 → split_hero_top）
```

#### 4. 整体质量
```python
# 验证：
# - 生成的页面是否合法（规则通过）
# - DeckQA 评分
# - 内容连贯性
# - 素材使用合理性
```

---

## 实现方案

### 方案 1：基于真实案例回放

**数据来源**：
- 收集真实用户的导入任务
- 匿名化处理
- 人工标注"黄金标准"输出

**优点**：
- 最接近真实场景
- 验证实际产品问题

**缺点**：
- 需要人工标注
- 难以自动化评估

---

### 方案 2：合成端到端案例

**构建流程**：

```python
@dataclass
class E2EBenchmarkCase:
    """端到端基准案例"""
    case_id: str
    task_description: str  # "制作产品介绍 PPT"
    input_documents: list[Path]  # [产品介绍.pdf]
    input_images: list[Path]  # [产品图1.jpg, ...]
    expected_outcomes: E2EExpectedOutcomes

@dataclass
class E2EExpectedOutcomes:
    """期望的输出质量"""
    min_slide_count: int
    max_slide_count: int
    required_content_keywords: list[str]  # 必须出现的关键词
    hero_asset_criteria: dict[str, Any]  # 如 {"should_be": "product_image"}
    layout_distribution: dict[LayoutFamily, tuple[int, int]]  # 期望的布局分布
    min_rule_pass_rate: float  # 至少 90% 页面通过规则
    min_deck_qa_score: float  # 至少 0.8
```

**构建步骤**：

```python
class E2EBenchmarkService:
    def build_and_evaluate(self, case: E2EBenchmarkCase) -> E2EBenchmarkResult:
        # 1. 模拟用户导入
        presentation = self._ingestion_service.import_documents(
            task=case.task_description,
            documents=case.input_documents,
            images=case.input_images,
        )
        
        # 2. 运行完整生成流程
        for slide in presentation.slides:
            # Archium 自主决策：
            # - VisualIntentService 选择 LayoutFamily
            # - AssetSelectionService 选择素材
            # - LayoutSolver 生成布局
            plan = self._visual_edit_service.generate_layout(slide.id)
        
        # 3. 评估结果
        results = []
        for slide in presentation.slides:
            report = self._validation_service.validate(slide.plan)
            results.append(report)
        
        # 4. 对比期望
        return E2EBenchmarkResult(
            case_id=case.case_id,
            actual_slide_count=len(presentation.slides),
            rule_pass_rate=sum(r.valid for r in results) / len(results),
            deck_qa_score=self._deck_qa_service.evaluate(presentation),
            content_coverage=self._check_content_coverage(
                presentation,
                case.expected_outcomes.required_content_keywords
            ),
            hero_asset_correctness=self._check_hero_assets(
                presentation,
                case.expected_outcomes.hero_asset_criteria
            ),
            layout_distribution=self._check_layout_distribution(
                presentation,
                case.expected_outcomes.layout_distribution
            ),
            passed=self._overall_pass(results, case.expected_outcomes),
        )
```

**优点**：
- 可自动化
- 可重复执行
- 可量化评估

**缺点**：
- 需要设计合理的期望标准
- 初期构建成本高

---

### 方案 3：混合方案（推荐）

**Phase 1（当前）**：
- 保持 Layer A Generator Benchmark
- 明确标注其为"回归测试"，不代表产品能力

**Phase 2（1-2 个月）**：
- 构建 5-10 个 E2E 合成案例
- 涵盖典型场景：
  - 产品介绍（图文并茂）
  - 数据报告（图表密集）
  - 项目提案（结构化文本）
  - 学术演讲（概念图示）
  - 活动宣传（视觉驱动）

**Phase 3（3-6 个月）**：
- 收集真实用户案例
- 建立人工评估流程
- 定期更新 Benchmark

---

## 当前 100% 通过率的正确解读

### ✅ 积极信号

1. **生成器质量提升**
   - 布局合法性确实改善了
   - 设计规范遵守度提高

2. **验证体系成熟**
   - 规则体系完善
   - 能够捕获布局错误

3. **稳定性提升**
   - 确定性输入下表现一致
   - 适合回归测试

### ⚠️ 需要警惕

1. **不代表产品端到端能力**
   - 内容选择质量未验证
   - 素材选择质量未验证
   - LayoutFamily 选择质量未验证

2. **可能存在的问题**
   - Benchmark 案例可能过于理想
   - 规则阈值可能被调整过
   - 真实用户场景可能更困难

3. **测试盲区**
   - 混乱输入处理能力
   - 歧义消解能力
   - 错误恢复能力

---

## 行动建议

### 立即行动（本周）

1. **文档化当前 Benchmark 的范围**
   - 在 README 中明确标注为 "Generator Benchmark"
   - 说明其验证的能力和局限性
   - 避免误读为"产品 100% 完美"

2. **检查规则阈值历史**
   - 查看 git 历史，确认规则是否被放宽
   - 如果有，需要评估是否合理

3. **添加边界案例**
   - 在当前 Benchmark 中增加"困难案例"：
     - 极少内容（只有标题）
     - 极多内容（10+ 要点）
     - 无素材
     - 冲突素材（横竖构图不一致）

### 短期行动（1 个月）

4. **设计 5 个 E2E 案例**
   - 选择典型场景
   - 定义期望标准
   - 手动验证一次

5. **实现 E2EBenchmarkService**
   - 调用完整导入流程
   - 评估端到端质量
   - 生成对比报告

### 中期行动（3 个月）

6. **建立双层 Benchmark 流程**
   - CI 运行 Layer A（快速反馈）
   - 每周运行 Layer B（深度验证）
   - 两者结果分开报告

7. **收集真实案例**
   - 用户反馈中的问题案例
   - 生产环境日志回放
   - 人工标注"好"与"坏"

---

## 总结

### 当前状态

- ✅ Layer A (Generator Benchmark): 30/30 通过
- ❓ Layer B (E2E Benchmark): 未建立

### 核心问题

**100% 规则通过不应被过度解读为"产品已完美"。**

当前 Benchmark 验证的是：
> 给定正确的输入，生成器能否产生合法布局。

它没有验证：
> 面对混乱资料，系统能否自己选对内容、素材和版式。

### 下一步

1. 立即标注当前 Benchmark 的范围和局限性
2. 设计并实现 E2E Benchmark
3. 建立双层验证体系
4. 定期更新 Benchmark 案例

---

**关键原则**：
> 好的 Benchmark 不是为了让系统"通过测试"，而是为了暴露系统的真实能力边界。

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)
