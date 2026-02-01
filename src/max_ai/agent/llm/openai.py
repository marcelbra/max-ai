from openai import AsyncOpenAI

from max_ai.core.config import get_settings

from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI LLM adapter."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self._model = model or settings.llm_model
        self._api_key = api_key or settings.openai_api_key
        self._client = AsyncOpenAI(api_key=self._api_key)

    def get_model_name(self) -> str:
        """Return the OpenAI model identifier for pydantic-ai."""
        return f"openai:{self._model}"

    def get_client(self) -> AsyncOpenAI:
        """Return the AsyncOpenAI client instance."""
        return self._client
