# 文档一致性审计（2026-07-23）

## 结论

代码已经明显超过 README 与早期 Visual/Studio 文档描述。当前最需要治理的不是继续累积“完成总结”，而是建立少量可维护的现行文档，并明确其余材料都是带时点的历史记录。

## 已确认的高优先级失配

| 优先级 | 文档或范围 | 代码事实 | 建议 |
|---|---|---|---|
| P0 | `docs/configuration-reference.md`、`.env.example` | `Settings` 新增的页面恢复与图片衍生字段未加入 `FIELD_DOMAINS`，生成器与同步测试失败 | 先补注册表映射，再重新生成两份文档 |
| P0 | `docs/visual/README.md` | 仍把拖拽编辑、自动修图、模板导入列为不做；代码已有 Canvas Editor、图片 derivative、模板归纳/Studio | 改成当前能力与边界，避免使用 Round 1 非目标描述现状 |
| P0 | `docs/studio-user-guide.md` | 指南写 5 个检查器 Tab；代码为属性/布局/内容/AI/评论/风格/检查 7 个 | 合并 `studio-current-capabilities.md` |
| P0 | 根 `README.md` | 能力矩阵未覆盖多选/框选、评论 Inbox/rebase、容量门禁、图片衍生；仍使用 Stage 16+/历史 sprint 描述当前架构 | 链接当前系统架构与文档中心，更新能力矩阵 |
| P1 | `archium/ui/components/canvas_editor/README.md` | README 的 TODO 仍写“多选支持”，前端已支持 Shift 多选和框选 | 更新 API、交互、返回值与构建说明 |
| P1 | Studio AI 编辑章节 | 当前评论可绑定 node、selection、region、slide，并固定 Scene 版本 | 补状态机、rebase 和作用域说明 |
| P1 | 内容适配章节 | 当前存在正式容量状态和图纸最低可读预算 | 补 `fits/tight/overloaded/impossible` 行为 |
| P1 | 图片与风格文档 | 当前存在原图不可变的 derivative 管线和证据资产限制 | 说明处理模式、缓存/溯源和安全边界 |

## 文档信息架构问题

`docs/` 当前约有 85 份 Markdown，其中大量文件名或标题包含 `SUMMARY`、`COMPLETE`、`FINAL`、`FIX`、`ANALYSIS`。这些文件有审计价值，但不应与用户指南、架构和部署文档处于同一导航层级。

建议保留三层：

1. 根 README：产品定位、安装、关键能力与文档入口。
2. `docs/README.md`：现行文档唯一索引。
3. 历史目录：analysis/delivery/implementation/review/sessions，默认不进入使用路径。

## 本轮已新增

- `docs/README.md`：文档中心，区分现行与历史资料。
- `docs/architecture/current-system.md`：不依赖历史 Stage/Round 的当前架构快照。
- `docs/studio-current-capabilities.md`：覆盖近期 Studio、容量、评论、图片和字体能力。
- `docs/documentation-maintenance.md`：事实源、变更映射与提交前检查。

## 下一批执行顺序

1. 修复配置 registry 后重新生成配置参考与 `.env.example`。
2. 将 Studio 补充合并入主用户指南，并更新 Canvas Editor README。
3. 更新根 README 和 Visual README，删除已失真的“明确不做”。
4. 检查现行文档的相对链接、命令和 UI 名称。
5. 给历史材料统一增加时点/非现行提示；确认无反向链接后再决定归档或删除，避免直接批量删除审计记录。
