"""Minimal LLM connectivity test for the settings UI."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from archium.logging import get_logger

logger = get_logger(__name__, operation="llm_connection_test")

_TEST_PROMPT = "Return exactly ARCHIUM_CONNECTION_OK"
_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{8,})", re.IGNORECASE)
_AUTH_HINT_RE = re.compile(
    r"(api[\s_-]?key|invalid.?argument|authentication|unauthorized|permission|credentials?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    latency_ms: int = 0
    model: str = ""
    message: str = ""
    error_code: str | None = None
    detail: str | None = None


def normalize_api_key(api_key: str) -> str:
    """Strip whitespace, BOM, and accidental surrounding quotes from pasted keys."""
    cleaned = api_key.strip().replace("\ufeff", "").replace("\u200b", "")
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def normalize_base_url(base_url: str | None) -> str | None:
    if base_url is None:
        return None
    cleaned = base_url.strip()
    return cleaned or None


def _sanitize_detail(text: str) -> str:
    sanitized = _SECRET_RE.sub("***", text)
    return sanitized[:400]


def _message_from_api_error(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, list) and err:
            first = err[0]
            if isinstance(first, dict):
                nested = first.get("error")
                if isinstance(nested, dict) and nested.get("message"):
                    return str(nested["message"])
                if first.get("message"):
                    return str(first["message"])
    return str(exc)


def _is_auth_like_bad_request(exc: BadRequestError | APIStatusError) -> bool:
    text = _message_from_api_error(exc)
    status = getattr(exc, "status_code", None)
    if status in {401, 403}:
        return True
    return bool(_AUTH_HINT_RE.search(text))


def verify_llm_connection(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    timeout_seconds: float = 20.0,
    client: OpenAI | None = None,
) -> ConnectionTestResult:
    """Send a minimal chat completion to verify credentials and model access."""
    started_at = time.perf_counter()
    cleaned_key = normalize_api_key(api_key)
    cleaned_base = normalize_base_url(base_url)
    cleaned_model = model.strip()

    if not cleaned_key:
        return ConnectionTestResult(
            success=False,
            error_code="authentication_failed",
            message="API Key 为空，请重新输入。",
        )
    if not cleaned_model:
        return ConnectionTestResult(
            success=False,
            error_code="model_invalid",
            message="模型名称为空，请填写模型。",
        )

    llm_client = client or OpenAI(
        api_key=cleaned_key,
        base_url=cleaned_base,
        timeout=timeout_seconds,
        max_retries=0,
    )

    try:
        response = llm_client.chat.completions.create(
            model=cleaned_model,
            messages=[{"role": "user", "content": _TEST_PROMPT}],
            max_tokens=20,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ConnectionTestResult(
            success=True,
            latency_ms=latency_ms,
            model=cleaned_model,
            message=content,
        )
    except AuthenticationError as exc:
        return ConnectionTestResult(
            success=False,
            error_code="authentication_failed",
            message="API Key 无效或没有访问该模型的权限。",
            detail=_sanitize_detail(_message_from_api_error(exc)),
        )
    except PermissionDeniedError as exc:
        return ConnectionTestResult(
            success=False,
            error_code="authentication_failed",
            message="API Key 无权访问该模型或端点。",
            detail=_sanitize_detail(_message_from_api_error(exc)),
        )
    except NotFoundError as exc:
        return ConnectionTestResult(
            success=False,
            error_code="model_not_found",
            message=f"模型「{cleaned_model}」不存在或当前密钥不可用，请核对模型名与服务商。",
            detail=_sanitize_detail(_message_from_api_error(exc)),
        )
    except RateLimitError as exc:
        return ConnectionTestResult(
            success=False,
            error_code="rate_limited",
            message="请求受到限流，请稍后重试（免费额度用尽时也会出现）。",
            detail=_sanitize_detail(_message_from_api_error(exc)),
        )
    except BadRequestError as exc:
        # Gemini OpenAI-compat often returns 400 INVALID_ARGUMENT for bad keys
        # instead of 401 AuthenticationError.
        if _is_auth_like_bad_request(exc):
            return ConnectionTestResult(
                success=False,
                error_code="authentication_failed",
                message="API Key 无效或格式不正确（部分服务商会以 400 返回，而非 401）。",
                detail=_sanitize_detail(_message_from_api_error(exc)),
            )
        return ConnectionTestResult(
            success=False,
            error_code="bad_request",
            message="请求被拒绝，请检查模型名称、Base URL 是否与服务商匹配。",
            detail=_sanitize_detail(_message_from_api_error(exc)),
        )
    except (APIConnectionError, APITimeoutError) as exc:
        return ConnectionTestResult(
            success=False,
            error_code="connection_failed",
            message="无法连接到服务端，请检查 Base URL、代理与网络（Gemini 需能访问 Google）。",
            detail=_sanitize_detail(str(exc)),
        )
    except APIStatusError as exc:
        if _is_auth_like_bad_request(exc):
            return ConnectionTestResult(
                success=False,
                error_code="authentication_failed",
                message="API Key 无效或没有访问该模型的权限。",
                detail=_sanitize_detail(_message_from_api_error(exc)),
            )
        return ConnectionTestResult(
            success=False,
            error_code="provider_error",
            message=f"服务商返回错误（HTTP {exc.status_code}）。",
            detail=_sanitize_detail(_message_from_api_error(exc)),
        )
    except Exception as exc:
        logger.exception("LLM connection test failed unexpectedly")
        return ConnectionTestResult(
            success=False,
            error_code="unexpected_error",
            message="连接测试失败，请查看下方详情。",
            detail=_sanitize_detail(f"{type(exc).__name__}: {exc}"),
        )
