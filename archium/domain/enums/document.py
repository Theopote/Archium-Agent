"""Domain enumerations — document bounded context (DOM-018)."""

from enum import StrEnum


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    IMAGE = "image"
    OTHER = "other"

class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"

class VerificationStatus(StrEnum):
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    USER_CONFIRMED = "user_confirmed"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"

class DocumentPurpose(StrEnum):
    """Role of an imported document in project knowledge."""

    PROJECT_MATERIAL = "project_material"
    REFERENCE_CASE = "reference_case"
    REFERENCE_STYLE = "reference_style"
    POLICY = "policy"
    PUBLIC_RESEARCH = "public_research"
