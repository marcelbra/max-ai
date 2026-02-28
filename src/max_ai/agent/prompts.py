"""Jinja2-based prompt loader."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), keep_trailing_newline=True)


def load_agent_prompt(voice_mode: bool = False) -> str:
    """Render the agent prompt template."""
    template = _env.get_template("agent.j2")
    return template.render(voice_mode=voice_mode).strip()
