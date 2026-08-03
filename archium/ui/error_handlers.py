"""Streamlit helpers for surfacing application errors."""

from __future__ import annotations

from archium.exceptions import (
    ArchiumError,
    ConfigurationError,
    DocumentParseError,
    ExternalServiceError,
    LLMProviderError,
    PresentationNotFoundError,
    ProjectNotFoundError,
    RenderingError,
    SlideRevisionNotFoundError,
    ValidationError,
    WorkflowError,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="ui_errors")

GENERIC_USER_ERROR = "操作失败，请稍后重试。若问题持续，请联系管理员。"


def format_user_error(exc: BaseException) -> str:
    """Return a user-facing message for known Archium failures (no logging)."""
    if isinstance(exc, ConfigurationError):
        return "配置错误，请联系管理员检查系统设置。"
    if isinstance(exc, DocumentParseError):
        return f"文档解析失败：{exc}"
    if isinstance(exc, LLMProviderError):
        return "模型调用失败，请检查网络或 API 配置后重试。"
    if isinstance(exc, RenderingError):
        return f"渲染失败：{exc}"
    if isinstance(exc, ExternalServiceError):
        service = f"（{exc.service_name}）" if exc.service_name else ""
        return f"外部工具不可用{service}：{exc}"
    if isinstance(exc, WorkflowError):
        return str(exc)
    if isinstance(exc, ProjectNotFoundError):
        return "项目不存在或已被删除，请刷新页面。"
    if isinstance(exc, PresentationNotFoundError):
        return "汇报不存在或已被删除，请刷新页面。"
    if isinstance(exc, SlideRevisionNotFoundError):
        return "页面修订不存在或已被删除，请刷新页面。"
    if isinstance(exc, ValidationError):
        return str(exc)
    if isinstance(exc, ArchiumError):
        return "操作失败，请稍后重试。"
    return GENERIC_USER_ERROR


def report_user_error(exc: BaseException) -> str:
    """Map failures for Streamlit; log unknowns so they are never silent.

    Use this in ``except Exception`` / catch-all UI handlers.
    """
    if isinstance(exc, ArchiumError):
        return format_user_error(exc)
    logger.exception("Unexpected UI error")
    return GENERIC_USER_ERROR


def surface_ui_error(exc: BaseException) -> str:
    """Preferred UI catch-all alias for ``report_user_error``."""
    return report_user_error(exc)
