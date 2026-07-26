# 第二轮：生命系统审计

**用途：** 按 Archium「生命系统」做深度架构检查（非按目录横向扫描）。  
**更新：** 2026-07-26（01–07；多模态 M1–M3；绘画 P1–P3；产品闭环审计开题）  
**与第一轮关系：** 第一轮（[module-audit](../module-audit/README.md)）收敛工程债务；本轮检查世界模型是否支撑「建筑设计智能体」演化。

## 判断前提

第一轮已证明：最大风险不是单文件写错，而是产品从「AI 建筑汇报工具」向「建筑设计智能体」演化时，旧工具型痕迹与新领域模型并存。

若核心世界模型不稳，Research / Visual / Presentation / BIM 会各自长出一套 Project，系统分裂。

## 专题顺序

| # | 专题 | 文件 | 状态 |
|---|------|------|------|
| 01 | Domain Model（世界模型） | [01-domain-model.md](01-domain-model.md) | **完成** |
| 02 | 建筑知识模型 | [02-knowledge-model.md](02-knowledge-model.md) | **完成** |
| 03 | AI 推理链 | [03-ai-reasoning-chain.md](03-ai-reasoning-chain.md) | **完成** |
| 04 | 设计循环（Create→Critique→Revise） | [04-design-loop.md](04-design-loop.md) | **完成** |
| 05 | 多模态建筑输入 | [05-multimodal-input.md](05-multimodal-input.md) | **完成**（M1–M3） |
| 06 | AI 绘画系统 | [06-ai-painting.md](06-ai-painting.md) | **完成**（P1–P3） |
| 07 | 产品闭环 | [07-product-loop.md](07-product-loop.md) | **进行中**（L1 ✅；L2–L3 pending） |
| 08 | 商业化与团队协作 | 待开 | pending |

## 纪律

- 修复 Issue 仍登记到 [module-audit](../module-audit/README.md)（`DOM-*` 等），本目录写**判断与结构结论**，不另造 Stage/Round 批次号。
- 不新建 `COMPLETE_*` / `SESSION_SUMMARY_*`。
- 产品六席位硬上限见 `docs/architecture/pipeline-roles.md`。
