# Visual Boldness Score 实现报告

**日期**: 2026-08-07  
**状态**: ✅ 已完成  
**任务**: 实现视觉大胆度评分系统，防止 AI 总是生成"安全页面"

---

## 问题陈述

当前 `LayoutValidationService` 的评分逻辑倾向于奖励：
- ✅ 不溢出
- ✅ 不重叠
- ✅ 留白合理

这会导致：
- ❌ 对称布局 = 非对称布局（分数相同）
- ❌ 大胆设计可能被判为"异常"
- ❌ AI 倾向于生成保守、可预测的页面

**核心问题**: "正确" ≠ "有气质"

---

## 解决方案

### 新增评分维度：Visual Boldness

设计大胆度评分（0-100）衡量 5 个维度：

1. **Proportion Contrast** (25%) — 元素尺寸对比
2. **Asymmetry** (25%) — 非对称性
3. **Whitespace Strategy** (20%) — 留白策略
4. **Visual Tension** (15%) — 视觉张力
5. **Hierarchy Clarity** (15%) — 层次清晰度

---

## 实现细节

### 1. 核心模块

**文件**: `archium/application/visual/visual_boldness_score.py`

```python
class VisualBoldnessScorer:
    def score_layout(
        self,
        layout: LayoutPlan,
        composition: CompositionStrategy | None = None,
    ) -> BoldnessBreakdown:
        """
        Score a layout's visual boldness.
        
        Returns:
            BoldnessBreakdown with scores across 5 dimensions + overall
        """
```

**输出**:
```python
@dataclass
class BoldnessBreakdown:
    proportion_contrast: float  # 0-100
    asymmetry: float           # 0-100
    whitespace_strategy: float # 0-100
    visual_tension: float      # 0-100
    hierarchy_clarity: float   # 0-100
    overall_score: float       # weighted average
```

---

### 2. 评分逻辑

#### 2.1 Proportion Contrast

**定义**: 元素尺寸差异程度

```python
# 计算变异系数（CV）
cv = std_dev / mean_area

# CV -> score mapping
# CV = 0: all same size -> 0 (safe)
# CV = 1: large variation -> 70 (bold)
# CV = 2+: extreme contrast -> 100 (very bold)

# Bonus: hero-dominated layouts (1 large + many small)
if max_area / mean_area > 3.0:
    score += 15
```

**示例**:
- 4 个相同大小卡片 → score: ~10
- 1 个巨大图片 + 3 个小标签 → score: ~85

---

#### 2.2 Asymmetry

**定义**: 布局重心偏离中心的程度

```python
# 计算面积加权重心
com_x = sum(center_x * area) / total_area
com_y = sum(center_y * area) / total_area

# 距离幻灯片中心的归一化距离
dx = |com_x - slide_center_x| / slide_center_x
dy = |com_y - slide_center_y| / slide_center_y

asymmetry = (dx + dy) / 2

# Bonus: 显著偏离中心
if dx > 0.3 or dy > 0.3:
    score += 10
```

**示例**:
- 居中对称布局 → score: ~5
- 元素聚集在左侧边缘 → score: ~75

---

#### 2.3 Whitespace Strategy

**定义**: 战略性留白程度

```python
coverage = total_element_area / slide_area

# Coverage -> score mapping
if coverage < 0.3:   # <30% coverage
    base_score = 80  # very bold (lots of breathing room)
elif coverage < 0.5: # 30-50%
    base_score = 60  # bold
elif coverage < 0.7: # 50-70%
    base_score = 40  # moderate
else:                # >70%
    base_score = 20  # safe/crowded

# Bonus: composition declares generous whitespace
if composition.white_space == WhiteSpaceStrategy.GENEROUS:
    base_score += 20
```

**示例**:
- 密集填满的页面 → score: ~20
- 大面积留白 + 小元素 → score: ~80

---

#### 2.4 Visual Tension

**定义**: 视觉动态和张力

```python
tension_score = 0.0

# 1. Edge proximity (elements near slide edges)
edge_elements = count(element near edge)
tension_score += (edge_elements / total) * 40

# 2. Composition strategy tension
if composition.tension == VisualTension.HIGH:
    tension_score += 30
elif composition.tension == VisualTension.DYNAMIC:
    tension_score += 20

# 3. Reading path dynamism
if composition.reading_path in (DIAGONAL, SPIRAL, SCATTERED):
    tension_score += 30
```

**示例**:
- 居中元素 + 平衡构图 → score: ~10
- 边缘元素 + 对角阅读 + HIGH tension → score: ~90

---

#### 2.5 Hierarchy Clarity

**定义**: 主次关系清晰度

```python
# Dominance ratio: largest element as % of total
dominance = max_area / total_area

# Score mapping
if dominance > 0.5:      # >50% = one clear hero
    score = 85 + ...     # 85-100 (bold)
elif dominance > 0.3:    # 30-50% = primary + secondary
    score = 50 + ...     # 50-85 (moderate)
else:                    # <30% = flat hierarchy
    score = ...          # 0-50 (safe)
```

**示例**:
- 4 个同等大小元素 → score: ~20
- 1 个占据 60% 面积的 hero → score: ~90

---

### 3. 整合到 Candidate Selection

**文件**: `archium/application/visual/layout_planning_service.py`

#### 修改点 1: 添加 boldness scorer

```python
class LayoutPlanningService:
    def __init__(...):
        self._boldness_scorer = VisualBoldnessScorer()
```

#### 修改点 2: 在 `_selection_sort_key()` 中整合 boldness

```python
def _selection_sort_key(...) -> tuple[float, float, float, float, str]:
    # ... existing logic ...
    
    # BOLDNESS SCORE INTEGRATION
    boldness_breakdown = boldness_scorer.score_layout(plan, composition_strategy)
    boldness_score = boldness_breakdown.overall_score
    
    # Normalize: 70+ is bold (bonus), 30- is safe (penalty)
    # Map 0-100 to -0.15 to +0.15 range
    boldness_adjustment = (boldness_score - 50.0) / 100.0 * 0.3
    
    if boldness_adjustment > 0:
        composition_bonus += boldness_adjustment
    else:
        composition_penalty += abs(boldness_adjustment)
    
    # Return tuple (lower is better)
    return (
        validity_rank + composition_penalty,
        score_rank - composition_bonus,
        -boldness_score,  # Higher boldness wins in tiebreaks
        composition_penalty,
        str(plan.id),
    )
```

**影响**:
- Boldness 作为**第三排序维度**（tiebreaker）
- 同时通过 `composition_bonus/penalty` 影响主排序
- 大胆布局在同等有效性下获得优势

---

## 测试

**文件**: `tests/unit/visual/test_visual_boldness_score.py`

### 测试覆盖

| 测试类 | 测试场景 | 断言 |
|--------|---------|------|
| `TestProportionContrast` | 均匀尺寸 | score < 30 |
| | Hero-dominated | score > 70 |
| | 单一元素 | score = 50 |
| `TestAsymmetry` | 居中布局 | score < 30 |
| | 边缘聚集 | score > 50 |
| | 对称网格 | score < 40 |
| `TestWhitespaceStrategy` | 大量留白 | score > 80 |
| | 拥挤布局 | score < 40 |
| `TestVisualTension` | 高张力 + 边缘 + 对角 | score > 70 |
| | 平静 + 居中 | score < 40 |
| `TestHierarchyClarity` | 清晰主导元素 | score > 80 |
| | 扁平层次 | score < 50 |
| `TestOverallScore` | 大胆设计 | overall > 70 |
| | 安全设计 | overall < 50 |

---

## 使用示例

### 基础使用

```python
from archium.application.visual.visual_boldness_score import score_boldness

# Quick score
boldness = score_boldness(layout_plan, composition_strategy)
# Returns: 0-100, where 70+ is bold, 30- is safe
```

### 详细分析

```python
from archium.application.visual.visual_boldness_score import VisualBoldnessScorer

scorer = VisualBoldnessScorer()
breakdown = scorer.score_layout(layout_plan, composition_strategy)

print(f"Overall: {breakdown.overall_score}")
print(f"Proportion Contrast: {breakdown.proportion_contrast}")
print(f"Asymmetry: {breakdown.asymmetry}")
print(f"Whitespace: {breakdown.whitespace_strategy}")
print(f"Tension: {breakdown.visual_tension}")
print(f"Hierarchy: {breakdown.hierarchy_clarity}")
```

---

## 预期效果

### Before (v0.2)

```
候选 A: 对称网格，4 个均匀卡片 → score: 85 (valid, no issues)
候选 B: 非对称 hero，大胆留白 → score: 82 (valid, but "risky")

→ 选择候选 A（保守）
```

### After (v0.3)

```
候选 A: 对称网格，4 个均匀卡片
  - validation: 85
  - boldness: 35
  - final sort key: (0.0, -85, -35, ...)

候选 B: 非对称 hero，大胆留白
  - validation: 82
  - boldness: 78
  - final sort key: (0.0, -82 + 0.084, -78, ...)
                    ≈ (0.0, -82.084, -78, ...)

→ 选择候选 B（大胆但有效）
```

**关键变化**: Boldness 不会覆盖 validation，但会在同等有效的候选中打破平局，倾向于更有气质的设计。

---

## 权重调优

当前权重（可调整）：

```python
# 维度权重
proportion_contrast: 25%
asymmetry: 25%
whitespace_strategy: 20%
visual_tension: 15%
hierarchy_clarity: 15%

# Selection 影响
boldness_adjustment = (score - 50) / 100 * 0.3  # ±0.15 bonus/penalty
```

**建议**:
- 如果发现 AI 仍然过于保守 → 增加 `0.3` 到 `0.4`
- 如果发现 AI 过于激进 → 减少到 `0.2`
- 根据用户反馈调整各维度权重

---

## 局限性

1. **不考虑品牌规范**  
   某些品牌要求保守布局（金融、法律）

2. **不考虑内容类型**  
   技术图解需要清晰而非大胆

3. **需要人工校准**  
   评分阈值基于假设，需要实际数据验证

**缓解措施**:
- 未来可添加 `boldness_preference` 参数（保守/平衡/大胆）
- 与 `ArtDirection` 整合，品牌风格影响 boldness 权重

---

## 下一步

### P0（立即）
- ✅ 实现 VisualBoldnessScorer
- ✅ 整合到 LayoutPlanningService
- ✅ 编写单元测试

### P1（短期）
- [ ] 收集实际生成结果，验证评分准确性
- [ ] 添加 `boldness_preference` 到 ArtDirection
- [ ] 调整权重基于用户反馈

### P2（中期）
- [ ] 整合到 Critic 反馈循环
- [ ] 添加可视化调试工具（显示每个维度的得分）
- [ ] 支持内容类型特定的 boldness 策略

---

## 总结

Visual Boldness Score 系统已实现并整合到候选选择逻辑。通过量化 5 个设计维度，系统现在能够：

1. ✅ **识别大胆设计** — 非对称、hero-dominated、战略留白
2. ✅ **奖励有气质的页面** — 在有效候选中倾向于更大胆的选择
3. ✅ **防止保守偏见** — 不再仅仅奖励"不出错"

**核心哲学**: 正确性是底线（validation），大胆性是追求（boldness）。

---

**相关文件**:
- 实现: `archium/application/visual/visual_boldness_score.py`
- 整合: `archium/application/visual/layout_planning_service.py`
- 测试: `tests/unit/visual/test_visual_boldness_score.py`
- 审计报告: `docs/visual/advanced-expression-audit.md`
