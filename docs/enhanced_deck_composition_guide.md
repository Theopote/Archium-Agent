# Enhanced Deck Composition Service - 使用指南

## 概述

增强版 Deck Composition Service 解决了原有系统的规则化和启发式限制，通过整合多维度信息提供更智能的 Deck 重规划。

## 核心改进

### 原系统 vs 增强版

| 维度 | 原系统 | 增强版 |
|------|--------|--------|
| 反馈理解 | 关键词匹配 | 语义理解（LLM 可选） |
| 调整策略 | 固定增量（+0.15） | 基于严重程度动态调整 |
| 信息整合 | 仅 VisualIntent | DeckQA + 视觉曲线 + 模式识别 |
| 问题识别 | 无 | 自动识别 6+ 种问题模式 |
| 验证反馈 | 无 | 可与 DeckQA 闭环验证 |

## 快速开始

### 基本用法

```python
from archium.application.visual.enhanced_deck_composition_service import (
    EnhancedDeckCompositionService,
)

# 创建服务
service = EnhancedDeckCompositionService(llm_provider=None)  # 或传入 LLM

# 使用增强版修订
revised_plan = service.revise_enhanced(
    plan=current_composition_plan,
    feedback="节奏太单调，主图不够突出",
    slides=slide_specs,
    visual_intents=visual_intents,
    deck_qa_report=qa_report,  # 可选但推荐
)
```

### 启用 LLM 语义理解

```python
from archium.infrastructure.llm.factory import create_llm_provider

# 创建 LLM provider
llm = create_llm_provider(settings)

# 创建增强服务
service = EnhancedDeckCompositionService(llm_provider=llm)

# LLM 会自动用于解析复杂反馈
revised_plan = service.revise_enhanced(
    plan=current_plan,
    feedback="前几页节奏平淡，缺乏视觉冲击力，建议在第3-5页增强主图，"
              "同时保持后半部分的文字密度不变",
    ...
)
```

## 功能详解

### 1. 语义反馈解析

**支持的问题类型**：

#### A. 单调节奏 (`monotonous_rhythm`)
```python
feedback = "节奏太单调" / "太平淡" / "缺少变化"

# 解析结果
FeedbackIntent(
    problem_type="monotonous_rhythm",
    desired_direction="increase_contrast",
    adjustment_magnitude=0.5,
)

# 自动操作
- 识别单调区间（连续 5+ 页相似）
- 在中间插入对比页面
- 提升视觉强度
```

#### B. 主图不突出 (`weak_hero`)
```python
feedback = "主图太小" / "视觉冲击力不足" / "图片不够突出"

# 自动操作
- 提升 hero_priority
- 增加视觉强度到 HERO
- 降低 drawing_priority
```

#### C. 文字过多 (`excessive_text`)
```python
feedback = "文字太密集" / "需要更多留白"

# 自动操作
- 降低 text_priority
- 调整 density 为 SPACIOUS
- 增加 hero_priority
```

#### D. 不一致 (`inconsistent_chrome`)
```python
feedback = "版式不统一" / "页脚位置不一致"

# 自动操作
- 设置 should_match_previous = True
- 优先修复 QA 报告的问题页面
```

### 2. 严重程度识别

**自动调整修改幅度**：

```python
# 轻微问题
"稍微有点单调" → magnitude = 0.3

# 中等问题
"节奏单调" → magnitude = 0.5

# 严重问题
"非常单调，太无聊了" → magnitude = 0.8
```

### 3. 特定页面识别

```python
# 自动提取页面编号
feedback = "第3页和第5页文字太多"

# 解析结果
specific_pages = [2, 4]  # 0-indexed

# 仅调整这些页面
```

### 4. DeckQA 集成

```python
# 传入 DeckQA 报告
revised_plan = service.revise_enhanced(
    plan=current_plan,
    feedback="整体需要改进",
    deck_qa_report=qa_report,  # 包含具体问题
    ...
)

# 自动处理
if qa_report.has_critical_issues:
    # 优先修复 CRITICAL 问题
    # 针对性调整受影响的页面
```

**DeckQA 问题自动修复**：

| QA 问题 | 自动操作 |
|---------|---------|
| Footer 不一致 | 设置 should_match_previous |
| 版式过度重复 | 强制 should_contrast_previous |
| 视觉强度偏离 | 调整 visual_intensity |
| 密度不平衡 | 调整 target_density |

### 5. 视觉强度曲线分析

**自动识别问题**：

```python
# 单调区间
monotonic_spans = [(0, 6), (10, 15)]  # 第 1-6 页和 11-15 页单调

# 自动操作
for start, end in monotonic_spans:
    mid = (start + end) // 2
    # 在中间插入对比点
```

**曲线特征**：
- `smoothness`: 0.0-1.0（1.0 = 完全平坦）
- `variance`: 变化幅度
- `peaks`: 高峰位置（适合放重要内容）
- `valleys`: 低谷位置（适合缓冲页）

### 6. 模式识别

**自动识别的问题模式**：

1. **单调节奏** (`monotonous_rhythm`)
   - 连续 5+ 页视觉强度相似
   - 自动插入对比页面

2. **过度重复** (`excessive_repetition`)
   - 连续 4+ 页使用相同 LayoutFamily
   - 自动变化版式

3. **低方差** (`low_variance`)
   - 整体视觉强度变化 < 0.05
   - 增加整体对比度

4. **QA 严重问题** (`qa_critical`)
   - DeckQA 报告 CRITICAL 级别问题
   - 优先级最高，强制修复

5. **章节过渡弱** (未来)
6. **视觉失衡** (未来)

## 使用示例

### 示例 1：基础反馈

```python
# 场景：用户觉得节奏单调
revised = service.revise_enhanced(
    plan=current_plan,
    feedback="节奏太单调",
    slides=slides,
    visual_intents=intents,
)

# 结果：
# - 识别单调区间
# - 插入对比页面
# - 调整视觉强度曲线
```

### 示例 2：结合 DeckQA

```python
# 场景：QA 报告发现 footer 不一致
qa_report = DeckQAService().evaluate(layout_plans, ...)

revised = service.revise_enhanced(
    plan=current_plan,
    feedback="版式不够统一",
    deck_qa_report=qa_report,  # 包含具体问题
    slides=slides,
    visual_intents=intents,
)

# 结果：
# - 自动读取 QA 的具体问题
# - 针对性修复 footer 不一致的页面
# - 设置 should_match_previous
```

### 示例 3：特定页面调整

```python
revised = service.revise_enhanced(
    plan=current_plan,
    feedback="第3页和第5页主图太小，需要放大",
    slides=slides,
    visual_intents=intents,
)

# 结果：
# - 仅调整第 3 和 5 页
# - 增加这两页的 hero_priority
# - 提升视觉强度到 HERO
```

### 示例 4：复杂反馈（需要 LLM）

```python
llm = create_llm_provider(settings)
service = EnhancedDeckCompositionService(llm_provider=llm)

revised = service.revise_enhanced(
    plan=current_plan,
    feedback="""
    前半部分节奏太平，建议：
    1. 第2-4页增强视觉冲击力
    2. 第5页作为过渡，保持平静
    3. 第6-8页文字略微减少
    4. 保持最后两页的现有风格
    """,
    slides=slides,
    visual_intents=intents,
)

# LLM 会解析出：
# - 多个子任务
# - 特定页面范围
# - 不同的调整策略
```

## 对比原系统

### 原 `revise()` 方法

```python
def revise(self, plan, feedback: str, ...):
    normalized = feedback.lower()
    
    # 简单关键词匹配
    if "节奏" in normalized:
        for directive in directives:
            directive.should_contrast_previous = True  # 所有页面
    
    if "主图" in normalized:
        for directive in directives:
            if directive.hero_priority >= 0.5:
                directive.hero_priority += 0.15  # 固定增量
```

**问题**：
- ❌ 所有页面都调整（过度矫正）
- ❌ 固定增量（不考虑严重程度）
- ❌ 不识别具体问题位置

### 增强版 `revise_enhanced()`

```python
def revise_enhanced(self, plan, feedback: str, ...):
    # 1. 语义解析
    feedback_intent = self._parse_feedback(feedback)
    # → problem_type, severity, specific_pages
    
    # 2. 分析当前状态
    intensity_curve = self._analyze_intensity(plan)
    patterns = self._recognize_patterns(plan, intensity_curve)
    
    # 3. 针对性调整
    if feedback_intent.problem_type == "monotonous_rhythm":
        # 仅调整单调区间
        for start, end in intensity_curve.monotonic_spans:
            mid = (start + end) // 2
            directives[mid].should_contrast_previous = True
            # 动态增量
            boost = feedback_intent.adjustment_magnitude * 0.3
            directives[mid].hero_priority += boost
```

**改进**：
- ✅ 识别具体问题位置（单调区间）
- ✅ 动态调整幅度（基于严重程度）
- ✅ 针对性修改（不影响其他页面）

## 验证效果

### 修订前后对比

```python
# 修订前
original_intensity = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]  # 单调
original_variance = 0.0

# 修订后
revised_intensity = [0.5, 0.5, 0.8, 0.5, 0.5, 0.8]  # 插入对比
revised_variance = 0.15  # 提升

# 对比 QA 分数
original_qa_score = 0.65
revised_qa_score = 0.82  # 改善
```

### 集成到工作流

```python
def iterative_improvement(plan, feedback, max_iterations=3):
    """迭代改进直到满意"""
    for i in range(max_iterations):
        # 1. 修订
        revised = service.revise_enhanced(
            plan=plan,
            feedback=feedback,
            ...
        )
        
        # 2. 重新生成布局
        layout_plans = generate_layouts(revised)
        
        # 3. QA 评估
        qa_report = DeckQAService().evaluate(layout_plans)
        
        # 4. 检查是否改善
        if qa_report.total_score > 0.8:
            return revised  # 满意
        
        # 5. 提取新反馈
        feedback = extract_qa_feedback(qa_report)
        plan = revised
    
    return plan
```

## 性能考虑

### 响应时间

| 组件 | 时间 | 说明 |
|------|------|------|
| 关键词解析 | ~1ms | 无 LLM |
| LLM 语义解析 | ~200-500ms | 可选 |
| 视觉曲线分析 | ~5ms | NumPy 计算 |
| 模式识别 | ~10ms | 规则匹配 |
| 调整应用 | ~5ms | 修改对象 |
| **总计（无 LLM）** | **~20ms** | |
| **总计（有 LLM）** | **~220-520ms** | |

### 何时使用 LLM

**推荐使用 LLM**：
- 复杂的多条件反馈
- 包含特定页面范围
- 需要理解隐含意图

**可以不用 LLM**：
- 简单单一反馈（"太单调"）
- 常见关键词（"主图"、"文字"）
- 性能敏感场景

## 扩展性

### 添加新的问题类型

```python
# 1. 在 FeedbackSemanticParser 添加关键词
PROBLEM_KEYWORDS = {
    "inconsistent_colors": ["颜色", "色彩", "不统一"],
    # ...
}

# 2. 在 EnhancedDeckCompositionService 添加处理
def _apply_targeted_adjustments(self, ...):
    if feedback_intent.problem_type == "inconsistent_colors":
        self._unify_colors(directives, ...)
```

### 添加新的模式识别

```python
class PatternRecognizer:
    def recognize(self, ...):
        # 添加新模式
        if self._detect_color_clash(layout_plans):
            patterns.append(RecognizedPattern(
                pattern_type="color_clash",
                ...
            ))
```

## 未来改进

### 短期（已规划）
- [ ] 页面截图分析（视觉特征提取）
- [ ] 章节语义分析（LLM 理解章节关系）
- [ ] 用户历史学习（记录调整模式）

### 中期
- [ ] 多目标优化（同时优化节奏、一致性、吸引力）
- [ ] A/B 方案生成
- [ ] 交互式调整预览

### 长期
- [ ] 端到端学习（从反馈直接生成最优方案）
- [ ] 风格迁移（学习优秀 Deck 的风格）

## 常见问题

### Q: 是否必须使用 LLM？
**A**: 不是。不使用 LLM 时，系统会使用增强的关键词匹配，已经比原系统显著改善。LLM 仅用于处理复杂反馈。

### Q: 如何知道调整是否有效？
**A**: 集成 DeckQA 验证：
```python
# 修订前
original_score = qa_report_before.total_score

# 修订后
revised_plan = service.revise_enhanced(...)
new_layouts = generate_layouts(revised_plan)
new_qa_report = DeckQAService().evaluate(new_layouts)
improvement = new_qa_report.total_score - original_score
```

### Q: 可以同时处理多个问题吗？
**A**: 可以。系统会识别所有问题模式并按优先级处理：
1. CRITICAL QA 问题
2. 用户明确反馈
3. 自动识别的模式

### Q: 如何调整优先级？
**A**: 修改 `_apply_targeted_adjustments()` 中的顺序。

## 结论

增强版 Deck Composition Service 通过整合多维度信息和智能分析，显著改善了原系统的规则化限制，提供了更精准、更可靠的 Deck 重规划能力。

核心优势：
- ✅ 语义理解（vs 关键词匹配）
- ✅ 多维度分析（QA + 曲线 + 模式）
- ✅ 针对性调整（vs 全局修改）
- ✅ 动态调整幅度（vs 固定增量）
- ✅ 可验证改善（闭环反馈）
