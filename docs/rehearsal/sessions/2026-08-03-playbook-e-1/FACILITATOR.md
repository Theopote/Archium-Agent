# Playbook E — Facilitator 执行单

**Session:** `2026-08-03-playbook-e-1`  
**日期:** 2026-08-03  
**状态:** `ready_for_operator`  
**目标:** 关闭 **UI-006** / **ST-007**

---

## 会前检查

- [x] `python scripts/run_playbook_e_gate.py -q` — **31 passed**（commit `d4b65c68`）
- [x] 导航无歧义：`资料 → 大纲 → 生成 → 工作室 → 交付`
- [x] FontSize / 模板导入可启动
- [x] pptxgen `node_modules` 已就绪（Node v22）
- [x] Streamlit 已用当前 venv 启动于 `:8501`
- [x] 工程预演 `evidence/run_e_dry_run.py`：**set_text → Scene → PPTX 含标记 → Undo** 全绿
- [x] 种子脚本写入 **baseline SceneRevision**（修复首次编辑无法 Undo）
- [x] 已绑定资料 stub（解锁正式「导出 PPTX」；交付页曾见 96/100 可正式导出）
- [x] 浏览器工程预演见 `ENGINEER_REHEARSAL.md`（E0/E1 通过；E2–E5 服务层通过；**不能关 UI-006**）
- [ ] 操作者已就位（**优先非开发**；Developer 预演不能关 UI-006）
- [ ] 本机 PowerPoint 或 WPS 可打开 `.pptx`

---

## 选项目（用这一份，勿用旧 seed）

- **项目名：** `Playbook E · Architectural Benchmark`
- `project_id`: `7ad9c03b-bf46-43ff-a30b-7917099f8434`
- `presentation_id`: `fd7cde92-3f53-4902-a001-06c67f61a8c2`
- `deck_page_count`: **20**

路径：侧栏 **切换项目** → 选上述项目 → **制作 → 工作室**

若本地库被清，重新灌入：

```powershell
python scripts/seed_playbook_e_benchmark_deck.py --count 20 --session 2026-08-03-playbook-e-1
```

（会生成新的 project/presentation id，并写回 `session-meta.json`。）

---

## 逐步执行（E0–E5 + 强制覆盖）

| 步 | 动作 | 证据 | step log |
|----|------|------|----------|
| E0 | 浏览 ~20 页，操作者选最差页并口述原因 | `evidence/E0-*.png` + notes | pass + 耗时 |
| E1 | 选中单个元素 | `E1-selection-properties.png` | |
| E2 | 移动或缩放 | `E2-geometry-before-after.png` | |
| E3 | **换图 + 改标题 + 接受一次 AI 提案** | 三张截图 | |
| E4 | Undo 一次 | `E4-undo-result.png` | |
| E5 | 重导出 → PowerPoint 打开 → **改字并保存** | `E5-export-success.png` + `E5-ppt-edit-saved.png` | `pptx_edit_verified=Y` |

**红线（任一条 = 本轮失败）：**

- Studio 改动不在 PPTX 中可见
- 接受提案后 live Scene 回滚
- Undo 后无法再导出
- 未捕获 Streamlit 栈 trace

---

## 工程预演结论（不能替代真人）

- 命令层改标题后，PPTX **含**标记文案（相对 2026-07-27 E5 失败已改善）
- 首次 Undo 可用（`undo_steps_before=1`），因种子写入 baseline revision
- AI 提案路径、浏览器点选、PPT 内再编辑 **未** 覆盖 → 仍须真人 E3/E5

---

## 上次失败教训（2026-07-27-playbook-e-1）

- E3：属性框改标题后，设计助理与导出 PPTX 仍为旧标题
- E5：导出成功但封面无 Studio 改动 → **e_blocker**

**E3 验证要点：** 改标题后，导出前切页再回来确认画布仍是新标题；导出后用 PowerPoint 打开核对。

---

## 会后 10 分钟

1. 填 `playbook-e-step-log.csv`
2. 问题写入 `playbook-e-issues.csv`
3. 更新 `session-meta.json` → `overall_pass`
4. 通过则改审计表 UI-006 / ST-007 为 `done`

---

## 启动

浏览器打开：http://localhost:8501  

若需重启：

```powershell
cd c:\Users\navib\Desktop\development\Archium-Agent
.venv\Scripts\Activate.ps1
archium
```

参与者说明：[`docs/rehearsal/playbook-e-participant-guide.md`](../../playbook-e-participant-guide.md)
