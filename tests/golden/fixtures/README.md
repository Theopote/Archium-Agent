# Layer 2 — Real Fixture Acceptance

**真实资料 → 真实 parser → 缓存/Mock LLM → 完整导出**

## 五个场景

| Manifest | 场景 | Inline 回退 | 真实文件目录 |
|----------|------|-------------|--------------|
| `case_a_hospital.fixture.json` | 医院老院区 | DOCX | `files/case_a_hospital/` |
| `case_b_campus.fixture.json` | 校园改造 | DOCX + XLSX | `files/case_b_campus/` |
| `case_c_competition.fixture.json` | 概念投标 | DOCX + Spec 导出 | `files/case_c_competition/` |
| `case_d_full_deck.fixture.json` | 20 页完整汇报 | DOCX | `files/case_d_full_deck/` |
| `case_e_real_paths.fixture.json` | 中文/空格路径 + 多格式 | DOCX+PDF+PPTX+JPG | `files/case_e_real_paths/` |

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
└── case_d_full_deck/
    └── 任务书.pdf
```

存在真实文件时优先使用；否则 CI 使用 manifest 内 `inline_docx` / `inline_xlsx` 生成临时文件，仍走真实 parser。

## LLM 缓存（可选）

`llm_cache/<case_id>.json` — prompt 子串 → 固定 JSON 响应。未命中时回退 `pipeline_mock_selector`。

### 录制脚本

对真实 LLM 跑一次 workflow，将 request 关键片段与 response 写入缓存，供 L2 稳定回归：

```bash
# 配置 .env：LLM_PROVIDER=openai_compatible，并设置 API Key
python scripts/record_llm_cache.py case_d_full_deck
python scripts/record_llm_cache.py case_a_hospital --source regression
python scripts/record_llm_cache.py case_b_campus --dry-run
```

输出默认写入 `tests/golden/fixtures/llm_cache/<case_id>.json`。更具体的 needle（如 `请生成约 20 页`）会排在前面，避免被通用 key 抢先匹配。

## 运行

```bash
pytest tests/golden/fixtures -v -m fixture_acceptance
```

产物：`tests/golden/artifacts/fixture_<case_id>/`

## L3 人工评审

见 [live/EVALUATION_CHECKLIST.md](../live/EVALUATION_CHECKLIST.md)
