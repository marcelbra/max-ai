"""Jinja2-based prompt loader."""

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_AGENT_DIR = Path(__file__).parent
_env = Environment(
    loader=FileSystemLoader(_AGENT_DIR),
    keep_trailing_newline=True,
)


def load_agent_prompt() -> str:
    """Render the agent prompt template."""
    current_date = date.today().strftime("%B %d, %Y")
    template = _env.get_template("system_prompt.j2")
    return str(template.render(current_date=current_date)).strip()
