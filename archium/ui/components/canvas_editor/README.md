# Canvas Editor Component

交互式画布编辑器组件，用于 Archium Studio 的可视化幻灯片编辑。

## 功能特性

### ✅ 已实现
- **点击选择元素** - 点击画布上的元素进行选择
- **悬停高亮** - 鼠标悬停时高亮显示元素边界
- **元素边界可视化** - 显示所有元素的边界框
- **颜色编码** - 根据元素类型使用不同颜色
- **元素标签** - 显示元素角色和 ID
- **锁定状态** - 显示锁定元素的图标
- **响应式布局** - 自适应容器尺寸

### 元素类型颜色

| 角色 | 颜色 | 说明 |
|------|------|------|
| HERO_VISUAL | 蓝色 (#175cd3) | 主视觉元素 |
| TITLE | 绿色 (#12b76a) | 标题 |
| BODY | 灰色 (#667085) | 正文 |
| CAPTION | 紫色 (#7a5af8) | 说明文字 |
| DECORATION | 橙色 (#f79009) | 装饰元素 |

## 安装

### 1. 构建组件（生产模式必需）

生产模式（默认）使用 `frontend/build/` 中的静态资源。仓库不包含构建产物，克隆后需先构建：

```bash
# 推荐：项目根目录
archium-build-canvas

# 或
cd archium/ui/components/canvas_editor
bash build.sh
```

构建成功后会生成 `frontend/build/index.html`。若未构建，Studio 会自动降级为静态预览/线框，并提示运行上述命令。

### 2. 开发模式（可选）

设置环境变量 `ARCHIUM_CANVAS_EDITOR_DEV=1` 后，组件会连接 React 开发服务器（默认 `http://localhost:3000`）：

```bash
export ARCHIUM_CANVAS_EDITOR_DEV=1
cd frontend
npm install
npm start
```

也可通过 `ARCHIUM_CANVAS_EDITOR_DEV_URL` 覆盖 dev server 地址。

## 使用方法

### 基础用法

```python
import streamlit as st
from archium.ui.components.canvas_editor import canvas_editor
from archium.domain.visual.layout import LayoutPlan

# 假设你有一个 LayoutPlan 和预览图片
layout_plan = ...  # 你的 LayoutPlan 对象
image_url = "path/to/preview.png"

# 渲染交互式画布
selected_element_id = canvas_editor(
    image_url=image_url,
    layout_plan=layout_plan,
    selected_element_id=st.session_state.get("selected_element"),
    show_labels=True,
    show_all_borders=True,
)

# 处理选择变化
if selected_element_id != st.session_state.get("selected_element"):
    st.session_state["selected_element"] = selected_element_id
    st.rerun()
```

### 集成到 Studio

```python
from archium.ui.studio.slide_canvas_enhanced import render_slide_canvas

# 在 Studio UI 中使用
render_slide_canvas(
    slide_snapshot=current_slide_snapshot,
    advanced=advanced_mode,
    use_interactive_canvas=True,  # 启用交互式画布
)
```

### 参数说明

#### `canvas_editor()`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `image_url` | `str` | 必需 | 预览图片的 URL 或路径 |
| `layout_plan` | `LayoutPlan` | 必需 | 包含元素位置的布局计划 |
| `selected_element_id` | `str \| None` | `None` | 当前选中的元素 ID |
| `show_labels` | `bool` | `True` | 悬停/选中时显示元素标签 |
| `show_all_borders` | `bool` | `True` | 显示所有元素边界（否则仅显示选中/悬停） |
| `key` | `str \| None` | `None` | Streamlit 组件唯一键 |

**返回值**: 被点击的元素 ID（`str`），或 `None` 如果点击了空白区域。

## 架构

### 组件结构

```
canvas_editor/
├── __init__.py              # Python 包装器
├── build.sh                 # 构建脚本
└── frontend/
    ├── package.json         # NPM 配置
    ├── tsconfig.json        # TypeScript 配置
    ├── public/
    │   └── index.html       # HTML 模板
    ├── src/
    │   ├── index.tsx        # 入口文件
    │   └── CanvasEditor.tsx # 主组件
    └── build/               # 构建输出（生成）
```

### 数据流

```
Python (Streamlit)
    ↓ [传递]
    - image_url
    - elements (从 LayoutPlan 转换)
    - selectedId
    - 配置选项
    ↓
React Component
    ↓ [渲染]
    - 显示图片
    - 绘制元素边界
    - 监听用户交互
    ↓ [用户点击]
    ↓
Streamlit.setComponentValue(elementId)
    ↓
Python 接收返回值
    ↓
更新 session_state
    ↓
重新渲染
```

### 坐标转换

```python
# LayoutPlan 使用绝对坐标（英寸）
element.x = 1.5  # 1.5 英寸
element.width = 8.0  # 8.0 英寸

# 组件使用相对坐标（百分比）
element_percent = {
    "x": (element.x / page_width) * 100,  # 转换为 %
    "width": (element.width / page_width) * 100,
}
```

## 交互行为

### 点击选择
- 点击元素边界框 → 选中该元素
- 点击空白区域 → 取消选择（返回 `None`）
- 选中的元素显示蓝色粗边框

### 悬停高亮
- 鼠标悬停 → 边框加粗，背景加深
- 显示元素标签（角色 + ID）
- 锁定元素显示锁图标 🔒

### 视觉反馈
- 选中元素：蓝色粗边框（3px）
- 悬停元素：加粗边框（2px）+ 加深背景
- 普通元素：细边框（2px）+ 浅背景
- 锁定元素：鼠标显示禁止图标

## 开发指南

### 修改前端组件

1. 编辑 `frontend/src/CanvasEditor.tsx`
2. 在开发模式下测试：
   ```bash
   cd frontend
   npm start
   ```
3. 在 `__init__.py` 中设置 `_RELEASE = False`
4. Streamlit 会连接到 `localhost:3000`

### 构建生产版本

```bash
cd archium/ui/components/canvas_editor
bash build.sh
```

在 `__init__.py` 中设置 `_RELEASE = True`

### 添加新功能

要添加新的交互功能（如拖拽），需要：

1. **前端**：在 `CanvasEditor.tsx` 中添加事件处理
   ```typescript
   const handleMouseDown = (elementId: string) => {
       // 处理拖拽开始
   };
   ```

2. **数据传递**：使用 `Streamlit.setComponentValue()`
   ```typescript
   Streamlit.setComponentValue({
       type: "drag",
       elementId: "hero",
       x: 50,
       y: 30,
   });
   ```

3. **后端**：在 Python 中处理返回值
   ```python
   result = canvas_editor(...)
   if isinstance(result, dict) and result.get("type") == "drag":
       # 处理拖拽事件
   ```

## 故障排除

### 组件无法加载

**问题**: 显示 "Component not found" 错误

**解决**:
1. 确保已运行构建脚本：`bash build.sh`
2. 检查 `frontend/build` 目录是否存在
3. 确认 `__init__.py` 中 `_RELEASE = True`

### 选择不响应

**问题**: 点击元素没有反应

**解决**:
1. 检查 `layout_plan` 是否为 `None`
2. 确认元素有有效的坐标（非负数）
3. 查看浏览器控制台的 JavaScript 错误

### 显示不正确

**问题**: 元素边界框位置错误

**解决**:
1. 检查 `page_width` 和 `page_height` 是否正确
2. 确认图片宽高比为 16:9
3. 验证坐标转换逻辑

### 开发模式连接失败

**问题**: 无法连接到 `localhost:3000`

**解决**:
1. 确保 React 开发服务器正在运行：`npm start`
2. 检查端口 3000 是否被占用
3. 尝试使用不同端口并更新 `__init__.py`

## 性能优化

### 渲染优化
- 使用 CSS `transform` 而非 `top/left` 动画
- 限制同时显示的元素数量（< 50）
- 避免在 `onMouseMove` 中进行复杂计算

### 内存优化
- 及时清理事件监听器
- 使用 `React.memo` 优化组件重渲染
- 控制 Streamlit 重渲染频率

## 未来改进

### 短期（1-2 周）
- [ ] 添加键盘快捷键（Delete, Esc）
- [ ] 显示元素尺寸信息
- [ ] 添加缩放控制

### 中期（1-2 月）
- [ ] 拖拽调整位置
- [ ] 调整元素尺寸
- [x] 多选支持（Shift 多选与框选）

### 长期（3-6 月）
- [ ] 撤销/重做
- [ ] 对齐辅助线
- [ ] 吸附网格
- [ ] 复制粘贴

## 许可证

本组件是 Archium Agent 项目的一部分。

## 相关文档

- [STUDIO_INTERACTION_ROADMAP.md](../../../STUDIO_INTERACTION_ROADMAP.md) - 完整的交互改进路线图
- [Streamlit Components API](https://docs.streamlit.io/library/components/components-api) - Streamlit 组件开发文档
