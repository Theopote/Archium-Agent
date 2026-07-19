# 规则阈值历史变化分析

## 检查结果

### 阈值添加时间

**2026-07-18** - Commit `4ee2751` "refactor(layout): 优化布局验证服务和相关配置"

这次提交**首次引入**了布局验证阈值配置，将之前散落在代码中的"魔法数字"集中到配置系统。

### 新增的阈值参数

#### 在 `archium/config/settings.py` 中添加：

```python
# 字体大小阈值
layout_min_body_font_pt: float = 14.0        # 正文最小字号
layout_min_caption_font_pt: float = 9.0      # 说明文字最小字号
layout_min_source_font_pt: float = 8.0       # 来源标注最小字号

# 面积比例阈值
layout_min_hero_area_ratio: float = 0.45     # Hero 元素最小面积占比
layout_min_whitespace_ratio: float = 0.08    # 最小留白比例
layout_max_whitespace_ratio: float = 0.60    # 最大留白比例
```

#### 在 `archium/domain/visual/design_system.py` 中添加：

```python
class LayoutThresholds(DomainModel):
    """验证阈值（归属于设计系统，不再是散落的魔法数字）"""
    
    min_body_font_pt: float = 14.0
    min_caption_font_pt: float = 9.0
    min_source_font_pt: float = 8.0
    min_hero_area_ratio: float = 0.45
    min_whitespace_ratio: float = 0.08
    max_whitespace_ratio: float = 0.60
    max_title_lines: int = 2
    max_overlap_tolerance: float = 0.01        # 元素重叠容忍度：1%
    text_overflow_validation_tolerance_in: float = 0.012  # 文本溢出检测容差
    text_overflow_repair_slack_in: float = 0.020         # 文本修复额外空间
```

---

## 分析结论

### ✅ 这是架构改进，不是放宽规则

**性质**：重构（Refactoring）

**目的**：
1. 将散落的硬编码阈值集中管理
2. 使阈值可配置、可测试
3. 归属到 `DesignSystem`，符合领域模型

**证据**：
- Commit 标题：`refactor(layout): 优化布局验证服务和相关配置`
- 描述明确指出：移除"魔法数字"，集中到配置
- 阈值数值合理，未见明显放宽迹象

### ✅ 阈值数值合理性检查

#### 字体大小
```python
min_body_font_pt: 14.0    # 合理：演示文稿正文推荐 14-18pt
min_caption_font_pt: 9.0  # 合理：图表说明文字推荐 9-12pt  
min_source_font_pt: 8.0   # 合理：来源标注可稍小，8pt 可接受
```

#### 面积比例
```python
min_hero_area_ratio: 0.45      # 合理：Hero 元素应占 45%+ 才有视觉主导性
min_whitespace_ratio: 0.08     # 合理：至少 8% 留白避免拥挤
max_whitespace_ratio: 0.60     # 合理：超过 60% 留白显得空洞
```

#### 重叠容忍度
```python
max_overlap_tolerance: 0.01    # 合理：允许 1% 重叠（可能是边框或阴影）
```

#### 文本溢出
```python
text_overflow_validation_tolerance_in: 0.012  # 0.012 英寸 ≈ 0.3mm
text_overflow_repair_slack_in: 0.020          # 0.020 英寸 ≈ 0.5mm
```
这两个值非常小，说明对文本溢出的检测很严格。

---

## 历史演变

### Phase 1：硬编码（2026-07-18 之前）

验证逻辑中散落着硬编码数值：

```python
# 推测：之前可能是这样
if font_size < 14:  # 魔法数字
    issues.append(...)

if hero_area / safe_area < 0.45:  # 魔法数字
    issues.append(...)
```

### Phase 2：集中配置（2026-07-18）

引入 `LayoutThresholds` 数据类：

```python
thresholds = design_system.thresholds
if font_size < thresholds.min_body_font_pt:
    issues.append(...)
```

**优点**：
- 可测试性：不同设计系统可有不同阈值
- 可维护性：集中修改，不再散落
- 可配置性：用户可覆盖默认值

---

## 对 100% 通过率的影响

### ❌ 不太可能是阈值放宽导致

**理由 1**：阈值是**新引入**的架构改进
- 之前就有验证逻辑，只是阈值散落在代码中
- 这次只是集中管理，数值未见明显变化

**理由 2**：阈值数值严格
- `min_body_font_pt: 14.0` - 不算宽松
- `max_overlap_tolerance: 0.01` - 仅 1%，很严格
- `min_hero_area_ratio: 0.45` - 要求 Hero 必须占主导

**理由 3**：Commit 时间线
- 阈值引入：2026-07-18
- 如果 Benchmark 在此之前已经高通过率，说明不是阈值导致

---

## 潜在风险点

虽然阈值本身合理，但需要警惕以下情况：

### ⚠️ 风险 1：默认值可能被"优化"到刚好通过 Benchmark

**场景**：
```python
# 如果 Benchmark 案例中最小字号是 13.5pt
# 可能会把阈值设为 13.0 以"容纳"这个案例
min_body_font_pt: 13.0  # ⚠️ 是为了产品需求，还是为了通过测试？
```

**检查方法**：
- 查看 Benchmark 案例的实际字号分布
- 对比行业标准（PPT 正文通常 14-18pt）
- 如果阈值明显低于行业标准，可能存在"优化测试"问题

### ⚠️ 风险 2：阈值可能被动态调整过

虽然当前代码显示阈值是配置项，但需要检查：
- 是否有代码在运行时动态修改阈值？
- 是否有"宽松模式"开关？

**检查**：
```bash
grep -r "thresholds\\.min_body_font_pt\\s*=" archium/
grep -r "LayoutThresholds.*update" archium/
```

### ⚠️ 风险 3：容忍度（tolerance）被滥用

```python
max_overlap_tolerance: 0.01           # 1%
text_overflow_validation_tolerance_in: 0.012  # 很小
```

如果未来这些值被调大（如 0.05、0.1），可能是为了"容忍"更多问题。

---

## 建议的监控指标

### 1. 阈值变更监控

建立 Git Hook 或 CI 检查：

```python
# tests/benchmark/test_threshold_stability.py

def test_layout_thresholds_not_relaxed():
    """确保阈值不被无故放宽"""
    thresholds = LayoutThresholds()
    
    # 基线值（当前）
    assert thresholds.min_body_font_pt >= 14.0
    assert thresholds.min_caption_font_pt >= 9.0
    assert thresholds.max_overlap_tolerance <= 0.01
    assert thresholds.min_hero_area_ratio >= 0.45
    
    # 如果需要放宽，必须在此测试中说明原因
```

### 2. Benchmark 案例的阈值分布

记录每个 Benchmark 案例实际触及的阈值：

```python
# 运行 Benchmark 时输出
Case A1-001:
  - Min font size used: 14.2pt (阈值: 14.0pt, 余量: 0.2pt)
  - Hero area ratio: 0.48 (阈值: 0.45, 余量: 0.03)
  - Max overlap: 0.005 (阈值: 0.01, 余量: 0.005)

# 如果所有案例都刚好卡在阈值附近，说明可能过拟合
```

### 3. 实际字号分布统计

```python
# 统计真实生成页面的字号分布
Body font sizes in generated slides:
  Min: 14.0pt
  P25: 14.5pt
  P50: 15.0pt
  P75: 16.0pt
  Max: 18.0pt

# 如果 Min 总是刚好等于阈值 14.0，可能有问题
```

---

## 最终判断

### ✅ 当前阈值设置合理

基于检查结果：
- 阈值数值符合行业标准
- 引入时间是架构重构，不是应急修复
- Commit 描述清晰，目的明确

### ⚠️ 但需要持续监控

虽然当前没有问题，但应建立机制防止未来：
1. 阈值被悄悄放宽以提高通过率
2. Benchmark 案例被"优化"到刚好通过阈值
3. 容忍度被滥用

### 推荐行动

1. **立即**：在文档中标注阈值基线（当前值）
2. **本周**：添加阈值稳定性测试
3. **持续**：每次 Benchmark 运行时记录阈值余量分布

---

## 附录：相关 Commits

```
4ee2751 2026-07-18 refactor(layout): 优化布局验证服务和相关配置
  + 添加 LayoutThresholds 到 design_system
  + 添加 layout_* 配置到 settings.py
  + 重构验证服务使用集中阈值

7abed7d 2026-07-19 feat(visual): 引入版式质量评分系统
  + 添加 LayoutScore 数据类
  + 多维度评分（有效性、可读性、层次、对齐、留白、素材、一致性）

dad2880 2026-07-18 feat(visual): 添加布局验证审查流程以阻止无效导出
  + 在导出前强制验证
  + 阻止包含 CRITICAL/ERROR 的页面导出
```

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)
