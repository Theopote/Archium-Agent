from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.prompts.storyline import build_storyline_user_prompt


def test_storyline_prompt_includes_locked_narrative_mode() -> None:
    prompt = build_storyline_user_prompt(
        project_context="context",
        brief_json="{}",
        narrative_mode=ArchitecturalNarrativeMode.DECISION_FIRST,
    )
    assert "decision_first" in prompt
    assert "decision -> evidence -> strategy -> tension -> decision" in prompt

