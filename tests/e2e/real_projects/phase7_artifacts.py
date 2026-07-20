"""Read/write Phase 7 project-folder acceptance artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from archium.domain.project_acceptance import RealProjectAcceptanceRecord

from tests.e2e.real_projects.phase7_loader import phase7_project_root

UPDATE_ENV = "UPDATE_PHASE7_ACCEPTANCE_RECORDS"


def acceptance_record_path(project_id: str) -> Path:
    return phase7_project_root(project_id) / "acceptance_record.json"


def write_phase7_acceptance_record(record: RealProjectAcceptanceRecord) -> Path:
    path = acceptance_record_path(record.project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def assert_or_update_phase7_acceptance_record(record: RealProjectAcceptanceRecord) -> None:
    if os.environ.get(UPDATE_ENV) == "1":
        write_phase7_acceptance_record(record)
        return

    path = acceptance_record_path(record.project_id)
    assert path.exists(), f"Missing Phase 7 acceptance baseline: {path}"
    expected = RealProjectAcceptanceRecord.model_validate(_read_json(path))
    assert _stable_record_fingerprint(record) == _stable_record_fingerprint(expected), (
        f"Phase 7 acceptance drift in {record.project_id}. "
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
