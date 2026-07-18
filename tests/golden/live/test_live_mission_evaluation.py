"""Layer 3: live LLM evaluation for Mission golden cases M1–M6."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from archium.config.settings import Settings, get_settings
from archium.infrastructure.llm.factory import create_llm_provider
from sqlalchemy.orm import Session
from tests.golden.live.mission_eval import (
    live_artifacts_root,
    run_mission_live_case,
)
from tests.golden.mission.loader import list_mission_case_paths

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("ARCHIUM_LIVE_LLM") != "1",
        reason="Live LLM evaluation requires ARCHIUM_LIVE_LLM=1 and configured API keys",
    ),
]


@pytest.fixture
def live_settings(test_settings: Settings) -> Settings:
    env = get_settings()
    if not env.llm_configured:
        pytest.skip("Live LLM evaluation requires llm_api_key in environment / .env")
    return test_settings.model_copy(
        update={
            "llm_provider": env.llm_provider,
            "llm_api_key": env.llm_api_key,
            "llm_base_url": env.llm_base_url,
            "llm_model": env.llm_model,
            "llm_timeout_seconds": max(float(env.llm_timeout_seconds), 120.0),
            "llm_max_retries": env.llm_max_retries,
            "llm_repair_attempts": env.llm_repair_attempts,
        }
    )


@pytest.fixture(scope="module")
def live_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]


@pytest.mark.parametrize("case_path", list_mission_case_paths(), ids=lambda p: p.stem)
def test_live_mission_case(
    db_session: Session,
    live_settings: Settings,
    live_run_id: str,
    case_path: Path,
) -> None:
    llm = create_llm_provider(live_settings)
    result = run_mission_live_case(
        db_session,
        llm,
        live_settings,
        case_path,
        run_id=live_run_id,
        write_artifacts=True,
    )

    assert result.generation.mission.task_statement.strip()
    assert result.workstreams
    assert result.plan.deliverables
    assert result.artifact_dir is not None
    assert (result.artifact_dir / "scorecard.json").is_file()
    assert (result.artifact_dir / "SCORECARD.md").is_file()

    # Critical quality gates that should not depend on "lucky" mock JSON.
    assert "fabricated_metrics" not in result.auto_flags, (
        "live model appears to fabricate metrics: " + "; ".join(result.auto_notes)
    )
    if result.case.id == "case_m6_green_campus":
        assert "consulting_as_full_design" not in result.auto_flags, (
            "M6 consulting task misclassified as full design: "
            + "; ".join(result.auto_notes)
        )

    # Keep a running SUMMARY.md for the human reviewer.
    run_dir = live_artifacts_root() / live_run_id
    case_dirs = sorted(p.name for p in run_dir.iterdir() if p.is_dir())
    summary_lines = [
        f"# Mission Live Evaluation Summary — `{live_run_id}`",
        "",
        f"Model: `{live_settings.llm_model}`",
        f"Cases completed so far: {len(case_dirs)}",
        "",
    ]
    for name in case_dirs:
        summary_lines.append(f"- `{name}` → `{name}/SCORECARD.md`")
    (run_dir / "SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
