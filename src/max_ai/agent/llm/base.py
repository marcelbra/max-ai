from abc import ABC, abstractmethod
from typing import Any


class BaseLLM(ABC):
    """Abstract base class for LLM adapters."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier string for pydantic-ai."""
        pass

    @abstractmethod
    def get_client(self) -> Any:
        """Return the underlying client instance."""
        pass
