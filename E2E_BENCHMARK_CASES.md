# End-to-End Benchmark 案例定义

## 概述

本文件定义了 5 个典型的端到端 Benchmark 案例，涵盖真实产品使用场景。

每个案例包含：
- 原始输入文件（文档 + 图片）
- 用户任务描述
- 期望的输出质量标准

**与 Generator Benchmark 的区别**：
- ❌ 不预先指定 `LayoutFamily`
- ❌ 不预先指定 `hero_asset_id`
- ❌ 不预先指定 `Variant`
- ✅ 让 Archium 自主完成所有决策

---

## 案例 1：产品介绍（图文并茂）

### 场景描述
创业公司需要制作产品介绍 PPT，用于投资路演。

### 输入文件
```
benchmark_data/e2e/product_intro/
├── 产品介绍文档.pdf (10 页)
│   ├── 产品概述
│   ├── 核心功能
│   ├── 技术架构
│   ├── 商业模式
│   └── 市场分析
└── images/
    ├── product_screenshot_1.png (产品界面)
    ├── product_screenshot_2.png (功能演示)
    ├── team_photo.jpg (团队合影)
    ├── architecture_diagram.png (架构图)
    └── market_chart.png (市场数据图表)
```

### 用户任务
```
"根据产品介绍文档，制作一份 8-10 页的投资路演 PPT。
重点突出产品核心价值、技术优势和市场潜力。"
```

### 期望标准

#### 页面数量
- 最少：6 页
- 最多：12 页

#### 内容覆盖
必须包含关键词：
- "产品"、"功能"、"技术"、"市场"、"优势"

禁止关键词：
- （无）

标题长度：5-30 字符  
要点数量：2-5 条/页

#### Hero Asset 选择
- 优先标签：["product", "screenshot", "diagram"]
- 避免标签：["team_photo"]（团队照不应作为 hero）
- 最少使用率：60%（至少用 60% 的图片）
- 最大重用：2 次/图

#### 布局分布
期望：
- `HERO_CONTENT`: 3-5 页（产品展示）
- `METRIC_GRID`: 1-2 页（数据展示）
- `TEXT_FOCUS`: 1-3 页（文字说明）

#### 质量阈值
- 规则通过率：≥ 90%
- 平均布局得分：≥ 0.80
- DeckQA 得分：≥ 0.75

---

## 案例 2：数据报告（图表密集）

### 场景描述
企业季度业绩报告，包含大量数据图表。

### 输入文件
```
benchmark_data/e2e/data_report/
├── Q1业绩报告.xlsx (多个工作表)
│   ├── 收入数据
│   ├── 成本分析
│   ├── 客户增长
│   └── 区域分布
└── images/
    ├── revenue_trend.png (收入趋势图)
    ├── cost_breakdown.png (成本分解图)
    ├── customer_growth.png (客户增长图)
    ├── regional_map.png (区域分布地图)
    └── comparison_chart.png (同比对比图)
```

### 用户任务
```
"根据 Q1 业绩报告数据，生成一份数据可视化 PPT。
每页展示 1-2 个关键指标，配合图表说明。"
```

### 期望标准

#### 页面数量
- 最少：5 页
- 最多：10 页

#### 内容覆盖
必须包含关键词：
- "收入"、"增长"、"客户"、"成本"、"%"

#### Hero Asset 选择
- 优先标签：["chart", "graph", "data_visual"]
- 最少使用率：80%（图表密集）
- 最大重用：1 次/图（每个图表只用一次）

#### 布局分布
期望：
- `METRIC_GRID`: 3-6 页（数据展示为主）
- `HERO_CONTENT`: 1-3 页（关键指标突出）
- `COMPARISON`: 1-2 页（对比分析）

#### 质量阈值
- 规则通过率：≥ 95%（数据页面应该更规范）
- 平均布局得分：≥ 0.85
- DeckQA 得分：≥ 0.80

---

## 案例 3：项目提案（结构化文本）

### 场景描述
向管理层提交新项目立项提案。

### 输入文件
```
benchmark_data/e2e/project_proposal/
├── 项目提案书.docx (15 页)
│   ├── 项目背景
│   ├── 目标与范围
│   ├── 实施方案
│   ├── 时间计划
│   ├── 预算估算
│   └── 风险分析
└── images/
    ├── gantt_chart.png (甘特图)
    ├── org_structure.png (组织架构)
    └── budget_table.png (预算表格)
```

### 用户任务
```
"将项目提案书转换为 PPT，用于管理层评审会议。
结构清晰，逻辑连贯，重点突出预算和时间计划。"
```

### 期望标准

#### 页面数量
- 最少：8 页
- 最多：15 页

#### 内容覆盖
必须包含关键词：
- "项目"、"目标"、"方案"、"预算"、"时间"、"风险"

#### Hero Asset 选择
- 优先标签：["diagram", "chart", "timeline"]
- 最少使用率：50%（文字为主）
- 最大重用：2 次/图

#### 布局分布
期望：
- `TEXT_FOCUS`: 4-8 页（文字说明为主）
- `HERO_CONTENT`: 2-4 页（关键图表）
- `TIMELINE`: 1-2 页（时间计划）

#### 质量阈值
- 规则通过率：≥ 85%
- 平均布局得分：≥ 0.75
- DeckQA 得分：≥ 0.70

---

## 案例 4：学术演讲（概念图示）

### 场景描述
学术会议演讲，介绍研究成果。

### 输入文件
```
benchmark_data/e2e/academic_talk/
├── 研究论文.pdf (20 页)
│   ├── 摘要
│   ├── 研究背景
│   ├── 方法论
│   ├── 实验结果
│   └── 结论
└── images/
    ├── concept_diagram_1.png (概念图)
    ├── concept_diagram_2.png (流程图)
    ├── experiment_setup.png (实验装置)
    ├── result_graph_1.png (结果图1)
    ├── result_graph_2.png (结果图2)
    └── comparison_table.png (对比表)
```

### 用户任务
```
"将研究论文转换为学术演讲 PPT，时长 15 分钟。
重点展示研究方法和实验结果，适合专业听众。"
```

### 期望标准

#### 页面数量
- 最少：10 页
- 最多：18 页

#### 内容覆盖
必须包含关键词：
- "研究"、"方法"、"实验"、"结果"、"结论"

#### Hero Asset 选择
- 优先标签：["diagram", "graph", "result", "concept"]
- 最少使用率：70%
- 最大重用：1 次/图

#### 布局分布
期望：
- `HERO_CONTENT`: 4-8 页（图示为主）
- `TEXT_FOCUS`: 2-4 页（方法说明）
- `COMPARISON`: 2-3 页（结果对比）

#### 质量阈值
- 规则通过率：≥ 88%
- 平均布局得分：≥ 0.78
- DeckQA 得分：≥ 0.73

---

## 案例 5：活动宣传（视觉驱动）

### 场景描述
公司年会活动宣传 PPT，视觉冲击力强。

### 输入文件
```
benchmark_data/e2e/event_promotion/
├── 年会策划方案.docx (5 页)
│   ├── 活动主题
│   ├── 时间地点
│   ├── 节目安排
│   └── 亮点介绍
└── images/
    ├── event_poster.png (活动海报)
    ├── venue_photo_1.jpg (场地照片1)
    ├── venue_photo_2.jpg (场地照片2)
    ├── stage_design.png (舞台设计图)
    ├── food_menu.jpg (菜单照片)
    └── entertainment.jpg (娱乐节目照片)
```

### 用户任务
```
"制作年会宣传 PPT，风格活泼，图片为主。
吸引员工参与，营造期待氛围。"
```

### 期望标准

#### 页面数量
- 最少：5 页
- 最多：8 页

#### 内容覆盖
必须包含关键词：
- "年会"、"活动"、"时间"、"地点"

#### Hero Asset 选择
- 优先标签：["photo", "poster", "venue", "visual"]
- 最少使用率：90%（图片密集）
- 最大重用：1 次/图（避免重复）

#### 布局分布
期望：
- `HERO_CONTENT`: 4-6 页（大图展示）
- `TEXT_FOCUS`: 0-2 页（文字极少）

#### 质量阈值
- 规则通过率：≥ 85%
- 平均布局得分：≥ 0.75
- DeckQA 得分：≥ 0.70

---

## 边界案例（困难场景）

### 边界案例 1：极少内容
```
输入：只有 3 行文字，无图片
挑战：如何生成有价值的页面？
期望：至少 1 页，不应崩溃
```

### 边界案例 2：极多内容
```
输入：50 页文档，15 个要点/页
挑战：如何合理分页和筛选？
期望：不超过 20 页，每页 ≤ 7 要点
```

### 边界案例 3：无素材
```
输入：纯文字 PDF，完全无图
挑战：如何选择布局？
期望：使用 TEXT_FOCUS，不报错
```

### 边界案例 4：冲突素材
```
输入：横图 + 竖图混合，尺寸不一致
挑战：Variant 选择是否合理？
期望：横图 → split_hero_left，竖图 → split_hero_top
```

---

## 实现计划

### Phase 1：准备测试数据（1 周）
1. 创建 `benchmark_data/e2e/` 目录结构
2. 准备 5 个场景的文档和图片
3. 人工标注"黄金标准"输出（参考）

### Phase 2：实现 E2EBenchmarkService（1 周）
1. 完善服务代码
2. 实现各项检查逻辑
3. 单元测试

### Phase 3：运行初始验证（3 天）
1. 执行 5 个案例
2. 分析失败原因
3. 调整期望标准（如果过于严格）

### Phase 4：持续优化（进行中）
1. 每周运行一次
2. 跟踪指标变化
3. 新增案例

---

## JSON 配置示例

```json
{
  "case_id": "e2e_product_intro_001",
  "scenario": "product_intro",
  "title": "产品介绍 - 投资路演",
  "description": "创业公司产品介绍 PPT，用于投资路演",
  "task_description": "根据产品介绍文档，制作一份 8-10 页的投资路演 PPT。重点突出产品核心价值、技术优势和市场潜力。",
  "input_documents": [
    "e2e/product_intro/产品介绍文档.pdf"
  ],
  "input_images": [
    "e2e/product_intro/images/product_screenshot_1.png",
    "e2e/product_intro/images/product_screenshot_2.png",
    "e2e/product_intro/images/team_photo.jpg",
    "e2e/product_intro/images/architecture_diagram.png",
    "e2e/product_intro/images/market_chart.png"
  ],
  "expected_outcomes": {
    "min_slide_count": 6,
    "max_slide_count": 12,
    "content_expectations": {
      "required_keywords": ["产品", "功能", "技术", "市场", "优势"],
      "forbidden_keywords": [],
      "min_title_length": 5,
      "max_title_length": 30,
      "min_key_points_per_slide": 2,
      "max_key_points_per_slide": 5
    },
    "hero_asset_expectations": {
      "should_prefer_tags": ["product", "screenshot", "diagram"],
      "should_avoid_tags": ["team_photo"],
      "min_usage_ratio": 0.6,
      "max_reuse_count": 2
    },
    "layout_distribution": [
      {
        "layout_family": "HERO_CONTENT",
        "min_count": 3,
        "max_count": 5
      },
      {
        "layout_family": "METRIC_GRID",
        "min_count": 1,
        "max_count": 2
      },
      {
        "layout_family": "TEXT_FOCUS",
        "min_count": 1,
        "max_count": 3
      }
    ],
    "min_rule_pass_rate": 0.90,
    "min_avg_layout_score": 0.80,
    "min_deck_qa_score": 0.75,
    "allow_partial_success": true,
    "max_failed_slides": 2
  },
  "difficulty": "medium",
  "tags": ["product", "startup", "pitch", "investor"]
}
```

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)
