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
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from llm.client import LLMClient
from llm.langchain_adapter import GiAsLLM

from .react_prompts import build_system_prompt
from .tool_registry import DetailStore, build_agent_tools

logger = logging.getLogger(__name__)


class ReactOrchestrator:
    """Orchestratore agentico basato su create_react_agent.

    La persistenza cross-turno e' affidata al checkpointer di LangGraph:
    una `InMemorySaver` condivisa tra le invocazioni, con `thread_id`
    legato al sender della sessione. Questo permette all'agente di
    ricordare la conversazione (es. "controlli A22" -> "2026" ->
    continuare con A22+2026) senza ricostruire manualmente la history.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._client = llm_client or LLMClient()
        self._adapter = GiAsLLM(client=self._client)
        # Checkpointer per persistere lo stato (messages) tra turni. Lo
        # stesso oggetto viene riutilizzato tra le invocazioni: il
        # thread_id (sender) chiavizza le conversazioni.
        self._checkpointer = InMemorySaver()
        # DetailStore per thread (two-phase handoff): una istanza per
        # sender, cosi' il tool `mostra_dettagli_completi` ritrova il
        # payload anche a turni successivi.
        self._detail_stores: Dict[str, DetailStore] = {}

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def run(
        self,
        message: str,
        metadata: Dict[str, Any],
        session_context: Optional[Dict[str, Any]] = None,
        detail_store: Optional[DetailStore] = None,
        history: Optional[List[Dict[str, Any]]] = None,  # legacy, ignorato
    ) -> Dict[str, Any]:
        """Esegue un turno.

        Args:
            message: messaggio utente corrente.
            metadata: session metadata (sender/user_id, asl, uos, ...).
            session_context: ultimo intent/riassunto per anaforica.
            detail_store: override DetailStore (se None ne gestisce uno per thread).
            history: legacy, ignorato — lo state e' gestito dal checkpointer.
        """
        thread_id = self._resolve_thread_id(metadata)
        store = detail_store or self._detail_stores.setdefault(thread_id, DetailStore())
        tools = build_agent_tools(metadata, detail_store=store)
        system_prompt = build_system_prompt(metadata, session_context)

        # Ricostruiamo l'agente per turno (tools hanno closure sul metadata
        # corrente) ma il checkpointer e' condiviso -> lo stato persiste.
        agent = create_react_agent(
            model=self._adapter,
            tools=tools,
            prompt=system_prompt,
            checkpointer=self._checkpointer,
        )

        config = {"configurable": {"thread_id": thread_id}}
        try:
            result = agent.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
        except Exception as exc:
            logger.exception("ReactOrchestrator.invoke failed: %s", exc)
            # Pulisci lo state del thread per evitare INVALID_CHAT_HISTORY al
            # prossimo turno (AIMessage con tool_calls orfani nel checkpoint).
            try:
                self._checkpointer.delete_thread(thread_id)
            except Exception:
                pass
            self._detail_stores.pop(thread_id, None)
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

    @staticmethod
    def _resolve_thread_id(metadata: Dict[str, Any]) -> str:
        """Thread id per il checkpointer: privilegia sender/user_id."""
        for key in ("sender", "user_id", "session_id"):
            val = metadata.get(key)
            if val:
                return str(val)
        return "__anonymous__"

    def clear_thread(self, thread_id: str) -> None:
        """Rimuove lo stato di un thread (detail store; la checkpointer non
        espone delete ufficiale, la history si estingue con il processo)."""
        self._detail_stores.pop(thread_id, None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
