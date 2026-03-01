"""Jinja2-based prompt loader."""

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), keep_trailing_newline=True)


def load_agent_prompt() -> str:
    """Render the agent prompt template."""
    current_date = date.today().strftime("%B %d, %Y")
    template = _env.get_template("agent.j2")
    return template.render(current_date=current_date).strip()
