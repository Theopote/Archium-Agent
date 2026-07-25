# LLM infrastructure

Capability runtime for Archium (not Agent classes).

| Module | Role |
|--------|------|
| `base.py` | `LLMProvider` Protocol, `LLMRequest` / `LLMResponse` (+ usage) |
| `factory.py` | Create mock / openai_compatible providers |
| `openai_compatible.py` | OpenAI SDK adapter (Gemini etc.) |
| `mock.py` | Deterministic tests |
| `structured.py` | JSON → Pydantic validate |
| `capabilities.py` | Task capability → `ModelRole` |
| `runtime.py` | Capability → model resolve → call → `LLMTrace` |
| `call.py` | Service helper `generate_structured(...)` |
| `trace.py` | In-memory `LLMTrace` recorder |
| `*_schemas.py` | Draft models for structured output |

Services should prefer `archium.infrastructure.llm.call.generate_structured` with an
`LLMCapability` and `metadata={"prompt_version": ...}` rather than picking models.
