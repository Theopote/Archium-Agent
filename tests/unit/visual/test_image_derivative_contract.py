"""Image derivative pipeline is NOT IMPLEMENTED — contract only."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.image_derivative_executor import (
    ImageDerivativeExecutor,
    ImageDerivativeNotImplementedError,
)
from archium.domain.visual.image_derivative import (
    ImageAssetClass,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    mode_allowed_for_asset_class,
)


def test_executor_not_implemented() -> None:
    executor = ImageDerivativeExecutor()
    assert executor.is_available() is False
    spec = ImageTreatmentSpec(original_asset_id=uuid4(), mode=ImageTreatmentMode.SAFE_NORMALIZE)
    with pytest.raises(ImageDerivativeNotImplementedError, match="NOT IMPLEMENTED"):
        executor.execute(spec)


def test_evidence_assets_cannot_use_presentation_unify() -> None:
    assert mode_allowed_for_asset_class(
        ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
        ImageTreatmentMode.SAFE_NORMALIZE,
    )
    assert not mode_allowed_for_asset_class(
        ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
        ImageTreatmentMode.PRESENTATION_UNIFY,
    )
    assert mode_allowed_for_asset_class(
        ImageAssetClass.PRESENTATION,
        ImageTreatmentMode.PRESENTATION_UNIFY,
    )
