"""KN-004 — LLM fact extraction must not invent non-standard keys."""

from __future__ import annotations

from uuid import uuid4

from archium.application.chunk_models import ProjectContextBundle
from archium.application.fact_extraction_service import FactExtractionService
from archium.config.settings import Settings
from archium.domain.document import DocumentChunk
from archium.domain.project import Project
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session


def test_llm_unknown_key_not_persisted(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(Project(name="KN-004"))
    chunk = DocumentChunk(
        document_id=uuid4(),
        project_id=project.id,
        chunk_index=0,
        content="用地约 12000 ㎡，FAR 1.5",
        page_number=1,
    )
    payload = """
    {
      "facts": [
        {
          "key": "site_area",
          "label": "用地面积",
          "value": "12000",
          "unit": "㎡",
          "category": "area",
          "confidence": 0.9,
          "chunk_id": null,
          "quote": "用地约 12000 ㎡"
        },
        {
          "key": "invented_foo_metric",
          "label": "发明指标",
          "value": "42",
          "unit": null,
          "category": "general",
          "confidence": 0.5,
          "chunk_id": null,
          "quote": "不应入库"
        },
        {
          "key": "far",
          "label": "容积率",
          "value": "1.5",
          "unit": null,
          "category": "ratio",
          "confidence": 0.8,
          "chunk_id": null,
          "quote": "FAR 1.5"
        }
      ]
    }
    """

    def selector(request: LLMRequest) -> str | None:
        if "结构化事实" in request.user_prompt or "允许的 key" in request.user_prompt:
            return payload
        return None

    settings = Settings(_env_file=None, fact_extraction_enabled=True)
    service = FactExtractionService(
        db_session,
        llm=MockLLMProvider(selector=selector),
        settings=settings,
    )
    bundle = ProjectContextBundle(
        text="用地约 12000 ㎡，FAR 1.5",
        chunks=[chunk],
        document_names={chunk.document_id: "任务书.pdf"},
    )
    facts, created = service.extract_from_context(project.id, bundle)
    keys = {fact.key for fact in facts}
    assert "site_area" in keys
    assert "plot_ratio" in keys  # far → plot_ratio
    assert "invented_foo_metric" not in keys
    assert "far" not in keys
    assert created >= 1
    stored = FactRepository(db_session).list_by_project(project.id)
    assert all(fact.key != "invented_foo_metric" for fact in stored)
