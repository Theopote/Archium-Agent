"""统一错误处理中间件 - 捕获和友好展示所有错误。"""

from __future__ import annotations

import logging
from typing import Callable, Any
from functools import wraps

import streamlit as st

from archium.ui.components.enhanced_ui import render_error_message

logger = logging.getLogger(__name__)


class ErrorTranslator:
    """将技术错误翻译为用户友好的消息。"""

    _translations = {
        # 验证错误
        "ValidationError": {
            "title": "输入验证失败",
            "message": "请检查表单内容是否符合要求",
            "suggestions": [
                "确保所有必填字段都已填写",
                "检查输入格式是否正确",
                "避免使用特殊字符",
            ],
        },
        # 项目错误
        "ProjectNotFoundError": {
            "title": "项目不存在",
            "message": "该项目可能已被删除或您没有访问权限",
            "suggestions": [
                "返回项目列表重新选择",
                "检查是否选择了正确的项目",
            ],
        },
        "ProjectAlreadyExistsError": {
            "title": "项目已存在",
            "message": "已经存在同名项目",
            "suggestions": [
                "使用不同的项目名称",
                "打开已有项目继续工作",
            ],
        },
        # 工作流错误
        "WorkflowError": {
            "title": "工作流执行失败",
            "message": "处理过程中出现问题，请重试",
            "suggestions": [
                "检查网络连接是否正常",
                "确认 API 配置正确",
                "稍后重试",
            ],
        },
        # 网络错误
        "ConnectionError": {
            "title": "网络连接失败",
            "message": "无法连接到服务器",
            "suggestions": [
                "检查网络连接",
                "确认服务是否正常运行",
                "检查防火墙设置",
            ],
        },
        "TimeoutError": {
            "title": "操作超时",
            "message": "请求处理时间过长",
            "suggestions": [
                "检查网络速度",
                "尝试减少数据量",
                "稍后重试",
            ],
        },
        # 权限错误
        "PermissionError": {
            "title": "权限不足",
            "message": "您没有执行此操作的权限",
            "suggestions": [
                "联系管理员获取权限",
                "使用其他账号登录",
            ],
        },
        # 文件错误
        "FileNotFoundError": {
            "title": "文件不存在",
            "message": "找不到指定的文件",
            "suggestions": [
                "检查文件路径是否正确",
                "确认文件未被移动或删除",
            ],
        },
        # LLM 错误
        "APIError": {
            "title": "API 调用失败",
            "message": "与 AI 服务通信出现问题",
            "suggestions": [
                "检查 API Key 是否配置正确",
                "确认服务额度充足",
                "稍后重试",
            ],
        },
        "RateLimitError": {
            "title": "请求过于频繁",
            "message": "已达到 API 调用限制",
            "suggestions": [
                "等待几分钟后重试",
                "升级服务套餐",
            ],
        },
    }

    @classmethod
    def translate(cls, error: Exception) -> dict[str, Any]:
        """翻译错误为用户友好的信息。

        Returns:
            dict with keys: title, message, suggestions, show_details
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # 查找匹配的翻译
        for key, translation in cls._translations.items():
            if key in error_type or key in error_msg:
                return {
                    "title": translation["title"],
                    "message": translation["message"],
                    "suggestions": translation["suggestions"],
                    "show_details": True,
                    "original_error": error,
                }

        # 默认翻译
        return {
            "title": "操作失败",
            "message": "出现意外错误，请重试或联系支持",
            "suggestions": [
                "刷新页面重试",
                "检查输入是否正确",
                "查看详细错误信息",
            ],
            "show_details": True,
            "original_error": error,
        }


def with_error_handling(func: Callable) -> Callable:
    """装饰器：为函数添加统一错误处理。

    Usage:
        @with_error_handling
        def my_function():
            # 可能抛出错误的代码
            pass
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            _render_friendly_error(e, context=func.__name__)
            return None

    return wrapper


def _render_friendly_error(error: Exception, context: str | None = None) -> None:
    """渲染用户友好的错误信息。"""
    translation = ErrorTranslator.translate(error)

    # 如果有上下文，添加到标题
    title = translation["title"]
    if context:
        title = f"{title} ({context})"

    # 渲染错误消息
    st.error(f"**{title}**")
    st.markdown(translation["message"])

    # 显示建议
    if translation.get("suggestions"):
        with st.expander("💡 解决建议", expanded=True):
            for suggestion in translation["suggestions"]:
                st.markdown(f"- {suggestion}")

    # 显示技术细节
    if translation.get("show_details"):
        with st.expander("🔧 技术细节", expanded=False):
            st.code(str(translation.get("original_error", error)), language="text")

    # 提供反馈选项
    with st.expander("📝 报告问题", expanded=False):
        st.markdown("如果问题持续出现，请提供以下信息给技术支持：")
        st.code(
            f"错误类型: {type(error).__name__}\n"
            f"上下文: {context or 'N/A'}\n"
            f"错误消息: {str(error)[:200]}",
            language="text",
        )
        if st.button("复制错误信息", key=f"copy_error_{id(error)}"):
            st.success("错误信息已复制到剪贴板（模拟）")


def safe_execute(
    func: Callable,
    *args,
    fallback_value: Any = None,
    error_message: str | None = None,
    **kwargs,
) -> Any:
    """安全执行函数，捕获错误并返回 fallback 值。

    Args:
        func: 要执行的函数
        *args: 函数参数
        fallback_value: 出错时返回的默认值
        error_message: 自定义错误消息
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果或 fallback_value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.exception(f"Safe execute failed: {e}")
        if error_message:
            st.warning(error_message)
        else:
            _render_friendly_error(e, context=func.__name__)
        return fallback_value


class ErrorBoundary:
    """错误边界上下文管理器。

    Usage:
        with ErrorBoundary("加载项目数据"):
            # 可能出错的代码
            load_project_data()
    """

    def __init__(self, context: str, show_error: bool = True):
        self.context = context
        self.show_error = show_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.exception(f"Error in {self.context}: {exc_val}")
            if self.show_error:
                _render_friendly_error(exc_val, context=self.context)
            # 返回 True 表示异常已处理，不再向上传播
            return True
        return False
