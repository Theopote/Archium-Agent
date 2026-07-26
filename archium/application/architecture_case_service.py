"""Writable project ArchitectureCase library (seeds remain bootstrap)."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.domain.architecture_case import ArchitectureCase
from archium.domain.case_ref import case_id_from_ref, normalize_case_id, normalize_precedent_ref
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import ArchitectureCaseStatus
from archium.domain.project_architecture_case import ProjectArchitectureCase
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ArchitectureCaseRepository
from archium.infrastructure.research.case_library.seeds import all_seed_cases

_SLUG_STRIP = re.compile(r"[^a-zA-Z0-9_-]+")


def allocate_case_slug(
    *,
    preferred: str | None,
    project_id: UUID,
    repo: ArchitectureCaseRepository,
) -> str:
    """Pick a unique-per-project slug; fall back to proj_{hex}."""
    base = normalize_case_id(preferred or "")
    if base is None:
        topic = (preferred or "").strip().casefold()
        ascii_bits = _SLUG_STRIP.sub("_", topic).strip("_")
        base = normalize_case_id(ascii_bits[:40]) if ascii_bits else None
    if base is None:
        base = f"proj_{uuid4().hex[:10]}"
    candidate = base
    suffix = 2
    while True:
        existing = repo.get_by_slug(project_id, candidate)
        if existing is None:
            return candidate
        candidate = f"{base}_{suffix}"[:80]
        if normalize_case_id(candidate) is None:
            candidate = f"proj_{uuid4().hex[:10]}"
        suffix += 1
        if suffix > 50:
            return f"proj_{uuid4().hex[:10]}"


def project_case_from_design_knowledge(
    *,
    project_id: UUID,
    knowledge: DesignKnowledge,
    source_knowledge_item_id: UUID | None = None,
    slug: str,
    status: ArchitectureCaseStatus = ArchitectureCaseStatus.DRAFT,
) -> ProjectArchitectureCase:
    name = (knowledge.topic or knowledge.principle or knowledge.strategy or "项目案例").strip()
    principles = [knowledge.principle.strip()] if knowledge.principle.strip() else []
    risks = [knowledge.applicability.strip()] if knowledge.applicability.strip() else []
    tags: list[str] = []
    for bit in (knowledge.topic, knowledge.strategy, knowledge.spatial_translation):
        token = (bit or "").strip()
        if token and len(token) <= 40 and token not in tags:
            tags.append(token)
    return ProjectArchitectureCase(
        project_id=project_id,
        slug=slug,
        status=status,
        source_knowledge_item_id=source_knowledge_item_id,
        name=name[:300],
        design_problem=(knowledge.problem or "").strip(),
        strategy=(knowledge.strategy or knowledge.principle or "").strip(),
        spatial_logic=(knowledge.spatial_translation or "").strip(),
        material_language=(knowledge.material_strategy or "").strip(),
        context=(knowledge.project_link or "").strip(),
        atmosphere="",
        transferable_principles=principles,
        risks=risks,
        tags=tags[:12],
    )


class ArchitectureCaseService:
    """Create / activate / link project ArchitectureCase rows."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cases = ArchitectureCaseRepository(session)

    def list_project_cases(
        self,
        project_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[ProjectArchitectureCase]:
        statuses = [
            ArchitectureCaseStatus.DRAFT,
            ArchitectureCaseStatus.ACTIVE,
        ]
        if include_archived:
            statuses.append(ArchitectureCaseStatus.ARCHIVED)
        return self._cases.list_by_project(project_id, statuses=statuses)

    def get_by_slug(
        self, project_id: UUID, slug: str
    ) -> ProjectArchitectureCase | None:
        return self._cases.get_by_slug(project_id, slug)

    def create_draft(
        self,
        project_id: UUID,
        *,
        name: str,
        design_problem: str = "",
        strategy: str = "",
        spatial_logic: str = "",
        material_language: str = "",
        slug: str | None = None,
        source_knowledge_item_id: UUID | None = None,
        architect: str = "",
        location: str = "",
        year: str = "",
        building_type: str = "",
        context: str = "",
        atmosphere: str = "",
        transferable_principles: list[str] | None = None,
        risks: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> ProjectArchitectureCase:
        allocated = allocate_case_slug(
            preferred=slug or name,
            project_id=project_id,
            repo=self._cases,
        )
        case = ProjectArchitectureCase(
            project_id=project_id,
            slug=allocated,
            status=ArchitectureCaseStatus.DRAFT,
            source_knowledge_item_id=source_knowledge_item_id,
            name=name.strip() or allocated,
            design_problem=design_problem,
            strategy=strategy,
            spatial_logic=spatial_logic,
            material_language=material_language,
            architect=architect,
            location=location,
            year=year,
            building_type=building_type,
            context=context,
            atmosphere=atmosphere,
            transferable_principles=list(transferable_principles or []),
            risks=list(risks or []),
            tags=list(tags or []),
        )
        return self._cases.create(case)

    def activate(self, case_id: UUID) -> ProjectArchitectureCase:
        case = self._cases.get_by_id(case_id)
        if case is None:
            raise WorkflowError(f"Architecture case {case_id} not found")
        case.activate()
        return self._cases.update(case)

    def ensure_from_knowledge_item(
        self,
        item: ProjectKnowledgeItem,
    ) -> ProjectArchitectureCase | None:
        """On research confirm: link seed/project case or create a draft.

        - If ``precedent_ref`` resolves to a seed: leave as seed link (no project row).
        - If resolves to existing project case: refresh source link; return it.
        - Else if DesignKnowledge has substance: create draft and set precedent_ref.
        """
        knowledge = item.design_knowledge
        if knowledge is None or not knowledge.has_substance:
            return None

        preferred = case_id_from_ref(knowledge.precedent_ref)
        seed_by_id = {case.id: case for case in all_seed_cases()}

        if preferred and preferred in seed_by_id:
            # Seed link is enough; ensure precedent_ref canonical.
            if knowledge.precedent_ref != normalize_precedent_ref(preferred):
                item.design_knowledge = knowledge.model_copy(
                    update={"precedent_ref": normalize_precedent_ref(preferred)}
                )
            return None

        if preferred:
            existing = self._cases.get_by_slug(item.project_id, preferred)
            if existing is not None:
                if existing.source_knowledge_item_id is None:
                    existing.source_knowledge_item_id = item.id
                    existing.touch()
                    return self._cases.update(existing)
                return existing

        slug = allocate_case_slug(
            preferred=preferred or knowledge.topic or knowledge.principle,
            project_id=item.project_id,
            repo=self._cases,
        )
        draft = project_case_from_design_knowledge(
            project_id=item.project_id,
            knowledge=knowledge,
            source_knowledge_item_id=item.id,
            slug=slug,
            status=ArchitectureCaseStatus.DRAFT,
        )
        created = self._cases.create(draft)
        item.design_knowledge = knowledge.model_copy(
            update={"precedent_ref": normalize_precedent_ref(created.slug)}
        )
        return created

    def to_architecture_cases(
        self,
        project_id: UUID,
        *,
        include_drafts: bool = False,
    ) -> list[ArchitectureCase]:
        statuses = [ArchitectureCaseStatus.ACTIVE]
        if include_drafts:
            statuses.append(ArchitectureCaseStatus.DRAFT)
        return [
            row.to_architecture_case()
            for row in self._cases.list_by_project(project_id, statuses=statuses)
        ]
