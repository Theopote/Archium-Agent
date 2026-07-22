---
name: apply-studio-comments
description: >-
  Applies Studio element-bound natural-language comments through ElementComment
  to StudioCommand to SceneChangeProposal without guessing targets. Use when
  the user selects a scene node and comments, or asks to turn NL notes into
  Before/After proposals.
---

# Apply Studio comments

## Intent

用户点击 / 选中 RenderScene 节点再评论时，**目标对象不猜测**。保留 Command → Patch → Proposal → QA → Revision 审计链；不要直接改 JSX / 静默写 Scene。

## Pipeline

```
Select element (studio_selected_element_id)
  → map to RenderScene node_id
  → ElementComment (status=pending; scene_revision_id / scene_hash / node_snapshot)
  → CommentToCommandPlanner (bound_node_id)
  → StudioCommand(+)
  → SceneChangeProposal
  → Before/After review
  → accept | reject
  → ElementComment status = accepted | rejected
```

若评论时 SceneRevision / scene_hash 与当前正式版本不一致 → `needs_rebase`（禁止静默应用到新版本；可 `rebind_to_current_scene` 后重试）。

## Hard rules

1. **硬绑定 `node_id`（默认 scope=`node`）** — 有选中时禁止再用「右边第二张图」类 hint 覆盖目标
2. **作用域可显式扩大** — `node_and_references` / `selection` / `region` / `slide`；多节点意图（「这三个卡片大小一致」）在 `node` 下会拒绝并提示改 scope
3. **只修改作用域内节点**；遵守 partial-edit 合同
4. **解析失败要明确 `unsupported_reason`** — 不可静默改错节点
5. **无选中** — 可回退纯 NL 提案路径（`StudioNLProposalService`），并提示用户选中更稳
6. **版本钉扎** — 提案前校验 `scene_revision_id` / `scene_hash`；漂移则 `needs_rebase`，不可直接 apply
7. 状态机：`pending → proposed → accepted|rejected → resolved`（旁路：`needs_rebase`）

## Agent behavior

- UI：AI 编辑面板显示「当前目标」；按钮「对选中元素生成提案」
- 代码入口：`ElementCommentService.create_and_propose`；planner：`CommentToCommandPlanner`
- 几何启发式：「放大一点」→ Resize / drawing readability；「和左边对齐」→ Align（最近左侧 sibling）或贴页左边 Move
- 接受/拒绝提案后由 `SceneProposalService` 回调同步评论状态

## Checklist

```
- [ ] 已解析 node_id（或明确走无绑定 NL）
- [ ] 评论已持久化为 ElementComment
- [ ] 全部 command 主目标 = 绑定节点
- [ ] 用户看过 Before/After 再接受
- [ ] 评论状态与提案决策一致
```

## Related

- Domain: `archium/domain/visual/element_comment.py`
- Service: `archium/application/visual/element_comment_service.py`
- Planner: `archium/application/visual/comment_to_command_planner.py`
- Parent authoring rules: `architectural-presentation-authoring`
- QA gate: `visual-qa-review`
