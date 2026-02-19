"""
Abstract base class for LLM provider backends.
All providers must implement query(), query_stream(), and ping().
"""

from abc import ABC, abstractmethod
from typing import Generator, Dict, Any


class LLMProvider(ABC):
    """Abstract base class for LLM provider backends."""

    def __init__(self, model: str, config: Dict[str, Any]):
        self.model = model
        self.config = config
        self.timeout = config.get("timeout_seconds", 60)

    @abstractmethod
    def query(self, messages: list, temperature: float, max_tokens: int,
              json_mode: bool = False, timeout: float = None) -> str:
        """Send messages and return complete response."""
        ...

    @abstractmethod
    def query_stream(self, messages: list, temperature: float, max_tokens: int,
                     json_mode: bool = False, timeout: float = None) -> Generator[str, None, None]:
        """Send messages and yield tokens as they arrive."""
        ...

    @abstractmethod
    def ping(self) -> bool:
        """Health check - returns True if provider is available."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...
