#!/usr/bin/env python3
"""Record real LLM responses into golden fixture cache files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.session import create_engine_from_settings
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.factory import create_llm_provider
from sqlalchemy.orm import Session
from tests.golden.fixtures.loader import load_fixture_case, seed_fixture_case
from tests.golden.regression.loader import load_regression_case, seed_regression_case

T = TypeVar("T", bound=BaseModel)

_CACHE_DIR = ROOT / "tests" / "golden" / "fixtures" / "llm_cache"


def resolve_cache_needle(request: LLMRequest) -> str | None:
    """Map an LLM request to a stable cache key (matched as substring)."""
    user_prompt = request.user_prompt
    if "生成 PresentationBrief JSON" in user_prompt:
        return "生成 PresentationBrief JSON"
    if "生成 Storyline JSON" in user_prompt:
        return "生成 Storyline JSON"
    slide_match = re.search(r"请生成约 (\d+) 页的 SlidePlan JSON", user_prompt)
    if slide_match:
        return f"请生成约 {slide_match.group(1)} 页"
    if "FactExtraction" in user_prompt or "ProjectFact JSON" in user_prompt:
        return "FactExtraction"
    if "BriefAlignment JSON" in user_prompt:
        return "BriefAlignment JSON"
    if "ProfessionalReview JSON" in user_prompt:
        return "ProfessionalReview JSON"
    if "ProfessionalReview" in user_prompt:
        return "ProfessionalReview"
    if "修订以下页面 JSON" in user_prompt:
        return "修订以下页面 JSON"
    return None


class RecordingLLMProvider:
    """Wrap a real LLM provider and capture prompt needles → JSON responses."""

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.recordings: dict[str, str] = {}

    def generate_text(self, request: LLMRequest) -> str:
        content = self._inner.generate_text(request)
        self._record(request, content)
        return content

    def generate_structured(self, request: LLMRequest, schema: type[T]) -> T:
        result = self._inner.generate_structured(request, schema)
        raw = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        self._record(request, raw)
        return result

    def _record(self, request: LLMRequest, content: str) -> None:
        needle = resolve_cache_needle(request)
        if needle is None:
            return
        if needle not in self.recordings:
            self.recordings[needle] = content


def _ordered_cache_entries(recordings: dict[str, str]) -> dict[str, str]:
    """Prefer longer needles first so slide-count-specific keys win over generic ones."""
    priority = [
        "请生成约",
        "BriefAlignment JSON",
        "ProfessionalReview JSON",
        "ProfessionalReview",
        "生成 PresentationBrief JSON",
        "生成 Storyline JSON",
        "FactExtraction",
        "修订以下页面 JSON",
    ]

    def sort_key(item: tuple[str, str]) -> tuple[int, str]:
        needle = item[0]
        for index, prefix in enumerate(priority):
            if needle.startswith(prefix) or prefix in needle:
                return (index, needle)
        return (len(priority), needle)

    return dict(sorted(recordings.items(), key=sort_key))


def run_case(
    *,
    case_id: str,
    source: str,
    settings: Settings,
    scratch_dir: Path,
) -> dict[str, str]:
    llm = RecordingLLMProvider(create_llm_provider(settings))
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session = Session(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    try:
        if source == "regression":
            case_path = ROOT / "tests" / "golden" / "regression" / "cases" / f"{case_id}.json"
            case, project = seed_regression_case(session, case_path)
        else:
            manifest_path = ROOT / "tests" / "golden" / "fixtures" / "manifests" / f"{case_id}.fixture.json"
            case, project, _ = seed_fixture_case(session, manifest_path, scratch_dir=scratch_dir)

        service = PresentationWorkflowService(session, llm, settings=settings)
        try:
            service.run(
                project.id,
                case.request,
                export_json=True,
                export_marp=False,
                export_presentation_spec=case.export_presentation_spec,
                require_brief_review=False,
                require_storyline_review=False,
                require_outline_review=False,
                require_slides_review=False,
            )
        finally:
            service.close()
        session.commit()
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

    return _ordered_cache_entries(llm.recordings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case_id",
        help="Golden case id, e.g. case_a_hospital or case_d_full_deck",
    )
    parser.add_argument(
        "--source",
        choices=("fixture", "regression"),
        default="fixture",
        help="Load case from L2 fixture manifest or L1 regression JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output cache path (default: tests/golden/fixtures/llm_cache/<case_id>.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print captured cache entries without writing",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.llm_provider.lower() == "mock":
        print("Error: set LLM_PROVIDER to openai_compatible (or similar) before recording.", file=sys.stderr)
        return 1
    if not settings.llm_configured:
        print("Error: configure LLM_API_KEY / GEMINI_API_KEY in .env before recording.", file=sys.stderr)
        return 1

    scratch_dir = ROOT / ".cache" / "record_llm_cache"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "regression":
        case_path = ROOT / "tests" / "golden" / "regression" / "cases" / f"{args.case_id}.json"
        if not case_path.exists():
            print(f"Error: regression case not found: {case_path}", file=sys.stderr)
            return 1
        load_regression_case(case_path)
    else:
        manifest_path = ROOT / "tests" / "golden" / "fixtures" / "manifests" / f"{args.case_id}.fixture.json"
        if not manifest_path.exists():
            print(f"Error: fixture manifest not found: {manifest_path}", file=sys.stderr)
            return 1
        load_fixture_case(manifest_path)

    print(f"Recording LLM cache for {args.case_id} ({args.source})...")
    entries = run_case(
        case_id=args.case_id,
        source=args.source,
        settings=settings,
        scratch_dir=scratch_dir,
    )
    if not entries:
        print("Warning: no cache entries captured.", file=sys.stderr)
        return 1

    output_path = args.output or (_CACHE_DIR / f"{args.case_id}.json")
    payload = json.dumps(entries, ensure_ascii=False, indent=2)
    if args.dry_run:
        print(payload)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{payload}\n", encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
