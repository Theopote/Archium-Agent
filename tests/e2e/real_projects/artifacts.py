"""Read/write real-project acceptance artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from archium.domain.project_acceptance import RealProjectAcceptanceRecord

UPDATE_ENV = "UPDATE_REAL_PROJECT_ACCEPTANCE_RECORDS"
RECORDS_ROOT = Path(__file__).resolve().parent / "records"


def record_path(project_id: str) -> Path:
    return RECORDS_ROOT / project_id / "acceptance_record.json"


def write_acceptance_record(record: RealProjectAcceptanceRecord) -> Path:
    path = record_path(record.project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def assert_or_update_acceptance_record(record: RealProjectAcceptanceRecord) -> None:
    if os.environ.get(UPDATE_ENV) == "1":
        write_acceptance_record(record)
        return

    path = record_path(record.project_id)
    assert path.exists(), f"Missing acceptance record baseline: {path}"
    expected = RealProjectAcceptanceRecord.model_validate(_read_json(path))
    assert _stable_record_fingerprint(record) == _stable_record_fingerprint(expected), (
        f"Acceptance record drift in {record.project_id}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )


def _stable_record_fingerprint(record: RealProjectAcceptanceRecord) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    payload.pop("run_at", None)
    metrics = dict(payload.get("metrics", {}))
    metrics.pop("first_generation_seconds", None)
    payload["metrics"] = metrics
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
