"""KN-012 — Evidence authority namespace catalog and legacy aliases."""

from __future__ import annotations

from archium.application.context_evidence import ContextMaterialsPack, ProjectEvidencePack
from archium.application.evidence_readiness_service import (
    MaterialsExportReadiness,
    ProjectEvidenceStatus,
)
from archium.application.review.evidence import EvidenceReviewer, PresentationEvidenceReviewer
from archium.application.visual.scene_compilers.specialized import (
    PhotoEvidenceGridCompiler,
    PresentationPhotoEvidenceGridCompiler,
)
from archium.domain.enums import EvidenceAvailability, MaterialsAvailability
from archium.domain.evidence_authority import (
    DESIGN_EVIDENCE_AUTHORITIES,
    LEGACY_EVIDENCE_ALIASES,
    PRESENTATION_EVIDENCE_TYPES,
    canonical_evidence_type_name,
    is_design_evidence_authority,
)
from archium.domain.intent.intent_evidence import IntentEvidence, IntentEvidenceSourceType
from archium.domain.presentation_manuscript import EvidenceItem, PresentationEvidenceItem
from archium.domain.project_knowledge import SourceCitation
from archium.domain.visual.architectural_content_schema import (
    EvidenceRequirement,
    PresentationEvidenceRequirement,
)
from archium.domain.visual.visual_grammar import EvidenceSlot, PresentationEvidenceSlot
from archium.infrastructure.layout.generators.evidence_board import (
    EvidenceBoardLayoutGenerator,
    PresentationEvidenceBoardLayoutGenerator,
)


def test_design_authorities_are_intent_and_citation() -> None:
    assert is_design_evidence_authority("IntentEvidence")
    assert is_design_evidence_authority("SourceCitation")
    assert not is_design_evidence_authority("EvidenceItem")
    assert "IntentEvidence" in DESIGN_EVIDENCE_AUTHORITIES
    assert SourceCitation is not None
    evidence = IntentEvidence(
        statement="山地应减少开挖",
        source_type=IntentEvidenceSourceType.USER_INPUT,
        knowledge_item_id=None,
    )
    assert evidence.statement


def test_presentation_aliases_point_to_canonical_types() -> None:
    assert EvidenceItem is PresentationEvidenceItem
    assert EvidenceSlot is PresentationEvidenceSlot
    assert EvidenceRequirement is PresentationEvidenceRequirement
    assert PresentationEvidenceItem.__name__ == "PresentationEvidenceItem"
    assert "PresentationEvidenceItem" in PRESENTATION_EVIDENCE_TYPES


def test_delivery_and_layout_aliases() -> None:
    assert EvidenceAvailability is MaterialsAvailability
    assert ProjectEvidenceStatus is MaterialsExportReadiness
    assert ProjectEvidencePack is ContextMaterialsPack
    assert EvidenceReviewer is PresentationEvidenceReviewer
    assert EvidenceBoardLayoutGenerator is PresentationEvidenceBoardLayoutGenerator
    assert PhotoEvidenceGridCompiler is PresentationPhotoEvidenceGridCompiler


def test_canonical_evidence_type_name_map() -> None:
    assert canonical_evidence_type_name("EvidenceItem") == "PresentationEvidenceItem"
    assert canonical_evidence_type_name("IntentEvidence") == "IntentEvidence"
    assert LEGACY_EVIDENCE_ALIASES["ProjectEvidencePack"] == "ContextMaterialsPack"
