# Pinned dependency locks for reproducible installs.
#
# Source of truth for *ranges*: pyproject.toml
# Source of truth for *pins* (CI / Docker / release candidates): *.lock here
#
# Tooling: uv only (see scripts/compile_requirement_locks.py).
# Do not introduce a second lock toolchain (Poetry / pip-tools) in parallel.
#
# Regenerate after changing project dependencies:
#   pip install uv
#   python scripts/compile_requirement_locks.py
#
# Verify locks match pyproject (hard gate — run in CI):
#   python scripts/compile_requirement_locks.py --check
#
# Install examples:
#   pip install -r requirements/base.lock
#   pip install -r requirements/full-py312.lock
#   pip install -e ".[dev]"   # still fine for day-to-day editable extras
#
# Files:
#   base.lock         — [project].dependencies only
#   full-py311.lock   — .[full] resolved for CPython 3.11
#   full-py312.lock   — .[full] resolved for CPython 3.12
#
# Node locks (separate from Python):
#   archium/infrastructure/renderers/pptxgen/package-lock.json
#   archium/ui/components/canvas_editor/frontend/package-lock.json
# Install with: npm ci  (never npm install in CI)
