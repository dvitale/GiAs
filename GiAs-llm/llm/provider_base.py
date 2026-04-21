"""
Abstract base class for LLM provider backends.
All providers must implement query(), query_stream(), and ping().
"""

from abc import ABC, abstractmethod
from typing import Generator, Dict, Any, List, Optional


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

    # ------------------------------------------------------------------
    # Tool calling (used by ReAct agent). Providers that do not support
    # function calling should leave supports_tool_calling() = False.
    # ------------------------------------------------------------------

    def supports_tool_calling(self) -> bool:
        """Return True if the provider supports native tool/function calling."""
        return False

    def query_with_tools(
        self,
        messages: list,
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout: Optional[float] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send messages with OpenAI-style tools schema and return a provider-normalized dict.

        The returned dict always contains:
            {
                "content": str | None,           # assistant text (may be empty when tool_calls)
                "tool_calls": [                  # list, possibly empty
                    {"id": str, "name": str, "arguments": dict}
                ],
                "finish_reason": str | None,     # "stop" | "tool_calls" | ...
            }

        `tools` is the OpenAI-style schema list:
            [{"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}]

        Providers without native support MUST raise NotImplementedError.
        """
        raise NotImplementedError(
            f"{self.provider_name} does not support tool calling"
        )
