"""Phase 5 spike — five page archetypes end-to-end validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from archium.application.slide_recovery_service import SlideRecoveryRequest, SlideRecoveryService
from archium.domain.slide_recovery import (
    SIMILARITY_TARGET,
    TEXT_POSITION_ERROR_MAX,
    TEXT_RECALL_TARGET,
    SlideRecoveryPageKind,
)
from tests.spike.slide_recovery_fixtures import SPIKE_SCENES

_REPORT_DIR = Path(__file__).resolve().parent / "artifacts"


@pytest.fixture(scope="module")
def service() -> SlideRecoveryService:
    return SlideRecoveryService(session=None)


@pytest.mark.parametrize("page_kind", list(SlideRecoveryPageKind))
def test_spike_page_archetype(
    service: SlideRecoveryService,
    page_kind: SlideRecoveryPageKind,
) -> None:
    source = SPIKE_SCENES[page_kind]
    result = service.recover_page(
        SlideRecoveryRequest(
            source_page_id=f"spike_{page_kind.value}",
            source_scene=source,
            page_kind=page_kind,
        )
    )
    assert result.metrics is not None
    metrics = result.metrics

    assert metrics.text_recall >= TEXT_RECALL_TARGET, page_kind.value
    assert metrics.text_position_error <= TEXT_POSITION_ERROR_MAX, page_kind.value
    assert metrics.similarity_score >= SIMILARITY_TARGET, page_kind.value
    assert metrics.drawing_integrity_ok, page_kind.value
    assert metrics.asset_identity_preserved, page_kind.value

    if page_kind == SlideRecoveryPageKind.DRAWING_DOMINANT:
        assert metrics.line_recall >= 0.90

    assert result.hybrid_scene is not None
    assert result.hybrid_scene.scene.nodes


def test_spike_report_artifact(service: SlideRecoveryService, tmp_path: Path) -> None:
    """Emit a JSON summary for manual spike review (under tmp, not committed)."""
    rows: list[dict[str, object]] = []
    for page_kind, source in SPIKE_SCENES.items():
        result = service.recover_page(
            SlideRecoveryRequest(
                source_page_id=f"spike_{page_kind.value}",
                source_scene=source,
                page_kind=page_kind,
            )
        )
        rows.append(
            {
                "page_kind": page_kind.value,
                "fidelity": result.reconstruction_fidelity.value,
                "metrics": result.metrics.model_dump() if result.metrics else {},
                "warnings": result.warnings,
                "blockers": result.blockers,
            }
        )

    report_path = tmp_path / "slide_recovery_spike.json"
    report_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    assert report_path.is_file()
    assert len(rows) == 5
