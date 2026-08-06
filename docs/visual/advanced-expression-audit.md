# 高级视觉表达能力审计报告

**审计日期**: 2026-08-07  
**审计范围**: RenderScene 高级元素、VisualConcept 影响链、Candidate Selection 评分

---

## 1. RenderScene 高级元素支持审计

### 问题陈述

文档声称支持高级表达：
- `ShapeNode`（形状）
- `ConnectorNode`（连接线）
- `FreeformNode`（自由多边形）
- `DecorationNode`（装饰）

但需要验证：**"存在" ≠ "主链可控"**

### 审计结果

#### ✅ ShapeNode（形状）— 完全支持

**Domain 模型**:
```python
class ShapeNode(BaseRenderNode):
    shape_kind: "rectangle" | "ellipse" | "line" | "card"
    fill_color: str | None
    fill: GradientFill | None
    stroke_color: str | None
    stroke_width: float
    corner_radius: float
```

**Scene Compiler 支持**:
- ✅ `_compile_shape()` 方法存在
- ✅ 从 `LayoutElement` 编译
- ✅ 支持 metric card、装饰形状

**PPTX Exporter 支持**:
- ✅ `_shape_instruction()` 方法存在
- ✅ 输出到 PptxGen
- ✅ 支持渐变填充、描边、圆角

**结论**: ✅ **ShapeNode 完全可控**

---

#### ⚠️ ConnectorNode（连接线）— 部分支持

**Domain 模型**:
```python
class ConnectorNode(BaseRenderNode):
    start: ConnectorEndpoint  # node_id + anchor
    end: ConnectorEndpoint
    routing: "straight" | "elbow" | "curve"
    stroke_color: str
    stroke_width: float
    arrow_start: bool
    arrow_end: bool
```

**Scene Compiler 支持**:
- ❌ **未找到** `_compile_connector()` 方法
- ❌ **没有** 从 LayoutElement 自动生成 Connector
- ⚠️ 只能手动创建（不在主链）

**PPTX Exporter 支持**:
- ✅ `_connector_instruction()` 方法存在
- ✅ `connector_path_points()` 计算路径
- ⚠️ 注释说明：`V1: approximate line export`（简化导出）

**结论**: ⚠️ **ConnectorNode 存在但不在主链可控**

**影响**:
- 分析图中的流程连接线需要手动创建
- LayoutPlan 无法自动生成 Connector
- 限制了图解页面的表达能力

---

#### ⚠️ FreeformNode（自由多边形）— 部分支持

**Domain 模型**:
```python
class FreeformNode(BaseRenderNode):
    points: list[Point]  # 多边形顶点
    closed: bool
    fill_color: str | None
    stroke_color: str | None
    stroke_width: float
```

**Scene Compiler 支持**:
- ✅ 有使用案例：`silhouette_overlay_frame()`
- ⚠️ 仅用于特殊效果（剪影遮罩）
- ❌ 没有通用的 `_compile_freeform()` 方法
- ❌ 不在主链可控

**PPTX Exporter 支持**:
- ✅ `_freeform_instruction()` 方法存在
- ✅ 输出到 PptxGen

**结论**: ⚠️ **FreeformNode 存在但仅用于特殊效果**

**影响**:
- 无法生成自由形状标注
- 无法生成分析区域轮廓
- 限制了建筑分析图的表达

---

#### ❌ DecorationNode — 未实现

**搜索结果**:
- ❌ **没有** `DecorationNode` 类定义
- ❌ **没有** 相关编译或导出逻辑

**结论**: ❌ **DecorationNode 不存在**（文档错误或计划功能）

---

### 1.1 主链可控性评估

| 元素类型 | 模型定义 | Scene Compiler | PPTX Exporter | 主链可控 | 评分 |
|---------|---------|---------------|--------------|---------|------|
| TextNode | ✅ | ✅ | ✅ | ✅ | 100% |
| ImageNode | ✅ | ✅ | ✅ | ✅ | 100% |
| DrawingNode | ✅ | ✅ | ✅ | ✅ | 100% |
| ShapeNode | ✅ | ✅ | ✅ | ✅ | 100% |
| ConnectorNode | ✅ | ❌ | ✅ | ❌ | 50% |
| FreeformNode | ✅ | ⚠️ | ✅ | ❌ | 50% |
| DecorationNode | ❌ | ❌ | ❌ | ❌ | 0% |

**总体评分**: 71% (5/7 完全支持)

---

### 1.2 Screenshot 一致性（未测试）

**需要验证**:
- [ ] LibreOffice PDF 导出是否保留 Connector 路径
- [ ] Screenshot 是否正确显示 Freeform
- [ ] 渐变填充是否一致

**风险**: 如果 screenshot 不一致，Critic 评分会失真

---

## 2. VisualConcept 影响链追踪

### 问题陈述

当前存在多层视觉规划：
- `VisualConcept` — 整体概念
- `ArtDirection` — 艺术指导
- `DeckComposition` — deck 节奏
- `VisualIntent` — 单页意图

但文档承认：**很多只是停留在规划叙述或弱偏好，没有改变最终页面气质**

需要追踪：`VisualConcept → ? → LayoutPlan` 是否断了

### 追踪结果

#### 链路图

```
VisualConcept
  ↓ (通过 LLM 生成)
ArtDirection
  ├─ concept_name: str
  ├─ palette_strategy: str
  ├─ typography_strategy: str
  ├─ grid_strategy: str
  └─ style_preset_id: str | None
  ↓
DesignSystem (apply_style_overlays)
  ├─ colors: ColorSystem
  ├─ typography: TypographySystem
  └─ spacing: SpacingSystem
  ↓
VisualIntent
  ├─ page_type: PageType
  ├─ composition_strategy: CompositionStrategy
  └─ (读取 ArtDirection)
  ↓
LayoutPlan (via LayoutPlanningService)
  ├─ layout_family: LayoutFamily  ← 受 composition_strategy 影响
  ├─ elements: list[LayoutElement]
  └─ (几何坐标)
  ↓
RenderScene (via RenderSceneCompiler)
  ├─ nodes: list[RenderNode]
  └─ 应用 DesignSystem (colors, fonts, spacing)
  ↓
PPTX
```

#### 断点分析

**1. ArtDirection → DesignSystem**
- ✅ `apply_style_overlays()` 存在
- ⚠️ 但 `palette_strategy` 等字符串**未结构化**
- ⚠️ LLM 输出 `"use bold colors"` → 无法执行

**2. ArtDirection → VisualIntent**
- ⚠️ `ArtDirection` 传递给 LLM
- ⚠️ LLM 参考但**不强制执行**
- ❌ 没有验证 VisualIntent 是否符合 ArtDirection

**3. VisualIntent.composition_strategy → LayoutPlan**
- ✅ v0.3 已实施（本次升级）
- ✅ 结构化策略可执行

**4. DeckComposition → LayoutFamily selection**
- ✅ `SlideCompositionDirective.preferred_layout_families` 影响候选
- ✅ `PacingRole` 影响 `DensityLevel`

#### 关键断点

**断点 1**: `ArtDirection.palette_strategy: str` 无法执行

```python
# 当前
art_direction.palette_strategy = "use bold, saturated colors"
# ❌ RenderScene 不知道如何执行这个字符串

# 需要
art_direction.palette_strategy = PaletteStrategy(
    saturation=0.8,  # 0-1
    brightness=0.7,
    contrast="high",
)
```

**断点 2**: `VisualConcept` 对 LayoutPlan 无直接影响

```python
# VisualConcept 只影响 ArtDirection 生成
# 但 ArtDirection 的大部分字段是描述性的
# 最终 LayoutPlan 主要由 CompositionStrategy 决定
```

---

### 2.1 影响力评估

| 层级 | 对 LayoutPlan 的影响 | 对 RenderScene 的影响 | 评分 |
|------|---------------------|---------------------|------|
| VisualConcept | ⚠️ 间接（通过 ArtDirection） | ⚠️ 间接 | 30% |
| ArtDirection | ⚠️ 弱（字符串描述） | ✅ 强（DesignSystem） | 60% |
| DeckComposition | ✅ 强（Family + Density） | ❌ 无 | 70% |
| VisualIntent | ✅ 强（v0.3 结构化） | ✅ 强 | 90% |
| CompositionStrategy | ✅ 强（可执行） | ✅ 强 | 95% |

**结论**: 
- ✅ **VisualIntent/CompositionStrategy 影响强**（v0.3 升级成功）
- ⚠️ **ArtDirection 影响中等**（DesignSystem 层面有效，Layout 层面弱）
- ❌ **VisualConcept 影响弱**（过于高层，缺少执行路径）

---

## 3. Candidate Selection 评分问题

### 问题陈述

当前评分倾向于"安全页面"：
- 不溢出 ✅
- 不重叠 ✅
- 留白合理 ✅

这会**奖励普通，惩罚大胆**。

### 当前评分逻辑

```python
# LayoutValidationService
def validate(layout: LayoutPlan) -> LayoutValidationReport:
    issues = []
    
    # 1. Overflow check
    if element.overflows():
        issues.append(LayoutValidationIssue(severity=CRITICAL))
    
    # 2. Overlap check
    if element.overlaps(other):
        issues.append(LayoutValidationIssue(severity=ERROR))
    
    # 3. Whitespace check
    if whitespace_ratio < 0.1:
        issues.append(LayoutValidationIssue(severity=WARNING))
    
    score = 100 - sum(issue.penalty for issue in issues)
    return LayoutValidationReport(score=score, issues=issues)
```

**问题**:
- ❌ 没有奖励视觉大胆
- ❌ 对称布局分数 = 非对称布局分数
- ❌ 大面积留白可能被判为"浪费空间"

### 需要增加的维度

**Visual Boldness Score** — 衡量设计大胆程度：

1. **比例对比** — 元素尺寸差异
2. **非对称性** — 布局不对称程度
3. **留白策略** — 战略性留白
4. **视觉张力** — 元素间的动态关系
5. **层次清晰度** — 主次分明

---

## 建议改进

### 优先级 P0（立即）

1. **实现 VisualBoldnessScore**
   - 文件：`archium/application/visual/visual_boldness_score.py`
   - 集成到 candidate selection

2. **修复 ConnectorNode 主链**
   - 在 `RenderSceneCompiler` 添加 `_compile_connector()`
   - 从 LayoutElement 自动生成分析连接线

3. **结构化 ArtDirection palette_strategy**
   - 从 `str` 升级为 `PaletteStrategy` 对象
   - 可执行的色彩策略

### 优先级 P1（短期）

4. **FreeformNode 主链支持**
   - 添加 `_compile_freeform()` 通用方法
   - 支持分析区域标注

5. **VisualConcept 执行路径**
   - 添加从 VisualConcept 到 LayoutPlan 的直接影响
   - 验证 VisualIntent 符合 Concept

6. **Screenshot 一致性测试**
   - 验证 Connector/Freeform 渲染
   - 验证 Gradient 渲染

### 优先级 P2（中期）

7. **DecorationNode 实现**
   - 定义模型
   - 实现编译和导出

8. **Advanced Layout Validator**
   - 分离 "correctness" 和 "boldness" 评分
   - 允许用户选择风险偏好

---

## 总结

### 当前状态

| 维度 | 状态 | 评分 |
|------|------|------|
| RenderScene 高级元素 | ⚠️ 部分支持 | 71% |
| VisualConcept 影响链 | ⚠️ 存在断点 | 60% |
| Candidate Selection | ❌ 偏向安全 | 40% |

### 关键风险

1. **高级表达受限** — Connector/Freeform 不在主链
2. **设计意图断层** — ArtDirection 字符串无法执行
3. **大胆表达惩罚** — 评分偏向保守布局

### 改进优先级

```
P0: Visual Boldness Score > ConnectorNode 主链 > ArtDirection 结构化
P1: FreeformNode 主链 > VisualConcept 路径 > Screenshot 测试
P2: DecorationNode > Advanced Validator
```

这些改进将使 Archium 从"能生成正确页面"升级到"能生成有气质的页面"。
