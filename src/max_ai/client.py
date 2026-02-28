import anthropic

from max_ai.config import settings


def create_client() -> anthropic.AsyncAnthropic:
    """Create and return an async Anthropic client."""
    if not settings.anthropic_api_key:
        raise ValueError(
            "Missing MAX_AI_ANTHROPIC_API_KEY. Set it in your .env file or environment."
        )
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
