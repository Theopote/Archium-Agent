# Cross-Platform Validation Notes

Archium targets **Windows (primary)** and **Linux/macOS (CI + developer)**.

> **Beta 支持矩阵（自动化 vs 人工）：** [beta-platform-support-matrix.md](beta-platform-support-matrix.md)

## Automation vs manual authority

| Layer | Linux PR CI | Windows nightly smoke | Authoritative visual check |
|-------|-------------|----------------------|----------------------------|
| Workflow / Golden L1–L2 | ✅ | ✅ (subset) | — |
| PptxGen structure | ✅ | ✅ + Unicode output path | — |
| Checkpoint SQLite lifecycle | unit tests | ✅ real Windows paths | — |
| Marp PNG visual regression | ✅ | — | — |
| Chinese typography in PPTX | font fallback only | same Node render | **Manual: PowerPoint on Windows** |

**Windows smoke is institutionalized** — not documentation-only:

- Workflow: [`.github/workflows/windows-smoke.yml`](../.github/workflows/windows-smoke.yml)
- Schedule: daily 02:00 UTC + `workflow_dispatch` + `v*` tag push
- Tests: `tests/smoke/test_windows_platform.py`

```powershell
pytest tests/smoke/test_windows_platform.py -v
```

## Python

| Item | Policy |
|------|--------|
| Supported versions | **3.11** and **3.12** (`requires-python >=3.11`) |
| Type checking | `mypy` uses `python_version = "3.11"` (lowest supported) |
| CI matrix | Ubuntu latest, Python 3.11 + 3.12 |
| Windows smoke | `windows-latest`, Python 3.12 (nightly / RC) |

## Windows — Chinese paths and spaces

Golden Case **L2 `case_e_real_paths`** materializes files under:

```
tmp/<scratch>/中文路径/项目 资料/任务书 摘要.docx
```

Ingestion uses `pathlib.Path` end-to-end; no manual string encoding. Windows smoke re-runs this on `windows-latest`.

If import fails on Windows locally:

1. Confirm project path does not exceed `MAX_PATH` without long-path support.
2. Prefer UTF-8 code page (`chcp 65001`) in legacy terminals.
3. Avoid mixing short (8.3) paths with Unicode project roots.

PptxGen smoke additionally writes:

```
<tmp>/中文输出目录/项目 资料/汇报 文件.pptx
```

## Fonts (PptxGenJS / PowerPoint)

Native-element PPTX uses theme fonts from `archium/infrastructure/renderers/pptxgen/core/theme.mjs`.

| Platform | Behavior |
|----------|----------|
| Windows + Office | Uses installed Chinese fonts (e.g. 微软雅黑) when available |
| Linux CI | Falls back to Latin fonts; **Chinese glyphs may substitute** — file opens, layout intact |
| Validation | Smoke tests check slide count, titles, speaker notes — **not** pixel-perfect typography |

Opening exported PPTX on Windows with Microsoft PowerPoint is the **authoritative visual check** (L3 manual). See [beta-platform-support-matrix.md](beta-platform-support-matrix.md).

## Node.js / PptxGenJS

```bash
cd archium/infrastructure/renderers/pptxgen
npm install
node render.mjs --input ../../../tests/fixtures/pptxgen/smoke.spec.json --output /tmp/smoke.pptx
```

CI runs `pytest tests/smoke/test_pptxgen_render.py` (Linux PR) and `test_windows_platform.py` (Windows nightly).

## SQLite / Checkpointer (Windows)

`WorkflowCheckpointerManager` must be closed before deleting checkpoint DB files. Streamlit uses `@st.cache_resource` lifecycle; tests call `service.close()` explicitly.

Windows smoke verifies checkpoint DB deletion after workflow on real Windows paths (including spaced filenames).

## Recommended local validation (Windows)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[full,legacy,dev]"
cd archium/infrastructure/renderers/pptxgen; npm install; cd ../../../../
pytest tests/golden -v
pytest tests/smoke/test_windows_platform.py -v
pytest tests/smoke/test_pptxgen_render.py -v
ruff check archium tests
mypy archium
streamlit run app.py
```

Place sanitized real PDFs under `tests/golden/fixtures/files/<case_id>/` to override inline fallbacks.
