# 工程预演记录（不能关闭 UI-006）

**Session:** `2026-08-03-playbook-e-1`  
**时间:** 2026-08-03  
**方式:** 浏览器点选 + 服务层命令预演

## 结论摘要

| 步骤 | 浏览器 | 服务层 | 备注 |
|------|--------|--------|------|
| E0 打开 20 页工作室 | Pass | — | 导航 `资料→大纲→生成→工作室→交付` 清晰 |
| E1 选中 | Pass | — | 画布选区 + 助理显示「选中：正文 / 图片·hero」 |
| E2 移动 | Partial | Pass | 服务层 `move_node` 成功；浏览器拖拽未深测 |
| E3 改字/提案 | Partial | Pass | `set_text_runs`→PPTX 含标记；AI「改短标题」未跑通 |
| E4 Undo | — | Pass | 依赖 seed baseline SceneRevision |
| E5 导出 | Partial | Pass | 正式导出曾被资料门禁挡住；绑 stub 后 UI 显示 96/100 可正式导出 |

## 本轮修掉的会前阻塞

1. **资料门禁** — 无 `SourceDocument` 时正式「导出 PPTX」禁用。种子脚本已写 stub PDF；本场项目已绑定。
2. **首次 Undo** — 无 baseline SceneRevision 时第一次编辑不可撤销。种子已写 baseline。
3. **双「汇报」导航** — 已恢复 `生成` / `工作室` 区分。

## 仍留给真人场次

- AI 提案接受路径（E3）
- 画布拖拽几何（E2）的真人手感
- PPT / WPS 打开并再编辑（E5 后半）
- 工程预演 **不能** 将 UI-006 标为 done

## 摩擦（非硬阻塞，记 issues）

- Streamlit 故事线章节按钮易被相邻文本拦截点击
- 进度条仍可能提示「建议先完成大纲」，即使交付已可正式导出

## 证据

- `evidence/browser-rehearsal-service.json`
- `evidence/browser-rehearsal-export.pptx`（本地生成，已 gitignore，勿提交）
- `evidence/E1-canvas-selection.png`
- `evidence/E5-deliver-gate-blocked.png`
