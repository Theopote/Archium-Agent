"""Evidence authority map (KN-012) — design vs presentation vs delivery namespaces.

Design-chain provenance (authoritative):
  - ``IntentEvidence`` on ``DesignIntent.evidence``
  - ``SourceCitation`` on ``ProjectKnowledgeItem`` / renovation evidence

Presentation / visual (deck & layout — NOT design provenance):
  - ``PresentationEvidenceItem`` (legacy alias ``EvidenceItem``)
  - ``PresentationEvidenceSlot`` (legacy alias ``EvidenceSlot``)
  - ``PresentationEvidenceRequirement`` (legacy alias ``EvidenceRequirement``)
  - Layout/compiler class aliases under ``Presentation*``

Delivery / materials gates (export readiness — NOT IntentEvidence):
  - ``MaterialsAvailability`` (legacy alias ``EvidenceAvailability``)
  - ``MaterialsExportReadiness`` (legacy alias ``ProjectEvidenceStatus``)
  - ``ContextMaterialsPack`` (legacy alias ``ProjectEvidencePack``)

Free-text label lists (not typed Evidence identities):
  - ``DesignKnowledge.evidence``
  - ``DesignRationale.evidence``
  - ``ConfirmedKnowledgeEdge.evidence``

Do not rename ``LayoutFamily.EVIDENCE_BOARD`` / ``photo_evidence_grid`` string
contracts in this phase — they are PPT pipeline vocabulary, not type names.
"""

from __future__ import annotations

from typing import Final

# Chain labels for docs / UI / guards
DESIGN_EVIDENCE_AUTHORITIES: Final[tuple[str, ...]] = (
    "IntentEvidence",
    "SourceCitation",
)
PRESENTATION_EVIDENCE_TYPES: Final[tuple[str, ...]] = (
    "PresentationEvidenceItem",
    "PresentationEvidenceSlot",
    "PresentationEvidenceRequirement",
    "LayoutEvidenceItem",
)
DELIVERY_MATERIALS_TYPES: Final[tuple[str, ...]] = (
    "MaterialsAvailability",
    "MaterialsExportReadiness",
    "ContextMaterialsPack",
)
LEGACY_EVIDENCE_ALIASES: Final[dict[str, str]] = {
    "EvidenceItem": "PresentationEvidenceItem",
    "EvidenceSlot": "PresentationEvidenceSlot",
    "EvidenceRequirement": "PresentationEvidenceRequirement",
    "EvidenceAvailability": "MaterialsAvailability",
    "ProjectEvidenceStatus": "MaterialsExportReadiness",
    "ProjectEvidencePack": "ContextMaterialsPack",
    "EvidenceReviewer": "PresentationEvidenceReviewer",
    "EvidenceBoardLayoutGenerator": "PresentationEvidenceBoardLayoutGenerator",
    "PhotoEvidenceGridCompiler": "PresentationPhotoEvidenceGridCompiler",
}


def is_design_evidence_authority(type_name: str) -> bool:
    return type_name in DESIGN_EVIDENCE_AUTHORITIES


def canonical_evidence_type_name(type_name: str) -> str:
    """Map legacy Evidence* names to Presentation*/Materials* canonical names."""
    return LEGACY_EVIDENCE_ALIASES.get(type_name, type_name)
