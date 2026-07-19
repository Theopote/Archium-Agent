# E2E Benchmark 实现问题分析与修复方案

## 问题诊断

### ✅ 概念和设计：正确

**双层 Benchmark 体系**：
- Layer A: Generator Benchmark（已知输入 → 验证生成器）
- Layer B: E2E Benchmark（原始任务 → 验证完整流程）

**设计目标**：
- 5 个典型场景
- 4 个边界案例
- 验证：内容选择、素材选择、布局分布、质量统计

### ❌ 实现：存在严重 API 不匹配

## 问题清单

### 问题 1：调用了不存在的 `import_from_files()` API

**错误代码**（`e2e_benchmark_service.py` 第 60 行）：
```python
presentation = self._ingestion.import_from_files(
    task_description=case.task_description,
    document_paths=document_paths,
    image_paths=image_paths,
)
```

**实际 API**（`ingestion_service.py`）：
```python
class IngestionService:
    def import_file(
        self,
        project_id: UUID,
        source_path: Path,
    ) -> ImportItemResult:
        """Import one file into a project."""
```

**问题**：
- ❌ 没有 `import_from_files()` 方法
- ❌ 需要先创建 `Project`
- ❌ 需要逐个文件调用 `import_file()`
- ❌ 不返回 `Presentation`

---

### 问题 2：调用了不存在的 `get_layout_plan()` 方法

**错误代码**（`e2e_benchmark_service.py` 第 75 行）：
```python
plans = [
    self._presentations.get_layout_plan(slide.id)
    for slide in slides
]
```

**实际 API**（`PresentationRepository`）：
```python
class PresentationRepository:
    def get_presentation(...)
    def list_by_project(...)
    def get_slide(...)
    def save_slide(...)
    def list_slides(...)
    # ❌ 没有 get_layout_plan()
```

**正确方式**：
```python
from archium.infrastructure.database.repositories import LayoutPlanRepository

layout_repo = LayoutPlanRepository(session)
plans = [
    layout_repo.get_by_id(slide.layout_plan_id)
    for slide in slides
    if slide.layout_plan_id is not None
]
```

---

### 问题 3：错误假设 `Presentation` 包含 `design_system`

**错误代码**（`e2e_benchmark_service.py` 第 83 行）：
```python
validation_reports = []
for plan in plans:
    report = self._validation.validate(
        plan,
        presentation.design_system,  # ❌ Presentation 没有此字段
        require_source=False,
    )
```

**实际架构**：
- `DesignSystem` 是独立的领域实体
- 通过 `DesignSystemRepository` 管理
- 通过 `VisualWorkflow` 加载和应用

**正确方式**：
```python
from archium.infrastructure.database.repositories import DesignSystemRepository

design_system_repo = DesignSystemRepository(session)
design_system = design_system_repo.get_default()  # 或根据 presentation 配置获取
```

---

### 问题 4：跳过了完整的端到端流程

**当前实现**（简化流程）：
```python
# 导入文档（实际 API 不存在）
presentation = self._ingestion.import_from_files(...)

# 逐页生成布局
for slide in slides:
    self._visual_edits.regenerate_layout(slide.id)

# 验证
validation_reports = [...]
```

**缺失的关键步骤**：
1. ❌ 创建 Project
2. ❌ 生成 Brief
3. ❌ 生成 Storyline
4. ❌ 生成 SlideSpec
5. ❌ 生成 VisualIntent
6. ❌ 应用 ArtDirection
7. ❌ 执行 DeckCompositionPlan
8. ❌ 完整 VisualWorkflow
9. ❌ 导出 PPTX
10. ❌ 生成截图

**真正的 E2E 应该是**：
```
原始任务 + 原始文档 + 原始图片
  ↓
创建 Project
  ↓
导入文档（IngestionService）
  ↓
导入图片（AssetService）
  ↓
创建 Presentation
  ↓
执行 PresentationWorkflow
  ├─ Brief 生成
  ├─ Storyline 生成
  └─ SlideSpec 生成
  ↓
执行 VisualWorkflow
  ├─ VisualIntent 生成
  ├─ ArtDirection 生成
  ├─ DeckCompositionPlan 生成
  └─ LayoutPlan 生成
  ↓
导出 PPTX
  ↓
生成截图
  ↓
QA 验证
```

---

## 正确的实现方案

### 方案 A：完整 E2E（推荐，但工程量大）

```python
class E2EBenchmarkService:
    """真正的端到端 Benchmark 服务"""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        benchmark_data_dir: Path,
    ) -> None:
        self._session = session
        self._data_dir = benchmark_data_dir
        
        # 完整服务链
        self._projects = ProjectRepository(session)
        self._ingestion = IngestionService(session)
        self._assets = AssetService(session)
        self._presentations = PresentationRepository(session)
        self._presentation_service = PresentationService(session, llm)
        self._visual_workflow = VisualWorkflowService(session, llm)
        self._renderer = PptxRenderer(session)
        self._screenshot = ScreenshotService(session)
        self._validation = LayoutValidationService()
        self._deck_qa = DeckQAService()

    def run_case(self, case: E2EBenchmarkCase) -> E2EBenchmarkResult:
        """执行完整的端到端流程"""
        
        # Step 1: 创建项目
        project = self._projects.create_project(
            Project(name=f"E2E_Benchmark_{case.case_id}")
        )
        
        # Step 2: 导入文档
        for doc_path in case.input_documents:
            full_path = self._data_dir / doc_path
            self._ingestion.import_file(project.id, full_path)
        
        # Step 3: 导入图片
        for img_path in case.input_images:
            full_path = self._data_dir / img_path
            self._assets.import_asset(project.id, full_path)
        
        # Step 4: 创建演示
        request = PresentationRequest(
            title=case.task_description,
            # ... 其他参数
        )
        presentation = self._presentation_service.create_presentation(
            project.id, request
        )
        
        # Step 5: 生成 Brief
        brief = self._presentation_service.generate_brief(
            project.id, presentation.id, request
        )
        
        # Step 6: 生成 Storyline
        storyline = self._presentation_service.generate_storyline(
            project.id, brief
        )
        
        # Step 7: 生成 SlideSpec
        slides = self._presentation_service.generate_slide_plan(
            project.id, brief, storyline
        )
        
        # Step 8: 执行 Visual Workflow（为每个 slide 生成布局）
        for slide in slides:
            self._visual_workflow.execute(slide.id)
        
        # Step 9: 导出 PPTX
        pptx_path = self._renderer.render(presentation.id)
        
        # Step 10: 生成截图
        screenshots = []
        for slide in slides:
            screenshot = self._screenshot.capture(slide.id)
            screenshots.append(screenshot)
        
        # Step 11: 验证和评估
        # ... QA 检查
        
        return E2EBenchmarkResult(...)
```

**优点**：
- ✅ 真正的端到端
- ✅ 验证完整流程
- ✅ 发现所有环节的问题

**缺点**：
- ❌ 工程量大（需要 2-3 周）
- ❌ 依赖 LLM（成本高、速度慢）
- ❌ 需要完善的错误处理

---

### 方案 B：渐进式 E2E（推荐作为过渡）

**Phase 1**：修复当前 API 调用错误

```python
class E2EBenchmarkService:
    def run_case(self, case: E2EBenchmarkCase) -> E2EBenchmarkResult:
        # Step 1: 创建项目
        project = self._projects.create_project(
            Project(name=f"E2E_{case.case_id}")
        )
        
        # Step 2: 导入文档（修复 API 调用）
        for doc_path in case.input_documents:
            full_path = self._data_dir / doc_path
            result = self._ingestion.import_file(project.id, full_path)
            if result.error:
                # 处理错误
                pass
        
        # Step 3: 导入图片
        for img_path in case.input_images:
            full_path = self._data_dir / img_path
            self._assets.import_asset(project.id, full_path)
        
        # Step 4: 创建演示（简化版，暂时手动构建）
        presentation = self._presentations.create_presentation(
            Presentation(
                project_id=project.id,
                title=case.task_description,
            )
        )
        
        # Step 5: 手动创建 SlideSpec（暂时跳过 Brief/Storyline）
        slides = self._create_slides_from_case(case, presentation.id)
        
        # Step 6: 为每个 slide 生成布局
        layout_repo = LayoutPlanRepository(self._session)
        design_system_repo = DesignSystemRepository(self._session)
        design_system = design_system_repo.get_default()
        
        for slide in slides:
            # 使用 VisualEditService 生成布局
            plan = self._visual_edits.regenerate_layout(slide.id)
        
        # Step 7: 验证
        plans = [
            layout_repo.get_by_id(slide.layout_plan_id)
            for slide in slides
            if slide.layout_plan_id
        ]
        
        validation_reports = [
            self._validation.validate(plan, design_system)
            for plan in plans
        ]
        
        # Step 8: 评估
        deck_qa_report = self._deck_qa.evaluate(
            plans, slides=slides, design_system=design_system
        )
        
        return E2EBenchmarkResult(...)
```

**优点**：
- ✅ 修复了 API 调用错误
- ✅ 可以立即运行
- ✅ 工程量适中（1-2 天）

**缺点**：
- ⚠️ 仍然跳过了 Brief/Storyline/完整 Workflow
- ⚠️ 手动构建 SlideSpec（不是真正的"自主决策"）

---

### 方案 C：分阶段实现（推荐）

**当前阶段（立即修复）**：
1. 修复 API 调用错误
2. 使用简化流程（跳过 Brief/Storyline）
3. 标注为 "E2E Lite" 或 "Integration Test"

**下一阶段（1 个月内）**：
1. 补充 Brief 生成
2. 补充 Storyline 生成
3. 补充完整 Visual Workflow

**最终阶段（3 个月内）**：
1. 真正的端到端
2. 包含 PPTX 导出和截图
3. 完整的 QA 验证

---

## 当前状态判定

| 项目 | 状态 | 说明 |
|------|------|------|
| E2E 概念设计 | ✅ 通过 | 双层体系正确 |
| E2E 领域模型 | ✅ 通过 | 数据结构完整 |
| E2E 案例定义 | ✅ 通过 | 5 个场景清晰 |
| **E2E 服务实现** | ❌ **未通过** | **API 不匹配** |
| **E2E 执行流程** | ❌ **未通过** | **跳过关键步骤** |

## 修复优先级

### P0（立即修复）

1. **修复 API 调用错误**
   - 文件：`e2e_benchmark_service.py`
   - 问题：调用了不存在的 API
   - 影响：代码无法运行

2. **标注实现范围**
   - 在文档中明确当前实现的局限性
   - 标注为 "E2E Lite" 或 "Integration Test"
   - 避免误导

### P1（本周）

3. **补充缺失的 Repository 调用**
   - 使用 `LayoutPlanRepository`
   - 使用 `DesignSystemRepository`
   - 修复数据访问逻辑

4. **简化流程验证**
   - 确保简化版能够运行
   - 生成测试报告

### P2（本月）

5. **补充完整流程**
   - Brief 生成
   - Storyline 生成
   - 完整 Workflow

6. **验证端到端能力**
   - 使用真实测试数据
   - 评估质量

---

## 推荐行动

### 立即行动（今天）

1. **承认问题**
   - 在文档中明确标注当前实现的局限性
   - 说明这是"设计原型"而非"可运行实现"

2. **创建修复计划**
   - 分阶段修复（P0 → P1 → P2）
   - 明确每个阶段的交付标准

### 短期行动（本周）

3. **修复 API 调用**
   - 使用正确的 `import_file()` API
   - 使用正确的 Repository
   - 确保代码能够运行

4. **实现简化版 E2E**
   - 跳过 Brief/Storyline
   - 手动构建 SlideSpec
   - 验证布局生成和 QA

### 中期行动（本月）

5. **补充完整流程**
   - 集成 PresentationService
   - 集成 VisualWorkflow
   - 实现真正的端到端

---

## 总结

### 核心问题

**E2E Benchmark 的实现存在严重的 API 不匹配问题，导致代码无法运行。**

### 根本原因

1. 实现时没有查看实际的 API 接口
2. 假设了理想的 API 而非实际存在的 API
3. 跳过了关键的端到端流程步骤

### 修复路径

**分阶段实现**：
1. 立即修复 API 调用（P0）
2. 实现简化版 E2E（P1）
3. 补充完整流程（P2）

### 诚实标注

在当前阶段，应该：
- ✅ 保留 E2E 设计和领域模型（概念正确）
- ✅ 标注服务实现为 "原型" 或 "未完成"
- ✅ 创建明确的修复计划
- ❌ 不要声称 E2E Benchmark "已完成"

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)  
状态：问题分析完成，待修复
