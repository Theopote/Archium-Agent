# 文化名村脱敏素材包（cultural_village_001）

案例化名：**砚溪村（脱敏）**

本目录为 Phase 7 真实项目验收的 drop-in 资料包，供 `manifests/cultural_village_001.json` 引用。
内容为虚构脱敏材料，用于验证资料导入、文化叙事与图文编排流水线；**不得冒充已完成真人评审**。

## 目录

```text
documents/   调研纪要、研究摘要、文保说明、参考版式
data/        村落基础指标表
assets/      11 张示意图纸/照片（PNG）
```

## 重新生成

若需批量重建占位文件（例如 CI 环境缺失）：

```bash
python scripts/materialize_cultural_village_files.py
```

有真实脱敏资料时，可直接替换同名文件，无需改 manifest。

## 验收

```bash
pytest tests/e2e/real_projects/test_cultural_village_files.py -q
pytest tests/e2e/real_projects/test_phase7_acceptance_run.py -m phase7_acceptance -q
```
