"""Jinja2-based prompt loader."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), keep_trailing_newline=True)


def load_prompt(name: str, **kwargs: object) -> str:
    """Render a prompt template by name (without the .j2 extension)."""
    template = _env.get_template(f"{name}.j2")
    return template.render(**kwargs).strip()
