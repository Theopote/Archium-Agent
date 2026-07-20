"""Cultural narrative plan for heritage village and cultural heritage projects."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus, InformationOrigin
from archium.domain.project_knowledge import SourceCitation


CULTURAL_NARRATIVE_LOGICAL_KEY = "project-cultural-narrative"


class NarrativeEvent(DomainModel):
    """A historical event on the village timeline."""

    id: str = Field(min_length=1, max_length=100)
    year_or_period: str = Field(min_length=1)
    event: str = Field(min_length=1)
    origin: InformationOrigin = InformationOrigin.USER_UPLOAD
    is_legend: bool = False
    source_citations: list[SourceCitation] = Field(default_factory=list)


class CulturalCharacter(DomainModel):
    """A person representing village identity."""

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    significance: str = Field(min_length=1)
    origin: InformationOrigin = InformationOrigin.USER_UPLOAD
    is_legend: bool = False
    source_citations: list[SourceCitation] = Field(default_factory=list)


class CulturalPlace(DomainModel):
    """A spatial node in the cultural narrative."""

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    significance: str = Field(min_length=1)
    space_type: str = Field(default="public_space")
    asset_refs: list[str] = Field(default_factory=list)
    source_citations: list[SourceCitation] = Field(default_factory=list)


class CulturalRitual(DomainModel):
    """Folk custom, festival, or intangible heritage element."""

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    season: str | None = None
    origin: InformationOrigin = InformationOrigin.USER_UPLOAD
    is_legend: bool = False
    source_citations: list[SourceCitation] = Field(default_factory=list)


class ArchitecturalSymbol(DomainModel):
    """Building or built element carrying cultural meaning."""

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    building_type: str = Field(default="traditional")
    cultural_meaning: str = Field(min_length=1)
    asset_refs: list[str] = Field(default_factory=list)
    source_citations: list[SourceCitation] = Field(default_factory=list)


class CommunicationTheme(DomainModel):
    """A传播主题 linked to real village evidence."""

    id: str = Field(min_length=1, max_length=100)
    theme: str = Field(min_length=1)
    linked_characters: list[str] = Field(default_factory=list)
    linked_places: list[str] = Field(default_factory=list)
    linked_rituals: list[str] = Field(default_factory=list)
    linked_buildings: list[str] = Field(default_factory=list)
    source_citations: list[SourceCitation] = Field(default_factory=list)


class CulturalNarrativePlan(IdentifiedModel, VersionedModel, TimestampedModel):
    """Structured cultural story for heritage village presentations."""

    project_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    logical_key: str = Field(default=CULTURAL_NARRATIVE_LOGICAL_KEY, max_length=200)
    central_story: str = Field(min_length=1)
    identity_keywords: list[str] = Field(default_factory=list)
    historical_timeline: list[NarrativeEvent] = Field(default_factory=list)
    characters: list[CulturalCharacter] = Field(default_factory=list)
    places: list[CulturalPlace] = Field(default_factory=list)
    rituals: list[CulturalRitual] = Field(default_factory=list)
    architectural_symbols: list[ArchitecturalSymbol] = Field(default_factory=list)
    emotional_arc: list[str] = Field(default_factory=list)
    visitor_storyline: list[str] = Field(default_factory=list)
    communication_themes: list[CommunicationTheme] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @property
    def is_approved(self) -> bool:
        return self.approval_status == ApprovalStatus.APPROVED

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
