# Prompt frameworks

Shared **reasoning protocols** injected into task SYSTEM prompts.

| Module | Constant | Role |
|--------|----------|------|
| `architectural_reasoning.py` | `ARCHITECTURAL_REASONING_FRAMEWORK` | Context → Problem → Intent → Spatial → Expression → Verify（输出落点 `design_rationale` 链） |
| `design_critique.py` | `DESIGN_CRITIQUE_FRAMEWORK` | Independent five-question critique |
| `research_knowledge.py` | `RESEARCH_KNOWLEDGE_FRAMEWORK` | Case dump → transferable design knowledge |

Version strings live next to each framework (`*_VERSION`). Task prompts that include a
framework should bump their own `PROMPT_VERSION` when the include or wrapping text changes.

Not Agent classes — fragments only.
