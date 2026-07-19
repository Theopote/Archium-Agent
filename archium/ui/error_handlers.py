"""Streamlit helpers for surfacing application errors."""

from __future__ import annotations

from archium.exceptions import (
    ArchiumError,
    ConfigurationError,
    PresentationNotFoundError,
    ProjectNotFoundError,
    SlideRevisionNotFoundError,
    ValidationError,
    WorkflowError,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="ui_errors")

GENERIC_USER_ERROR = "操作失败，请稍后重试。若问题持续，请联系管理员。"


def format_user_error(exc: Exception) -> str:
    """Return a user-facing message for common Archium failures."""
    if isinstance(exc, ConfigurationError):
        return "配置错误，请联系管理员检查系统设置。"
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


def report_user_error(exc: Exception) -> str:
    """Log unexpected failures and return a safe message for Streamlit."""
    if isinstance(exc, ArchiumError):
        return format_user_error(exc)
    logger.exception("Unexpected UI error")
    return GENERIC_USER_ERROR
