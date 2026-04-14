# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""
Orchestratore ReAct: singolo nodo che sostituisce classify + dialogue_manager
+ tool_wrappers + response_generator del grafo legacy.

L'agente e' costruito via `langgraph.prebuilt.create_react_agent` con il
nostro `GiAsLLM` come ChatModel e i tool prodotti da `tool_registry.
build_agent_tools(metadata)`. Il loop interno di LangGraph gestisce:
    (1) LLM riceve messaggi + tools schema
    (2) risponde con tool_calls -> ToolNode esegue -> feedback -> torna a (1)
    (3) risponde con testo -> fine

Il nodo espone `run(message, metadata, session_context)` che ritorna un dict
piatto compatibile con il `ConversationState` del grafo esistente.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from llm.client import LLMClient
from llm.langchain_adapter import GiAsLLM

from .react_prompts import build_system_prompt
from .tool_registry import DetailStore, build_agent_tools

logger = logging.getLogger(__name__)


_MAX_HISTORY_TURNS = 3  # ultimi N turni (6 messaggi) nel contesto


class ReactOrchestrator:
    """Orchestratore agentico basato su create_react_agent."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._client = llm_client or LLMClient()
        self._adapter = GiAsLLM(client=self._client)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def run(
        self,
        message: str,
        metadata: Dict[str, Any],
        session_context: Optional[Dict[str, Any]] = None,
        detail_store: Optional[DetailStore] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Esegue un turno.

        Args:
            message: messaggio utente corrente.
            metadata: session metadata (asl, user_id, uos, ...).
            session_context: ultimo intent/riassunto per anaforica.
            detail_store: store two-phase per la sessione.
            history: lista di turni precedenti come [{role, content}, ...].

        Returns:
            dict con chiavi compatibili con ConversationState:
                final_response, intent, slots, tool_output, tool_name,
                tool_calls_trace, has_more_details, detail_context_id.
        """
        store = detail_store if detail_store is not None else DetailStore()
        tools = build_agent_tools(metadata, detail_store=store)
        system_prompt = build_system_prompt(metadata, session_context)

        agent = create_react_agent(
            model=self._adapter,
            tools=tools,
            prompt=system_prompt,
        )

        messages = self._build_messages(message, history)
        try:
            result = agent.invoke({"messages": messages})
        except Exception as exc:
            logger.exception("ReactOrchestrator.invoke failed: %s", exc)
            return {
                "final_response": (
                    "Mi dispiace, si e' verificato un errore interno. Riprova tra qualche istante."
                ),
                "error": str(exc),
                "intent": "agent_error",
                "slots": {},
                "tool_output": None,
                "tool_name": None,
                "tool_calls_trace": [],
                "has_more_details": False,
                "detail_context_id": None,
            }

        return self._extract_result(result, store)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        message: str,
        history: Optional[List[Dict[str, Any]]],
    ) -> List[Any]:
        msgs: List[Any] = []
        if history:
            recent = history[-(_MAX_HISTORY_TURNS * 2):]
            for m in recent:
                role = m.get("role")
                content = m.get("content", "")
                if not content:
                    continue
                if role == "user":
                    msgs.append(HumanMessage(content=content))
                elif role == "assistant":
                    msgs.append(AIMessage(content=content))
                elif role == "system":
                    msgs.append(SystemMessage(content=content))
        msgs.append(HumanMessage(content=message))
        return msgs

    def _extract_result(self, agent_result: Dict[str, Any], store: DetailStore) -> Dict[str, Any]:
        messages = agent_result.get("messages", []) or []
        final_ai: Optional[AIMessage] = None
        tool_trace: List[Dict[str, Any]] = []
        last_tool_output: Any = None
        last_tool_name: Optional[str] = None

        for m in messages:
            # AIMessage: raccogli tool_calls trace e tieni traccia dell'ultima risposta
            if isinstance(m, AIMessage):
                for tc in getattr(m, "tool_calls", []) or []:
                    tool_trace.append({
                        "id": tc.get("id"),
                        "name": tc.get("name"),
                        "args": tc.get("args", {}),
                    })
                if m.content and not (getattr(m, "tool_calls", None) or []):
                    final_ai = m
            else:
                # ToolMessage
                role = getattr(m, "role", None) or (m.type if hasattr(m, "type") else None)
                if role == "tool" or getattr(m, "type", "") == "tool":
                    last_tool_output = getattr(m, "content", None)
                    last_tool_name = getattr(m, "name", None) or last_tool_name

        final_text = ""
        if final_ai is not None:
            content = final_ai.content
            final_text = content if isinstance(content, str) else str(content)

        # Se l'agente non ha prodotto testo finale ma esiste un tool output, usa formatted_response
        if not final_text and last_tool_output:
            final_text = self._fallback_text_from_tool(last_tool_output)

        # Intent derivato dal primo tool chiamato (o "agent" se nessuno)
        intent = tool_trace[0]["name"] if tool_trace else "agent_conversation"

        # Detail context id (two-phase): cerca l'ultimo payload nello store
        detail_ctx = None
        last_payload = store.last()
        if last_payload:
            # il context_id non e' memorizzato nel payload; lo ricaviamo dai risultati tool
            for tc in tool_trace:
                args = tc.get("args", {}) or {}
                if "context_id" in args:
                    detail_ctx = args["context_id"]

        return {
            "final_response": final_text.strip(),
            "intent": intent,
            "slots": tool_trace[0]["args"] if tool_trace else {},
            "tool_output": {"type": intent, "data": last_tool_output} if last_tool_output else None,
            "tool_name": last_tool_name or intent,
            "tool_calls_trace": tool_trace,
            "has_more_details": bool(last_payload),
            "detail_context_id": detail_ctx,
        }

    @staticmethod
    def _fallback_text_from_tool(tool_content: Any) -> str:
        """Quando l'LLM non produce testo finale, usa il formatted_response del tool."""
        if isinstance(tool_content, str):
            return tool_content
        if isinstance(tool_content, dict):
            fr = tool_content.get("formatted_response")
            if fr:
                return str(fr)
        return ""
