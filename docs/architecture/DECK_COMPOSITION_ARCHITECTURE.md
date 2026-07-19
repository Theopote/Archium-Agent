# 增强版 Deck Composition 架构设计

## 架构概览

### 核心理念

**从规则驱动到数据驱动**：整合多维度信息，使用智能分析替代简单关键词匹配。

```
                    增强版 Deck Composition 系统
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   输入层               分析层                决策层
        │                     │                     │
    ┌───┴───┐           ┌─────┴─────┐         ┌────┴────┐
    │多维度 │           │智能分析器 │         │优化引擎│
    │信息源 │──────────→│           │────────→│         │
    └───────┘           └───────────┘         └─────────┘
        │                     │                     │
        ↓                     ↓                     ↓
  • DeckQA              • 语义理解           • 方案生成
  • 章节语义            • 模式识别           • 冲突解决
  • 页面截图            • 趋势分析           • 优先级排序
  • 视觉强度            • 异常检测           • 验证反馈
  • 用户历史            • 关联分析
```

## 输入层：多维度信息源

### 1. DeckQA 反馈

**数据结构**：
```python
@dataclass
class DeckQAContext:
    report: DeckQAReport
    findings_by_severity: dict[LayoutIssueSeverity, list[DeckQAFinding]]
    affected_slides: list[UUID]
    consistency_score: float
    variety_score: float
```

**提取信息**：
- 具体问题（footer 不一致、版式重复等）
- 严重程度（CRITICAL → ERROR → WARNING → INFO）
- 受影响的页面
- 总体评分

**使用方式**：
```python
qa_context = DeckQAAnalyzer().analyze(deck_qa_report)

# 针对严重问题优先修复
for finding in qa_context.findings_by_severity[LayoutIssueSeverity.CRITICAL]:
    apply_targeted_fix(finding)
```

### 2. 章节语义

**数据结构**：
```python
@dataclass
class SectionSemantics:
    section_id: str
    title: str
    theme: str  # LLM 提取的主题
    importance: float  # 0.0-1.0
    relationship_to_previous: str  # "continuation", "contrast", "conclusion"
    key_message: str
    suggested_visual_strategy: str
```

**提取方式**：
```python
# 使用 LLM 分析章节
class SectionSemanticAnalyzer:
    def analyze(self, slides: list[SlideSpec]) -> list[SectionSemantics]:
        # 按章节分组
        # 使用 LLM 分析每个章节的主题、重要性
        # 分析章节间关系
        pass
```

**LLM Prompt 示例**：
```
分析以下演示文稿章节：

章节标题: "市场分析"
页面标题:
- 市场规模趋势
- 竞争对手分析
- 用户需求调研

请提供：
1. 章节主题（一句话）
2. 重要性（0-1）
3. 与前一章节的关系（递进/对比/并列）
4. 推荐的视觉策略
```

### 3. 页面截图分析

**数据结构**：
```python
@dataclass
class VisualFeatures:
    slide_id: UUID
    dominant_colors: list[str]  # RGB hex
    color_contrast: float  # 0.0-1.0
    element_density: float  # 元素密度
    whitespace_ratio: float  # 留白比例
    visual_balance: float  # 左右平衡
    actual_hero_size: float  # 主图实际占比
    text_density: float  # 文字密度
    complexity_score: float  # 视觉复杂度
```

**提取方式**：
```python
from PIL import Image
import numpy as np

class ScreenshotAnalyzer:
    def analyze(self, image_path: str) -> VisualFeatures:
        img = Image.open(image_path)
        
        # 颜色分析
        dominant_colors = self._extract_dominant_colors(img)
        contrast = self._calculate_contrast(img)
        
        # 布局分析
        density = self._calculate_element_density(img)
        balance = self._calculate_balance(img)
        
        # 复杂度分析
        complexity = self._calculate_complexity(img)
        
        return VisualFeatures(...)
```

### 4. 视觉强度曲线

**数据结构**：
```python
@dataclass
class VisualIntensityCurve:
    scores: list[float]  # 每页的视觉强度分数
    smoothness: float  # 曲线平滑度
    variance: float  # 方差
    peaks: list[int]  # 高峰位置（索引）
    valleys: list[int]  # 低谷位置
    monotonic_spans: list[tuple[int, int]]  # 单调区间
    contrast_points: list[int]  # 强对比点
```

**计算方式**：
```python
class VisualIntensityAnalyzer:
    def analyze(
        self,
        layout_plans: list[LayoutPlan],
        screenshots: dict[UUID, VisualFeatures],
    ) -> VisualIntensityCurve:
        scores = []
        
        for plan in layout_plans:
            # 综合计算视觉强度
            layout_score = self._layout_intensity(plan)
            screenshot_score = screenshots[plan.slide_id].complexity_score
            
            # 加权平均
            score = 0.6 * layout_score + 0.4 * screenshot_score
            scores.append(score)
        
        # 分析曲线特征
        smoothness = self._calculate_smoothness(scores)
        peaks, valleys = self._find_peaks_valleys(scores)
        monotonic = self._find_monotonic_spans(scores)
        
        return VisualIntensityCurve(...)
```

### 5. 用户调整历史

**数据结构**：
```python
@dataclass
class UserAdjustmentHistory:
    adjustments: list[Adjustment]
    patterns: list[AdjustmentPattern]
    preferences: UserPreferences

@dataclass
class Adjustment:
    timestamp: datetime
    slide_index: int
    before: SlideCompositionDirective
    after: SlideCompositionDirective
    feedback: str
    result_score: float  # 调整后的 QA 分数

@dataclass
class AdjustmentPattern:
    pattern_type: str  # "increase_hero", "reduce_text", etc.
    frequency: int
    avg_improvement: float
    contexts: list[str]  # 什么情况下应用

@dataclass
class UserPreferences:
    prefers_visual_heavy: bool
    text_tolerance: float
    contrast_preference: str  # "high", "medium", "low"
    learned_rules: dict[str, float]
```

**学习方式**：
```python
class UserHistoryLearner:
    def learn(self, history: list[Adjustment]) -> UserPreferences:
        # 分析用户调整模式
        patterns = self._extract_patterns(history)
        
        # 识别偏好
        prefers_visual = sum(
            1 for adj in history 
            if adj.after.hero_priority > adj.before.hero_priority
        ) / len(history) > 0.6
        
        # 学习有效规则
        effective_rules = {}
        for pattern in patterns:
            if pattern.avg_improvement > 0.1:
                effective_rules[pattern.pattern_type] = pattern.frequency
        
        return UserPreferences(...)
```

## 分析层：智能分析器

### 1. 语义理解器

**功能**：解析用户反馈的真实意图

```python
class FeedbackSemanticAnalyzer:
    def __init__(self, llm_provider):
        self._llm = llm_provider
    
    def parse(self, feedback: str) -> FeedbackIntent:
        prompt = f"""
        解析用户对演示文稿的反馈：
        
        反馈: "{feedback}"
        
        请识别：
        1. 具体问题（问题类型、严重程度）
        2. 受影响的范围（全局/特定章节/特定页面）
        3. 期望的改进方向
        4. 调整力度（微调/中等/大幅）
        
        返回 JSON 格式。
        """
        
        request = LLMRequest(
            system_prompt="你是演示文稿用户反馈的语义解析器，只返回符合要求格式的 JSON。",
            user_prompt=prompt,
            temperature=0.1,
            json_mode=True,
        )
        draft = self._llm.generate_structured(request, _FeedbackIntentDraft)
        return FeedbackIntent(**draft.model_dump())

@dataclass
class FeedbackIntent:
    problem_type: str  # "monotonous_rhythm", "weak_hero", "inconsistent_footer"
    severity: str  # "minor", "moderate", "severe"
    scope: str  # "global", "section:chapter_1", "slide:3,5,7"
    desired_direction: str  # "increase_contrast", "enhance_hero", "unify_chrome"
    adjustment_magnitude: float  # 0.1-1.0
```

### 2. 模式识别器

**功能**：识别 Deck 中的问题模式

```python
class PatternRecognizer:
    def recognize(
        self,
        layout_plans: list[LayoutPlan],
        qa_report: DeckQAReport,
        intensity_curve: VisualIntensityCurve,
    ) -> list[RecognizedPattern]:
        patterns = []
        
        # 识别单调区间
        for start, end in intensity_curve.monotonic_spans:
            if end - start >= 5:  # 连续 5 页以上单调
                patterns.append(RecognizedPattern(
                    type="monotonous_rhythm",
                    severity="moderate",
                    affected_slides=list(range(start, end)),
                    description=f"第 {start+1}-{end+1} 页视觉节奏单调",
                    suggested_fix="insert_contrast_slides",
                ))
        
        # 识别版式重复
        family_streak = 0
        current_family = None
        for i, plan in enumerate(layout_plans):
            if plan.layout_family == current_family:
                family_streak += 1
            else:
                current_family = plan.layout_family
                family_streak = 1
            
            if family_streak >= 4:
                patterns.append(RecognizedPattern(
                    type="excessive_family_repetition",
                    severity="moderate",
                    affected_slides=[i - 3, i - 2, i - 1, i],
                    suggested_fix="vary_layout_family",
                ))
        
        # 识别章节过渡弱
        # ... 更多模式识别逻辑
        
        return patterns

@dataclass
class RecognizedPattern:
    type: str
    severity: str
    affected_slides: list[int]
    description: str
    suggested_fix: str
    confidence: float = 0.8
```

### 3. 趋势分析器

**功能**：分析整体趋势和异常点

```python
class TrendAnalyzer:
    def analyze(
        self,
        intensity_curve: VisualIntensityCurve,
        density_curve: list[float],
    ) -> TrendAnalysis:
        # 计算梯度（变化率）
        intensity_gradient = np.gradient(intensity_curve.scores)
        
        # 识别突变点
        sudden_changes = []
        for i, grad in enumerate(intensity_gradient):
            if abs(grad) > 0.5:  # 阈值
                sudden_changes.append((i, grad))
        
        # 计算整体趋势
        overall_trend = "increasing" if np.mean(intensity_gradient) > 0.1 else \
                       "decreasing" if np.mean(intensity_gradient) < -0.1 else \
                       "stable"
        
        # 检测异常页面
        mean_intensity = np.mean(intensity_curve.scores)
        std_intensity = np.std(intensity_curve.scores)
        outliers = [
            i for i, score in enumerate(intensity_curve.scores)
            if abs(score - mean_intensity) > 2 * std_intensity
        ]
        
        return TrendAnalysis(
            overall_trend=overall_trend,
            sudden_changes=sudden_changes,
            outliers=outliers,
            smoothness_score=intensity_curve.smoothness,
        )
```

## 决策层：优化引擎

### 核心优化器

```python
class EnhancedDeckOptimizer:
    def optimize(
        self,
        current_plan: DeckCompositionPlan,
        feedback_intent: FeedbackIntent,
        patterns: list[RecognizedPattern],
        trends: TrendAnalysis,
        qa_context: DeckQAContext,
        user_prefs: UserPreferences,
    ) -> DeckCompositionPlan:
        # 1. 生成候选调整
        adjustments = self._generate_adjustments(
            feedback_intent, patterns, trends, user_prefs
        )
        
        # 2. 解决冲突
        resolved = self._resolve_conflicts(adjustments)
        
        # 3. 应用调整
        updated_plan = self._apply_adjustments(current_plan, resolved)
        
        # 4. 验证改进
        validation = self._validate_improvement(current_plan, updated_plan, qa_context)
        
        if not validation.improved:
            # 回退或尝试其他方案
            updated_plan = self._try_alternative(current_plan, adjustments)
        
        return updated_plan
```

### 调整生成器

```python
class AdjustmentGenerator:
    def generate(
        self,
        feedback_intent: FeedbackIntent,
        patterns: list[RecognizedPattern],
    ) -> list[ProposedAdjustment]:
        adjustments = []
        
        # 基于反馈意图生成调整
        if feedback_intent.problem_type == "monotonous_rhythm":
            adjustments.extend(
                self._generate_rhythm_adjustments(feedback_intent)
            )
        
        # 基于识别的模式生成调整
        for pattern in patterns:
            if pattern.type == "excessive_family_repetition":
                adjustments.extend(
                    self._generate_variety_adjustments(pattern)
                )
        
        # 优先级排序
        adjustments.sort(key=lambda x: x.priority, reverse=True)
        
        return adjustments

@dataclass
class ProposedAdjustment:
    adjustment_type: str
    target_slides: list[int]
    parameters: dict[str, Any]
    priority: float
    expected_improvement: float
    rationale: str
```

### 冲突解决器

```python
class ConflictResolver:
    def resolve(
        self,
        adjustments: list[ProposedAdjustment],
    ) -> list[ProposedAdjustment]:
        # 检测冲突
        conflicts = self._detect_conflicts(adjustments)
        
        # 解决策略
        resolved = []
        for group in self._group_by_target(adjustments):
            if len(group) == 1:
                resolved.append(group[0])
            else:
                # 多个调整针对同一页面
                best = self._pick_best_adjustment(group)
                resolved.append(best)
        
        return resolved
    
    def _detect_conflicts(
        self,
        adjustments: list[ProposedAdjustment],
    ) -> list[tuple[ProposedAdjustment, ProposedAdjustment]]:
        conflicts = []
        for i, adj1 in enumerate(adjustments):
            for adj2 in adjustments[i+1:]:
                if self._are_conflicting(adj1, adj2):
                    conflicts.append((adj1, adj2))
        return conflicts
```

## 完整工作流程

```python
class EnhancedDeckCompositionService:
    def revise(
        self,
        current_plan: DeckCompositionPlan,
        feedback: str,
        *,
        layout_plans: list[LayoutPlan],
        screenshots: dict[UUID, str],  # slide_id -> image_path
        deck_qa_report: DeckQAReport,
        slides: list[SlideSpec],
        user_history: list[Adjustment] | None = None,
    ) -> DeckCompositionPlan:
        # === 输入层：收集多维度信息 ===
        
        # 1. 分析 DeckQA
        qa_context = DeckQAAnalyzer().analyze(deck_qa_report)
        
        # 2. 分析章节语义
        section_semantics = SectionSemanticAnalyzer(self._llm).analyze(slides)
        
        # 3. 分析页面截图
        visual_features = {
            slide_id: ScreenshotAnalyzer().analyze(path)
            for slide_id, path in screenshots.items()
        }
        
        # 4. 分析视觉强度曲线
        intensity_curve = VisualIntensityAnalyzer().analyze(
            layout_plans, visual_features
        )
        
        # 5. 学习用户偏好
        user_prefs = UserHistoryLearner().learn(user_history or [])
        
        # === 分析层：智能分析 ===
        
        # 6. 解析反馈语义
        feedback_intent = FeedbackSemanticAnalyzer(self._llm).parse(feedback)
        
        # 7. 识别问题模式
        patterns = PatternRecognizer().recognize(
            layout_plans, deck_qa_report, intensity_curve
        )
        
        # 8. 分析趋势
        trends = TrendAnalyzer().analyze(
            intensity_curve,
            [d.target_density for d in current_plan.slide_directives],
        )
        
        # === 决策层：优化 ===
        
        # 9. 生成优化方案
        updated_plan = EnhancedDeckOptimizer().optimize(
            current_plan,
            feedback_intent,
            patterns,
            trends,
            qa_context,
            user_prefs,
        )
        
        # 10. 记录调整历史
        self._record_adjustment(current_plan, updated_plan, feedback)
        
        return updated_plan
```

## 性能优化

### 缓存策略

```python
class CachedAnalyzer:
    def __init__(self):
        self._screenshot_cache = {}  # slide_id -> VisualFeatures
        self._section_semantic_cache = {}  # chapter_id -> SectionSemantics
    
    def get_visual_features(self, slide_id: UUID, image_path: str):
        if slide_id not in self._screenshot_cache:
            self._screenshot_cache[slide_id] = ScreenshotAnalyzer().analyze(image_path)
        return self._screenshot_cache[slide_id]
```

### 增量更新

```python
def revise_incremental(
    self,
    current_plan: DeckCompositionPlan,
    changed_slides: list[int],  # 只重新分析变化的页面
    ...
):
    # 仅更新受影响的部分
    pass
```

## 可扩展性

### 插件式分析器

```python
class AnalyzerPlugin(ABC):
    @abstractmethod
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        pass

class EnhancedDeckCompositionService:
    def __init__(self):
        self._analyzers: list[AnalyzerPlugin] = []
    
    def register_analyzer(self, analyzer: AnalyzerPlugin):
        self._analyzers.append(analyzer)
    
    def analyze_all(self, context: AnalysisContext):
        results = [analyzer.analyze(context) for analyzer in self._analyzers]
        return self._merge_results(results)
```

## 总结

这个架构设计的核心优势：

1. **多维度信息整合** - DeckQA、语义、截图、强度、历史
2. **智能分析** - 语义理解、模式识别、趋势分析
3. **数据驱动** - 基于实际数据而非固定规则
4. **可学习** - 从用户历史中学习偏好
5. **可验证** - 闭环反馈，验证改进效果
6. **可扩展** - 插件式架构，易于添加新分析器

下一步：实现这个架构的核心组件。
