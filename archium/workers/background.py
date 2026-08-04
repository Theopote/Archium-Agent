"""Poll and execute durable ``background_jobs``.

Usage::

    python -m archium.workers.background --once
    python -m archium.workers.background --poll 2
    archium-worker --once
"""

from __future__ import annotations

import argparse
import time

from archium.application.background_job_worker import BackgroundJobWorker
from archium.infrastructure.database import session as db_session
from archium.logging import get_logger

logger = get_logger(__name__, operation="background_worker")


def run_worker_loop(
    *,
    once: bool = False,
    poll_seconds: float = 2.0,
    max_jobs: int | None = None,
) -> int:
    """Claim and process jobs until idle (``once``) or forever.

    Returns the number of jobs processed.
    """
    processed = 0
    poll = max(0.2, float(poll_seconds))
    while True:
        job = None
        try:
            with db_session.get_session() as session:
                job = BackgroundJobWorker(session).process_once()
        except Exception:
            logger.exception("Worker tick failed")
            if once:
                raise
            time.sleep(poll)
            continue

        if job is None:
            if once or (max_jobs is not None and processed >= max_jobs):
                break
            time.sleep(poll)
            continue

        processed += 1
        logger.info(
            "Processed background job %s kind=%s status=%s",
            job.id,
            job.kind.value,
            job.status.value,
        )
        if once or (max_jobs is not None and processed >= max_jobs):
            break
    return processed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archium-worker",
        description="Process durable Archium background_jobs.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job (or exit immediately if queue empty).",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Idle poll interval when running continuously (default: 2).",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        metavar="N",
        help="Stop after processing N jobs (continuous mode).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count = run_worker_loop(
        once=bool(args.once),
        poll_seconds=float(args.poll),
        max_jobs=args.max_jobs,
    )
    if args.once:
        print(f"processed={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
