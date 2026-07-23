# 第一轮最终判断（工程收敛）

**日期：** 2026-07-23  
**范围：** 全仓健康检查 Batches → 工程骨架修复 → 本台账建立 → Domain 逐文件开查

## 判断

Archium **当前不是“缺少功能”**，而是进入另一类风险期：

功能、领域模型、测试、文档与兼容路径都在迅速增加；下一步最大的风险是 **重复、断链、状态不一致与维护成本**，而不是再堆能力。

第一模块（工程骨架，`PF-*`）的主要问题 **不是严重业务 Bug**，而是工程收敛：

| 现象 | 台账 |
|------|------|
| Legacy 仍在树内（已隔离、未删除） | PF-010 accepted-debt |
| 依赖完整锁定（uv lock + CI） | PF-004 done |
| 静态检查范围对齐 | PF-006 done |
| CI 分层，避免重型重复 | PF-007 done |
| 文档能力声明偏强 → 发布矩阵/剧本校正 | PF-008 done |
| 真实用户任务验收仍弱 | PF-011 / TS-010 / QD-010 open |

## 下一批（进行中）

**Domain 层逐文件检查**（模块 [02-domain.md](02-domain.md)），重点：

1. 重复模型  
2. 同义枚举  
3. Domain 是否导入 Application / Infrastructure / UI  
4. 模型是否承担 Service 逻辑  
5. `domain/visual` 是否过度膨胀  
6. RenderScene / LayoutPlan / SlideSpec 字段重复  
7. Compatibility / 废弃字段  
8. ORM 与 Domain 边界  

检查记录与新 Issue：`DOM-011` 起，见 [02-domain.md](02-domain.md)。

## 不做的事

- 不用 Stage / Round / Phase 作为修复批次名（本文件标题的「第一轮」仅指判断时点）。  
- 不在未立项时大拆 `domain/visual`；先登记 Issue，再按 P0 收敛 SSOT。
