"""Slide recovery tool workflow steps (DOM-007)."""

from enum import StrEnum


class SlideRecoveryWorkflowStep(StrEnum):
    SLIDE_RECOVERY_QUEUED = "slide_recovery_queued"
    SLIDE_RECOVERY_OCR = "slide_recovery_ocr"
    SLIDE_RECOVERY_VLM_ANALYSIS = "slide_recovery_vlm_analysis"
    SLIDE_RECOVERY_REGION_RECOVERY = "slide_recovery_region_recovery"
    SLIDE_RECOVERY_HYBRID_SCENE = "slide_recovery_hybrid_scene"
    SLIDE_RECOVERY_QA = "slide_recovery_qa"
    SLIDE_RECOVERY_AWAIT_REVIEW = "slide_recovery_await_review"
    SLIDE_RECOVERY_FINALIZE = "slide_recovery_finalize"
