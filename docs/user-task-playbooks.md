# 关键用户任务剧本（发版门禁）

> **目的：** 用「用户能否完成整条任务」补充模块级测试。  
> **规则：** 每次准备打发布标签（Beta / RC / Stable）前，必须跑完下列剧本并留下记录。  
> **更新：** 2026-07-23

自动化（golden / e2e / smoke）证明管线可跑；**剧本验收**证明人能在真实资料上走通。二者缺一不可。

## 发布等级 ↔ 剧本

| 发布动作 | 最低剧本要求 |
|----------|--------------|
| 日常 PR | 不强制剧本；相关模块自动测试即可 |
| 内部 Preview 演示 | 剧本 A 走通一次（可 Mock LLM） |
| **Context Intelligence 验收** | 剧本 **F** 自动化 + 一次真人 partial-knowledge 走通 |
| **v0.2-beta 标签** | 剧本 **A** 真人验收 + 修改成本记录 |
| RC / 对外试用 | 剧本 A + 至少 B 或 E |
| Stable 声明 | 剧本 **A–E** 均有脱敏验收记录 |

能力与发布等级见 [release-capability-matrix.md](release-capability-matrix.md)。

## 剧本 A — 新建建筑汇报

**目标：** 从空项目到可打开的 PPTX。

| 步骤 | 操作 | 通过标准 |
|------|------|----------|
| A1 | 新建项目并导入资料（PDF/DOCX/图片至少一种） | 文件出现在资料库；无崩溃 |
| A2 | 生成 / 审阅事实 | 关键指标可引用；冲突可见 |
| A3 | 生成并确认 Mission | 可批准；approval_hash 非空 |
| A4 | 批准大纲 / Storyline | 页序合理；可继续生成 |
| A5 | 生成约 12 页幻灯片 | 页数在约定范围内；可进 Studio |
| A6 | 编辑至少一页（改字或换图） | 提案可接受；画布可见变化 |
| A7 | 导出原生 PPTX | 文件可被 PowerPoint/WPS 打开；关键页无大面积空白 |

**自动化映射（不足以代替真人验收）：**

```bash
# 可重复门禁（默认：golden regression + mission + PptxGen smoke）
python scripts/run_playbook_a_gate.py

# 加上真实项目验收（更慢）
python scripts/run_playbook_a_gate.py --with-real-projects
```

- `tests/golden/regression`、`tests/golden/mission`
- `tests/e2e/real_projects/test_real_project_acceptance.py`
- `tests/smoke/test_pptxgen_render.py` / layout-plan PPTX smoke

**记录位置：** `docs/rehearsal/sessions/` 或 `tests/e2e/real_projects/records/`

## 剧本 B — 模板填充

**目标：** 导入原生模板后填充内容，且结构不被冲掉。

| 步骤 | 操作 | 通过标准 |
|------|------|----------|
| B1 | 导入参考 / 模板 PPTX | 可识别 Layout / 占位 |
| B2 | 绑定项目内容 | 标题/正文/图位有对应填充 |
| B3 | 导出 | 母版结构、页数意图保持；非整页重排为「另一套版式」 |

**自动化映射：** template induction / template studio unit + composition goldens（部分）  
**真实验收：** 仍 ❌ → 发布等级保持 Experimental，直到留下记录。

## 剧本 C — 现有 PPT 美化

**目标：** 保持页数、顺序与文字，重排版式后可对比。

| 步骤 | 操作 | 通过标准 |
|------|------|----------|
| C1 | 导入既有汇报 PPTX | 页数/顺序与源一致 |
| C2 | 触发版式重排 / 视觉编排 | 文字内容不丢、不乱序 |
| C3 | 对比验证 | 有 before/after 或提案对比；人工确认无「改写故事」 |

**自动化映射：** reference slide / scene proposal 对比相关测试  
**真实验收：** ❌

## 剧本 D — 页面复活

**目标：** 图片式页面 → 可编辑场景。

| 步骤 | 操作 | 通过标准 |
|------|------|----------|
| D1 | 导入位图页或扫描页 | 进入页面复活流程 |
| D2 | 区域识别 | 给出可校正区域 |
| D3 | 人工校正 | 调整框选后可保存 |
| D4 | 生成可编辑 RenderScene | Studio 可选中文字/图片节点 |

**自动化映射：** `tests/domain/test_slide_recovery.py`、slide recovery application tests  
**真实验收：** ❌ → Experimental

## 剧本 E — Studio 修改闭环

**目标：** 选中 → 变换 → 换图/改字 → Undo → 导出。

| 步骤 | 操作 | 通过标准 |
|------|------|----------|
| E1 | 选中单个元素 | 属性面板反映选区 |
| E2 | 移动 / 缩放 | 几何写入 Scene；可预览 |
| E3 | 换图或改文字 | 提案或直接编辑可接受 |
| E4 | Undo | 回到上一修订；无脏数据 |
| E5 | 导出 PPTX | 与画布一致的可打开文件 |

**自动化映射：** Studio unit/integration、scene proposal、undo tests、PPTX smoke  
**真实验收：** ⚠️（需浏览器真人点选）→ 当前 Experimental / Preview 边界见矩阵

## 剧本 F — 部分资料项目（Partial Knowledge）

**目标：** 验证 Context Intelligence 连续谱——用户不必在「纯想法」与「完备资料」之间二选一。

**典型输入：**

> 西安市某医院老院区改造，手头有一张老门诊楼照片、地址和一份旧院区介绍，甲方还没说清功能分区。

| 步骤 | 操作 | 通过标准 |
|------|------|----------|
| F1 | 「开始项目」描述上述情况（可不选手动模式） | 显示知识完整度约 20–45%；阶段判断为研究/概念；**不是**仅提示上传资料 |
| F2 | 查看建议下一步 | 优先 **澄清 / 推演方向 / 任务理解** 之一；可并行建议补资料 |
| F3 | 上传 1 份简介或 1 张照片（可选） | 知识状态刷新；已知含地点/类型；未知含功能或规模 |
| F4 | 推演 2 个概念方向 | 含 `spatial_strategy`、`formal_language`、`visual_prompt` |
| F5 | 选定方向并提交 Mission | Mission 与设计使命写回；IntentEvolution 有选定/提交记录 |
| F6 | （可选）生成概念示意 | 有 `visual_prompt` 时跳过 LLM 简报扩写；compiled_prompt 含 scene seed |
| F7 | 继续大纲 → 生成 | 草稿预览可出；**正式交付**仍提示补资料（evidence gate） |

**自动化映射（不足以代替 F1/F4 真人感受）：**

```bash
python scripts/run_playbook_f_gate.py
# or
pytest tests/integration/test_partial_knowledge_project_flow.py tests/unit/test_knowledge_state_routing.py tests/unit/test_project_context_routing.py -q
```

- `tests/integration/test_partial_knowledge_project_flow.py` — 评估路由、规则降级、探索→Mission、结构化方向
- 相关 unit：`test_project_context.py`、`test_workspace_mode_service.py`、`test_concept_direction_structure.py`

**记录位置：** `docs/rehearsal/sessions/`（注明 partial-knowledge 场景）

## 每次发版检查表

复制到发版 PR 或 rehearsal session：

```text
[ ] 剧本 A 通过（操作者：____ 日期：____ 项目：____）
[ ] 剧本 B 通过 / Waive 原因：____
[ ] 剧本 C 通过 / Waive 原因：____
[ ] 剧本 D 通过 / Waive 原因：____
[ ] 剧本 E 通过 / Waive 原因：____
[ ] 剧本 F 通过（部分资料 / Context Intelligence：____ 日期：____）
[ ] 能力矩阵等级已按验收结果下调或上调
[ ] CI compatibility + quality-full 绿
```

Waive 必须写清风险 Owner 与补测日期；不得用「单测已绿」代替 Waive 理由。
