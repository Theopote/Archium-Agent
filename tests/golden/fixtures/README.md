# Layer 2 — Real Fixture Acceptance

**真实资料 → 真实 parser → 缓存/Mock LLM → 完整导出**

## 三个场景

| Manifest | 场景 | Inline 回退 | 真实文件目录 |
|----------|------|-------------|--------------|
| `case_a_hospital.fixture.json` | 医院老院区 | DOCX | `files/case_a_hospital/` |
| `case_b_campus.fixture.json` | 校园改造 | DOCX + XLSX | `files/case_b_campus/` |
| `case_c_competition.fixture.json` | 概念投标 | DOCX + Spec 导出 | `files/case_c_competition/` |

## 添加脱敏真实资料

将文件放入对应子目录（gitignore，不提交仓库）：

```
files/
├── case_a_hospital/
│   └── 任务书.pdf
├── case_b_campus/
│   ├── 现状调研.pdf
│   └── 面积表.xlsx
└── case_c_competition/
    └── 任务书摘要.pdf
```

存在真实文件时优先使用；否则 CI 使用 manifest 内 `inline_docx` / `inline_xlsx` 生成临时文件，仍走真实 parser。

## LLM 缓存（可选）

`llm_cache/<case_id>.json` — prompt 子串 → 固定 JSON 响应。未命中时回退 `pipeline_mock_selector`。

录制建议：对真实 LLM 跑一次，将 request 关键片段与 response 写入缓存，供 L2 稳定回归。

## 运行

```bash
pytest tests/golden/fixtures -v -m fixture_acceptance
```

产物：`tests/golden/artifacts/fixture_<case_id>/`

## L3 人工评审

见 [live/EVALUATION_CHECKLIST.md](../live/EVALUATION_CHECKLIST.md)
