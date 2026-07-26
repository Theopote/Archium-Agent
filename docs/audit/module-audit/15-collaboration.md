# 15 — Collaboration / RBAC / invites

模块：项目成员、邀请、角色化协作  
前缀：`COLLAB-`  
更新：2026-07-26（Topic 08）

相关：[第二轮-08 商业化与协作](../life-system/08-commercialization-collab.md)

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| COLLAB-001 | P0 | open | RBAC 未接写路径（Mission/Studio/Generate/Ingest） | services; life-system 08 | 任意 session 可改设计 | 写入口 `require_project_permission` | 无成员无权写；单测 | `-` |
| COLLAB-002 | P1 | done | `list_all` 无成员过滤；无「我的项目」 | `project_access_service`; `workspace_service` | 实例内项目全可见 | `list_visible_projects` | 有成员时仅见自己的项目 | Topic 08 C1 |
| COLLAB-003 | P1 | done | 无 session actor SSOT；全局硬编码 local-user | `session_actor.py` | 无法切换身份 | session `actor_id` + redeem 写入 | 兑换后身份切换 | Topic 08 C1 |
| COLLAB-004 | P1 | open | 邀请码仅 Home 手输；无 deep link / 邮件 | `project_members_panel` | 难分享给甲方 | `?invite=` redeem | URL 可兑换 | `-` |
| COLLAB-005 | P1 | open | 无 Client/Reviewer 角色化导航 | product_flow / chrome | 全员同一五阶段 | 角色化 chrome | Client 主见 deliver | `-` |
| COLLAB-006 | P2 | open | ProjectEvent 无 member 级 attribution | `project_event.py` | 无法答「谁批准」 | payload actor_id | 事件可读成员 | `-` |
