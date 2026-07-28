# Playbook E 补测 — Facilitator 执行单

**Session:** `2026-07-28-playbook-e-2`  
**日期:** 2026-07-28  
**目标:** 关闭 **UI-006** / **ST-007**

---

## 会前检查（已完成 / 待填）

- [x] `python scripts/run_playbook_e_gate.py -q` — **31 passed**（2026-07-28，commit `ed09b05d`）
- [ ] Streamlit 已启动：`archium`（仅一个进程占用 `:8501`）
- [ ] 操作者已就位（**优先非开发**；Developer 跑只能作预演，不能关 UI-006）
- [ ] 本机 PowerPoint 或 WPS 可打开 `.pptx`
- [ ] Node + `archium/infrastructure/renderers/pptxgen` 已 `npm install`

---

## 选项目要求

- 自动生成的汇报，**约 20 页**（非 toy case）
- 侧栏 **制作 → 工作室** 可打开，画布有内容
- 建议：已有真实验证项目（如清凉寺 / 医院 Demo）

记录到 `session-meta.json`：

- `project_id` / `project_name`
- `deck_page_count`
- `worst_slide_id` / `worst_slide_reason`

---

## 逐步执行（E0–E5 + 强制十项）

| 步 | 动作 | 证据 | step log |
|----|------|------|----------|
| E0 | 浏览 ~20 页，操作者选最差页并口述原因 | `evidence/E0-*.png` + notes | pass + 耗时 |
| E1 | 选中单个元素 | `E1-selection-properties.png` | |
| E2 | 移动或缩放 | `E2-geometry-before-after.png` | |
| E3 | **换图 + 改标题 + 接受一次 AI 提案** | 三张截图 | |
| E4 | Undo 一次 | `E4-undo-result.png` | |
| E5 | 重导出 → PowerPoint 打开 → **改字并保存** | `E5-export-success.png` + `E5-ppt-edit-saved.png` | `pptx_edit_verified=Y` |

**红线（任一条 = 本轮失败）：**

- Studio 改动不在 PPTX 中可见（2026-07-27 曾在此失败）
- 接受提案后 live Scene 回滚
- Undo 后无法再导出
- 未捕获 Streamlit 栈 trace

---

## 上次失败教训（2026-07-27-playbook-e-1）

- E3：属性框改标题后，设计助理与导出 PPTX 仍为旧标题
- E5：导出成功但封面无 Studio 改动 → **e_blocker**

**E3 验证要点：** 改标题后，在 **交付** 导出前刷新或切页再回来，确认画布仍显示新标题；导出后用 PowerPoint 打开核对。

---

## 会后 10 分钟

1. 填 `playbook-e-step-log.csv`（含 `step_seconds`、`blocker_tag`、`pptx_edit_verified`）
2. 有问题写入 `playbook-e-issues.csv`（`e_blocker` / `post_e_improvement`）
3. 更新 `session-meta.json` → `overall_pass`
4. 通过则改审计表 UI-006 / ST-007 为 `done`，链到本 session

---

## 启动命令

```powershell
cd c:\Users\navib\Desktop\development\Archium-Agent
.venv\Scripts\Activate.ps1
python scripts/run_playbook_e_gate.py -q
archium
```

参与者说明发给操作者：[`docs/rehearsal/playbook-e-participant-guide.md`](../../playbook-e-participant-guide.md)
