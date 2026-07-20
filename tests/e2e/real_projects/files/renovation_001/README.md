# 老旧建筑改造脱敏素材包（renovation_001）

案例化名：**东华文创园（脱敏）**

工业厂房转创意办公的 Phase 7 验收 drop-in 资料，由 `manifests/renovation_001.json` 引用。

## 目录

```text
documents/   改造任务书、现状调研、结构检测摘要、参考版式
data/        改造面积指标表
assets/      11 张厂区/平面/分期示意图（PNG）
```

## 重新生成

```bash
python scripts/materialize_renovation_files.py
```

## 验收

```bash
pytest tests/e2e/real_projects/test_renovation_files.py -q
pytest tests/e2e/real_projects/test_phase7_acceptance_run.py -m phase7_acceptance -q
```
