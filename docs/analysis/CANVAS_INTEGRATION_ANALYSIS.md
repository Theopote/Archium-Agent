# 交互式画布集成分析


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 当前状态诊断

### ✅ 已完成的组件开发

**Canvas Editor 自定义组件**（`archium/ui/components/canvas_editor/`）

**功能特性**：
- ✅ 点击选择元素
- ✅ 悬停高亮
- ✅ 元素边界可视化
- ✅ 颜色编码（按元素角色）
- ✅ 元素标签显示
- ✅ 锁定状态图标
- ✅ 响应式布局

**技术栈**：
- React + TypeScript
- Streamlit 自定义组件
- 构建脚本（`build.sh`）

**组件 API**：
```python
clicked_element_id = canvas_editor(
    image_url=preview_path,
    layout_plan=plan,
    selected_element_id=selected_element_id,
    show_labels=True,
    show_all_borders=True,
    key=f"canvas_{slide.id}",
)
```

### ✅ 已完成的集成准备

**Enhanced Canvas 包装器**（`archium/ui/studio/slide_canvas_enhanced.py`）

**关键代码**（第 133-149 行）：
```python
if use_interactive_canvas and plan is not None and preview_path and Path(preview_path).is_file():
    try:
        from archium.ui.components.canvas_editor import canvas_editor
        
        # Render interactive canvas
        clicked_element_id = canvas_editor(
            image_url=preview_path,
            layout_plan=plan,
            selected_element_id=selected_element_id,
            show_labels=True,
            show_all_borders=True,
            key=f"canvas_{slide.id}",
        )
        
        # Update selected element if clicked
        if clicked_element_id != selected_element_id:
            st.session_state["studio_selected_element_id"] = clicked_element_id
```

**函数签名**：
```python
def render_slide_canvas(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    advanced: bool,
    use_interactive_canvas: bool = True,  # ✅ 默认启用
)
```

### ❌ 未完成的 Studio 集成

**当前 Studio 主页面**（`archium/ui/pages/studio.py`）

**问题代码**（第 15 行）：
```python
from archium.ui.studio.slide_canvas import render_slide_canvas  # ❌ 旧版本
```

**调用位置**（第 71 行）：
```python
with center_col:
    render_slide_canvas(slide_snapshot=slide_snapshot, advanced=advanced)
    # ❌ 没有启用 use_interactive_canvas 参数
```

---

## 集成缺失的环节

### 1. Studio 页面未切换到 Enhanced 版本

**当前**：
```python
from archium.ui.studio.slide_canvas import render_slide_canvas
```

**应该**：
```python
from archium.ui.studio.slide_canvas_enhanced import render_slide_canvas
```

### 2. 缺少完整的交互流程

**已实现**：
- ✅ 点击元素 → 更新 `st.session_state["studio_selected_element_id"]`

**缺失**：
- ❌ 右侧属性面板同步显示选中元素的属性
- ❌ 修改元素属性后保存到 LayoutPlan
- ❌ 保存后触发验证
- ❌ 验证通过后更新预览
- ❌ 记录修改历史（Revision）
- ❌ Undo/Redo 功能

### 3. 组件可能未构建

**需要验证**：
```bash
ls archium/ui/components/canvas_editor/frontend/build/
```

如果不存在，需要运行：
```bash
cd archium/ui/components/canvas_editor
bash build.sh
```

---

## 完整的交互流程设计

### 理想的用户体验

```
用户操作流程：
1. 打开 Studio
2. 选择页面
3. 在画布上点击元素（例如：标题）
   ↓
4. 右侧属性面板自动显示该元素的属性
   - 位置（x, y, width, height）
   - 文字内容
   - 字体大小
   - 颜色
   - 锁定状态
   ↓
5. 修改属性（例如：调整位置）
   ↓
6. 点击"保存"按钮
   ↓
7. 系统保存 LayoutPlan
   ↓
8. 触发验证
   ↓
9. 更新预览图
   ↓
10. 记录到修改历史
```

### 需要实现的功能模块

#### 模块 1：右侧属性面板同步 ✅ 部分存在

**文件**：`archium/ui/studio/slide_properties.py`

**需要增强**：
- 检查是否读取 `st.session_state["studio_selected_element_id"]`
- 如果有选中元素，显示该元素的详细属性
- 提供编辑表单

#### 模块 2：元素属性编辑器 ❌ 需要创建

**新文件**：`archium/ui/studio/element_editor.py`

**功能**：
```python
def render_element_editor(
    layout_plan: LayoutPlan,
    element_id: str,
    slide_id: UUID,
) -> None:
    """渲染选中元素的编辑器"""
    element = layout_plan.get_element_by_id(element_id)
    
    # 位置和尺寸
    st.number_input("X 坐标", value=element.x)
    st.number_input("Y 坐标", value=element.y)
    st.number_input("宽度", value=element.width)
    st.number_input("高度", value=element.height)
    
    # 文字内容
    if element.text_content:
        st.text_area("文字内容", value=element.text_content)
    
    # 锁定状态
    st.checkbox("锁定位置", value=element.locked)
    
    # 保存按钮
    if st.button("保存修改"):
        save_element_changes(layout_plan, element_id, ...)
```

#### 模块 3：LayoutPlan 保存服务 ❌ 需要实现

**新文件**：`archium/application/visual/layout_edit_service.py`

**功能**：
```python
class LayoutEditService:
    def update_element_position(
        self,
        layout_plan_id: UUID,
        element_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> LayoutPlan:
        """更新元素位置并保存"""
        # 1. 加载 LayoutPlan
        plan = self._layout_repo.get(layout_plan_id)
        
        # 2. 更新元素
        element = plan.get_element_by_id(element_id)
        element.x = x
        element.y = y
        element.width = width
        element.height = height
        
        # 3. 验证修改后的 LayoutPlan
        validation = self._validation.validate(plan, design_system)
        
        # 4. 保存
        updated_plan = self._layout_repo.save(plan)
        
        # 5. 记录修改历史
        self._create_revision(plan, "手动调整元素位置")
        
        return updated_plan
    
    def update_element_content(
        self,
        layout_plan_id: UUID,
        element_id: str,
        text_content: str,
    ) -> LayoutPlan:
        """更新元素文字内容"""
        # 类似实现
```

#### 模块 4：预览更新 ❌ 需要实现

**功能**：
- 保存 LayoutPlan 后，重新生成线框预览
- 或者重新渲染 PPTX 并截图

#### 模块 5：修改历史 ⚠️ 可能已存在

**文件**：`archium/ui/studio/history_panel.py`

**需要验证**：
- 是否记录手动编辑的修改
- 是否支持 Undo/Redo

---

## 集成实施计划

### Phase 1：基础集成（P0）

**目标**：让交互式画布显示在 Studio 中

**步骤**：

1. **构建 Canvas Editor 组件**
   ```bash
   cd archium/ui/components/canvas_editor
   bash build.sh
   ```
   验证：检查 `frontend/build/` 目录是否存在

2. **切换 Studio 到 Enhanced Canvas**
   
   修改 `archium/ui/pages/studio.py`：
   ```python
   # 第 15 行
   - from archium.ui.studio.slide_canvas import render_slide_canvas
   + from archium.ui.studio.slide_canvas_enhanced import render_slide_canvas
   
   # 第 71 行
   - render_slide_canvas(slide_snapshot=slide_snapshot, advanced=advanced)
   + render_slide_canvas(
   +     slide_snapshot=slide_snapshot,
   +     advanced=advanced,
   +     use_interactive_canvas=True,
   + )
   ```

3. **测试基础交互**
   - 启动 Studio
   - 点击画布上的元素
   - 验证 `st.session_state["studio_selected_element_id"]` 是否更新

**预期结果**：
- ✅ 画布可以点击选择元素
- ✅ 悬停高亮生效
- ✅ 元素边界显示

### Phase 2：属性面板同步（P1）

**目标**：右侧属性面板显示选中元素的详细信息

**步骤**：

1. **检查 `slide_properties.py` 当前实现**
   ```bash
   grep -n "studio_selected_element_id" archium/ui/studio/slide_properties.py
   ```

2. **增强属性面板**
   
   在 `slide_properties.py` 中添加：
   ```python
   def render_slide_properties(...):
       # 现有代码
       
       # 新增：选中元素属性
       selected_element_id = st.session_state.get("studio_selected_element_id")
       if selected_element_id and slide_snapshot.layout_plan:
           st.markdown("---")
           st.markdown("### 选中元素")
           render_selected_element_properties(
               slide_snapshot.layout_plan,
               selected_element_id,
           )
   ```

3. **创建元素属性查看器**
   ```python
   def render_selected_element_properties(
       layout_plan: LayoutPlan,
       element_id: str,
   ) -> None:
       element = layout_plan.get_element_by_id(element_id)
       if element is None:
           st.warning(f"元素 {element_id} 不存在")
           return
       
       st.markdown(f"**{element.role.value}** · `{element.id}`")
       st.caption(f"位置：({element.x:.2f}, {element.y:.2f})")
       st.caption(f"尺寸：{element.width:.2f} × {element.height:.2f}")
       
       if element.text_content:
           st.text_area("文字内容", value=element.text_content, disabled=True)
       
       if element.locked:
           st.info("🔒 此元素已锁定")
   ```

**预期结果**：
- ✅ 点击元素后，右侧显示元素详细信息

### Phase 3：元素编辑器（P2）

**目标**：允许用户修改元素属性并保存

**步骤**：

1. **创建 `element_editor.py`**
   - 表单输入：位置、尺寸、文字内容
   - 保存按钮

2. **创建 `LayoutEditService`**
   - 更新元素属性
   - 验证修改
   - 保存 LayoutPlan
   - 记录修改历史

3. **集成到属性面板**
   ```python
   if st.button("编辑元素"):
       render_element_editor(layout_plan, selected_element_id, slide.id)
   ```

**预期结果**：
- ✅ 可以修改元素属性
- ✅ 保存后更新 LayoutPlan

### Phase 4：预览更新和历史记录（P3）

**目标**：完整的编辑 → 保存 → 验证 → 预览流程

**步骤**：

1. **保存后重新验证**
   ```python
   updated_plan = layout_edit_service.update_element(...)
   validation = validation_service.validate(updated_plan, design_system)
   ```

2. **更新预览**
   - 重新生成线框预览
   - 或触发 PPTX 重新渲染

3. **记录修改历史**
   - 保存 Revision
   - 更新 History Panel

**预期结果**：
- ✅ 修改后验证通过
- ✅ 预览实时更新
- ✅ 修改历史可追溯

---

## 风险和注意事项

### 技术风险

1. **组件未构建**
   - 风险：`frontend/build/` 不存在导致组件无法加载
   - 缓解：先运行 `build.sh`

2. **LayoutPlan 可变性**
   - 风险：LayoutPlan 可能是不可变对象
   - 缓解：检查是否支持修改，可能需要创建新版本

3. **预览更新性能**
   - 风险：每次修改都重新渲染 PPTX 太慢
   - 缓解：只更新线框预览，PPTX 导出由用户手动触发

### 用户体验风险

1. **频繁的 Streamlit 重新运行**
   - 风险：每次点击都会重新运行整个页面
   - 缓解：使用 `st.session_state` 保持状态

2. **没有 Undo/Redo**
   - 风险：用户误操作无法撤销
   - 缓解：Phase 4 实现修改历史和回滚

---

## 验收标准

### Phase 1（基础集成）

- [ ] Canvas Editor 组件已构建
- [ ] Studio 页面加载时显示交互式画布
- [ ] 可以点击元素，元素高亮显示
- [ ] `st.session_state["studio_selected_element_id"]` 正确更新

### Phase 2（属性面板同步）

- [ ] 点击元素后，右侧属性面板显示元素详细信息
- [ ] 显示：位置、尺寸、文字内容、锁定状态
- [ ] 切换选择时，属性面板实时更新

### Phase 3（元素编辑器）

- [ ] 可以修改元素位置和尺寸
- [ ] 可以修改文字内容
- [ ] 点击"保存"后，LayoutPlan 更新成功
- [ ] 保存后触发验证

### Phase 4（完整流程）

- [ ] 保存后预览实时更新
- [ ] 修改记录在历史面板中
- [ ] 可以查看和回滚历史版本
- [ ] 验证错误正确显示

### 完整端到端验证

**用户流程**：
```
1. 打开 Studio ✅
2. 选择页面 ✅
3. 点击画布上的标题元素 ✅
4. 右侧显示标题元素的属性 ✅
5. 修改标题位置（Y 坐标 +0.5） ✅
6. 点击"保存修改" ✅
7. 系统保存 LayoutPlan ✅
8. 触发验证并显示结果 ✅
9. 预览更新，标题位置下移 ✅
10. 历史面板显示"手动调整标题位置" ✅
```

---

## 当前判定

| 项目 | 状态 | 说明 |
|------|------|------|
| Canvas 自定义组件 | ✅ 已完成 | React/TypeScript 实现完整 |
| Canvas Enhanced 包装器 | ✅ 已完成 | Python 包装器已实现 |
| Studio 集成 | ❌ **未完成** | **仍使用旧版 canvas** |
| 属性面板同步 | ❌ 未完成 | 未读取选中元素 |
| 元素编辑器 | ❌ 未完成 | 不存在 |
| LayoutPlan 保存 | ❌ 未完成 | 没有编辑服务 |
| 预览更新 | ❌ 未完成 | 没有自动刷新 |
| 修改历史 | ❌ 未验证 | 可能存在但未测试 |
| **整体可用性** | ❌ **未通过** | **组件未接入主界面** |

---

## 推荐行动

### 立即（今天）

1. **验证组件是否已构建**
   ```bash
   ls -la archium/ui/components/canvas_editor/frontend/build/
   ```
   
2. **如果未构建，执行构建**
   ```bash
   cd archium/ui/components/canvas_editor
   bash build.sh
   ```

3. **执行 Phase 1：基础集成**
   - 修改 `studio.py`（2 行代码）
   - 测试交互式画布是否显示

### 本周

4. **执行 Phase 2：属性面板同步**
   - 增强 `slide_properties.py`
   - 创建元素属性查看器

5. **测试端到端用户体验**
   - 点击 → 选中 → 属性显示

### 本月

6. **执行 Phase 3 & 4**
   - 创建元素编辑器
   - 实现 LayoutEditService
   - 完整的编辑流程

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)  
状态：分析完成，待集成
