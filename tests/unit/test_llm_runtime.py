"""Unit tests for LLMRuntime, capabilities, and LLMTrace."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from archium.config.settings import Settings
from archium.domain.model_roles import ModelRole
from archium.infrastructure.llm.base import LLMRequest, LLMResponse
from archium.infrastructure.llm.call import generate_structured
from archium.infrastructure.llm.capabilities import (
    LLMCapability,
    model_role_for_capability,
)
from archium.infrastructure.llm.mock import MockLLMProvider
from archium.infrastructure.llm.runtime import LLMRuntime
from archium.infrastructure.llm.trace import (
    InMemoryLLMTraceRecorder,
    get_llm_trace_recorder,
    set_llm_trace_recorder,
    usage_from_openai_completion,
)


class _TinyDraft(BaseModel):
    title: str = ""


@pytest.fixture(autouse=True)
def _fresh_trace_recorder():
    recorder = InMemoryLLMTraceRecorder(maxlen=50)
    set_llm_trace_recorder(recorder)
    yield recorder
    set_llm_trace_recorder(None)


def test_capability_maps_to_model_role() -> None:
    assert model_role_for_capability(LLMCapability.CONCEPT_GENERATION) == ModelRole.PLANNING
    assert model_role_for_capability(LLMCapability.RESEARCH_SYNTHESIS) == ModelRole.RESEARCH
    assert model_role_for_capability(LLMCapability.DESIGN_CRITIQUE) == ModelRole.PLANNING


def test_usage_from_openai_completion() -> None:
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15
    response = MagicMock()
    response.usage = usage
    parsed = usage_from_openai_completion(response)
    assert parsed.prompt_tokens == 10
    assert parsed.total_tokens == 15


def test_runtime_records_trace_and_prompt_version() -> None:
    provider = MockLLMProvider(default_text='{"title": "台地"}')
    settings = Settings(_env_file=None, llm_model="test-model", llm_provider="mock")
    runtime = LLMRuntime(provider, settings=settings)

    draft = runtime.generate_structured(
        LLMRequest(
            system_prompt="sys",
            user_prompt="user",
            metadata={"prompt_version": "concept_direction.v2"},
        ),
        _TinyDraft,
        capability=LLMCapability.CONCEPT_GENERATION,
        project_id="proj-1",
    )
    assert draft.title == "台地"
    traces = get_llm_trace_recorder().list_recent()
    assert traces
    last = traces[-1]
    assert last.success is True
    assert last.capability == LLMCapability.CONCEPT_GENERATION.value
    assert last.prompt_version == "concept_direction.v2"
    assert last.project_id == "proj-1"
    assert last.model_role == ModelRole.PLANNING.value
    assert provider.calls[-1].metadata.get("capability") == "concept_generation"


def test_generate_structured_helper_wraps_provider(_fresh_trace_recorder) -> None:
    provider = MockLLMProvider(default_text='{"title": "x"}')
    settings = Settings(_env_file=None, llm_model="m", llm_provider="mock")
    draft = generate_structured(
        provider,
        LLMRequest(system_prompt="s", user_prompt="u"),
        _TinyDraft,
        capability=LLMCapability.IDEA_SEED,
        settings=settings,
    )
    assert draft.title == "x"
    assert _fresh_trace_recorder.list_recent()[-1].capability == "idea_seed"


def test_openai_provider_captures_usage() -> None:
    from archium.infrastructure.llm.openai_compatible import OpenAICompatibleProvider

    client = MagicMock()
    choice = MagicMock()
    choice.message.content = '{"title": "ok"}'
    choice.finish_reason = "stop"
    response = MagicMock()
    response.model = "gpt-test"
    response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 3
    usage.completion_tokens = 2
    usage.total_tokens = 5
    response.usage = usage
    client.chat.completions.create.return_value = response

    settings = Settings(_env_file=None, llm_api_key="k", llm_model="gpt-test")
    provider = OpenAICompatibleProvider(settings, client=client)
    text = provider.generate_text(LLMRequest(system_prompt="s", user_prompt="u"))
    assert text == '{"title": "ok"}'
    assert provider.last_response is not None
    assert provider.last_response.total_tokens == 5
    assert isinstance(provider.last_response, LLMResponse)
