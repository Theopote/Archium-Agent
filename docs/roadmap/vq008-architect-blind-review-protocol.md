# VQ-008 — Architect Blind Review Protocol（Beta 硬门）

> **状态：** 基建已落地；真人盲评未跑 → **Beta 禁止**  
> **实现：** `archium/domain/visual/architect_blind_review.py`  
> **服务：** `archium/application/visual/architect_blind_review_service.py`  
> **CLI：** `scripts/evaluate_vq008_blind_review.py`  
> **规范来源：** [`architectural-visual-quality-recovery-p0.md`](architectural-visual-quality-recovery-p0.md) §6

## 1. 目的

证明新版 Archium 的**视觉表达**被建筑师认可，而不是规则 QA 通过。  
材料三盲：旧版 Archium / 新版 Archium / 人工优秀参考——**不标来源**。

## 2. 门槛（全部满足才 `beta_allowed`）

| 指标 | 阈值 |
|------|------|
| 建筑师人数 | ≥ 5 |
| 新版对旧版胜率 | ≥ 80% |
| 「可直接使用或轻微修改」（新版） | ≥ 60% |
| 新版平均视觉分 | ≥ 7 / 10 |
| 改稿时间相对旧版下降 | ≥ 50% |

未收集齐全或任一门槛未达 → **fail closed**（禁止打 `v0.2-beta`）。

## 3. 审美维度（可选细项，总分仍 1–10）

Hierarchy、Focal Clarity、Typography Expressiveness、Color Harmony、Graphic Coherence、Composition Tension、Image Treatment、Architectural Relevance、Deck Rhythm、Template Repetition。

## 4. 流程

1. 准备每页三张截图（legacy / current / reference）。  
2. `py -3 scripts/evaluate_vq008_blind_review.py --scaffold tests/benchmark/vq008_pack/`  
3. 只把 `reviewer_pack.json` + 图片发给评审（**勿发** `sealed_key.json`）。  
4. 每位建筑师对每个 trial：排序 A/B/C、就绪度、视觉分、估计改稿分钟。  
5. 把 ballots 写回 `session.sealed.json`。  
6. `py -3 scripts/evaluate_vq008_blind_review.py session.sealed.json` → 仅 exit 0 时视觉硬门可通过。

## 5. 与既有 Human Visual Review 的关系

| 体系 | 用途 |
|------|------|
| `HumanVisualReview` + `human_review_gate` | 单页问题驱动异常复核（benchmark 套件） |
| **VQ-008 Blind Review** | 三方盲比 + **Software Beta 硬门** |

二者并存；**打 Beta 标签必须以 VQ-008 `beta_allowed=true` 为准**（另仍需 B10 等工程门槛）。

## 6. 当前诚实状态

- 协议 / 计分 / 门禁 / CLI：**已实现**（单测覆盖 fail-closed 与合成达标样例）  
- ≥5 名建筑师真人盲评包：**未执行** → **Beta 仍禁止**
