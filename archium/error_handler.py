"""Global error handling and logging infrastructure."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from archium.exceptions import (
    AccessDeniedError,
    ArchiumError,
    ConcurrencyError,
    ConfigurationError,
    DocumentParseError,
    ExternalServiceError,
    FileOperationError,
    LLMProviderError,
    PresentationNotFoundError,
    ProjectNotFoundError,
    RateLimitError,
    RenderingError,
    RepositoryError,
    SlideRevisionNotFoundError,
    StructuredOutputError,
    UnsupportedOperationError,
    ValidationError,
    WorkflowError,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
P = ParamSpec('P')


class ErrorHandler:
    """Centralized error handling with logging and user-friendly messages."""
    
    def __init__(self) -> None:
        self._error_mappings: dict[type[Exception], str] = {
            ConfigurationError: "配置错误：请检查环境变量和设置",
            DocumentParseError: "文档解析失败：请检查文件格式是否支持",
            LLMProviderError: "AI服务连接失败：请检查API密钥和网络连接",
            StructuredOutputError: "AI输出格式错误：请重试或联系技术支持",
            RenderingError: "演示文稿渲染失败：请检查模板和内容格式",
            RepositoryError: "数据库操作失败：请稍后重试",
            AccessDeniedError: "权限不足：请检查您的访问权限",
            WorkflowError: "工作流执行失败：请检查输入参数",
            ValidationError: "数据验证失败：请检查输入格式",
            ProjectNotFoundError: "项目不存在：请检查项目ID",
            PresentationNotFoundError: "演示文稿不存在：请检查演示文稿ID",
            SlideRevisionNotFoundError: "幻灯片版本不存在：请检查版本ID",
            UnsupportedOperationError: "不支持的操作：此功能已被移除或禁用",
            ExternalServiceError: "外部服务错误：请稍后重试",
            FileOperationError: "文件操作失败：请检查文件路径和权限",
            ConcurrencyError: "并发冲突：请稍后重试",
            RateLimitError: "请求过于频繁：请稍后再试",
        }
    
    def handle_error(
        self,
        error: Exception,
        *,
        context: dict[str, Any] | None = None,
        user_friendly: bool = True,
    ) -> tuple[str, int]:
        """Handle an error and return (message, status_code).
        
        Args:
            error: The exception to handle
            context: Additional context information for logging
            user_friendly: Whether to return user-friendly messages
        
        Returns:
            Tuple of (error_message, http_status_code)
        """
        context = context or {}
        
        # Log the error with context
        log_context = ", ".join(f"{k}={v}" for k, v in context.items())
        logger.error(
            f"Error handling: {type(error).__name__}: {error}",
            extra={"context": log_context, "traceback": traceback.format_exc()},
        )
        
        # Determine user-friendly message
        message = self._get_user_message(error) if user_friendly else str(error)
        
        # Determine HTTP status code
        status_code = self._get_status_code(error)
        
        return message, status_code
    
    def _get_user_message(self, error: Exception) -> str:
        """Get user-friendly message for an error."""
        for error_type, default_message in self._error_mappings.items():
            if isinstance(error, error_type):
                # Use error-specific message if available, otherwise use default
                if str(error) and str(error) != f"{error_type.__name__}()":
                    return f"{default_message}：{str(error)}"
                return default_message
        
        # Fallback for unknown errors
        return f"发生错误：{str(error)}"
    
    def _get_status_code(self, error: Exception) -> int:
        """Map error types to HTTP status codes."""
        status_mappings: dict[type[Exception], int] = {
            ConfigurationError: 500,
            DocumentParseError: 422,
            LLMProviderError: 503,
            StructuredOutputError: 422,
            RenderingError: 422,
            RepositoryError: 500,
            AccessDeniedError: 403,
            WorkflowError: 422,
            ValidationError: 400,
            ProjectNotFoundError: 404,
            PresentationNotFoundError: 404,
            SlideRevisionNotFoundError: 404,
            UnsupportedOperationError: 400,
            ExternalServiceError: 502,
            FileOperationError: 422,
            ConcurrencyError: 409,
            RateLimitError: 429,
        }
        
        for error_type, status_code in status_mappings.items():
            if isinstance(error, error_type):
                return status_code
        
        return 500  # Internal Server Error for unknown errors


# Global error handler instance
_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_errors(
    *,
    error_mapping: dict[type[Exception], str] | None = None,
    default_message: str = "操作失败，请稍后重试",
    raise_on_error: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for consistent error handling in functions.
    
    Args:
        error_mapping: Custom error type to message mappings
        default_message: Default message for unmapped errors
        raise_on_error: Whether to re-raise the error after handling
    
    Example:
        @handle_errors(default_message="Failed to process presentation")
        def process_presentation(presentation_id: UUID) -> Result:
            # Function that might raise various exceptions
            return do_processing(presentation_id)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except ArchiumError as error:
                handler = get_error_handler()
                message, _ = handler.handle_error(
                    error,
                    context={"function": func.__name__},
                    user_friendly=True,
                )
                
                if raise_on_error:
                    raise
                else:
                    # For now, we'll just log and return None
                    # In a real application, this might return a Result type
                    logger.error(f"Function {func.__name__} failed: {message}")
                    raise  # Re-raise for now, can be changed to return error result
            except Exception as error:
                # Handle unexpected exceptions
                logger.error(
                    f"Unexpected error in {func.__name__}: {error}",
                    exc_info=True,
                )
                if raise_on_error:
                    raise
                else:
                    raise RuntimeError(default_message) from error
        
        return wrapper
    return decorator


@contextmanager
def error_context(
    operation: str,
    **context: Any,
) -> Iterator[None]:
    """Context manager for error handling with context.
    
    Args:
        operation: Description of the operation being performed
        **context: Additional context information
    
    Example:
        with error_context("database_query", table="projects", query="select *"):
            result = session.execute(query)
    """
    try:
        yield
    except ArchiumError as error:
        handler = get_error_handler()
        message, _ = handler.handle_error(
            error,
            context={"operation": operation, **context},
            user_friendly=True,
        )
        logger.error(f"Operation '{operation}' failed: {message}")
        raise
    except Exception as error:
        logger.error(
            f"Unexpected error in operation '{operation}': {error}",
            extra={"context": context},
            exc_info=True,
        )
        raise RuntimeError(f"操作 '{operation}' 失败：{str(error)}") from error


def safe_execute(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T | None:
    """Safely execute a function with error handling.
    
    Returns None if the function raises an exception, otherwise returns the result.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    
    Example:
        result = safe_execute(process_data, data)
        if result is None:
            # Handle error case
    """
    try:
        return func(*args, **kwargs)
    except Exception as error:
        handler = get_error_handler()
        message, _ = handler.handle_error(
            error,
            context={"function": func.__name__},
            user_friendly=False,
        )
        logger.error(f"Safe execution failed for {func.__name__}: {message}")
        return None
