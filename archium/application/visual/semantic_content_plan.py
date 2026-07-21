"""Map ArchitecturalContentSchema communication contract → SlideSpec fill plan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRole,
)
from archium.domain.visual.template_induction import OutlineTemplateCompatibility

_VISUAL_EVIDENCE_ROLE_SET = frozenset(
    {
        "hero_image",
        "supporting_image",
        "drawing",
        "before_after_pair",
        "multi_image_grid",
    }
)

@dataclass
class SemanticContentPlan:
    """Ordered text/asset bindings derived from schema + SlideSpec."""

    uses_semantic_contract: bool = False
    title: str = ""
    central_claim: str = ""
    evidence_labels: list[str] = field(default_factory=list)
    interpretation: str = ""
    decision_request: str = ""
    captions: list[str] = field(default_factory=list)
    source: str = ""
    metrics: list[str] = field(default_factory=list)
    visual_evidence_roles: list[str] = field(default_factory=list)

    def has_central_claim(self) -> bool:
        return bool(self.central_claim.strip())

    def has_evidence(self) -> bool:
        return bool(self.evidence_labels)

    def has_interpretation(self) -> bool:
        return bool(self.interpretation.strip())

    def expected_image_slot_count(self) -> int:
        return len(self.visual_evidence_roles)


def expected_text_evidence_count(schema: ArchitecturalContentSchema) -> int:
    """How many text evidence labels the schema contract expects."""
    hydrated = schema.hydrate_semantic_contract()
    total = 0
    for item in hydrated.evidence_items:
        if item.role != ContentRole.EVIDENCE:
            continue
        if item.required:
            total += max(item.min_count, 1)
        else:
            total += max(item.min_count, 0)
    return total


def expand_visual_evidence_roles(schema: ArchitecturalContentSchema) -> list[str]:
    """Expand visual roles using min_count and align with evidence_items depth."""
    hydrated = schema.hydrate_semantic_contract()
    roles: list[str] = []

    def append_roles(items: list, *, use_min: bool = True) -> None:
        for item in items:
            if item.role not in _VISUAL_EVIDENCE_ROLE_SET:
                continue
            repeat = max(item.min_count, 1) if (use_min and item.required) else max(item.min_count, 0)
            for _ in range(repeat):
                roles.append(item.role)

    append_roles(hydrated.visual_evidence)
    if not roles:
        append_roles(hydrated.visual_requirements)

    min_evidence = expected_text_evidence_count(hydrated)
    while len(roles) < min_evidence:
        roles.append("hero_image" if not roles else "supporting_image")

    if hydrated.min_asset_count and len(roles) < hydrated.min_asset_count:
        while len(roles) < hydrated.min_asset_count:
            roles.append("supporting_image")

    return roles


def build_slide_spec_from_outline_page(
    *,
    outline: OutlinePlan,
    section: OutlineSection,
    page: OutlineTemplateCompatibility,
    slide_type_resolver: Callable[[str, str], str] | None = None,
) -> SlideSpec:
    """Build a SlideSpec aligned with semantic contract fill from outline sections."""
    message = (section.key_message or section.purpose or section.title).strip()
    if page.page_role == "overflow" and section.purpose.strip():
        message = section.purpose.strip()

    key_points: list[str] = []
    seen: set[str] = set()
    for item in section.evidence_requirements:
        text = item.strip()
        if text and text not in seen:
            key_points.append(text)
            seen.add(text)
    key_message = section.key_message.strip()
    if key_message and key_message not in seen and key_message != message:
        key_points.append(key_message)
    key_points = key_points[:8]

    speaker_notes = ""
    purpose = section.purpose.strip()
    if purpose and purpose not in {message, *key_points}:
        speaker_notes = purpose

    slide_type = "content"
    if slide_type_resolver is not None:
        slide_type = slide_type_resolver(
            page.inferred_functional_type,
            page.inferred_content_type,
        )

    return SlideSpec(
        presentation_id=outline.presentation_id,
        chapter_id=section.id,
        order=page.planned_page_index,
        title=section.title,
        message=message,
        key_points=key_points,
        speaker_notes=speaker_notes,
        slide_type=slide_type,
    )


@dataclass
class SemanticFillState:
    evidence_idx: int = 0
    caption_idx: int = 0
    metric_idx: int = 0
    body_idx: int = 0
    central_claim_used: bool = False
    title_used: bool = False


_SEMANTIC_TEXT_ROLES = frozenset(
    {
        ContentRole.CENTRAL_CLAIM,
        ContentRole.EVIDENCE,
        ContentRole.INTERPRETATION,
        ContentRole.DECISION_REQUEST,
    }
)


def schema_uses_semantic_contract(schema: ArchitecturalContentSchema) -> bool:
    """True when schema carries a communication contract (explicit or flat)."""
    hydrated = schema.hydrate_semantic_contract()
    if (
        hydrated.central_claim
        or hydrated.evidence_items
        or hydrated.visual_evidence
        or hydrated.interpretation
        or hydrated.decision_request
    ):
        return True
    if any(item.role in _SEMANTIC_TEXT_ROLES for item in hydrated.required_content):
        return True
    return any(item.role in _VISUAL_EVIDENCE_ROLE_SET for item in hydrated.visual_requirements)


def build_semantic_content_plan(
    schema: ArchitecturalContentSchema,
    slide_spec: SlideSpec,
) -> SemanticContentPlan:
    hydrated = schema.hydrate_semantic_contract()
    uses_contract = schema_uses_semantic_contract(hydrated)

    source = ""
    if slide_spec.source_citations:
        cite = slide_spec.source_citations[0]
        page = f", p.{cite.page_number}" if cite.page_number else ""
        source = f"{cite.document_name}{page}"

    captions: list[str] = []
    if slide_spec.speaker_notes and slide_spec.speaker_notes.strip():
        captions.append(slide_spec.speaker_notes.strip())
    captions.extend(slide_spec.key_points)

    evidence_labels = list(slide_spec.key_points)
    if not evidence_labels and hydrated.evidence_items:
        evidence_labels = [slide_spec.message]
    if not evidence_labels and any(
        item.role == ContentRole.EVIDENCE for item in hydrated.required_content
    ):
        evidence_labels = [slide_spec.message]

    has_central = bool(
        hydrated.central_claim
        or any(item.role == ContentRole.CENTRAL_CLAIM for item in hydrated.required_content)
    )
    has_evidence = bool(
        hydrated.evidence_items
        or any(item.role == ContentRole.EVIDENCE for item in hydrated.required_content)
    )
    has_interpretation = bool(
        hydrated.interpretation
        or any(item.role == ContentRole.INTERPRETATION for item in hydrated.required_content)
    )

    visual_roles = expand_visual_evidence_roles(hydrated)

    return SemanticContentPlan(
        uses_semantic_contract=uses_contract,
        title=slide_spec.title,
        central_claim=slide_spec.message if has_central else "",
        evidence_labels=evidence_labels if has_evidence else [],
        interpretation=(slide_spec.speaker_notes or slide_spec.message).strip()
        if has_interpretation
        else "",
        decision_request=slide_spec.message
        if hydrated.decision_request
        or any(item.role == ContentRole.DECISION_REQUEST for item in hydrated.required_content)
        else "",
        captions=captions if hydrated.caption_required or has_interpretation else [],
        source=source,
        metrics=list(slide_spec.key_points) if hydrated.metric_unit_required else [],
        visual_evidence_roles=visual_roles,
    )


def normalize_text_role_for_schema(
    role: str,
    *,
    schema: ArchitecturalContentSchema,
    plan: SemanticContentPlan,
    state: SemanticFillState,
) -> str:
    """Remap geometric roles (e.g. body) onto semantic contract roles when needed."""
    role = (role or "").strip().lower()
    if not plan.uses_semantic_contract:
        return role or ContentRole.BODY.value

    if role in {ContentRole.TITLE.value, "title"}:
        return ContentRole.TITLE.value
    if role in {ContentRole.CENTRAL_CLAIM.value, "central_claim"}:
        return ContentRole.CENTRAL_CLAIM.value
    if role in {ContentRole.EVIDENCE.value, "evidence"}:
        return ContentRole.EVIDENCE.value
    if role in {ContentRole.INTERPRETATION.value, "interpretation"}:
        return ContentRole.INTERPRETATION.value
    if role in {ContentRole.DECISION_REQUEST.value, "decision_request"}:
        return ContentRole.DECISION_REQUEST.value
    if role in {ContentRole.CAPTION.value, "caption"}:
        return ContentRole.CAPTION.value
    if role in {ContentRole.SOURCE.value, "source", "citation"}:
        return ContentRole.SOURCE.value
    if role in {ContentRole.METRIC.value, "metric"}:
        return ContentRole.METRIC.value

    if role in {ContentRole.BODY.value, "body", "subtitle", "lead_statement"}:
        if plan.has_central_claim() and not state.central_claim_used:
            return ContentRole.CENTRAL_CLAIM.value
        if plan.has_evidence() and state.evidence_idx < len(plan.evidence_labels):
            return ContentRole.EVIDENCE.value
        if plan.has_interpretation():
            return ContentRole.INTERPRETATION.value
        return ContentRole.BODY.value

    return role or ContentRole.BODY.value


def replacement_text_for_role(
    role: str,
    *,
    plan: SemanticContentPlan,
    slide_spec: SlideSpec,
    state: SemanticFillState,
) -> str:
    if not plan.uses_semantic_contract:
        return _legacy_replacement_text(role, slide_spec, state)

    if role == ContentRole.TITLE.value:
        state.title_used = True
        return plan.title or slide_spec.title
    if role == ContentRole.CENTRAL_CLAIM.value and plan.has_central_claim():
        state.central_claim_used = True
        return plan.central_claim
    if role == ContentRole.EVIDENCE.value and plan.has_evidence():
        if state.evidence_idx < len(plan.evidence_labels):
            text = plan.evidence_labels[state.evidence_idx]
            state.evidence_idx += 1
            return text
        return slide_spec.message
    if role == ContentRole.INTERPRETATION.value and plan.has_interpretation():
        return plan.interpretation
    if role == ContentRole.DECISION_REQUEST.value:
        return plan.decision_request or slide_spec.message
    if role == ContentRole.CAPTION.value:
        if state.caption_idx < len(plan.captions):
            text = plan.captions[state.caption_idx]
            state.caption_idx += 1
            return text
        return (slide_spec.speaker_notes or "").strip()
    if role == ContentRole.SOURCE.value:
        return plan.source
    if role == ContentRole.METRIC.value:
        if state.metric_idx < len(plan.metrics):
            text = plan.metrics[state.metric_idx]
            state.metric_idx += 1
            return text
        return slide_spec.key_points[0] if slide_spec.key_points else slide_spec.message
    if role == ContentRole.BODY.value:
        if slide_spec.key_points and state.body_idx < len(slide_spec.key_points):
            text = slide_spec.key_points[state.body_idx]
            state.body_idx += 1
            return text
        return slide_spec.message
    return slide_spec.message


def _legacy_replacement_text(role: str, slide_spec: SlideSpec, state: SemanticFillState) -> str:
    if role in {"title", ContentRole.TITLE.value}:
        return slide_spec.title
    if role in {"subtitle"}:
        return slide_spec.key_points[0] if slide_spec.key_points else slide_spec.message
    if role in {"metric", ContentRole.METRIC.value}:
        return slide_spec.key_points[0] if slide_spec.key_points else slide_spec.message
    if role in {"caption", ContentRole.CAPTION.value}:
        return (slide_spec.speaker_notes or "").strip()
    if role in {"source", ContentRole.SOURCE.value}:
        if slide_spec.source_citations:
            cite = slide_spec.source_citations[0]
            page = f", p.{cite.page_number}" if cite.page_number else ""
            return f"{cite.document_name}{page}"
        return ""
    if role in {
        "central_claim",
        ContentRole.CENTRAL_CLAIM.value,
        "lead_statement",
        ContentRole.LEAD_STATEMENT.value,
    }:
        return slide_spec.message
    if slide_spec.key_points and state.body_idx < len(slide_spec.key_points):
        text = slide_spec.key_points[state.body_idx]
        state.body_idx += 1
        return text
    return slide_spec.message
