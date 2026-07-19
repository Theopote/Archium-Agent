"""Structured error codes for Presentation Studio edit-time validation."""

from __future__ import annotations

from archium.exceptions import WorkflowError

STUDIO_ASSET_NOT_FOUND = "STUDIO.ASSET_NOT_FOUND"
STUDIO_ASSET_PROJECT_MISMATCH = "STUDIO.ASSET_PROJECT_MISMATCH"
STUDIO_ASSET_TYPE_INCOMPATIBLE = "STUDIO.ASSET_TYPE_INCOMPATIBLE"
STUDIO_ASSET_FILE_MISSING = "STUDIO.ASSET_FILE_MISSING"
STUDIO_DRAWING_REPLACED_BY_PHOTO = "STUDIO.DRAWING_REPLACED_BY_PHOTO"


class StudioAssetReferenceError(WorkflowError):
    """Raised when a Studio asset binding fails integrity checks."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
