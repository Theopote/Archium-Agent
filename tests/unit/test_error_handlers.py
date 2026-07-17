"""Unit tests for workflow error formatting."""

from __future__ import annotations

from archium.exceptions import ConfigurationError, WorkflowError
from archium.ui.error_handlers import format_user_error


def test_format_workflow_error() -> None:
    assert format_user_error(WorkflowError("pipeline failed")) == "工作流失败：pipeline failed"


def test_format_configuration_error() -> None:
    assert format_user_error(ConfigurationError("missing key")) == "配置错误：missing key"


def test_format_generic_error() -> None:
    assert format_user_error(RuntimeError("boom")) == "发生错误：boom"
