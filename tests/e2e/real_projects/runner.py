"""Run real-project acceptance scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.application.project_acceptance_service import ProjectAcceptanceService
from archium.domain.project_acceptance import RealProjectAcceptanceRecord
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session

from tests.e2e.real_projects.artifacts import (
    assert_or_update_acceptance_record,
    record_path,
    write_acceptance_record,
)
from tests.e2e.real_projects.loader import list_manifest_paths, seed_real_project_case
from tests.fixtures.mock_llm import pipeline_mock_selector


@dataclass(frozen=True)
class AcceptanceRunSummary:
    project_id: str
    succeeded: bool
    slide_count: int
    asset_count: int
    record_path: Path


def run_acceptance_case(
    manifest_path: Path,
    *,
    session: Session,
    settings: object,
    scratch_dir: Path,
    update: bool = False,
) -> AcceptanceRunSummary:
    loaded, project, _paths = seed_real_project_case(session, manifest_path, scratch_dir=scratch_dir)
    record = _build_record(session, settings, loaded.manifest, project, loaded.request)
    if update:
        path = write_acceptance_record(record)
    else:
        assert_or_update_acceptance_record(record)
        path = record_path(record.project_id)
    return AcceptanceRunSummary(
        project_id=record.project_id,
        succeeded=record.metrics.generation_succeeded,
        slide_count=record.metrics.slide_count,
        asset_count=record.metrics.asset_count,
        record_path=path,
    )


def run_all_acceptance_cases(
    *,
    session: Session,
    settings: object,
    scratch_dir: Path,
    update: bool = False,
) -> list[RealProjectAcceptanceRecord]:
    records: list[RealProjectAcceptanceRecord] = []
    for manifest_path in list_manifest_paths():
        loaded, project, _paths = seed_real_project_case(session, manifest_path, scratch_dir=scratch_dir)
        record = _build_record(session, settings, loaded.manifest, project, loaded.request)
        if update:
            write_acceptance_record(record)
        else:
            assert_or_update_acceptance_record(record)
        records.append(record)
    return records


def _build_record(session, settings, manifest, project, request) -> RealProjectAcceptanceRecord:
    service = ProjectAcceptanceService(
        session,
        MockLLMProvider(selector=pipeline_mock_selector),
        settings=settings,  # type: ignore[arg-type]
    )
    return service.run(manifest, project=project, presentation_request=request)
