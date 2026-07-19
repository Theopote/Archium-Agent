# Critical Module Coverage Gate

PR CI runs **two** coverage passes that append into one report:

1. `pytest -m unit --cov=archium --cov-report=xml --cov-fail-under=65`
2. `pytest -m "integration and not e2e" --cov=archium --cov-append --cov-report=xml`

The global **65%** floor stays for fast iteration. A second gate (`scripts/ci_critical_coverage_gate.py`) enforces **higher per-file floors** on services that must not regress silently:

| Module | Floor |
|--------|------:|
| `transaction_executor.py` | 75% (target 80%) |
| `project_deletion_service.py` | 80% |
| `layout_repair_service.py` | 80% |
| `visual_edit_service.py` | 75% (target 80%) |
| `asset_reference.py` | 85% |
| `slide_history_service.py` (revision restore) | 80% |
| `visual_history_service.py` (revision restore) | 80% |
| `content_adaptation_service.py` (revision restore) | 80% |

## Local reproduction

```bash
pytest -m unit --cov=archium --cov-report=xml --cov-fail-under=65
pytest -m "integration and not e2e" --cov=archium --cov-append --cov-report=xml
python scripts/ci_critical_coverage_gate.py
```

## Raising floors

When `transaction_executor.py` sustains ≥80% on main, bump its floor from 75 → 80 in `scripts/ci_critical_coverage_gate.py`.
