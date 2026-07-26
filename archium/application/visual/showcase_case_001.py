"""Showcase Case 001 — hospital renovation deck (~20 pages).

CI-safe outline + deck composition smoke. Full PPTX stays under
``scripts/showcase/case_001_hospital/outputs/`` (gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.visual.deck_composition_service import DeckCompositionPlanningService
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    climax_budget_for_deck,
    is_climax_peak,
)
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.showcase_score import (
    SHOWCASE_GATE_AESTHETIC_MIN,
    SHOWCASE_GATE_PROFESSIONALISM_MIN,
    SHOWCASE_GATE_TOTAL_MIN,
    empty_showcase_score,
)
from archium.domain.visual.style.presets import StylePresetId
from archium.domain.visual.visual_intent import VisualIntent

CASE_001_ID = "case_001_hospital"
CASE_001_DEFAULT_PRESET = StylePresetId.ARCHITECTURE_TECHNICAL.value
CASE_001_SKILL = "hospital-renovation-report"

# Fixed IDs for reproducible smoke snapshots (not persisted projects).
CASE_001_PRESENTATION_ID = UUID("a0010001-0001-4000-8000-000000000001")
CASE_001_ART_DIRECTION_ID = UUID("a0010001-0001-4000-8000-0000000000ad")

# Demo tour anchors (roadmap §4.3): cover → site → strategy → atmosphere.
DEMO_TOUR_TITLES: tuple[str, ...] = ("封面", "区位与交通", "设计策略", "效果表达")


def showcase_case_001_dir() -> Path:
    """Repo-relative Case 001 pack directory."""
    return Path(__file__).resolve().parents[3] / "scripts" / "showcase" / "case_001_hospital"


def load_case_001_manifest(path: Path | None = None) -> dict[str, Any]:
    target = path or (showcase_case_001_dir() / "manifest.json")
    return json.loads(target.read_text(encoding="utf-8"))


def load_case_001_outline(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or (showcase_case_001_dir() / "outline.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError(f"Case 001 outline missing slides: {target}")
    return slides


def build_case_001_deck(
    outline: list[dict[str, Any]] | None = None,
    *,
    presentation_id: UUID | None = None,
) -> tuple[list[SlideSpec], list[VisualIntent]]:
    """Build SlideSpec + VisualIntent lists from the Case 001 outline JSON."""
    rows = outline if outline is not None else load_case_001_outline()
    presentation_id = presentation_id or CASE_001_PRESENTATION_ID
    slides: list[SlideSpec] = []
    intents: list[VisualIntent] = []
    for order, row in enumerate(rows):
        title = str(row["title"])
        chapter = str(row.get("chapter") or _chapter_for_order(order))
        slide = SlideSpec(
            presentation_id=presentation_id,
            chapter_id=chapter,
            order=order,
            title=title,
            message=str(row.get("message") or f"{title} — 医院更新汇报"),
            slide_type=SlideType(str(row["slide_type"])),
            key_points=list(row.get("key_points") or [f"{title}-1", f"{title}-2"]),
        )
        slides.append(slide)
        intents.append(
            VisualIntent(
                slide_id=slide.id,
                presentation_id=presentation_id,
                communication_goal=str(
                    row.get("communication_goal") or f"传达{title}"
                ),
                audience_takeaway=slide.message,
                visual_priority="title > visual > body",
                dominant_content_type=VisualContentType(
                    str(row["dominant_content_type"])
                ),
                preferred_layout_families=[
                    LayoutFamily(str(row["preferred_layout_family"]))
                ],
                density_level=DensityLevel.COMPACT,
                continuity_role=ContinuityRole(str(row["continuity_role"])),
            )
        )
    return slides, intents


def plan_case_001_composition(
    *,
    outline: list[dict[str, Any]] | None = None,
) -> DeckCompositionPlan:
    slides, intents = build_case_001_deck(outline)
    return DeckCompositionPlanningService().plan(
        presentation_id=CASE_001_PRESENTATION_ID,
        art_direction_id=CASE_001_ART_DIRECTION_ID,
        slides=slides,
        visual_intents=intents,
    )


def assert_case_001_rhythm(plan: DeckCompositionPlan) -> dict[str, Any]:
    """CI assertions for Case 001 deck rhythm (no PPTX required)."""
    directives = plan.slide_directives
    if len(directives) != 20:
        raise AssertionError(f"Case 001 expects 20 slides, got {len(directives)}")
    peaks = [d for d in directives if is_climax_peak(d)]
    budget = climax_budget_for_deck(20)
    if len(peaks) > budget:
        raise AssertionError(f"climax overload: {len(peaks)} > budget {budget}")
    density_values = set(plan.density_curve)
    if len(density_values) < 2:
        raise AssertionError("density curve is flat")
    snapshot = {
        "case_id": CASE_001_ID,
        "slide_count": len(directives),
        "style_preset_id": CASE_001_DEFAULT_PRESET,
        "climax_budget": budget,
        "peak_count": len(peaks),
        "density_curve": list(plan.density_curve),
        "demo_tour_titles": list(DEMO_TOUR_TITLES),
        "gate": {
            "total_min": SHOWCASE_GATE_TOTAL_MIN,
            "aesthetic_min": SHOWCASE_GATE_AESTHETIC_MIN,
            "professionalism_min": SHOWCASE_GATE_PROFESSIONALISM_MIN,
        },
    }
    return snapshot


def scorecard_template() -> dict[str, Any]:
    score = empty_showcase_score(
        CASE_001_ID, style_preset_id=CASE_001_DEFAULT_PRESET
    )
    payload = score.model_dump(mode="json")
    payload["gate"] = {
        "total_min": SHOWCASE_GATE_TOTAL_MIN,
        "aesthetic_min": SHOWCASE_GATE_AESTHETIC_MIN,
        "professionalism_min": SHOWCASE_GATE_PROFESSIONALISM_MIN,
        "total_max": 50,
    }
    payload["skill"] = CASE_001_SKILL
    return payload


def _chapter_for_order(order: int) -> str:
    if order < 3:
        return "intro"
    if order < 8:
        return "site"
    if order < 14:
        return "strategy"
    return "delivery"
