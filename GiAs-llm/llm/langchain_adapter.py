"""
LangChain ChatModel adapter for the project's LLMClient facade.

Exposes `GiAsLLM`, a `BaseChatModel` subclass that delegates generation to
our multi-provider `LLMClient` (Ollama, llama.cpp, OpenAI, Anthropic,
OpenAI-compatible). This allows the ReAct agent (`langgraph.prebuilt.
create_react_agent`) to drive our existing LLM stack without bypassing
provider selection, GDPR checks, timeouts and fallback logic.

Design:
- `_generate` handles both pure-text generation and tool calling.
- `bind_tools` converts LangChain tools to the OpenAI-style schema once
  and returns a `RunnableBinding` (the standard LangChain pattern).
- Tool call responses are turned into `AIMessage(tool_calls=...)` so that
  the ReAct loop inside LangGraph can dispatch them.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field

from .client import LLMClient

logger = logging.getLogger(__name__)


def _lc_messages_to_provider(messages: Sequence[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert LangChain messages to the provider wire format."""
    out: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            out.append({"role": "system", "content": m.content or ""})
        elif isinstance(m, HumanMessage):
            out.append({"role": "user", "content": m.content or ""})
        elif isinstance(m, AIMessage):
            entry: Dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            tool_calls = getattr(m, "tool_calls", None) or []
            if tool_calls:
                import json as _json
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id") or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": _json.dumps(tc.get("args", {}) or {}),
                        },
                    }
                    for i, tc in enumerate(tool_calls)
                ]
            out.append(entry)
        elif isinstance(m, ToolMessage):
            out.append({
                "role": "tool",
                "tool_call_id": m.tool_call_id,
                "content": m.content if isinstance(m.content, str) else str(m.content),
            })
        else:
            out.append({"role": "user", "content": getattr(m, "content", "") or ""})
    return out


class GiAsLLM(BaseChatModel):
    """BaseChatModel that delegates to the project `LLMClient`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: LLMClient = Field(...)
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: Optional[float] = None

    @property
    def _llm_type(self) -> str:
        return "gias-llm"

    # ------------------------------------------------------------------
    # Tool binding
    # ------------------------------------------------------------------

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ):
        """Bind tools (LangChain @tool or dict schema) to this model.

        Returns a Runnable binding so that `.invoke(messages)` transparently
        forwards the tools schema to `_generate`.
        """
        schemas = [convert_to_openai_tool(t) for t in tools]
        bound_kwargs: Dict[str, Any] = {"tools": schemas}
        if tool_choice:
            bound_kwargs["tool_choice"] = tool_choice
        return self.bind(**bound_kwargs, **kwargs)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        provider_messages = _lc_messages_to_provider(messages)
        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        timeout = kwargs.get("timeout", self.timeout)

        if tools and self.client.supports_tool_calling():
            result = self.client.query_with_tools(
                messages=provider_messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tool_choice=tool_choice,
            )
            ai = AIMessage(
                content=result.get("content") or "",
                tool_calls=[
                    {"id": tc["id"], "name": tc["name"], "args": tc.get("arguments", {}) or {}}
                    for tc in result.get("tool_calls", [])
                ],
            )
            return ChatResult(generations=[ChatGeneration(message=ai)])

        text = self.client.query(
            messages=provider_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        if stop:
            for s in stop:
                if s and s in text:
                    text = text.split(s, 1)[0]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
