"""Unit tests for product_flow helpers."""

from __future__ import annotations

import pytest
from archium.ui.product_flow import get_stage, next_stage, previous_stage


def test_unknown_stage_raises() -> None:
    with pytest.raises(KeyError):
        get_stage("missing")
    with pytest.raises(KeyError):
        next_stage("missing")
    with pytest.raises(KeyError):
        previous_stage("missing")
