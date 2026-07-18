#!/usr/bin/env python3
"""Regenerate PNG visual baselines for golden visual regression cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.config.settings import Settings  # noqa: E402
from archium.infrastructure.database.base import Base  # noqa: E402
from archium.infrastructure.database.session import create_engine_from_settings  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from tests.golden.visual.baseline import (  # noqa: E402
    VISUAL_CASE_IDS,
    build_manifest,
    save_baseline,
)
from tests.golden.visual.runner import run_visual_baseline_case  # noqa: E402


def _build_settings(output_root: Path) -> Settings:
    base = output_root / "visual-baseline-work"
    (base / "database").mkdir(parents=True, exist_ok=True)
    return Settings(
        _env_file=None,
        database_path=base / "database" / "test.db",
        workflow_checkpoint_path=base / "database" / "workflow_checkpoints.db",
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
        llm_api_key="baseline-key",
        embedding_provider="mock",
        retrieval_enabled=True,
        marp_preview_images_enabled=True,
        marp_preview_image_format="png",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_PROJECT_ROOT / "data" / "tmp",
        help="Temporary working directory for DB/output (default: data/tmp)",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="Case id to refresh (default: all visual baseline cases)",
    )
    args = parser.parse_args(argv)
    case_ids = tuple(args.cases or VISUAL_CASE_IDS)

    settings = _build_settings(args.output_root)
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session = Session(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    try:
        for case_id in case_ids:
            run = run_visual_baseline_case(session, settings, case_id)
            manifest = build_manifest(
                case_id=case_id,
                slides=list(run.workflow.slides),
                preview_paths=list(run.preview_paths),
            )
            out_dir = save_baseline(case_id, manifest, list(run.preview_paths))
            print(f"Updated {out_dir} ({manifest.preview_count} previews)")
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
