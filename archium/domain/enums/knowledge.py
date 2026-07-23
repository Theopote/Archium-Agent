"""Domain enumerations — knowledge bounded context (DOM-018)."""

from enum import StrEnum

class InformationOrigin(StrEnum):
    """Provenance of a knowledge item or claim."""

    USER_UPLOAD = "user_upload"
    USER_CONFIRMED = "user_confirmed"
    PUBLIC_RESEARCH = "public_research"
    SYSTEM_INFERENCE = "system_inference"
    REFERENCE_CASE = "reference_case"

class InformationReliability(StrEnum):
    """Confidence tier for a knowledge item used in generation gating."""

    CONFIRMED = "confirmed"
    HIGH_CONFIDENCE = "high_confidence"
    UNVERIFIED = "unverified"
    INFERENCE = "inference"
    CONFLICTING = "conflicting"

class KnowledgeItemStatus(StrEnum):
    """Lifecycle status for a project knowledge item."""

    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

class KnowledgeGapCategory(StrEnum):
    PROJECT_SCOPE = "project_scope"
    SITE = "site"
    AREA = "area"
    PROGRAM = "program"
    USER_NEEDS = "user_needs"
    REGULATION = "regulation"
    HISTORY = "history"
    OPERATION = "operation"
    BUDGET = "budget"
    SCHEDULE = "schedule"
    STAKEHOLDER = "stakeholder"
    TECHNICAL = "technical"
    DELIVERABLE = "deliverable"
    OTHER = "other"

class KnowledgeGapStatus(StrEnum):
    OPEN = "open"
    ASSUMED = "assumed"
    ANSWERED = "answered"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"

class ResolutionMethod(StrEnum):
    USER_INPUT = "user_input"
    DOCUMENT_REVIEW = "document_review"
    SITE_VISIT = "site_visit"
    STAKEHOLDER_INTERVIEW = "stakeholder_interview"
    RESEARCH = "research"
    ASSUMPTION = "assumption"
    DEFER = "defer"
    OTHER = "other"

class AssumptionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    CONFIRMED = "confirmed"

class QuestionAnswerType(StrEnum):
    TEXT = "text"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    BOOLEAN = "boolean"
    NUMBER = "number"

class QuestionStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DEFERRED = "deferred"
    ASSUMED = "assumed"
    NOT_APPLICABLE = "not_applicable"
