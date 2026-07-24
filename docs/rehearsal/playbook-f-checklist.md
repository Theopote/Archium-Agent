# Playbook F — 部分资料项目人工走查清单

> **用途：** Context Intelligence 连续谱验收（partial knowledge）。  
> **不可替代：** `python scripts/run_playbook_f_gate.py` 只证明路由与管线；**F1–F7 必须至少一次真人走通**。  
> **关联：** [user-task-playbooks.md § 剧本 F](../user-task-playbooks.md) · 自动化映射见 `tests/integration/test_partial_knowledge_project_flow.py`

---

## 何时必须做

| 场景 | 要求 |
|------|------|
| Context Intelligence / Genesis 大改 | F 自动化绿 + **一次**真人 F1–F5 |
| 内部 Preview（partial-knowledge 演示） | F1–F4 走通即可 |
| v0.2-beta 前（若宣称「部分资料也能推进设计」） | F1–F5 必过；F6–F7 记 Waive 或实测 |
| RC / 对外试用 | F1–F7 均有记录或明确 Waive |

---

## Session 信息（会前填写）

| 项 | 值 |
|----|-----|
| session_id | `YYYY-MM-DD-playbook-f-N` |
| 日期 / 时长 | |
| 操作者（建议非开发） | |
| Facilitator | |
| LLM 已配置 | 是 / 否 |
| Vision 出图已开启 | 是 / 否（F6 可选） |
| 自动化门禁已通过 | `run_playbook_f_gate.py` 日期：____ |

**标准场景描述（复制粘贴）：**

> 西安市某医院老院区改造，手头有一张老门诊楼照片、地址和一份旧院区介绍，甲方还没说清功能分区。

可换用同类型场景（改造 + 少量资料 + 关键未知项），但须在 `playbook-f-step-log.csv` 的 `scenario_variant` 列注明。

---

## 会前 15 分钟（Facilitator）

```powershell
cd <项目根目录>
.venv\Scripts\Activate.ps1
pip install -e ".[full]"
copy .env.example .env
# 填入 LLM_API_KEY；F6 出图需 vision 相关配置
python scripts/run_playbook_f_gate.py -q
python scripts/new_playbook_f_session.py YYYY-MM-DD-playbook-f-1
python scripts/run_playbook_f_rehearsal.py YYYY-MM-DD-playbook-f-1
archium
```

- [ ] Streamlit 启动无报错
- [ ] `run_playbook_f_gate.py` 全绿（或已知 flaky 已记 triage）
- [ ] 已创建 `docs/rehearsal/sessions/<session_id>/`
- [ ] 准备 1 份 DOCX/PDF「旧院区介绍」+ 1 张 JPG/PNG（可脱敏）
- [ ] **告知操作者：** 按清单自己点 UI；你只记通过/失败与截图路径，不替点「生成」
- [ ] 已分享 [playbook-f-participant-guide.md](playbook-f-participant-guide.md) 给操作者（非开发一页纸）

---

## 逐步走查（F1–F7）

每步在 `playbook-f-step-log.csv` 记：`pass`（Y/N/Partial）、`notes`、`evidence_path`（本地截图路径，勿提交含敏感信息的原图）。

### F1 — Genesis 单次描述，无手动模式

| | |
|---|---|
| **页面** | 开始项目 |
| **操作** | 粘贴标准场景 →「开始理解项目」 |
| **通过** | 出现知识状态摘要；完整度约 **20–45%**；阶段为 **研究 / 概念**（非「仅文档化」） |
| **通过** | **不**出现「请先选手动模式：有资料 / 无资料」类二选一阻断 |
| **通过** | 卡片显示：阶段判断 + 建议优先工作流 + 把握度 |
| **失败信号** | 完整度 &lt;15% 且仅提示上传；或默认「现有项目资料库」为主路径 |
| **证据** | Genesis 评估卡片截图；记录 `completeness_score` 与 `lifecycle_stage` |

- [ ] F1 通过

### F2 — 建议下一步（NBA）

| | |
|---|---|
| **页面** | 开始项目（评估卡）或侧边栏知识面板 |
| **操作** | 阅读「建议下一步」列表 |
| **通过** | 第一条为 **澄清 / 推演方向 / 任务理解** 之一 |
| **通过** | 「上传资料」若出现，**优先级低于**澄清或探索（非唯一动作） |
| **失败信号** | 仅「请先上传全部资料」；或跳转到资料库且无 Mission/探索入口 |
| **证据** | NBA 列表截图或抄录前三条 `action` |

- [ ] F2 通过

### F3 — 补一份资料后刷新（可选但推荐）

| | |
|---|---|
| **页面** | 资料库 或 Genesis「刷新知识状态」 |
| **操作** | 上传 1 份简介 DOCX/PDF **或** 1 张照片；触发重新评估 |
| **通过** | 知识状态刷新；**已知**含地点/类型/现状片段；**未知**仍含功能分区或规模 |
| **通过** | 完整度有变化但不跃迁到 &gt;70%「完备资料」假象 |
| **失败信号** | 上传后系统仍像「零资料纯概念」或「资料已够直接交付」 |
| **证据** | 刷新前后 `summary_line` 对比 |

- [ ] F3 通过 / Waive（未测上传）：____

### F4 — 推演结构化概念方向

| | |
|---|---|
| **页面** | 概念探索 |
| **操作** | 「推演概念方向（2–3 个）」 |
| **通过** | ≥2 个方向；展开可见 **spatial_strategy**、**formal_language** |
| **通过** | 至少 1 个方向含 **visual_prompt**（image_prompt 非空） |
| **通过** | 「预览 Vision 编译 prompt」可展开且含 Primary scene seed 或等价种子句 |
| **失败信号** | 方向仅 title/summary 纯文字；或推演失败无降级提示 |
| **证据** | 一个方向展开截图 |

- [ ] F4 通过

### F5 — 选定方向 → Mission

| | |
|---|---|
| **页面** | 概念探索 |
| **操作** | 「选为当前方向」→「确认方向并生成项目任务」 |
| **通过** | 进入项目任务；Mission 标题/任务陈述合理 |
| **通过** | 设计使命（DesignIntent）写回；与所选方向主题一致 |
| **通过** | 知识面板 / IntentEvolution 可见「选定方向」或「提交 Mission」类事件 |
| **失败信号** | Mission 空白；或仍要求先选手动 origin 模式 |
| **证据** | Mission 第一步截图 + evolution 条目 |

- [ ] F5 通过

### F6 — 概念示意（可选）

| | |
|---|---|
| **页面** | 概念探索（提交前）或项目任务 → 概念方向区 |
| **操作** | 「生成概念示意（文字）」或「+ 出图」 |
| **通过（文字）** | VisualConceptBrief 生成；有 `visual_prompt` 时 LLM 扩写可跳过或极短 |
| **通过（出图）** | `compiled_prompt` 含 scene seed；出图失败时有可读 warning 非崩溃 |
| **Waive** | 未开 Vision API → 记 Waive，F6 文字路径仍建议测 |
| **证据** | compiled prompt 片段或示意缩略图路径 |

- [ ] F6 通过 / Waive：____

### F7 — 继续生成与证据门禁（可选，RC 前建议测）

| | |
|---|---|
| **页面** | 项目任务 → 大纲 / 生成 |
| **操作** | 批准 Mission → 尝试生成大纲或草稿预览 |
| **通过** | 草稿/预览可出（页序或占位合理） |
| **通过** | **正式交付 / 导出** 仍提示证据不足或需补资料（evidence gate 生效） |
| **失败信号** | 部分资料项目被当作完备资料直接「可交付」无警告 |
| **证据** | 导出 blocker 或 warning 文案截图 |

- [ ] F7 通过 / Waive：____

---

## 产品红线（任一条即 F 未通过）

- [ ] 用户必须在 Genesis **手动选择** concept vs existing 才能继续
- [ ] 部分资料输入被路由为 **仅资料整理**，无法进入概念探索或 Mission
- [ ] `origin_mode=existing_project` **且** UI 文案暗示「资料已完备」
- [ ] 概念方向无结构化字段（回退到纯 bullet 文案）
- [ ] 评估或推演步骤 **无错误提示崩溃**（Streamlit 栈 trace 裸露）

---

## 会中禁忌

- Facilitator 不要替操作者完成 F4/F5 的 LLM 步骤（可帮配置 Key）
- 不要会中改代码；问题写入 `playbook-f-issues.csv`
- 不要把含甲方/地址的截图 commit 进仓库

---

## 会后 10 分钟

```powershell
# 更新 session-meta.json 中 steps / overall_pass
# 可选：本地截图仅保存在 session 目录，默认 gitignore
```

- [ ] `playbook-f-step-log.csv` 中 F1–F5 均为 `Y`（或 Waive 有 Owner + 补测日期）
- [ ] `playbook-f-issues.csv` 中 critical/high 已分级
- [ ] `session-meta.json` → `"overall_pass": true` 或 `"status": "failed"` + blockers
- [ ] 发版 PR 检查表勾选：「剧本 F 通过（部分资料 / Context Intelligence）」
- [ ] 若 F 失败：在 PR 或 issue 中链接 `docs/rehearsal/sessions/<session_id>/`

---

## 问题分级（记入 playbook-f-issues.csv）

| 档位 | 含义 |
|------|------|
| **f_blocker** | 部分资料主线走不通；不修不能宣称 Context Intelligence 验收 |
| **post_f_improvement** | 能走通但 UX/文案/路由令人困惑 |
| **future_idea** | 增强项，不挡 Preview |

---

## 通过线（Context Intelligence 验收）

- [ ] F1–F5 全部 **Y**（F3/F6/F7 允许 documented Waive）
- [ ] 无 open 的 **f_blocker**
- [ ] `run_playbook_f_gate.py` 与会话同日或更近的 commit 上为绿
- [ ] 至少 **1 名非开发** 操作者完成 F1–F4（F5 可在 Facilitator 陪同下）

---

## 脚手架

```powershell
python scripts/new_playbook_f_session.py 2026-07-25-playbook-f-1
```

生成目录：`docs/rehearsal/sessions/<session_id>/`（含 CSV 模板与 `session-meta.json`）。
