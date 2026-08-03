# 用户概念映射关系

## 五大用户概念

### 1. 项目
用户对整个设计项目的理解和管理。

**内部对象 → 用户界面表达：**
- `KnowledgeState` → 项目理解程度
- `ProjectContext` → 当前项目状态
- `ProjectMission` → 本次设计任务
- `Project` → 项目

### 2. 资料
项目相关的所有资料和文档。

**内部对象 → 用户界面表达：**
- `Asset` → 资料
- `Document` → 文档
- `Reference` → 参考资料
- `AssetBoard` → 资料库

### 3. 方案
设计方案的探索和确定。

**内部对象 → 用户界面表达：**
- `ConceptDirection` → 方案方向
- `SceneProposal` → 方案提案
- `ConceptExploration` → 方案探索
- `DesignConcept` → 设计概念

### 4. 汇报
汇报内容的组织和编辑。

**内部对象 → 用户界面表达：**
- `Storyline` → 汇报结构
- `SlideSpec` → 页面内容
- `LayoutPlan` → 页面版式
- `RenderScene` → 可编辑页面
- `Presentation` → 汇报
- `Slide` → 幻灯片

### 5. 交付
最终成果的生成和导出。

**内部对象 → 用户界面表达：**
- `Workstream` → 工作内容
- `DeliverablePlan` → 预期成果
- `Deliverable` → 交付成果
- `Export` → 导出

## 隐藏的系统术语

以下系统术语不应在用户界面中出现：

### 知识管理相关
- ❌ `KnowledgeDimensions` → 使用"项目理解维度"
- ❌ `ProcessBoard` → 使用"工作流程"
- ❌ `KnowledgeProfile` → 使用"项目知识档案"

### 场景管理相关
- ❌ `SceneProposal` → 使用"方案提案"
- ❌ `SceneRevision` → 使用"方案版本"
- ❌ `SceneContext` → 使用"方案背景"

### 工作流相关
- ❌ `WorkflowRun` → 使用"生成任务"
- ❌ `WorkflowCheckpoint` → 使用"任务进度"
- ❌ `WorkflowState` → 使用"任务状态"

### 视觉相关
- ❌ `VisualWorkflowResult` → 使用"视觉生成结果"
- ❌ `RenderScene` → 使用"可编辑页面"
- ❌ `LayoutPlan` → 使用"页面版式"

### 质量相关
- ❌ `QualityAssessment` → 使用"质量评估"
- ❌ `CritiqueReport` → 使用"评审报告"
- ❌ `QAReport` → 使用"质量报告"

## 界面术语替换规则

### 导航和菜单
- "工作流" → "生成"
- "场景" → "方案"
- "知识" → "项目理解"
- "资产" → "资料"
- "交付物" → "交付成果"

### 按钮和操作
- "生成工作流" → "生成汇报"
- "创建场景" → "创建方案"
- "上传资产" → "上传资料"
- "导出交付物" → "导出成果"

### 状态和反馈
- "工作流运行中" → "生成进行中"
- "场景已创建" → "方案已创建"
- "资产已上传" → "资料已上传"
- "交付物已生成" → "成果已生成"

### 面板和区域
- "工作流面板" → "生成面板"
- "场景面板" → "方案面板"
- "知识面板" → "项目理解面板"
- "资产面板" → "资料面板"
- "交付物面板" → "交付成果面板"
