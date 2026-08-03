"""Unit tests for workflow error formatting."""

from __future__ import annotations

from uuid import uuid4

from archium.exceptions import (
    ConfigurationError,
    DocumentParseError,
    ExternalServiceError,
    LLMProviderError,
    ProjectNotFoundError,
    RenderingError,
    ValidationError,
    WorkflowError,
)
from archium.ui.error_handlers import GENERIC_USER_ERROR, format_user_error, report_user_error


def test_format_workflow_error() -> None:
    assert format_user_error(WorkflowError("pipeline failed")) == "pipeline failed"


def test_format_configuration_error() -> None:
    assert format_user_error(ConfigurationError("missing key")) == (
        "配置错误，请联系管理员检查系统设置。"
    )


def test_format_project_not_found_error() -> None:
    assert format_user_error(ProjectNotFoundError(uuid4())) == "项目不存在或已被删除，请刷新页面。"


def test_format_validation_error() -> None:
    assert format_user_error(ValidationError("项目名称不能为空")) == "项目名称不能为空"


def test_format_document_parse_error() -> None:
    assert format_user_error(DocumentParseError("bad pdf")) == "文档解析失败：bad pdf"


def test_format_llm_provider_error() -> None:
    assert "模型调用失败" in format_user_error(LLMProviderError("timeout"))


def test_format_rendering_error() -> None:
    assert format_user_error(RenderingError("pptx failed")) == "渲染失败：pptx failed"


def test_format_external_service_error() -> None:
    message = format_user_error(
        ExternalServiceError("missing binary", service_name="LibreOffice")
    )
    assert "LibreOffice" in message
    assert "外部工具不可用" in message


def test_format_generic_error() -> None:
    assert format_user_error(RuntimeError("boom")) == GENERIC_USER_ERROR


def test_report_user_error_hides_unexpected_exception() -> None:
    assert report_user_error(RuntimeError("database path /secret/db.sqlite")) == GENERIC_USER_ERROR
