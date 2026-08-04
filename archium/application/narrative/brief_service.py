"""Brief generation — Application Service owns persist; Agent proposes only."""

from __future__ import annotations

from uuid import UUID

from archium.agents.brief_builder import BriefBuilder
from archium.application._helpers import (
    build_retrieval_query_from_request,
    resolve_design_context_text,
)
from archium.application.artifact_history_service import BriefHistoryService
from archium.application.artifact_lineage import apply_brief_lineage
from archium.application.context.presentation_readiness import (
    format_readiness_for_prompt,
    presentation_readiness_from_context,
)
from archium.application.context.project_context_builder import build_project_context
from archium.application.mission_context_bridge import (
    enrich_mission_generation_context,
    resolve_project_mission,
)
from archium.application.presentation_models import PresentationRequest
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.enums import PresentationStatus, RevisionSource
from archium.domain.presentation import PresentationBrief
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider


class BriefService:
    """Orchestrate Brief proposal + persistence (not an Agent)."""

    def __init__(
        self,
        session: SessionLike,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._history = BriefHistoryService(session)
        self._builder = BriefBuilder(llm, settings=self._settings)

    def generate(
        self,
        project_id: UUID,
        presentation_id: UUID,
        request: PresentationRequest,
        *,
        manuscript: PresentationManuscript | None = None,
        version: int | None = None,
    ) -> PresentationBrief:
        previous_briefs = self._presentations.list_briefs(presentation_id)
        previous = previous_briefs[0] if previous_briefs else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        if version is None:
            version = (previous.version + 1) if previous is not None else 1

        project_context = resolve_design_context_text(
            self._session,
            project_id,
            manuscript=manuscript,
            use_manuscript_pipeline=request.use_manuscript_pipeline,
            query=build_retrieval_query_from_request(request),
            settings=self._settings,
        )
        mission = resolve_project_mission(
            self._session,
            project_id,
            presentation_id=presentation_id,
        )
        project_context = enrich_mission_generation_context(
            self._session,
            project_context,
            mission,
        )
        try:
            pc = build_project_context(self._session, project_id)
            readiness = presentation_readiness_from_context(pc)
            cognition_bits: list[str] = []
            if readiness.warnings or readiness.verdict.value != "proceed":
                cognition_bits.append(format_readiness_for_prompt(readiness))
            from archium.application.research_topics import (
                collect_mission_research_topic_candidates,
                collect_project_research_topic_candidates,
            )

            topic_candidates = (
                collect_mission_research_topic_candidates(mission)
                if mission is not None
                else collect_project_research_topic_candidates(
                    project_name="",
                    project_description="",
                    knowledge_state=pc.knowledge_state if pc is not None else None,
                    max_topics=3,
                )
            )
            if topic_candidates:
                lines = ["【优先研究主题（按设计影响排序）】"]
                for item in topic_candidates[:3]:
                    lines.append(f"- {item.text}（{item.axis.value} · {item.design_impact}）")
                cognition_bits.append("\n".join(lines))
            if cognition_bits:
                project_context = (
                    f"{project_context}\n\n" + "\n\n".join(cognition_bits)
                ).strip()
        except Exception:  # noqa: BLE001 — cognition note must not abort brief
            pass
        brief = self._builder.propose(
            project_id=project_id,
            presentation_id=presentation_id,
            request=request,
            project_context=project_context,
            version=version,
        )
        apply_brief_lineage(brief, previous)
        saved = self._presentations.save_brief(brief)
        self._history.record_snapshot(saved, RevisionSource.GENERATED)

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is not None:
            presentation.current_brief_id = saved.id
            if presentation.status == PresentationStatus.DRAFT:
                presentation.status = PresentationStatus.IN_PROGRESS
            self._presentations.update_presentation(presentation)
        return saved
