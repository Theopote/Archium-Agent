# Archium Agent Skills

正式产品级 Agent Skill 资产。Cursor、Codex 与未来 Archium Agent **共用同一套规则**，真源在本目录，不维护 `.cursor/skills/` 副本。

## 技能索引

| Skill | 何时使用 |
|-------|----------|
| [architectural-presentation-authoring](architectural-presentation-authoring/SKILL.md) | 建筑汇报总则、叙事与事实约束 |
| [drawing-page-design](drawing-page-design/SKILL.md) | 总平面 / 平面 / 剖面等图纸页 |
| [photo-evidence-layout](photo-evidence-layout/SKILL.md) | 现场照片证据板、问题网格 |
| [executive-summary-writing](executive-summary-writing/SKILL.md) | 开篇 / 结论 / 执行摘要页 |
| [hospital-renovation-report](hospital-renovation-report/SKILL.md) | 医院老院区 / 医疗改造汇报 |
| [campus-renovation-report](campus-renovation-report/SKILL.md) | 校园建筑 / 功能置换汇报 |
| [apply-studio-comments](apply-studio-comments/SKILL.md) | Studio 元素评论 → Command → Proposal |
| [visual-qa-review](visual-qa-review/SKILL.md) | 视觉 / 建筑表达 QA 审核 |

## 如何消费

### Cursor

仓库规则 [`.cursor/rules/archium-skills.mdc`](../.cursor/rules/archium-skills.mdc) 在匹配场景时要求代理 **先 Read** 本目录下对应 `SKILL.md`，再执行任务。也可在对话中显式 `@archium-agent-skills/<skill>/SKILL.md`。

### Codex / 其他代理

任务开始前打开或引用相关 `SKILL.md`。多技能可叠加（例如医院汇报 = `architectural-presentation-authoring` + `hospital-renovation-report` + `visual-qa-review`）。

### 未来 Archium Agent

以本目录为 system / tool 规则注入源；路径稳定，勿改名目录除非同步更新消费方。

## 编写约定

- 每个技能一个目录，入口文件必须是 `SKILL.md`
- Frontmatter：`name`（小写连字符）+ 第三人称 `description`（含 WHAT 与 WHEN）
- 规则优先、少叙述；细则可链到 `docs/visual/` 等正式文档
- 会话笔记不放这里（见 `.dev-notes/`）
