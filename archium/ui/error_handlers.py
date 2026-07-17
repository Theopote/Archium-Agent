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


def format_user_error(exc: Exception) -> str:
    """Return a user-facing message for common Archium failures."""
    if isinstance(exc, ConfigurationError):
        return f"配置错误：{exc}"
    if isinstance(exc, WorkflowError):
        return f"工作流失败：{exc}"
    if isinstance(exc, ProjectNotFoundError):
        return f"项目不存在：{exc.project_id}"
    if isinstance(exc, PresentationNotFoundError):
        return f"汇报不存在：{exc.presentation_id}"
    if isinstance(exc, SlideRevisionNotFoundError):
        return f"页面修订不存在：{exc.revision_id}"
    if isinstance(exc, ValidationError):
        return f"输入无效：{exc}"
    if isinstance(exc, ArchiumError):
        return str(exc)
    return f"发生错误：{exc}"
