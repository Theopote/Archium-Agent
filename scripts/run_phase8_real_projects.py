#!/usr/bin/env python3
"""Run Phase 8 real-project RenderScene deliverable pipelines."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.e2e.real_projects.phase8_artifacts import (  # noqa: E402
    PHASE8_PROJECT_IDS,
    assert_phase8_hard_artifacts,
    inspect_phase8_artifacts,
)
from tests.e2e.real_projects.phase8_runner import run_all_phase8_projects  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        choices=list(PHASE8_PROJECT_IDS),
        help="Run one project (repeatable). Default: both Phase 8 projects.",
    )
    parser.add_argument(
        "--assert-hard",
        action="store_true",
        help="Fail if hard artifact checklist is incomplete after the run.",
    )
    parser.add_argument(
        "--min-slides",
        type=int,
        default=15,
        help="Minimum slide count when --assert-hard is set (default: 15).",
    )
    args = parser.parse_args(argv)

    from archium.config.settings import Settings
    from archium.infrastructure.database.base import Base
    from archium.infrastructure.database.session import create_engine_from_settings, get_session

    data_root = _PROJECT_ROOT / ".data" / "phase8"
    settings = Settings(
        _env_file=None,
        database_path=data_root / "phase8.db",
        workflow_checkpoint_path=data_root / "checkpoints.db",
        project_storage_path=data_root / "projects",
        output_path=data_root / "outputs",
        chroma_path=data_root / "chroma",
        llm_api_key=None,
        embedding_provider="mock",
        retrieval_enabled=True,
    )
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)

    with tempfile.TemporaryDirectory() as scratch, get_session(engine) as session:
        summaries = run_all_phase8_projects(
            session=session,
            settings=settings,
            scratch_dir=Path(scratch),
            project_ids=args.project_ids,
        )

    exit_code = 0
    for summary in summaries:
        checklist = inspect_phase8_artifacts(summary.project_id)
        soft = ", ".join(summary.soft_notes) if summary.soft_notes else "none"
        print(
            f"{summary.project_id}: slides={summary.slide_count} "
            f"pptx={'yes' if summary.pptx_path else 'no'} "
            f"pdf={'yes' if summary.pdf_path else 'no'} "
            f"shots={summary.screenshot_count} "
            f"hard_ok={checklist.hard_ok} "
            f"succeeded={summary.succeeded} "
            f"outputs={summary.outputs_dir}"
        )
        print(f"  soft_notes: {soft}")
        if args.assert_hard:
            try:
                assert_phase8_hard_artifacts(summary.project_id, min_slides=args.min_slides)
            except AssertionError as exc:
                print(f"  ASSERT FAIL: {exc}")
                exit_code = 1

    print(f"Processed {len(summaries)} Phase 8 project(s).")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
