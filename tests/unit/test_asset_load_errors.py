"""Tests for asset image load error classification."""

from __future__ import annotations

from archium.domain.review_rules import ReviewRuleCode
from archium.infrastructure.vision.asset_load_errors import rule_code_for_asset_load_error


def test_rule_code_for_asset_load_error_maps_file_not_found() -> None:
    assert (
        rule_code_for_asset_load_error(FileNotFoundError("missing"))
        == ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND
    )


def test_rule_code_for_asset_load_error_maps_permission_error() -> None:
    assert (
        rule_code_for_asset_load_error(PermissionError("denied"))
        == ReviewRuleCode.VISUAL_ASSET_PERMISSION_DENIED
    )


def test_rule_code_for_asset_load_error_maps_unknown_to_unreadable() -> None:
    assert (
        rule_code_for_asset_load_error(RuntimeError("boom"))
        == ReviewRuleCode.VISUAL_ASSET_UNREADABLE
    )
