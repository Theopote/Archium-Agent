# 视觉设计用户指南

> **日常编辑推荐先用 [汇报工作室用户指南](../studio-user-guide.md)**：三栏浏览、NL 视觉编辑、内容适配与 PPTX 导出均在一页完成。本页面向需要审核 **视觉方向** 或在 **多个候选版式** 间挑选的场景。

在 Streamlit 侧栏打开 **视觉设计**（路径 `visual-design`）。

## 前置条件

1. 已有项目，并在**项目工作台**生成过 Brief / Storyline / SlideSpec。
2. （可选）配置 LLM API Key；未配置时使用规则生成，仍可完成编排。
3. 导出原生 PPTX 需已安装 Node.js，并在 `archium/infrastructure/renderers/pptxgen` 运行过 `npm install`。

## 推荐流程

1. 选择项目与汇报。
2. 设置偏好（密度、强调、正式度、留白、图纸显示、汇报情境等）。
3. 勾选是否需要 **ArtDirection 审核门**、是否用 LLM、是否导出 PPTX、候选数量。
4. 点击 **生成视觉编排**。
5. 在三个 Tab 中审核与调整：
   - **视觉方向**：编辑策略、批准、或「批准并继续工作流」
   - **单页视觉**：查看 VisualIntent / LayoutPlan、选择候选、一键预设重排
   - **预览与产物**：版式概览与输出文件路径

## 审核门

默认开启：生成 ArtDirection 后工作流暂停。

- **批准视觉方向**：仅批准，不自动续跑
- **批准并继续工作流**：批准并恢复后续意图 / 版式 / 渲染
- **根据反馈重新生成**：写入反馈后重生 ArtDirection

关闭审核门时，流程会一次跑完到 finalize。

## 单页预设

| 按钮 | 效果（意图层） |
|------|----------------|
| 减少文字 | 降低密度，强调主信息 |
| 放大主图 | 疏朗密度 + 放大主图策略 |
| 增加留白 | 疏朗密度 |
| 切换到图纸优先 | 偏好 `drawing_focus`，图纸 contain |

预设会更新 VisualIntent 并重新生成候选 LayoutPlan，**不会**在 UI 里手写坐标。

## 与工作台的关系

工作台负责内容：Brief → Storyline → SlideSpec。  
视觉设计负责看见：ArtDirection → Intent → LayoutPlan → PPTX。

生成 SlideSpec 后，工作台「生成汇报」区会提示前往视觉设计。

## 常见问题

**只有 JSON 没有 PPTX？**  
勾选导出 PPTX，并确认 PptxGenJS 依赖已安装；失败时警告会出现在结果摘要，不阻断 layout instructions。

**图纸被裁切？**  
`drawing_focus` 与图纸元素默认 forbid crop；若仍异常，检查资产路径是否解析成功（缺图会显示占位框）。

**想换版式但不想重跑整套？**  
在「单页视觉」选候选或点预设重排即可。
