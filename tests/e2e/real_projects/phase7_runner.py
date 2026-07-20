"""Run Phase 7 real-project acceptance scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.application.project_acceptance_service import ProjectAcceptanceService
from archium.domain.project_acceptance import RealProjectAcceptanceRecord
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session

from tests.e2e.real_projects.loader import seed_real_project_case
from tests.e2e.real_projects.phase7_artifacts import (
    acceptance_record_path,
    assert_or_update_phase7_acceptance_record,
    write_phase7_acceptance_record,
)
from tests.e2e.real_projects.phase7_loader import (
    load_phase7_project,
    resolve_input_manifest_path,
)
from tests.fixtures.mock_llm import pipeline_mock_selector


@dataclass(frozen=True)
class Phase7AcceptanceRunSummary:
    project_id: str
    succeeded: bool
    slide_count: int
    asset_count: int
    record: RealProjectAcceptanceRecord
    record_path: Path


def run_phase7_acceptance_case(
    project_id: str,
    *,
    session: Session,
    settings: object,
    scratch_dir: Path,
    update: bool = False,
    compare_baseline: bool = False,
) -> Phase7AcceptanceRunSummary:
    bundle = load_phase7_project(project_id)
    manifest_path = resolve_input_manifest_path(bundle)
    loaded, project, _paths = seed_real_project_case(session, manifest_path, scratch_dir=scratch_dir)
    record = _build_record(session, settings, loaded.manifest, project, loaded.request)
    record = record.model_copy(
        update={
            "project_id": bundle.profile.id,
            "scenario": bundle.profile.scenario,
            "title": bundle.profile.name,
        }
    )
    if update:
        path = write_phase7_acceptance_record(record)
    elif compare_baseline:
        assert_or_update_phase7_acceptance_record(record)
        path = acceptance_record_path(record.project_id)
    else:
        path = acceptance_record_path(record.project_id)
    return Phase7AcceptanceRunSummary(
        project_id=record.project_id,
        succeeded=record.metrics.generation_succeeded,
        slide_count=record.metrics.slide_count,
        asset_count=record.metrics.asset_count,
        record=record,
        record_path=path,
    )


def _build_record(session, settings, manifest, project, request) -> RealProjectAcceptanceRecord:
    service = ProjectAcceptanceService(
        session,
        MockLLMProvider(selector=pipeline_mock_selector),
        settings=settings,  # type: ignore[arg-type]
    )
    return service.run(manifest, project=project, presentation_request=request)
