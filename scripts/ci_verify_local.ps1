# Run the same checks as CI before push (Windows).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== Ruff =="
ruff check archium tests

Write-Host "== Config reference sync =="
python scripts/generate_config_docs.py --check

Write-Host "== Mypy =="
mypy archium --python-version 3.12

Write-Host "== Pytest unit (coverage) =="
pytest -m unit --cov=archium --cov-report=xml --cov-fail-under=65 -q

Write-Host "== Pytest integration (append coverage) =="
pytest -m "integration and not e2e" --cov=archium --cov-append --cov-report=xml -q

Write-Host "== Critical module coverage gate =="
python scripts/ci_critical_coverage_gate.py

Write-Host "== Pytest benchmark =="
pytest -m benchmark -q

Write-Host "== Canvas build smoke =="
pytest tests/smoke/test_canvas_editor_build.py -q

Write-Host "CI verify local: all steps passed."
