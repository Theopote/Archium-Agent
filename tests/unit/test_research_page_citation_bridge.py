"""Topic 07 — Research → page citation bridge."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from archium.application.citation_resolution import enrich_slide_citations
from archium.application.chunk_models import ProjectContextBundle
from archium.application.evidence_readiness_service import citation_lines_for_slide
from archium.application.research_page_citation_bridge import (
    attach_research_citations_to_slide,
)
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
    SlideType,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole
from archium.infrastructure.database.mappers import (
    slide_to_domain,
    slide_to_orm,
)


def _research_item(*, statement: str, url: str) -> ProjectKnowledgeItem:
    return ProjectKnowledgeItem(
        project_id=uuid4(),
        statement=statement,
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.HIGH_CONFIDENCE,
        category="research",
        status=KnowledgeItemStatus.CONFIRMED,
        requires_user_confirmation=False,
        source_citations=[
            SourceCitation(
                url=url,
                source_title="Urban Density Brief",
                quote="density drives courtyard depth",
            )
        ],
    )


def test_attach_research_citations_by_overlap() -> None:
    item = _research_item(
        statement="城市密度影响院落进深与通风策略",
        url="https://example.org/density",
    )
    # Confirmed research: requires_user_confirmation False after confirm path
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="问题分析",
        message="当前院落进深受城市密度挤压",
        slide_type=SlideType.CONTENT,
        slide_role=SlideRole.PROBLEM_ANALYSIS,
        key_points=["密度", "通风"],
    )
    session = MagicMock()
    with patch(
        "archium.application.project_knowledge_service.ProjectKnowledgeService"
    ) as svc_cls:
        svc_cls.return_value.list_confirmed_research_items.return_value = [item]
        added = attach_research_citations_to_slide(
            session,
            project_id=item.project_id,
            slide=slide,
        )
    assert added == 1
    assert len(slide.source_citations) == 1
    cite = slide.source_citations[0]
    assert cite.url == "https://example.org/density"
    assert cite.knowledge_item_id == item.id
    assert cite.display_label() == "Urban Density Brief"
    lines = citation_lines_for_slide(slide)
    assert lines
    assert "Urban Density Brief" in lines[0]


def test_analysis_slide_fallback_when_no_token_overlap() -> None:
    item = _research_item(
        statement="完全不相关的材料研究",
        url="https://example.org/materials",
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="场地分析",
        message="场地高差与汇水路径",
        slide_role=SlideRole.SITE_ANALYSIS,
    )
    session = MagicMock()
    with patch(
        "archium.application.project_knowledge_service.ProjectKnowledgeService"
    ) as svc_cls:
        svc_cls.return_value.list_confirmed_research_items.return_value = [item]
        added = attach_research_citations_to_slide(
            session,
            project_id=item.project_id,
            slide=slide,
        )
    assert added == 1
    assert slide.source_citations[0].url.endswith("/materials")


def test_enrich_slide_citations_falls_back_to_research() -> None:
    item = _research_item(
        statement="空间策略需要明确轴线",
        url="https://example.org/axis",
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="策略",
        message="空间策略需要明确轴线关系",
        slide_role=SlideRole.STRATEGY,
    )
    session = MagicMock()
    bundle = ProjectContextBundle(
        text="",
        chunks=[],
        document_names={},
    )

    class _EmptyRetrieval:
        def search(self, *_args, **_kwargs):
            return []

    with (
        patch(
            "archium.application.citation_resolution.create_retrieval_service",
            return_value=_EmptyRetrieval(),
        ),
        patch(
            "archium.application.project_knowledge_service.ProjectKnowledgeService"
        ) as svc_cls,
    ):
        svc_cls.return_value.list_confirmed_research_items.return_value = [item]
        enrich_slide_citations(
            slide,
            session=session,
            project_id=item.project_id,
            context_bundle=bundle,
        )
    assert len(slide.source_citations) == 1
    assert slide.source_citations[0].url == "https://example.org/axis"


def test_slide_source_citation_orm_roundtrip_url() -> None:
    from archium.infrastructure.database.models import SlideORM

    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="对比",
        message="案例对比依赖公开研究",
        slide_role=SlideRole.COMPARISON,
        source_citations=[
            SourceCitation(
                url="https://example.org/case",
                source_title="Case Study",
                knowledge_item_id=uuid4(),
                quote="courtyard typology",
            )
        ],
    )
    orm = slide_to_orm(slide, SlideORM(id=slide.id))
    reloaded = slide_to_domain(orm)
    assert len(reloaded.source_citations) == 1
    cite = reloaded.source_citations[0]
    assert cite.url == "https://example.org/case"
    assert cite.source_title == "Case Study"
    assert cite.knowledge_item_id is not None
    assert cite.display_label() == "Case Study"
