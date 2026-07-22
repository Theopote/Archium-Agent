# Studio 交互能力评估与改进路线图

## 当前状态分析

### ✅ 已实现的功能

**预览能力**
- ✅ 图片预览（PPTX 截图 + 线框图）
- ✅ 质量评分显示
- ✅ 问题文字标注
- ✅ 单独的几何问题线框覆盖层

**编辑能力**
- ✅ 属性面板式编辑
- ✅ 命令式修改（自然语言指令）
- ✅ 元素选择（通过列表/属性面板）
- ✅ 参数化调整

**架构**
```
当前：预览 + 属性面板 + 命令式修改
特点：可靠工作台，适合结构化编辑
```

### ❌ 缺失的 WYSIWYG 功能

**直接交互**
- ❌ 直接点击截图中的元素
- ❌ 在图片上悬停识别元素
- ❌ 拖拽元素调整位置
- ❌ 拖动裁切框调整尺寸
- ❌ 双击直接编辑文字
- ❌ 在同一个画布上叠加完整元素边界

**视觉反馈**
- ❌ 实时预览（拖拽时）
- ❌ 辅助线（对齐、间距）
- ❌ 吸附网格
- ❌ 多选和批量操作

## 问题诊断

### 1. 架构层面

**当前设计**
```python
# slide_canvas.py
def render_slide_canvas(*, slide_snapshot: SlideVisualSnapshot | None, advanced: bool):
    st.image(preview_path, use_container_width=True)  # 静态图片
    _render_validation_overlay(...)  # HTML 覆盖层，不可交互
```

**限制**：
- Streamlit 的 `st.image` 是静态展示，无交互事件
- HTML 覆盖层仅用于标注，不响应用户输入
- 没有画布组件承载交互逻辑

### 2. 交互层面

**当前流程**
```
用户输入自然语言 → 解析意图 → 修改 LayoutPlan → 重新渲染预览
```

**缺失**：
- 鼠标事件监听（click, hover, drag）
- 坐标映射（屏幕坐标 ↔ 逻辑坐标）
- 拖拽状态管理
- 实时预览反馈

### 3. 技术栈限制

**Streamlit 的约束**
- 主要是表单/仪表板框架，不是画布编辑器
- 缺少原生的拖拽、画布组件
- 需要自定义组件或第三方库

## 改进路线图

### 第一阶段：增强元素可见性（1-2 周）

**目标**: 让用户能更清楚地看到元素边界和层级

**实现**：
```python
# 在 slide_canvas.py 中增强
def _render_enhanced_overlay(
    *,
    slide_snapshot: SlideVisualSnapshot,
    show_all_elements: bool = True,
    show_labels: bool = True,
) -> None:
    """渲染增强的元素覆盖层"""
    plan = slide_snapshot.layout_plan
    if plan is None:
        return
    
    # 为所有元素绘制边界框（不仅是问题元素）
    # 添加元素标签（role + id）
    # 使用不同颜色区分元素类型
    # 添加 z-index 显示
```

**改进点**：
- ✅ 显示所有元素边界（可切换）
- ✅ 元素标签（role 标识）
- ✅ 颜色编码（hero=蓝、title=绿、body=灰）
- ✅ 层级指示

### 第二阶段：基础点击选择（2-3 周）

**目标**: 点击画布上的元素进行选择

**技术方案**：使用 Streamlit 自定义组件

```python
# 创建自定义组件 streamlit_canvas_select
# components/canvas_select.py

import streamlit.components.v1 as components

def canvas_select(
    image_url: str,
    elements: list[dict],  # {id, x, y, width, height, role}
    selected_id: str | None,
) -> str | None:
    """
    渲染可交互的画布，返回被点击的元素 ID
    
    使用 JavaScript + Canvas/SVG 实现：
    1. 显示预览图
    2. 叠加元素边界框
    3. 监听点击事件
    4. 计算点击位置对应的元素
    5. 返回元素 ID 给 Streamlit
    """
    component_value = _component_func(
        image_url=image_url,
        elements=elements,
        selected_id=selected_id,
    )
    return component_value  # 返回被点击的元素 ID
```

**集成到 Studio**：
```python
# slide_canvas.py
def render_slide_canvas(...):
    if plan is not None and preview_path:
        # 替换静态 st.image
        selected_element_id = canvas_select(
            image_url=preview_path,
            elements=[
                {
                    "id": e.id,
                    "x": e.x / plan.page_width * 100,
                    "y": e.y / plan.page_height * 100,
                    "width": e.width / plan.page_width * 100,
                    "height": e.height / plan.page_height * 100,
                    "role": e.role.value,
                }
                for e in plan.elements
            ],
            selected_id=st.session_state.get("studio_selected_element_id"),
        )
        
        if selected_element_id:
            st.session_state["studio_selected_element_id"] = selected_element_id
            st.rerun()
```

**改进点**：
- ✅ 点击画布选择元素
- ✅ 高亮显示选中元素
- ✅ 悬停时显示元素信息
- ✅ 与属性面板联动

### 第三阶段：拖拽调整位置（4-6 周）

**目标**: 拖拽元素改变位置

**技术方案**：扩展自定义组件

```javascript
// components/canvas_editor/frontend/src/CanvasEditor.tsx

const CanvasEditor = ({ imageUrl, elements, onUpdate }) => {
  const [dragging, setDragging] = useState(null);
  
  const handleMouseDown = (elementId, e) => {
    setDragging({
      id: elementId,
      startX: e.clientX,
      startY: e.clientY,
      originalX: elements.find(e => e.id === elementId).x,
      originalY: elements.find(e => e.id === elementId).y,
    });
  };
  
  const handleMouseMove = (e) => {
    if (!dragging) return;
    
    const dx = e.clientX - dragging.startX;
    const dy = e.clientY - dragging.startY;
    
    // 更新元素位置（视觉反馈）
    // 显示辅助线、吸附提示
  };
  
  const handleMouseUp = () => {
    if (!dragging) return;
    
    // 将新位置返回给 Streamlit
    onUpdate({
      elementId: dragging.id,
      x: newX,
      y: newY,
    });
    
    setDragging(null);
  };
  
  return (
    <div 
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* 渲染画布 */}
    </div>
  );
};
```

**后端处理**：
```python
# visual_edit_service.py
def apply_element_position(
    self,
    slide_id: UUID,
    element_id: str,
    x: float,
    y: float,
) -> VisualEditResult:
    """直接更新元素位置（拖拽操作）"""
    plan = self._load_plan(slide)
    element = plan.element_by_id(element_id)
    
    # 检查是否锁定
    assert_element_editable(element, ElementEditOperation.MOVE)
    
    # 更新位置
    updated_element = element.model_copy(update={"x": x, "y": y})
    # ... 保存并返回
```

**改进点**：
- ✅ 拖拽元素调整位置
- ✅ 实时视觉反馈
- ✅ 吸附对齐（可选）
- ✅ 约束边界（不超出页面）
- ✅ 尊重锁定状态

### 第四阶段：尺寸调整和裁切（6-8 周）

**目标**: 拖拽边框调整元素尺寸

**实现**：
```javascript
// 在 CanvasEditor 中添加调整手柄
const ResizeHandles = ({ element, onResize }) => {
  const handles = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
  
  return handles.map(position => (
    <div
      key={position}
      className={`resize-handle handle-${position}`}
      onMouseDown={(e) => handleResizeStart(element.id, position, e)}
    />
  ));
};
```

**改进点**：
- ✅ 八向调整手柄
- ✅ 保持宽高比（可选）
- ✅ 图片裁切框
- ✅ 文字框自动换行

### 第五阶段：文字直接编辑（8-10 周）

**目标**: 双击文字元素进行编辑

**实现**：
```javascript
const TextEditor = ({ element, onUpdate }) => {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(element.text_content);
  
  const handleDoubleClick = () => {
    if (element.role === 'TITLE' || element.role === 'BODY') {
      setEditing(true);
    }
  };
  
  const handleBlur = () => {
    onUpdate({ elementId: element.id, text: content });
    setEditing(false);
  };
  
  return editing ? (
    <textarea value={content} onChange={...} onBlur={handleBlur} />
  ) : (
    <div onDoubleClick={handleDoubleClick}>{content}</div>
  );
};
```

**改进点**：
- ✅ 双击进入编辑模式
- ✅ 实时预览字数/行数
- ✅ 富文本支持（可选）
- ✅ 自动保存

### 第六阶段：完整 WYSIWYG（10-12 周）

**目标**: 成熟的可视化编辑器

**集成功能**：
- ✅ 多选（Shift + Click）
- ✅ 框选（拖拽矩形）
- ✅ 批量操作（对齐、分布、组合）
- ✅ 撤销/重做栈
- ✅ 键盘快捷键（Delete, Ctrl+C/V, 方向键）
- ✅ 辅助线系统
- ✅ 标尺和网格
- ✅ 缩放和平移

## 技术实施建议

### 方案 A：Streamlit 自定义组件（推荐）

**优点**：
- 与现有架构无缝集成
- 可以渐进式增强
- 保持 Streamlit 的简洁性

**缺点**：
- 需要前端开发（React/Vue）
- 组件通信有延迟

**工作量**：
- 基础组件：1-2 周
- 完整编辑器：8-12 周

### 方案 B：嵌入第三方编辑器

**候选**：
- Fabric.js - 画布编辑库
- Konva.js - 2D 画布框架
- Paper.js - 矢量图形编辑

**优点**：
- 功能完整，开箱即用
- 社区支持好

**缺点**：
- 与 LayoutPlan 数据结构需要适配
- 可能过度设计

### 方案 C：混合模式（推荐长期）

**策略**：
```
简单操作 → 命令式编辑（自然语言）
精细调整 → 可视化编辑（拖拽）
批量操作 → 属性面板
```

**优点**：
- 照顾不同用户习惯
- 各司其职，体验最佳

## 实施优先级

### P0 - 立即实施（增强的自然语言解析已完成）
- ✅ 增强的自然语言解析（已完成）
- ⏳ 显示所有元素边界
- ⏳ 元素颜色编码

### P1 - 短期（1-2 个月）
- ⏳ 点击选择元素
- ⏳ 悬停显示信息
- ⏳ 基础拖拽位置

### P2 - 中期（3-4 个月）
- ⏳ 尺寸调整
- ⏳ 文字直接编辑
- ⏳ 吸附对齐

### P3 - 长期（6-12 个月）
- ⏳ 多选和批量操作
- ⏳ 键盘快捷键
- ⏳ 完整 WYSIWYG

## 资源估算

### 第一阶段（增强可见性）
- 开发时间：1-2 周
- 技能要求：Python + HTML/CSS
- 依赖：无

### 第二阶段（点击选择）
- 开发时间：2-3 周
- 技能要求：Python + JavaScript/React
- 依赖：Streamlit Components API

### 第三阶段（拖拽）
- 开发时间：4-6 周
- 技能要求：全栈（Python + React + 画布编程）
- 依赖：自定义组件框架

### 完整 WYSIWYG
- 开发时间：10-12 周
- 技能要求：资深全栈 + 交互设计
- 依赖：可能需要专门的画布库

## 结论

### 当前状态
✅ **已实现**：可靠的工作台，命令式编辑  
❌ **缺失**：直接操作的可视化编辑  
📊 **评估**：符合第一版范围，但不是最终形态

### 下一步行动
1. **立即**：完善元素可见性（1-2 周工作量）
2. **短期**：实现点击选择（2-3 周工作量）
3. **中期**：评估是否需要完整 WYSIWYG（根据用户反馈）

### 权衡建议
- 如果用户主要是**专家**：命令式编辑 + 增强的自然语言已足够
- 如果用户是**设计师**：需要完整的可视化编辑
- 如果是**混合用户**：保持两种模式并存

当前的增强自然语言解析是正确的第一步，它显著提升了命令式编辑的能力。下一步应该根据实际使用反馈决定是否投入资源开发完整的 WYSIWYG 编辑器。

## 元素级评论 → Proposal（已接线）

open-slide 式 Inspector 评论适合 Archium，但应以 Command / Patch / Proposal / QA / Revision 保留可审计性，而不是直接改渲染树。

**已实现（最小闭环）**
- 领域模型 `ElementComment`（`pending → proposed → needs_rebase → accepted|rejected → resolved`）
- 选中 Layout 元素 → 映射 RenderScene `node_id` → 自然语言评论硬绑定
- 作用域 `ElementCommentScope`：默认 `NODE`；可显式扩大为 `NODE_AND_REFERENCES` / `SELECTION` / `REGION` / `SLIDE`（多卡片等齐、重排等）
- 版本钉扎：`scene_revision_id` / `scene_hash` / `node_snapshot_json`；生成提案前若与当前正式 SceneRevision 不一致 → `needs_rebase`（禁止静默应用到新版本）
- `CommentToCommandPlanner` → `ElementEditIntent`（关键词快捷 + Structured Output）→ `StudioCommand` → `SceneChangeProposal` → Before/After
- 元素意图操作：move / resize / align / distribute / replace_asset / rewrite_text / change_style / visibility / lock / reorder
- 提案接受/拒绝后回写评论状态
- Studio AI 工作区：选中 / 多选 / 选区(包围盒) / 整页；Inbox 展示 region bbox 并可「在画布定位」
- 画布非交互评论锚点：pending/proposed/needs_rebase 节点 pin + region 虚线框；Inbox 定位高亮
- `needs_rebase` 节点快照 vs 当前字段 Diff（几何/文本）+ 一键 rebind

**尚未做**
- 独立评论线程 UI / 多评论协作与指派
- 复合几何指令的完整 LLM 规划（关键词仅为高置信快捷路径；其余走 `ElementEditIntent` Structured Output）
- 自由框选 → 独立 region 评论手势（当前：多选包围盒 → `region_bbox`）
- 画布上点击气泡直接开评论（当前仅展示锚点，创建仍走 AI / Inbox）
## 全稿 Theme Token → ThemeChangeProposal（已接线）

open-slide Design Panel 的全稿 Token 调节值得参考，但 Archium **禁止像网页 CSS 一样静默覆盖正式页面**。

**已实现**
- `DeckThemeTokens`：主色 / 强调色 / 背景 / 标题·正文字体 / 标题比例 / 页面密度 / 圆角 / 线宽 / 图片处理 / 图标风格
- `ThemeChangeProposal`：Token → 新 DesignSystem 候选 → 样本页编译 QA → 接受后切换 `ArtDirection.design_system_id`
- 主题模型：`ThemeTokenReference` / `ExplicitStyleValue`；TextNode 带 `color_token`；接受为主题指针切换 + 重解析，**不**为每页写 Theme SceneRevision
- 可解释抽样：封面 / 章节 / 图纸 / 照片证据 / 数据 / 文字密集（缺失则跳过）+ `sample_selection_reason`
- Theme QA：`DRAWING_COLOR_INTEGRITY` / `EVIDENCE_PHOTO_TREATMENT_POLICY` / `CHART_SEMANTIC_COLOR_PROTECTION` / `CITATION_CONTRAST`
- Studio 检查器「风格」页：表单生成提案，Blocker 默认禁止接受
- 图纸 `contain` 不变量：Token 永不把 drawing fit 改成 cover

**尚未做**
- 样本页并排可视化 Before/After 缩略图墙
- 像素级 WYSIWYG Design Panel
- 按章节局部主题（仍是全稿级 DesignSystem）
- Shape/Image 全面 Token 化（当前 Text 已优先）

## 固定画布与容量预算（已接线）

open-slide 把「可用高度 = 页高 − 顶底边距」写进 Agent 规则；Archium 将其升级为 **LayoutPlan 前的机器约束**。

**已实现**
- `SlideCapacityBudget` + 正式状态 `CapacityStatus`：`fits` / `tight` / `overloaded` / `impossible`
- 图纸专用预算：`drawing_min_readable_area` / `caption_required_height` / `legend_required_area` / `annotation_density`（照片不继承图纸地板）
- `SlideCapacityService.estimate`：全部文本路径显式传 `TextStyleToken`（family/size/weight/line_height）+ `box_width` + `language`；记录 `used_real_font_metrics`
- 规则：`TIGHT` 可出候选但必须 QA；`OVERLOADED` 强制适配/拆页并禁缩字；`IMPOSSIBLE` → `CAPACITY.IMPOSSIBLE` BLOCKED（不产出候选）
- `LayoutPlanningService` / `LayoutRepairService` / `suggest_content_adaptations` 已按状态接线
- Studio「内容」页 **固定画布容量** 仪表：`status` / `capacity_ratio` / `overflow_risk` / `recommended_action` + 图纸可读区摘要

**尚未做**
- 按真实分栏几何的更细预算（当前为确定性启发式）
- 容量仪表历史曲线 / 与 Layout 候选并排对比

## TemplateUsageBrief 设计契约（已接线）

Template Induction 物化后写出可读设计契约，并被运行时模块真正消费。

**已实现**
- `TemplateUsageBrief`：Identified + Versioned；品牌 / 标题 / 字体 / 边距 / 密度 / 图片与图纸 / 页码 / 装饰 / 禁用模式
- 双产物：`TemplateUsageBrief.md` + `template_usage_brief.json`；DB 表 `template_usage_briefs`（每次重新归纳插入新版本行）
- `ArtDirection.template_usage_brief_id` + `template_usage_brief_version`：旧汇报钉住当时 Brief，不随最新归纳漂移
- 消费方：`SlideDesignBriefService`、`LayoutPlanningService`、`IconSelectionService`、`ImageTreatmentPlanningService`、`VisualCriticService`、`ThemeProposalService`
- `template_usage_brief_context`：`constraints_from_brief` / `load_brief_for_art_direction` / `bind_brief_to_art_direction`

**尚未做**
- Studio 独立 Brief 版本对比 UI
- Agent Skill 强制把 brief prompt_block 注入所有 LLM 阶段的统一门控

## Agent Skill Runtime Registry（已接线）

`archium-agent-skills/` 不再只是开发者 Markdown：产品运行时会选择、注入 Prompt，并记录版本审计。

**已实现**
- `ArchiumSkillDefinition`：id / version / applicable_stages|slide_types|project_types / required_rules / prompt_uri / checksum
- `SkillRegistry`：从 `archium-agent-skills/*/SKILL.md` 加载正文并计算 checksum
- `SkillSelectionService.resolve_for_task(task_type, slide_type, project_type, audience)`
- `apply_skills_to_request`：注入 system prompt；`LLMRequest.metadata` 写入 `skill_ids` / `skill_versions` / `skill_checksums`
- 已挂钩：ArtDirection、LayoutPlan、Visual QA、ElementEditIntent

**尚未做**
- Workflow Run / SceneRevision 持久化完整 SkillInvocationAudit 表
- Studio UI 显示「本步使用的 Skills」
- 全部 LLM 调用点统一强制走 SkillPromptService
