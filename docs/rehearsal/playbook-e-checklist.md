# Playbook E — Studio 修改闭环人工走查清单

> **用途：** Human-in-the-loop Studio 验收（选中 → 改 → Undo → 导出）。  
> **不可替代：** `python scripts/run_playbook_e_gate.py` 只证明服务/命令层；**E1–E5 必须至少一次真人浏览器点选**。  
> **关联：** [user-task-playbooks.md § 剧本 E](../user-task-playbooks.md) · 审计 **UI-006** / **ST-007**  
> **产品化意义：** 关此门之前，不得宣称「Studio 可用」或「Archium 已是产品」。

---

## 何时必须做

| 场景 | 要求 |
|------|------|
| Studio / 画布 / 提案 / Undo 大改 | E 自动化绿 + **一次**真人 E1–E5 |
| 内部 Preview（演示「能改能导出」） | E1–E5 走通 |
| 对外试用 / Showcase | E1–E5 有日期与操作者；无 open `e_blocker` |
| 仅跑自动化 | **不能**关闭 UI-006 |

---

## Session 信息（会前填写）

| 项 | 值 |
|----|-----|
| session_id | `YYYY-MM-DD-playbook-e-N` |
| 日期 / 时长 | |
| 操作者（建议非开发） | |
| Facilitator | |
| LLM 已配置 | 是 / 否（E3 提案路径需要；双击改字可不依赖） |
| PPTX 导出就绪 | Node + `pptxgen` `npm install`：是 / 否 |
| 自动化门禁已通过 | `run_playbook_e_gate.py` 日期：____ |
| 项目 | 建议：已有 **≥3 页且含 RenderScene** 的汇报（如清凉寺验证稿，或医院 Demo） |

**禁止范围（本场会）：** 不新增 Agent、不改导航 IA、不顺手「优化」生成页——问题进 `playbook-e-issues.csv`。

## 本轮强制覆盖（UI-006 / ST-007 关闭前）

- [ ] 使用自动生成的**约 20 页**汇报（记录 deck id / 页数）
- [ ] 由操作者指出“视觉最差的一页”（记录 slide id + 口述原因）
- [ ] 替换图片（该页）
- [ ] 修改标题（该页）
- [ ] 接受一次 AI 修改提案（该页）
- [ ] 执行一次 Undo
- [ ] 调整至少一个元素位置或尺寸
- [ ] 重新导出 PPTX
- [ ] 在 PowerPoint/WPS 打开并继续编辑一次（文字改动并保存）
- [ ] 记录全过程总时长、步骤耗时与卡点（写入 step log + session-meta）

---

## 会前 15 分钟（Facilitator）

```powershell
cd <项目根目录>
.venv\Scripts\Activate.ps1
python scripts/run_playbook_e_gate.py -q
python scripts/new_playbook_e_session.py YYYY-MM-DD-playbook-e-1
archium
```

- [ ] Streamlit 启动无报错；**仅一个**进程占用 `:8501`
- [ ] `run_playbook_e_gate.py` 全绿（或已知 flaky 已记 triage）
- [ ] 已创建 `docs/rehearsal/sessions/<session_id>/`
- [ ] 选好一个「工作室可打开」的项目：侧栏显示生成页数 > 0；进入工作室有画布
- [ ] 已分享 [playbook-e-participant-guide.md](playbook-e-participant-guide.md) 给操作者
- [ ] **告知操作者：** 按清单自己点 UI；你只记通过/失败与截图路径

---

## 逐步走查（E1–E5）

每步在 `playbook-e-step-log.csv` 至少记录：`pass`（Y/N/Partial）、`step_seconds`、`blocker_tag`、`pptx_edit_verified`、`notes`、`evidence_path`。

### E1 — 选中单个元素

| | |
|---|---|
| **页面** | 制作 → **工作室** |
| **操作** | 打开有版式的一页；在画布上点击一个文字或图片元素 |
| **通过** | 右侧 **属性** 反映当前选区（名称/角色/几何可见） |
| **通过** | 预览区对当前选中有可见反馈（高亮或标注） |
| **失败信号** | 点选无反应；属性仍显示上一页/空选；双 key 选区不同步导致「点了 A 改 B」 |
| **证据** | 画布 + 属性面板同屏截图 |

- [ ] E1 通过

### E2 — 移动 / 缩放

| | |
|---|---|
| **页面** | 工作室（同一页） |
| **操作** | 拖移元素，或用属性/手柄调整宽高（任选一种真实交互） |
| **通过** | 几何变化写入 Scene（刷新/重进页后仍在） |
| **通过** | 主画布预览与属性中的尺寸/位置一致 |
| **失败信号** | 一刷新回到旧位置；改了属性但画布不变；静默失败无提示 |
| **证据** | 修改前后对比截图（或属性数值前后） |

- [ ] E2 通过

### E3 — 换图或改文字

| | |
|---|---|
| **页面** | 工作室 |
| **操作（二选一即可）** | **A** 双击文字直接改字并确认；或 **B**「修改」Tab 生成提案 → 接受；或 **C** 属性区换图（若该元素支持） |
| **通过** | 画布显示新内容；修订/提案历史有记录（至少一条） |
| **通过** | 有 Scene 时：视觉写入走提案确认，或画布几何命令——**不**出现「旁路直写导致状态分叉」的困惑 |
| **失败信号** | 接受提案后画布回滚；改字丢失；崩溃栈裸露 |
| **证据** | 修改后画布截图 +（若有）提案 Before/After |

- [ ] E3 通过

### E4 — Undo

| | |
|---|---|
| **页面** | 工作室 |
| **操作** | 对 E2 或 E3 的改动执行 **撤销**（工具栏「撤销视觉」或「撤销内容」，与改动类型一致） |
| **通过** | 回到上一修订；画布与属性一致 |
| **通过** | 无脏数据：再导出或切换页不会「半新半旧」 |
| **失败信号** | Undo 无效；Undo 后空白页；Undo 错页 |
| **证据** | Undo 后画布截图 |

- [ ] E4 通过

### E5 — 导出 PPTX

| | |
|---|---|
| **页面** | 工作室导出入口 **或** **交付** |
| **操作** | 导出可编辑 PPTX；用本机 PowerPoint / WPS 打开 |
| **通过** | 文件可打开；**至少一处** E3（或未 Undo 的 E2）改动在文件中可见 |
| **通过** | 与画布大体一致（允许字体回退等已知差异，须记 notes） |
| **失败信号** | 导出失败无可读错误；打开空白/旧稿；改动只在预览不在 PPTX |
| **证据** | PPTX 文件名 + 打开后一页截图（脱敏） |

- [ ] E5 通过

---

## 产品红线（任一条即 E 未通过）

- [ ] 选中与属性长期不同步（改错对象）
- [ ] 接受提案后 live Scene 被回滚
- [ ] Undo 后无法再导出或 Scene 损坏
- [ ] 导出与画布明显两套内容且无说明
- [ ] 操作中出现未捕获的 Streamlit 栈 trace

---

## 会中禁忌

- Facilitator 不要替操作者完成 E2–E5（可帮启动与选项目）
- 不要会中改代码；问题写入 `playbook-e-issues.csv`
- 不要把含甲方敏感信息的截图 commit 进仓库

---

## 会后 10 分钟

- [ ] `playbook-e-step-log.csv` 中 E1–E5 均为 `Y`（或 Waive 有 Owner + 补测日期）
- [ ] `playbook-e-step-log.csv` 明确记录上述“本轮强制覆盖”十项动作（含耗时）
- [ ] `playbook-e-issues.csv` 中 critical/high 已分级
- [ ] `session-meta.json` → `"overall_pass": true` 或 `"status": "failed"` + blockers
- [ ] 发版检查表勾选：「剧本 E 通过」并写操作者/日期
- [ ] 若通过：将 `docs/audit/module-audit/13-ui.md` **UI-006**、`10-studio.md` **ST-007** 改为 done，并链到本 session 路径

---

## 问题分级（记入 playbook-e-issues.csv）

| 档位 | 含义 |
|------|------|
| **e_blocker** | Studio 修改闭环走不通；不修不能宣称 HITL / 产品化 |
| **post_e_improvement** | 能走通但交互/文案令人困惑 |
| **future_idea** | 增强项（如更强对齐工具），不挡 Preview |

---

## 通过线（UI-006 关闭条件）

- [ ] E1–E5 全部 **Y**
- [ ] “本轮强制覆盖”十项动作全部完成，且有证据路径
- [ ] 无 open 的 **e_blocker**
- [ ] `run_playbook_e_gate.py` 与会话同日或更近的 commit 上为绿
- [ ] 至少 **1 名操作者** 完成（优先非开发）；`session-meta.json` 含日期与姓名/代号

---

## 脚手架

```powershell
python scripts/new_playbook_e_session.py 2026-07-27-playbook-e-1
python scripts/run_playbook_e_gate.py -q
```

生成目录：`docs/rehearsal/sessions/<session_id>/`。
