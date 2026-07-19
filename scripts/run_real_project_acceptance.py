#!/usr/bin/env python3
"""Run five real-project acceptance scenarios and write acceptance records."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.e2e.real_projects.artifacts import UPDATE_ENV  # noqa: E402
from tests.e2e.real_projects.runner import run_all_acceptance_cases  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Rewrite acceptance record baselines")
    args = parser.parse_args(argv)

    if args.update:
        os.environ[UPDATE_ENV] = "1"

    from archium.config.settings import Settings
    from archium.infrastructure.database.base import Base
    from archium.infrastructure.database.session import create_engine_from_settings, get_session

    settings = Settings(
        _env_file=None,
        database_path=_PROJECT_ROOT / ".data" / "acceptance" / "acceptance.db",
        workflow_checkpoint_path=_PROJECT_ROOT / ".data" / "acceptance" / "checkpoints.db",
        project_storage_path=_PROJECT_ROOT / ".data" / "acceptance" / "projects",
        output_path=_PROJECT_ROOT / ".data" / "acceptance" / "outputs",
        chroma_path=_PROJECT_ROOT / ".data" / "acceptance" / "chroma",
        llm_api_key=None,
        embedding_provider="mock",
        retrieval_enabled=True,
    )
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)

    with tempfile.TemporaryDirectory() as scratch, get_session(engine) as session:
        records = run_all_acceptance_cases(
            session=session,
            settings=settings,
            scratch_dir=Path(scratch),
            update=args.update,
        )

    for record in records:
        print(
            f"{record.project_id}: slides={record.metrics.slide_count} "
            f"assets={record.metrics.asset_count} "
            f"ok={record.metrics.generation_succeeded}"
        )
    print(f"Processed {len(records)} real-project acceptance scenario(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
