#!/usr/bin/env python3
"""Run Mission golden cases M1–M6 against a real LLM and emit human scorecards.

Usage (PowerShell):

    $env:ARCHIUM_LIVE_LLM = "1"
    py scripts/eval_mission_live.py
    py scripts/eval_mission_live.py --case case_m1_temple
    py scripts/eval_mission_live.py --case m6

Artifacts land in tests/golden/artifacts/live_mission/<run_id>/
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.session import create_engine_from_settings
from archium.infrastructure.llm.factory import create_llm_provider
from sqlalchemy.orm import Session
from tests.golden.live.mission_eval import (
    live_artifacts_root,
    run_mission_live_case,
    write_run_summary,
)
from tests.golden.mission.loader import list_mission_case_paths, load_mission_case


def _match_case(path: Path, needle: str) -> bool:
    case = load_mission_case(path)
    key = needle.lower().strip()
    return key in {
        case.id.lower(),
        path.stem.lower(),
        case.name.lower(),
        key,
    } or key in case.id.lower() or key in path.stem.lower()


def _build_live_settings(base: Settings) -> Settings:
    if not base.llm_configured:
        raise SystemExit(
            "LLM API key not configured. Set GEMINI_API_KEY / LLM_API_KEY in .env "
            "or configure via the app settings."
        )
    if base.llm_provider.lower() == "mock":
        raise SystemExit(
            "llm_provider is 'mock'. Point .env to a real provider before live eval."
        )
    tmp = Path(tempfile.mkdtemp(prefix="archium-live-mission-"))
    (tmp / "database").mkdir(parents=True)
    return Settings(
        _env_file=None,
        database_path=tmp / "database" / "live.db",
        workflow_checkpoint_path=tmp / "database" / "workflow_checkpoints.db",
        project_storage_path=tmp / "projects",
        output_path=tmp / "outputs",
        chroma_path=tmp / "chroma",
        llm_provider=base.llm_provider,
        llm_api_key=base.llm_api_key,
        llm_base_url=base.llm_base_url,
        llm_model=base.llm_model,
        llm_timeout_seconds=max(float(base.llm_timeout_seconds), 120.0),
        llm_max_retries=base.llm_max_retries,
        llm_repair_attempts=base.llm_repair_attempts,
        embedding_provider="mock",
        retrieval_enabled=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Mission golden evaluation (M1-M6)")
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Case id/stem/name substring (repeatable). Default: all M1-M6.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run id (default: timestamp + short uuid).",
    )
    args = parser.parse_args(argv)

    env = get_settings()
    settings = _build_live_settings(env)
    llm = create_llm_provider(settings)
    run_id = args.run_id or (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )

    paths = list_mission_case_paths()
    if args.case:
        selected: list[Path] = []
        for needle in args.case:
            matched = [path for path in paths if _match_case(path, needle)]
            if not matched:
                raise SystemExit(f"No mission case matched --case {needle!r}")
            selected.extend(matched)
        # stable unique
        paths = list(dict.fromkeys(selected))

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    results = []
    print(f"Live mission eval run_id={run_id}")
    print(f"Model={settings.llm_model} provider={settings.llm_provider}")
    print(f"Cases={', '.join(p.stem for p in paths)}")
    print(f"Artifacts → {live_artifacts_root() / run_id}")

    try:
        for path in paths:
            session = Session(
                bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
            )
            try:
                print(f"\n=== Running {path.stem} ===")
                result = run_mission_live_case(
                    session,
                    llm,
                    settings,
                    path,
                    run_id=run_id,
                    write_artifacts=True,
                )
                session.commit()
                results.append(result)
                flags = ", ".join(result.auto_flags) if result.auto_flags else "none"
                print(f"  flags: {flags}")
                print(f"  scorecard: {result.artifact_dir / 'SCORECARD.md'}")
                if result.has_critical_flags:
                    print("  CRITICAL flags present — review before trusting scores.")
            except Exception as exc:
                session.rollback()
                print(f"  FAILED: {exc}")
                raise
            finally:
                session.close()
    finally:
        engine.dispose()

    summary = write_run_summary(live_artifacts_root() / run_id, results)
    print(f"\nSummary: {summary}")
    critical = [r.case.id for r in results if r.has_critical_flags]
    if critical:
        print("Critical cases:", ", ".join(critical))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
