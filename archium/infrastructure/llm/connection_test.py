"""Minimal LLM connectivity test for the settings UI."""

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import APIConnectionError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from archium.logging import get_logger

logger = get_logger(__name__, operation="llm_connection_test")

_TEST_PROMPT = "Return exactly ARCHIUM_CONNECTION_OK"


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    latency_ms: int = 0
    model: str = ""
    message: str = ""
    error_code: str | None = None


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
    llm_client = client or OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout_seconds,
        max_retries=0,
    )

    try:
        response = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _TEST_PROMPT}],
            max_tokens=20,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ConnectionTestResult(
            success=True,
            latency_ms=latency_ms,
            model=model,
            message=content,
        )
    except AuthenticationError:
        return ConnectionTestResult(
            success=False,
            error_code="authentication_failed",
            message="API Key 无效或没有访问该模型的权限。",
        )
    except RateLimitError:
        return ConnectionTestResult(
            success=False,
            error_code="rate_limited",
            message="请求受到限流，请稍后重试。",
        )
    except (APIConnectionError, APITimeoutError):
        return ConnectionTestResult(
            success=False,
            error_code="connection_failed",
            message="连接失败，请检查地址、模型和网络。",
        )
    except Exception:
        logger.exception("LLM connection test failed")
        return ConnectionTestResult(
            success=False,
            error_code="connection_failed",
            message="连接失败，请检查地址、模型和网络。",
        )
