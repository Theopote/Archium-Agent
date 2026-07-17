"""Streamlit helpers for surfacing application errors."""

from __future__ import annotations

from archium.exceptions import ArchiumError, ConfigurationError, WorkflowError


def format_user_error(exc: Exception) -> str:
    """Return a user-facing message for common Archium failures."""
    if isinstance(exc, ConfigurationError):
        return f"配置错误：{exc}"
    if isinstance(exc, WorkflowError):
        return f"工作流失败：{exc}"
    if isinstance(exc, ArchiumError):
        return str(exc)
    return f"发生错误：{exc}"
