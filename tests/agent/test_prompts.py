"""Tests for the agent prompt loader."""

from datetime import date


def test_load_agent_prompt_returns_nonempty_string() -> None:
    from max_ai.agent.prompts import load_agent_prompt

    prompt = load_agent_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_load_agent_prompt_contains_current_date() -> None:
    from max_ai.agent.prompts import load_agent_prompt

    prompt = load_agent_prompt()
    current_date = date.today().strftime("%B %d, %Y")
    assert current_date in prompt


def test_load_agent_prompt_contains_expected_sections() -> None:
    from max_ai.agent.prompts import load_agent_prompt

    prompt = load_agent_prompt()
    assert "Max" in prompt
    assert "Behavior" in prompt
    assert "Guardrails" in prompt
