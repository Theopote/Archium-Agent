"""Showcase Case 001 — hospital renovation deck (~20 pages).

CI-safe outline + deck composition + LayoutSolver plans.
Full PPTX stays under ``scripts/showcase/case_001_hospital/outputs/`` (gitignored).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.visual.deck_composition_service import DeckCompositionPlanningService
from archium.application.visual.visual_grammar_intent import preferred_variant_for_intent
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual import default_presentation_design_system
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    climax_budget_for_deck,
    is_climax_peak,
)
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.showcase_score import (
    SHOWCASE_GATE_AESTHETIC_MIN,
    SHOWCASE_GATE_PROFESSIONALISM_MIN,
    SHOWCASE_GATE_TOTAL_MIN,
    empty_showcase_score,
)
from archium.domain.visual.style import (
    apply_style_preset,
    get_style_preset,
    resolve_style_preset_id,
)
from archium.domain.visual.style.presets import StylePresetId
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.layout.layout_solver import LayoutSolver

CASE_001_ID = "case_001_hospital"
CASE_001_DEFAULT_PRESET = StylePresetId.ARCHITECTURE_TECHNICAL.value
CASE_001_SKILL = "hospital-renovation-report"

# Fixed IDs for reproducible smoke snapshots (not persisted projects).
CASE_001_PRESENTATION_ID = UUID("a0010001-0001-4000-8000-000000000001")
CASE_001_ART_DIRECTION_ID = UUID("a0010001-0001-4000-8000-0000000000ad")

# Demo tour anchors (roadmap §4.3): cover → site → strategy → atmosphere.
DEMO_TOUR_TITLES: tuple[str, ...] = ("封面", "区位与交通", "设计策略", "效果表达")


@dataclass(frozen=True)
class Case001RenderBundle:
    """In-memory Case 001 deck ready for dry-run JSON or PPTX export."""

    slides: list[SlideSpec]
    intents: list[VisualIntent]
    plans: list[LayoutPlan]
    design: DesignSystem
    composition: DeckCompositionPlan
    style_preset_id: str


def showcase_case_001_dir() -> Path:
    """Repo-relative Case 001 pack directory."""
    return Path(__file__).resolve().parents[3] / "scripts" / "showcase" / "case_001_hospital"


def case_001_outputs_dir() -> Path:
    return showcase_case_001_dir() / "outputs"


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


def case_001_design_system(style_preset_id: str | None = None) -> DesignSystem:
    """Default DesignSystem with Case 001 Style Preset overlays."""
    preset_id = resolve_style_preset_id(style_preset_id or CASE_001_DEFAULT_PRESET)
    return apply_style_preset(
        default_presentation_design_system(),
        get_style_preset(preset_id),
    )


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
    slides: list[SlideSpec] | None = None,
    intents: list[VisualIntent] | None = None,
) -> DeckCompositionPlan:
    if slides is None or intents is None:
        slides, intents = build_case_001_deck(outline)
    return DeckCompositionPlanningService().plan(
        presentation_id=CASE_001_PRESENTATION_ID,
        art_direction_id=CASE_001_ART_DIRECTION_ID,
        slides=slides,
        visual_intents=intents,
    )


def build_case_001_render_bundle(
    *,
    outline: list[dict[str, Any]] | None = None,
    style_preset_id: str | None = None,
) -> Case001RenderBundle:
    """Outline → DeckComposition → Page Director → LayoutSolver (no LLM, no DB)."""
    from archium.application.visual.presentation_intelligence_service import (
        PresentationIntelligenceService,
    )

    preset = resolve_style_preset_id(style_preset_id or CASE_001_DEFAULT_PRESET).value
    design = case_001_design_system(preset)
    slides, intents = build_case_001_deck(outline)
    composition = plan_case_001_composition(slides=slides, intents=intents)
    intel = PresentationIntelligenceService()
    directed = intel.direct_deck_intents(
        slides, intents, composition, style_preset_id=preset
    )
    registry = get_layout_family_registry()
    solver = LayoutSolver()
    plans: list[LayoutPlan] = []
    clipped_slides: list[SlideSpec] = []

    for slide, intent in zip(slides, directed, strict=True):
        clipped = intel.clip_slide_copy(slide, intent)
        clipped_slides.append(clipped)
        families = list(intent.preferred_layout_families)
        family = families[0] if families else LayoutFamily.TEXTUAL_ARGUMENT
        variant = preferred_variant_for_intent(intent, family)
        variant = registry.resolve_variant(family, variant)
        plan = solver.generate(
            family,
            LayoutGeneratorContext(
                slide=clipped,
                visual_intent=intent,
                art_direction=None,
                design_system=design,
                content=intel.content_for_intent(clipped, intent),
                variant=variant,
            ),
        )
        direction = intent.page_direction
        if direction is not None and direction.visual_language is not None:
            from archium.application.visual.visual_language_apply import (
                apply_visual_language_to_plan,
            )

            plan = apply_visual_language_to_plan(
                plan,
                direction.visual_language,
                page_order=slide.order,
                visual_budget=direction.visual_budget,
            )
        plans.append(plan)

    return Case001RenderBundle(
        slides=clipped_slides,
        intents=directed,
        plans=plans,
        design=design,
        composition=composition,
        style_preset_id=preset,
    )


def write_case_001_dry_run(
    bundle: Case001RenderBundle,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Write layout plans + instruction deck JSON (no Node/PPTX)."""
    from archium.config.settings import Settings
    from archium.infrastructure.renderers.pptxgen_renderer import (
        PptxGenPresentationRenderer,
    )

    out = output_dir or case_001_outputs_dir()
    out.mkdir(parents=True, exist_ok=True)
    plans_dir = out / "layout_plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    for index, plan in enumerate(bundle.plans, start=1):
        path = plans_dir / f"slide_{index:02d}_{plan.layout_family.value}.json"
        path.write_text(
            json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    rhythm = assert_case_001_rhythm(bundle.composition)
    rhythm["style_preset_id"] = bundle.style_preset_id
    (out / "rhythm_snapshot.json").write_text(
        json.dumps(rhythm, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    renderer = PptxGenPresentationRenderer(Settings(_env_file=None))
    deck = renderer.build_layout_instruction_deck(
        title="医院更新汇报 — Showcase Case 001",
        plans=bundle.plans,
        design_system=bundle.design,
        slides=bundle.slides,
        project_id=None,
    )
    deck_path = out / "presentation.layout_instructions.json"
    deck_path.write_text(
        json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    from archium.application.visual.presentation_intelligence_service import (
        PresentationIntelligenceService,
    )

    intel_brief = PresentationIntelligenceService().build_brief(
        style_preset_id=bundle.style_preset_id,
        slides=bundle.slides,
        intents=bundle.intents,
        composition=bundle.composition,
        case_id=CASE_001_ID,
        demo_tour_titles=list(DEMO_TOUR_TITLES),
    )
    (out / "presentation_intelligence.json").write_text(
        json.dumps(intel_brief.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    page_claims = []
    visual_language_pages = []
    for slide, intent in zip(bundle.slides, bundle.intents, strict=True):
        direction = intent.page_direction
        if direction is None:
            continue
        card = direction.as_page_claim()
        card["title"] = slide.title
        card["order"] = slide.order
        page_claims.append(card)
        if direction.visual_language is not None:
            visual_language_pages.append(
                {
                    "title": slide.title,
                    "order": slide.order,
                    "visual_language": direction.visual_language.as_dict(),
                }
            )
    claims_path = out / "page_claims.json"
    claims_path.write_text(
        json.dumps(
            {
                "product_label": "页主张",
                "note": (
                    "Architects read claim / emotion / evidence_priority / avoid first; "
                    "derived_composition_bias is director output for layout, not input."
                ),
                "pages": page_claims,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    language_path = out / "visual_language.json"
    language_path.write_text(
        json.dumps(
            {
                "product_label": "视觉语言",
                "engine": "visual_language_v1",
                "note": (
                    "Typography / ColorStory / Decoration / Symbols — rhetoric layer "
                    "after VisualConcept, before Layout coordinates."
                ),
                "pages": visual_language_pages,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "case_id": CASE_001_ID,
        "mode": "dry_run",
        "slide_count": len(bundle.plans),
        "style_preset_id": bundle.style_preset_id,
        "output_dir": str(out),
        "layout_instructions": str(deck_path),
        "page_claims": str(claims_path),
        "visual_language": str(language_path),
        "demo_tour_titles": list(DEMO_TOUR_TITLES),
        "families": [plan.layout_family.value for plan in bundle.plans],
        "page_direction_hits": intel_brief.page_direction_hits,
        "project_personality": intel_brief.project_personality,
        "situation_rules_fired": intel_brief.situation_rules_fired,
    }
    (out / "render_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def export_case_001_pptx(
    bundle: Case001RenderBundle,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """LayoutPlan → render-plan.mjs → presentation.pptx (requires Node)."""
    from archium.config.settings import Settings
    from archium.infrastructure.renderers.pptxgen_renderer import (
        PptxGenPresentationRenderer,
    )

    summary = write_case_001_dry_run(bundle, output_dir=output_dir)
    out = Path(summary["output_dir"])
    renderer = PptxGenPresentationRenderer(Settings(_env_file=None))
    if not renderer.is_available():
        summary["mode"] = "dry_run_only"
        summary["pptx_path"] = None
        summary["note"] = (
            "Node/pptxgenjs unavailable; wrote layout instructions only. "
            "Install deps under archium/infrastructure/renderers/pptxgen."
        )
        (out / "render_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary

    deck_json, pptx_path = renderer.render_and_export_pptx_from_layout_plans(
        title="医院更新汇报 — Showcase Case 001",
        plans=bundle.plans,
        design_system=bundle.design,
        output_dir=out,
        slides=bundle.slides,
        project_id=None,
    )
    target = out / "presentation.pptx"
    if pptx_path.resolve() != target.resolve() and pptx_path.is_file():
        target.write_bytes(pptx_path.read_bytes())
    summary.update(
        {
            "mode": "pptx",
            "pptx_path": str(target if target.is_file() else pptx_path),
            "layout_instructions": str(deck_json),
            "note": None,
        }
    )
    (out / "render_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


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
