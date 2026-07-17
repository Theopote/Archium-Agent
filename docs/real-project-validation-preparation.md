# Real Project Validation Preparation

> Sprint checkpoint — no new Stages or major features. Validates engineering readiness for real architectural projects.

**Date:** 2026-07-18

## Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Flatten `pyproject.toml` optional-deps (no self-reference) | ✅ |
| 2 | Python 3.11/3.12 strategy + mypy aligned to 3.11 | ✅ |
| 3 | Remove `create_workflow_checkpointer()` leak | ✅ (already removed) |
| 4 | CI badge + matrix 3.11/3.12 | ✅ badge; remote run see below |
| 5 | ReviewIssue fingerprint dedupe | ✅ `domain/review.py` |
| 6 | Auto-repair protected content guards | ✅ tiered policy |
| 7 | Repair audit records (before/after/source/reason/removed) | ✅ `SlideRepairRecord` |
| 8 | Golden L1 + L2 real fixtures expanded | ✅ case_a–e |
| 9 | PptxGenJS smoke (Node + python-pptx) | ✅ `tests/smoke/` |
| 10 | Cross-platform notes | ✅ `docs/cross-platform-validation.md` |

## Local validation results (2026-07-18, Windows, Python 3.12)

| Command | Result |
|---------|--------|
| `ruff check archium tests` | **PASS** (0 issues) |
| `mypy archium` | **PASS** (138 files) |
| `pytest` | **244 passed**, 1 skipped (live_llm) |
| `pytest tests/smoke/test_pptxgen_render.py` | **2 passed** |
| `npm install` (pptxgen) | **OK** (19 packages) |
| PPTX smoke artifact size | **59,784 bytes** (`tests/smoke/artifacts/pptxgen_smoke.editable.pptx`) |

Python **3.11** not installed on this dev machine; validated via CI matrix configuration. Local run uses **3.12.0**.

## CI

- Workflow: `.github/workflows/ci.yml`
- Badge: [![CI](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Theopote/Archium-Agent/actions/workflows/ci.yml)
- Jobs: `test (3.11)`, `test (3.12)` — ruff, mypy, pytest, PptxGen smoke
- Artifacts: `golden-artifacts-py*`, `pptxgen-smoke-py*`

## Golden Case coverage

| Case | L1 Regression | L2 Real parser | Notes |
|------|---------------|----------------|-------|
| case_a_hospital | ✅ | ✅ DOCX | Fact conflict |
| case_b_campus | ✅ | ✅ DOCX+XLSX | Multi-chunk |
| case_c_competition | ✅ | ✅ DOCX+Spec | Export spec |
| case_d_full_deck | ✅ | ✅ | 20 slides |
| case_e_real_paths | — | ✅ | 中文/空格路径, PDF/DOCX/PPTX/JPG, conflicts |

## Install

```bash
# Users
pip install -e ".[full]"

# Developers / CI
pip install -e ".[full,legacy,dev]"
```

## Remaining risks (not closed this round)

- Remote GitHub Actions green after push (must verify on `master`)
- Branch protection not enforced until repo admin enables rules
- L3 live LLM quality evaluation (manual checklist only)
- Visual regression / pixel baselines for slide previews
- Windows + PowerPoint manual open test on architect machine
- Real sanitized PDFs not yet committed (inline fallbacks used in CI)
