"""Build and evaluate architectural slide visual benchmark cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from archium.application.visual.deck_qa_service import DeckQAService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.citation import Citation
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.benchmark import BenchmarkCaseDefinition, BenchmarkRuleScore
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    LayoutGeneratorContext,
    content_from_slide,
)
from archium.infrastructure.layout.layout_solver import LayoutSolver

BENCHMARK_PRESENTATION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BENCHMARK_DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@dataclass(frozen=True)
class BenchmarkSlideContent:
    """Optional structured content overrides for layout generation."""

    key_points: list[str] | None = None
    metrics: list[str] | None = None
    captions: list[str] | None = None
    insight: str | None = None
    hero_asset_id: UUID | None = None
    supporting_asset_ids: list[UUID] | None = None
    dominant_content_type: VisualContentType | None = None
    preferred_layout_families: list[LayoutFamily] | None = None
    drawing_hero: bool = False


@dataclass(frozen=True)
class BenchmarkCaseBuildRequest:
    """Inputs required to build one benchmark slide."""

    definition: BenchmarkCaseDefinition
    design_system: DesignSystem
    title: str
    message: str
    visual_requirements: list[VisualRequirement]
    content: BenchmarkSlideContent | None = None
    source_page: int = 1
    source_document: str = "项目资料.pdf"


@dataclass(frozen=True)
class BenchmarkCaseResult:
    """Resolved artifacts for one architectural benchmark case."""

    definition: BenchmarkCaseDefinition
    slide: SlideSpec
    intent: VisualIntent
    design_system: DesignSystem
    plan: LayoutPlan
    report: LayoutValidationReport
    rule_score: BenchmarkRuleScore


class BenchmarkService:
    """Deterministic benchmark case builder (no LLM, no database)."""

    def __init__(
        self,
        *,
        intent_service: VisualIntentService | None = None,
        validation_service: LayoutValidationService | None = None,
        deck_qa_service: DeckQAService | None = None,
    ) -> None:
        self._intents = intent_service or _standalone_intent_service()
        self._validation = validation_service or LayoutValidationService()
        self._deck_qa = deck_qa_service or DeckQAService()
        self._solver = LayoutSolver()

    def build_case(self, request: BenchmarkCaseBuildRequest) -> BenchmarkCaseResult:
        definition = request.definition
        content_input = request.content
        slide = SlideSpec(
            presentation_id=BENCHMARK_PRESENTATION_ID,
            chapter_id=definition.chapter_id,
            order=definition.slide_order,
            title=request.title,
            message=request.message,
            key_points=list(content_input.key_points or []) if content_input else [],
            visual_requirements=list(request.visual_requirements),
            source_citations=[
                Citation(
                    document_id=BENCHMARK_DOCUMENT_ID,
                    document_name=request.source_document,
                    page_number=request.source_page,
                )
            ],
        )
        intent = self._intents.generate_for_slide(slide, use_llm=False)
        content_override = request.content
        if content_override is not None:
            if content_override.dominant_content_type is not None:
                intent.dominant_content_type = content_override.dominant_content_type
            if content_override.preferred_layout_families is not None:
                intent.preferred_layout_families = list(
                    content_override.preferred_layout_families
                )
            if content_override.hero_asset_id is not None:
                intent.hero_asset_id = content_override.hero_asset_id
            if content_override.supporting_asset_ids is not None:
                intent.supporting_asset_ids = list(content_override.supporting_asset_ids)

        content = self._content_bundle(slide, intent, content_override)
        context = LayoutGeneratorContext(
            slide=slide,
            visual_intent=intent,
            art_direction=None,
            design_system=request.design_system,
            content=content,
            variant=definition.layout_variant,
        )
        plan = self._solver.generate(definition.expected_layout_family, context)
        report = self._validation.validate(
            plan,
            request.design_system,
            require_source=True,
            drawing_hero=content_override.drawing_hero
            if content_override is not None
            else False,
        )
        deck_report = self._deck_qa.evaluate(
            [plan],
            slides=[slide],
            design_system=request.design_system,
        )
        rule_score = BenchmarkRuleScore(
            case_id=definition.case_id,
            layout_valid=report.valid,
            layout_score=round(report.score, 4),
            has_critical=report.has_critical(),
            blocking_issue_count=sum(
                1
                for issue in report.issues
                if issue.severity.value in {"error", "critical"}
            ),
            rule_codes=sorted({issue.rule_code for issue in report.issues}),
            deck_qa_score=round(deck_report.total_score or 0.0, 4),
            passed=report.valid and not report.has_critical(),
        )
        return BenchmarkCaseResult(
            definition=definition,
            slide=slide,
            intent=intent,
            design_system=request.design_system,
            plan=plan,
            report=report,
            rule_score=rule_score,
        )

    @staticmethod
    def _content_bundle(
        slide: SlideSpec,
        intent: VisualIntent,
        override: BenchmarkSlideContent | None,
    ) -> LayoutContentBundle:
        base = content_from_slide(slide, intent)
        if override is None:
            return base
        return LayoutContentBundle(
            title=slide.title,
            message=slide.message,
            key_points=list(override.key_points or slide.key_points),
            metrics=list(override.metrics or []),
            captions=list(override.captions or []),
            source_text=base.source_text,
            hero_asset_ref=str(override.hero_asset_id) if override.hero_asset_id else base.hero_asset_ref,
            supporting_asset_refs=[
                str(asset_id) for asset_id in (override.supporting_asset_ids or [])
            ]
            or base.supporting_asset_refs,
            insight=override.insight or base.insight,
        )


class _InMemoryIntentRepo:
    def __init__(self) -> None:
        self._items: dict[UUID, VisualIntent] = {}

    def save(self, intent: VisualIntent) -> VisualIntent:
        self._items[intent.id] = intent
        return intent

    def get(self, intent_id: UUID) -> VisualIntent | None:
        return self._items.get(intent_id)


def _standalone_intent_service() -> VisualIntentService:
    from archium.config.settings import get_settings

    service = VisualIntentService.__new__(VisualIntentService)
    service._session = cast(Any, None)
    service._llm = cast(Any, None)
    service._settings = get_settings()
    service._intents = cast(Any, _InMemoryIntentRepo())
    return service
