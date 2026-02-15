"""
FastAPI wrapper per GiAs-llm
Implementa le stesse convenzioni di Rasa per compatibilità con GChat
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncGenerator, Callable
import logging
import sys
import os
import time
import threading
import asyncio
import json as json_module
from datetime import datetime
from queue import Queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.graph import ConversationGraph
from orchestrator.workflow_validator import WorkflowValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to track if data has been preloaded
_data_preloaded = False

# Global ConversationGraph singleton for better performance
# Avoids re-initializing LLMClient and Router on every request
_conversation_graph = None

# Session store for 2-phase response system
# Maps sender_id -> {detail_context: {...}, timestamp: ...}
_session_store: Dict[str, Dict[str, Any]] = {}
_session_lock = threading.Lock()  # Protegge accesso concorrente al session store

# Session TTL in seconds (5 minutes)
SESSION_TTL = 300

# Contatore richieste per cleanup periodico sessioni scadute
_request_count = 0
_CLEANUP_EVERY_N_REQUESTS = 100

# Timeout per esecuzione grafo (deve essere < timeout Go frontend 60s)
GRAPH_INVOKE_TIMEOUT = 50

# Intent metadata cache (loaded once from DB)
_intent_metadata_cache: Dict[str, Dict[str, Any]] = {}


def _cleanup_expired_sessions():
    """Rimuove sessioni scadute dal session store. Chiamata periodicamente."""
    now = time.time()
    expired = [k for k, v in _session_store.items() if now - v.get("timestamp", 0) > SESSION_TTL * 2]
    for k in expired:
        del _session_store[k]
    if expired:
        logger.info(f"[Session] Cleaned up {len(expired)} expired sessions, {len(_session_store)} remaining")


def _load_intent_metadata():
    """Load intent metadata from the intents table (tool, dataretriever, two_phase, sql)."""
    global _intent_metadata_cache
    try:
        from data_sources.postgresql_source import PostgreSQLDataSource
        engine = PostgreSQLDataSource._engine
        if engine is None:
            return
        from sqlalchemy import text
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT intent, tool, data_retriever, two_phase_threshold, query_equivalent FROM intents"
            )).fetchall()
        for row in rows:
            _intent_metadata_cache[row[0]] = {
                "tool": row[1],
                "dataretriever_class": row[2],
                "two_phase_threshold": row[3],
                "sql": row[4],
            }
        logger.info(f"[ChatLog] Intent metadata cache loaded: {len(_intent_metadata_cache)} intents")
    except Exception as e:
        logger.warning(f"[ChatLog] Could not load intent metadata: {e}")


def log_chat(
    ask: str,
    intent: str,
    answer: str,
    metadata: Dict[str, Any],
    session_id: str = "",
    slots: Optional[Dict[str, Any]] = None,
    response_time_ms: Optional[int] = None,
    error: Optional[str] = None,
):
    """Insert a record into chat_log in a background thread.

    Args:
        ask: User's question/message
        intent: Classified intent
        answer: Generated response
        metadata: User metadata (asl, user_id, codice_fiscale, etc.)
        session_id: Session/sender identifier for multi-turn tracking
        slots: Extracted slots as dict (stored as JSONB)
        response_time_ms: Total execution time in milliseconds
        error: Error message if any (separate from answer)
    """
    def _insert():
        try:
            from data_sources.postgresql_source import PostgreSQLDataSource
            engine = PostgreSQLDataSource._engine
            if engine is None:
                logger.warning("[ChatLog] No DB engine available, skipping log")
                return

            user_id = metadata.get("user_id", "")
            codice_fiscale = metadata.get("codice_fiscale", "")
            asl = metadata.get("asl", "") or metadata.get("asl_id", "")

            # Formato who: asl-user_id-codice_fiscale (include ASL per analisi territoriali)
            who_parts = [str(asl), str(user_id), str(codice_fiscale)]
            who = "-".join(p for p in who_parts if p)
            if not who:
                who = "anonymous"

            intent_meta = _intent_metadata_cache.get(intent, {})
            tool = intent_meta.get("tool") or None
            dataretriever_class = intent_meta.get("dataretriever_class") or None
            two_phase_threshold = intent_meta.get("two_phase_threshold")
            two_phase_resp = two_phase_threshold is not None and two_phase_threshold > 0
            sql_equivalent = intent_meta.get("sql") or None

            # Serialize slots to JSON string for JSONB column
            import json
            slots_json = json.dumps(slots) if slots else None

            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text(
                    """INSERT INTO chat_log
                    (ask, intent, tool, two_phase_resp, dataretriever_class, sql, who, "when", answer,
                     session_id, asl, slots, response_time_ms, error)
                    VALUES
                    (:ask, :intent, :tool, :two_phase_resp, :dataretriever_class, :sql, :who, NOW(), :answer,
                     :session_id, :asl, CAST(:slots AS jsonb), :response_time_ms, :error)"""
                ), {
                    "ask": ask,
                    "intent": intent,
                    "tool": tool,
                    "two_phase_resp": two_phase_resp,
                    "dataretriever_class": dataretriever_class,
                    "sql": sql_equivalent,
                    "who": who,
                    "answer": answer,
                    "session_id": session_id or None,
                    "asl": str(asl) if asl else None,
                    "slots": slots_json,
                    "response_time_ms": response_time_ms,
                    "error": error,
                })
                conn.commit()
            logger.debug(f"[ChatLog] Logged: intent={intent}, who={who}, asl={asl}, time={response_time_ms}ms")
        except Exception as e:
            logger.error(f"[ChatLog] Failed to log chat: {e}")

    threading.Thread(target=_insert, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    global _data_preloaded, _conversation_graph

    # === STARTUP ===
    if not _data_preloaded:
        logger.info("[Startup] Starting data preload...")
        start_time = time.time()

        try:
            from configs.config_loader import get_config
            config = get_config()

            # Import agents.data FIRST to ensure it uses the factory singleton
            # This triggers the data load and populates the class-level cache
            logger.info("[Startup] Importing agents.data module...")
            from agents import data as agents_data

            # Verify data loaded
            from agents.data import piani_df, controlli_df, osa_mai_controllati_df

            load_time = time.time() - start_time
            logger.info(f"[Startup] ✓ Data loaded in {load_time:.2f}s")
            logger.info(f"[Startup] Data rows: piani={len(piani_df):,}, controlli={len(controlli_df):,}, osa={len(osa_mai_controllati_df):,}")

            # Get cache stats
            from data_sources.postgresql_source import PostgreSQLDataSource
            cache_size = len(PostgreSQLDataSource._dataframe_cache)
            logger.info(f"[Startup] Cache populated: {cache_size} datasets")

            _data_preloaded = True

            # Initialize ConversationGraph singleton during startup
            logger.info("[Startup] Initializing ConversationGraph singleton...")
            _conversation_graph = ConversationGraph()
            logger.info("[Startup] ✓ ConversationGraph initialized")

            # Load intent metadata for chat_log
            _load_intent_metadata()

            logger.info("[Startup] ✓ Server ready to handle requests")

        except Exception as e:
            logger.error(f"[Startup] Error during data preload: {e}")
            logger.warning("[Startup] Server will load data on first request")
    else:
        logger.info("[Startup] Data already preloaded, skipping")

    yield  # Server is running

    # === SHUTDOWN ===
    logger.info("[Shutdown] Cleaning up resources...")
    try:
        from data_sources.postgresql_source import PostgreSQLDataSource
        PostgreSQLDataSource.dispose_engine()
        logger.info("[Shutdown] ✓ Resources cleaned up")
    except Exception as e:
        logger.error(f"[Shutdown] Error during cleanup: {e}")


app = FastAPI(
    title="GiAs-llm API",
    description="Sistema di assistenza per piani di monitoraggio veterinario",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RasaMessage(BaseModel):
    """Formato messaggio compatibile con Rasa webhook"""
    sender: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


class RasaResponse(BaseModel):
    """Formato risposta compatibile con Rasa webhook"""
    text: str
    recipient_id: Optional[str] = None
    custom: Optional[Dict[str, Any]] = None  # Per dati extra (execution_path, node_timings, ecc.)


async def format_sse_event(event: Dict[str, Any]) -> str:
    """Formatta evento in formato SSE (Server-Sent Events)"""
    event_type = event.get("type", "status")
    data = json_module.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


@app.get("/")
async def health_check():
    """Health check endpoint (compatibile con Rasa)"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "model_loaded": True
    }


@app.post("/webhooks/rest/webhook")
async def webhook(message: RasaMessage) -> List[RasaResponse]:
    """
    Endpoint webhook compatibile con Rasa REST channel.

    Request format:
    {
        "sender": "user123",
        "message": "quali attività ha il piano A1?",
        "metadata": {
            "asl": "NA1",
            "uoc": "Veterinaria",
            "user_id": "123",
            "codice_fiscale": "...",
            "username": "..."
        }
    }

    Response format (array di oggetti):
    [
        {"text": "Risposta del sistema..."}
    ]
    """
    try:
        logger.info(f"[Webhook] Ricevuto messaggio da {message.sender}: {message.message}")

        metadata = message.metadata or {}

        # Gestione intelligente metadata
        if not metadata.get('user_id'):
            metadata['user_id'] = message.sender

        # Risolvi UOC da user_id se manca (GChat non invia uoc)
        if not metadata.get('uoc') and metadata.get('user_id'):
            try:
                from agents.data import get_uoc_from_user_id
                resolved_uoc = get_uoc_from_user_id(metadata['user_id'])
                if resolved_uoc:
                    metadata['uoc'] = resolved_uoc
                    logger.debug(f"[METADATA] UOC resolved from user_id: {resolved_uoc}")
            except Exception as e:
                logger.debug(f"[METADATA] Could not resolve UOC from user_id: {e}")

        # Log warning solo se manca ASL (uoc può essere risolto da user_id)
        if not metadata.get('asl'):
            logger.warning(f"[METADATA] Missing ASL in production: {metadata}")

        logger.info(f"[Webhook] Metadata (with defaults): {metadata}")

        # Use singleton ConversationGraph for better performance
        # Falls back to creating a new instance if singleton not initialized
        global _conversation_graph, _session_store
        if _conversation_graph is None:
            logger.info("[Webhook] Initializing ConversationGraph (first request)")
            _conversation_graph = ConversationGraph()

        # Cleanup periodico sessioni scadute
        global _request_count
        _request_count += 1
        if _request_count % _CLEANUP_EVERY_N_REQUESTS == 0:
            with _session_lock:
                _cleanup_expired_sessions()

        # 2-phase system: retrieve detail_context from session if available
        with _session_lock:
            sender_session = _session_store.get(message.sender, {}).copy()
        detail_context = sender_session.get("detail_context", {})

        # Check session TTL
        session_timestamp = sender_session.get("timestamp", 0)
        session_valid = time.time() - session_timestamp <= SESSION_TTL

        if not session_valid:
            detail_context = {}  # Session expired

        # Inject session context into metadata for conversational memory
        if sender_session and session_valid:
            last_intent = sender_session.get("last_intent")
            last_slots = sender_session.get("last_slots")
            session_summary = sender_session.get("conversation_summary")
            if last_intent:
                metadata["_session_last_intent"] = last_intent
            if last_slots:
                metadata["_session_last_slots"] = last_slots
            if session_summary:
                metadata["_session_summary"] = session_summary

            # Inject contesto risposta per risoluzione anaforica (es. "le varianti" -> "del piano A2")
            last_response_context = sender_session.get("last_response_context")
            if not last_response_context:
                # Fallback: prova dal dialogue_state
                ds = sender_session.get("dialogue_state") or {}
                last_response_context = ds.get("last_response_context")
            if last_response_context:
                metadata["_session_last_response_context"] = last_response_context

            # NUOVO: Inject fallback recovery state
            fallback_suggestions = sender_session.get("fallback_suggestions")
            fallback_phase = sender_session.get("fallback_phase")
            fallback_count = sender_session.get("fallback_count")
            fallback_selected_category = sender_session.get("fallback_selected_category")
            if fallback_suggestions:
                metadata["_fallback_suggestions"] = fallback_suggestions
                logger.debug(f"[Webhook] Loaded {len(fallback_suggestions)} fallback_suggestions from session for {message.sender}")
            if fallback_phase:
                metadata["_fallback_phase"] = fallback_phase
            if fallback_count is not None:
                metadata["_fallback_count"] = fallback_count
            if fallback_selected_category:
                metadata["_fallback_selected_category"] = fallback_selected_category

        # NUOVO: Recupera e valida workflow_context da sessione
        workflow_context_raw = sender_session.get("workflow_context")

        # SECURITY: Valida workflow_context con TTL check
        workflow_context = WorkflowValidator.validate_workflow_context(
            workflow_context_raw,
            session_timestamp
        )

        # Se validazione fallisce, rimuovi solo workflow_context (non tutta la session)
        if workflow_context_raw and not workflow_context:
            logger.warning(f"[SECURITY] Invalid or expired workflow_context for user {message.sender}")
            # Non fare pop di tutta la session, solo rimuovi workflow_context
            with _session_lock:
                if message.sender in _session_store:
                    _session_store[message.sender].pop("workflow_context", None)
            workflow_context = None

        # Recupera dialogue_state da sessione (nuovo DST)
        dialogue_state_from_session = sender_session.get("dialogue_state") if session_valid else None

        # Esegui il grafo con timeout per evitare request pendenti
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _conversation_graph.run,
                message=message.message,
                metadata=metadata,
                detail_context=detail_context,
                workflow_context=workflow_context,
                dialogue_state=dialogue_state_from_session,
            )
            try:
                result = future.result(timeout=GRAPH_INVOKE_TIMEOUT)
            except FuturesTimeoutError:
                logger.error(f"[Webhook] Graph invoke timeout after {GRAPH_INVOKE_TIMEOUT}s for sender {message.sender}")
                return [RasaResponse(
                    recipient_id=message.sender,
                    text="⏱️ La richiesta ha impiegato troppo tempo. Riprova con una domanda più specifica."
                )]

        # Estrai last_response_context dal dialogue_state o direttamente dal result
        last_response_context = None
        ds = result.get("dialogue_state") or {}
        if ds.get("last_response_context"):
            last_response_context = ds["last_response_context"]
        elif result.get("response_context"):
            last_response_context = result["response_context"]

        # 2-phase system + conversational memory + workflow + DST: store in session
        if result.get("has_more_details") and result.get("detail_context"):
            session_data = {
                "detail_context": result["detail_context"],
                "last_intent": result.get("intent", ""),
                "last_slots": result.get("slots", {}),
                "conversation_summary": f"intent={result.get('intent', '')}, slots={result.get('slots', {})}",
                "timestamp": time.time(),
                "dialogue_state": result.get("dialogue_state"),  # NUOVO: DST
                "last_response_context": last_response_context,  # Per risoluzione anaforica
            }
            # NUOVO: Salva workflow_context se presente
            if result.get("workflow_id"):
                session_data["workflow_context"] = {
                    "workflow_id": result.get("workflow_id"),
                    "workflow_nonce": result.get("workflow_nonce"),
                    "workflow_type": result.get("workflow_type"),
                    "workflow_stage": result.get("workflow_stage"),
                    "pending_question": result.get("pending_question"),
                    "available_options": result.get("available_options"),
                    "workflow_history": result.get("workflow_history"),
                    "accumulated_filters": result.get("accumulated_filters"),
                    "selected_strategy_id": ((result.get("workflow_context") or {}).get("selected_strategy") or {}).get("id"),
                    "current_strategy_index": (result.get("workflow_context") or {}).get("current_strategy_index"),
                    "last_query_intent": ((result.get("workflow_context") or {}).get("last_query") or {}).get("intent"),
                }
            # NUOVO: Salva fallback recovery state
            if result.get("fallback_suggestions"):
                session_data["fallback_suggestions"] = result["fallback_suggestions"]
                session_data["fallback_phase"] = result.get("fallback_phase", 1)
                session_data["fallback_count"] = result.get("fallback_count", 0)
                if result.get("fallback_selected_category"):
                    session_data["fallback_selected_category"] = result["fallback_selected_category"]
            elif result.get("intent") != "fallback":
                # Reset fallback state se intent diverso da fallback
                session_data.pop("fallback_suggestions", None)
                session_data.pop("fallback_phase", None)
                session_data.pop("fallback_count", None)
                session_data.pop("fallback_selected_category", None)
            with _session_lock:
                _session_store[message.sender] = session_data
            logger.info(f"[Webhook] Stored detail_context + session for sender {message.sender}")
        elif result.get("intent") in ["confirm_show_details", "decline_show_details"]:
            # Clear detail_context but keep conversational memory
            if message.sender in _session_store:
                session_data = {
                    "last_intent": result.get("intent", ""),
                    "last_slots": result.get("slots", {}),
                    "conversation_summary": f"intent={result.get('intent', '')}, slots={result.get('slots', {})}",
                    "timestamp": time.time(),
                    "dialogue_state": result.get("dialogue_state"),  # NUOVO: DST
                    "last_response_context": last_response_context,  # Per risoluzione anaforica
                }
                # NUOVO: Mantieni workflow_context se attivo
                if result.get("workflow_id"):
                    session_data["workflow_context"] = {
                        "workflow_id": result.get("workflow_id"),
                        "workflow_nonce": result.get("workflow_nonce"),
                        "workflow_type": result.get("workflow_type"),
                        "workflow_stage": result.get("workflow_stage"),
                        "pending_question": result.get("pending_question"),
                        "available_options": result.get("available_options"),
                        "workflow_history": result.get("workflow_history"),
                        "accumulated_filters": result.get("accumulated_filters"),
                        "selected_strategy_id": result.get("workflow_context", {}).get("selected_strategy", {}).get("id"),
                        "current_strategy_index": result.get("workflow_context", {}).get("current_strategy_index"),
                        "last_query_intent": result.get("workflow_context", {}).get("last_query", {}).get("intent"),
                    }
                # NUOVO: Gestisci fallback recovery state
                if result.get("fallback_suggestions"):
                    session_data["fallback_suggestions"] = result["fallback_suggestions"]
                    session_data["fallback_phase"] = result.get("fallback_phase", 1)
                    session_data["fallback_count"] = result.get("fallback_count", 0)
                    if result.get("fallback_selected_category"):
                        session_data["fallback_selected_category"] = result["fallback_selected_category"]
                else:
                    # Reset fallback state
                    session_data.pop("fallback_suggestions", None)
                    session_data.pop("fallback_phase", None)
                    session_data.pop("fallback_count", None)
                    session_data.pop("fallback_selected_category", None)
                with _session_lock:
                    _session_store[message.sender] = session_data
                logger.info(f"[Webhook] Cleared detail_context, kept session for sender {message.sender}")
        else:
            # Always update conversational memory
            with _session_lock:
                existing = _session_store.get(message.sender, {}).copy()

            # Detect topic change: se l'intent cambia significativamente, reset contesto
            previous_intent = existing.get("last_intent", "")
            current_intent = result.get("intent", "")
            CONTINUATION_INTENTS = {"confirm_show_details", "decline_show_details", "fallback"}
            is_topic_change = (
                previous_intent and
                current_intent and
                previous_intent != current_intent and
                current_intent not in CONTINUATION_INTENTS
            )

            if is_topic_change:
                # Reset contesto che potrebbe confondere la prossima classificazione
                existing.pop("last_response_context", None)
                existing.pop("detail_context", None)
                logger.info(f"[Webhook] Topic change detected ({previous_intent} -> {current_intent}), reset session context for {message.sender}")

            existing["last_intent"] = current_intent
            existing["last_slots"] = result.get("slots", {})
            existing["conversation_summary"] = f"intent={current_intent}, slots={result.get('slots', {})}"
            existing["timestamp"] = time.time()
            # Keep detail_context if it was already there (don't overwrite)
            if "detail_context" not in existing:
                existing["detail_context"] = {}
            # NUOVO: Aggiorna dialogue_state
            existing["dialogue_state"] = result.get("dialogue_state")
            # Aggiorna contesto risposta per risoluzione anaforica (solo se NON cambio topic)
            if last_response_context and not is_topic_change:
                existing["last_response_context"] = last_response_context
            # NUOVO: Aggiorna workflow_context
            if result.get("workflow_id"):
                existing["workflow_context"] = {
                    "workflow_id": result.get("workflow_id"),
                    "workflow_nonce": result.get("workflow_nonce"),
                    "workflow_type": result.get("workflow_type"),
                    "workflow_stage": result.get("workflow_stage"),
                    "pending_question": result.get("pending_question"),
                    "available_options": result.get("available_options"),
                    "workflow_history": result.get("workflow_history"),
                    "accumulated_filters": result.get("accumulated_filters"),
                    "selected_strategy_id": ((result.get("workflow_context") or {}).get("selected_strategy") or {}).get("id"),
                    "current_strategy_index": (result.get("workflow_context") or {}).get("current_strategy_index"),
                    "last_query_intent": ((result.get("workflow_context") or {}).get("last_query") or {}).get("intent"),
                }
            elif "workflow_context" in existing:
                # Rimuovi workflow_context se workflow completato
                del existing["workflow_context"]

            # NUOVO: Aggiorna fallback recovery state
            if result.get("fallback_suggestions"):
                existing["fallback_suggestions"] = result["fallback_suggestions"]
                existing["fallback_phase"] = result.get("fallback_phase", 1)
                existing["fallback_count"] = result.get("fallback_count", 0)
                if result.get("fallback_selected_category"):
                    existing["fallback_selected_category"] = result["fallback_selected_category"]
                logger.debug(f"[Webhook] Saved {len(result['fallback_suggestions'])} fallback_suggestions to session for {message.sender}")
            elif result.get("intent") != "fallback":
                # Reset fallback state se intent diverso da fallback
                existing.pop("fallback_suggestions", None)
                existing.pop("fallback_phase", None)
                existing.pop("fallback_count", None)
                existing.pop("fallback_selected_category", None)

            with _session_lock:
                _session_store[message.sender] = existing

        final_response = result.get("response", "")
        error = result.get("error", "")

        if error:
            logger.error(f"[Webhook] Errore: {error}")
            response_text = f"❌ Errore: {error}"
        elif final_response:
            response_text = final_response
        else:
            response_text = "Non ho capito la tua richiesta. Puoi riformularla?"

        logger.info(f"[Webhook] Risposta generata ({len(response_text)} caratteri)")

        # Log to chat_log table with extended fields
        log_chat(
            ask=message.message,
            intent=result.get("intent", ""),
            answer=response_text,
            metadata=metadata,
            session_id=message.sender,
            slots=result.get("slots"),
            response_time_ms=result.get("total_execution_ms"),
            error=error if error else None,
        )

        # Costruisci custom payload con execution tracking
        custom_payload = {
            "execution_path": result.get("execution_path", []),
            "node_timings": result.get("node_timings", {}),
            "total_execution_ms": result.get("total_execution_ms"),
            "intent": result.get("intent", ""),
            "slots": result.get("slots", {}),
            "suggestions": result.get("suggestions", []),
        }

        return [
            RasaResponse(
                text=response_text,
                recipient_id=message.sender,
                custom=custom_payload
            )
        ]

    except Exception as e:
        logger.exception(f"[Webhook] Eccezione non gestita: {e}")
        return [
            RasaResponse(
                text=f"❌ Errore interno del sistema: {str(e)}",
                recipient_id=message.sender
            )
        ]


@app.post("/webhooks/rest/webhook/stream")
async def webhook_stream(message: RasaMessage):
    """
    Endpoint webhook con streaming SSE (Server-Sent Events).

    Restituisce eventi progressivi durante l'elaborazione:
    - status: Aggiornamenti sullo stato del nodo corrente
    - reasoning: Messaggi di ragionamento del sistema
    - token: Token streaming della risposta (se disponibile)
    - final: Risposta finale completa
    - error: Eventi di errore

    Response format: text/event-stream (SSE)
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        # Queue thread-safe per comunicazione tra thread sincrono e async generator
        event_queue = Queue()
        result_container = {"result": None, "exception": None}

        try:
            logger.info(f"[WebhookStream] Ricevuto messaggio da {message.sender}: {message.message}")

            metadata = message.metadata or {}

            # Gestione intelligente metadata (come webhook sincrono)
            if not metadata.get('user_id'):
                metadata['user_id'] = message.sender

            # Risolvi UOC da user_id se manca
            if not metadata.get('uoc') and metadata.get('user_id'):
                try:
                    from agents.data import get_uoc_from_user_id
                    resolved_uoc = get_uoc_from_user_id(metadata['user_id'])
                    if resolved_uoc:
                        metadata['uoc'] = resolved_uoc
                        logger.debug(f"[METADATA] UOC resolved from user_id: {resolved_uoc}")
                except Exception as e:
                    logger.debug(f"[METADATA] Could not resolve UOC from user_id: {e}")

            if not metadata.get('asl'):
                logger.warning(f"[METADATA] Missing ASL in production: {metadata}")

            # Event callback per emettere eventi SSE durante l'elaborazione
            def event_callback(event: Dict[str, Any]):
                """Callback invocato dal ConversationGraph per emettere eventi SSE"""
                event["timestamp"] = int(time.time() * 1000)
                # Put in queue thread-safe (sincrono)
                event_queue.put(event)

            # Yield evento iniziale
            yield await format_sse_event({
                "type": "status",
                "timestamp": int(time.time() * 1000),
                "message": "Connessione stabilita, elaborazione in corso..."
            })

            # Use singleton ConversationGraph
            global _conversation_graph, _session_store
            if _conversation_graph is None:
                logger.info("[WebhookStream] Initializing ConversationGraph (first request)")
                _conversation_graph = ConversationGraph()

            # 2-phase system: retrieve detail_context from session if available
            sender_session = _session_store.get(message.sender, {})
            detail_context = sender_session.get("detail_context", {})

            # Check session TTL
            session_timestamp = sender_session.get("timestamp", 0)
            if time.time() - session_timestamp > SESSION_TTL:
                detail_context = {}

            # Inject session context into metadata
            if sender_session and time.time() - session_timestamp <= SESSION_TTL:
                last_intent = sender_session.get("last_intent")
                last_slots = sender_session.get("last_slots")
                session_summary = sender_session.get("conversation_summary")
                if last_intent:
                    metadata["_session_last_intent"] = last_intent
                if last_slots:
                    metadata["_session_last_slots"] = last_slots
                if session_summary:
                    metadata["_session_summary"] = session_summary

                # Inject fallback recovery state (come endpoint sincrono)
                fallback_suggestions = sender_session.get("fallback_suggestions")
                fallback_phase = sender_session.get("fallback_phase")
                fallback_count = sender_session.get("fallback_count")
                fallback_selected_category = sender_session.get("fallback_selected_category")
                if fallback_suggestions:
                    metadata["_fallback_suggestions"] = fallback_suggestions
                    logger.debug(f"[WebhookStream] Loaded {len(fallback_suggestions)} fallback_suggestions from session for {message.sender}")
                if fallback_phase:
                    metadata["_fallback_phase"] = fallback_phase
                if fallback_count is not None:
                    metadata["_fallback_count"] = fallback_count
                if fallback_selected_category:
                    metadata["_fallback_selected_category"] = fallback_selected_category

            # NUOVO: Recupera e valida workflow_context da sessione
            workflow_context_raw = sender_session.get("workflow_context")

            # SECURITY: Valida workflow_context con TTL check
            workflow_context = WorkflowValidator.validate_workflow_context(
                workflow_context_raw,
                session_timestamp
            )

            # Se validazione fallisce, pulisci sessione
            if workflow_context_raw and not workflow_context:
                logger.warning(f"[SECURITY] Invalid or expired workflow_context for user {message.sender}")
                _session_store.pop(message.sender, None)
                workflow_context = None

            # NON injettiamo event_callback nel metadata!
            # Invece, lo passiamo direttamente al graph che lo userà internamente

            # Esegui ConversationGraph in thread separato per non bloccare async
            def run_graph():
                try:
                    # Passiamo il callback direttamente al metodo run
                    result = _conversation_graph.run(
                        message=message.message,
                        metadata=metadata,
                        detail_context=detail_context,
                        workflow_context=workflow_context,  # NUOVO parametro validato
                        event_callback=event_callback
                    )
                    result_container["result"] = result
                    # Signal completion
                    event_queue.put(None)
                except Exception as e:
                    result_container["exception"] = e
                    event_queue.put(None)

            # Start graph execution in thread pool
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, run_graph)

            # Stream eventi dalla queue mentre il graph esegue
            while True:
                # Poll queue con timeout per non bloccare
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, event_queue.get, True, 0.5  # timeout 0.5s
                    )
                except:
                    # Timeout - continua polling
                    continue

                # None indica completamento
                if event is None:
                    break

                # Yield evento formattato
                yield await format_sse_event(event)

            # Check per eccezioni durante l'esecuzione
            if result_container["exception"]:
                raise result_container["exception"]

            result = result_container["result"]

            # 2-phase system + conversational memory + workflow: store in session
            if result.get("has_more_details") and result.get("detail_context"):
                session_data = {
                    "detail_context": result["detail_context"],
                    "last_intent": result.get("intent", ""),
                    "last_slots": result.get("slots", {}),
                    "conversation_summary": f"intent={result.get('intent', '')}, slots={result.get('slots', {})}",
                    "timestamp": time.time()
                }
                # NUOVO: Salva workflow_context se presente
                if result.get("workflow_id"):
                    session_data["workflow_context"] = {
                        "workflow_id": result.get("workflow_id"),
                        "workflow_nonce": result.get("workflow_nonce"),
                        "workflow_type": result.get("workflow_type"),
                        "workflow_stage": result.get("workflow_stage"),
                        "pending_question": result.get("pending_question"),
                        "available_options": result.get("available_options"),
                        "workflow_history": result.get("workflow_history"),
                        "accumulated_filters": result.get("accumulated_filters"),
                        "selected_strategy_id": result.get("workflow_context", {}).get("selected_strategy", {}).get("id"),
                        "current_strategy_index": result.get("workflow_context", {}).get("current_strategy_index"),
                        "last_query_intent": result.get("workflow_context", {}).get("last_query", {}).get("intent"),
                    }
                # Salva fallback recovery state
                if result.get("fallback_suggestions"):
                    session_data["fallback_suggestions"] = result["fallback_suggestions"]
                    session_data["fallback_phase"] = result.get("fallback_phase", 1)
                    session_data["fallback_count"] = result.get("fallback_count", 0)
                    if result.get("fallback_selected_category"):
                        session_data["fallback_selected_category"] = result["fallback_selected_category"]
                    logger.debug(f"[WebhookStream] Saved {len(result['fallback_suggestions'])} fallback_suggestions to session for {message.sender}")
                _session_store[message.sender] = session_data
                logger.info(f"[WebhookStream] Stored detail_context + session for sender {message.sender}")
            elif result.get("intent") in ["confirm_show_details", "decline_show_details"]:
                if message.sender in _session_store:
                    session_data = {
                        "last_intent": result.get("intent", ""),
                        "last_slots": result.get("slots", {}),
                        "conversation_summary": f"intent={result.get('intent', '')}, slots={result.get('slots', {})}",
                        "timestamp": time.time()
                    }
                    # NUOVO: Mantieni workflow_context se attivo
                    if result.get("workflow_id"):
                        session_data["workflow_context"] = {
                            "workflow_id": result.get("workflow_id"),
                            "workflow_nonce": result.get("workflow_nonce"),
                            "workflow_type": result.get("workflow_type"),
                            "workflow_stage": result.get("workflow_stage"),
                            "pending_question": result.get("pending_question"),
                            "available_options": result.get("available_options"),
                            "workflow_history": result.get("workflow_history"),
                            "accumulated_filters": result.get("accumulated_filters"),
                            "selected_strategy_id": result.get("workflow_context", {}).get("selected_strategy", {}).get("id"),
                            "current_strategy_index": result.get("workflow_context", {}).get("current_strategy_index"),
                            "last_query_intent": result.get("workflow_context", {}).get("last_query", {}).get("intent"),
                        }
                    # Gestisci fallback recovery state
                    if result.get("fallback_suggestions"):
                        session_data["fallback_suggestions"] = result["fallback_suggestions"]
                        session_data["fallback_phase"] = result.get("fallback_phase", 1)
                        session_data["fallback_count"] = result.get("fallback_count", 0)
                        if result.get("fallback_selected_category"):
                            session_data["fallback_selected_category"] = result["fallback_selected_category"]
                        logger.debug(f"[WebhookStream] Saved {len(result['fallback_suggestions'])} fallback_suggestions to session for {message.sender}")
                    _session_store[message.sender] = session_data
                    logger.info(f"[WebhookStream] Cleared detail_context, kept session for sender {message.sender}")
            else:
                existing = _session_store.get(message.sender, {})
                existing["last_intent"] = result.get("intent", "")
                existing["last_slots"] = result.get("slots", {})
                existing["conversation_summary"] = f"intent={result.get('intent', '')}, slots={result.get('slots', {})}"
                existing["timestamp"] = time.time()
                if "detail_context" not in existing:
                    existing["detail_context"] = {}
                # NUOVO: Aggiorna workflow_context
                if result.get("workflow_id"):
                    existing["workflow_context"] = {
                        "workflow_id": result.get("workflow_id"),
                        "workflow_nonce": result.get("workflow_nonce"),
                        "workflow_type": result.get("workflow_type"),
                        "workflow_stage": result.get("workflow_stage"),
                        "pending_question": result.get("pending_question"),
                        "available_options": result.get("available_options"),
                        "workflow_history": result.get("workflow_history"),
                        "accumulated_filters": result.get("accumulated_filters"),
                        "selected_strategy_id": result.get("workflow_context", {}).get("selected_strategy", {}).get("id"),
                        "current_strategy_index": result.get("workflow_context", {}).get("current_strategy_index"),
                        "last_query_intent": result.get("workflow_context", {}).get("last_query", {}).get("intent"),
                    }
                elif "workflow_context" in existing:
                    # Rimuovi workflow_context se workflow completato
                    del existing["workflow_context"]

                # Aggiorna fallback recovery state
                if result.get("fallback_suggestions"):
                    existing["fallback_suggestions"] = result["fallback_suggestions"]
                    existing["fallback_phase"] = result.get("fallback_phase", 1)
                    existing["fallback_count"] = result.get("fallback_count", 0)
                    if result.get("fallback_selected_category"):
                        existing["fallback_selected_category"] = result["fallback_selected_category"]
                    logger.debug(f"[WebhookStream] Saved {len(result['fallback_suggestions'])} fallback_suggestions to session for {message.sender}")
                elif result.get("intent") != "fallback":
                    # Reset fallback state se intent diverso da fallback
                    existing.pop("fallback_suggestions", None)
                    existing.pop("fallback_phase", None)
                    existing.pop("fallback_count", None)
                    existing.pop("fallback_selected_category", None)

                _session_store[message.sender] = existing

            final_response = result.get("response", "")
            error = result.get("error", "")

            if error:
                logger.error(f"[WebhookStream] Errore: {error}")
                # FIX: Log anche gli errori (prima venivano persi)
                log_chat(
                    ask=message.message,
                    intent=result.get("intent", ""),
                    answer=f"❌ Errore: {error}",
                    metadata=metadata,
                    session_id=message.sender,
                    slots=result.get("slots"),
                    response_time_ms=result.get("total_execution_ms"),
                    error=error,
                )
                yield await format_sse_event({
                    "type": "error",
                    "timestamp": int(time.time() * 1000),
                    "error": error,
                    "recoverable": False
                })
                return

            if not final_response:
                final_response = "Non ho capito la tua richiesta. Puoi riformularla?"

            logger.info(f"[WebhookStream] Risposta generata ({len(final_response)} caratteri)")

            # Log to chat_log table with extended fields
            log_chat(
                ask=message.message,
                intent=result.get("intent", ""),
                answer=final_response,
                metadata=metadata,
                session_id=message.sender,
                slots=result.get("slots"),
                response_time_ms=result.get("total_execution_ms"),
                error=None,
            )

            # Yield evento finale con risposta completa
            yield await format_sse_event({
                "type": "final",
                "timestamp": int(time.time() * 1000),
                "content": final_response,
                "metadata": {
                    "intent": result.get("intent", ""),
                    "full_data": result.get("full_data", {}),
                    "data_type": result.get("data_type"),
                    "suggestions": result.get("suggestions", [])
                }
            })

        except Exception as e:
            logger.exception(f"[WebhookStream] Eccezione non gestita: {e}")
            yield await format_sse_event({
                "type": "error",
                "timestamp": int(time.time() * 1000),
                "error": f"Errore interno del sistema: {str(e)}",
                "recoverable": False
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


class RasaParseRequest(BaseModel):
    """Formato richiesta per /model/parse (compatibile con Rasa)"""
    text: str
    metadata: Optional[Dict[str, Any]] = None


@app.post("/model/parse")
async def parse(request: RasaParseRequest) -> Dict[str, Any]:
    """
    Endpoint per parsing NLU (compatibile con Rasa).
    Utile per debugging e testing.

    Request format:
    {
        "text": "messaggio da analizzare",
        "metadata": {...}
    }

    Response format:
    {
        "text": "messaggio originale",
        "intent": {"name": "ask_piano_description", "confidence": 0.95},
        "entities": [...],
        "metadata": {...}
    }
    """
    try:
        # Reuse singleton ConversationGraph for better performance
        global _conversation_graph
        if _conversation_graph is None:
            logger.info("[Parse] Initializing ConversationGraph (first request)")
            _conversation_graph = ConversationGraph()

        router = _conversation_graph.router

        result = router.classify(
            message=request.text,
            metadata=request.metadata or {}
        )

        return {
            "text": request.text,
            "intent": {
                "name": result.get("intent", "fallback"),
                "confidence": 0.95 if result.get("intent") else 0.3
            },
            "entities": [
                {"entity": k, "value": v}
                for k, v in result.get("slots", {}).items()
            ],
            "metadata": request.metadata,
            "slots": result.get("slots", {}),
            "needs_clarification": result.get("needs_clarification", False)
        }

    except Exception as e:
        logger.exception(f"[Parse] Errore: {e}")
        return {
            "text": request.text,
            "intent": {"name": "fallback", "confidence": 0.0},
            "entities": [],
            "error": str(e)
        }


@app.get("/conversations/{conversation_id}/tracker")
async def get_tracker(conversation_id: str) -> Dict[str, Any]:
    """
    Endpoint per ottenere lo stato della conversazione.
    Stub per compatibilità con Rasa.
    """
    return {
        "sender_id": conversation_id,
        "slots": {},
        "latest_message": {},
        "events": [],
        "paused": False,
        "followup_action": None,
        "active_loop": {}
    }


@app.get("/status")
async def status():
    """Status endpoint con informazioni sul modello"""
    from agents.data import piani_df, controlli_df, osa_mai_controllati_df
    from configs.config_loader import get_config
    from configs.config import AppConfig
    from llm.client import LLMClient

    config = get_config()

    # Check actual LLM availability
    llm_model = AppConfig.get_model_name()
    try:
        test_client = LLMClient()
        llm_mode = "real" if test_client.use_real_llm else "stub"
    except Exception:
        llm_mode = "stub"
    llm_status = f"{llm_model} ({llm_mode})"

    return {
        "status": "ok",
        "model_loaded": True,
        "current_year": config.get_current_year(),
        "data_loaded": {
            "piani": len(piani_df),
            "controlli": len(controlli_df),
            "osa_mai_controllati": len(osa_mai_controllati_df)
        },
        "framework": "LangGraph",
        "llm": llm_status
    }


@app.get("/config")
async def get_config_info():
    """Endpoint per ottenere informazioni di configurazione"""
    from configs.config_loader import get_config

    config = get_config()

    return {
        "current_year": config.get_current_year(),
        "data_source_type": config.get_data_source_type(),
        "status": "ok"
    }


# =============================================================================
# CHAT LOG ANALYTICS API
# =============================================================================

def _get_db_engine():
    """Get database engine for chat_log queries."""
    try:
        from data_sources.postgresql_source import PostgreSQLDataSource
        return PostgreSQLDataSource._engine
    except Exception:
        return None


@app.get("/api/chat-log/stats")
async def chat_log_stats(days: int = 7):
    """
    Statistiche aggregate chat_log.

    Query params:
        days: numero di giorni da considerare (default: 7)

    Returns:
        - totale messaggi
        - totale errori
        - tempo medio risposta
        - distribuzione per intent
        - distribuzione per ASL
    """
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            # Stats generali
            stats_query = text("""
                SELECT
                    COUNT(*) AS totale_messaggi,
                    COUNT(*) FILTER (WHERE error IS NOT NULL) AS totale_errori,
                    ROUND(AVG(response_time_ms)) AS tempo_medio_ms,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) AS p95_ms,
                    COUNT(DISTINCT session_id) AS sessioni_uniche,
                    COUNT(DISTINCT asl) AS asl_attive
                FROM chat_log
                WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
                   OR "when" IS NULL
            """)
            stats = conn.execute(stats_query, {"days": days}).fetchone()

            # Top intent
            intent_query = text("""
                SELECT intent, COUNT(*) AS count
                FROM chat_log
                WHERE ("when"::timestamp >= NOW() - INTERVAL '1 day' * :days OR "when" IS NULL)
                  AND intent IS NOT NULL AND intent != ''
                GROUP BY intent
                ORDER BY count DESC
                LIMIT 10
            """)
            intents = conn.execute(intent_query, {"days": days}).fetchall()

            # Top ASL
            asl_query = text("""
                SELECT asl, COUNT(*) AS count
                FROM chat_log
                WHERE ("when"::timestamp >= NOW() - INTERVAL '1 day' * :days OR "when" IS NULL)
                  AND asl IS NOT NULL AND asl != ''
                GROUP BY asl
                ORDER BY count DESC
                LIMIT 10
            """)
            asls = conn.execute(asl_query, {"days": days}).fetchall()

            return {
                "period_days": days,
                "totale_messaggi": stats[0] or 0,
                "totale_errori": stats[1] or 0,
                "tasso_errore_pct": round(100 * (stats[1] or 0) / max(stats[0] or 1, 1), 2),
                "tempo_medio_ms": stats[2] or 0,
                "p95_ms": stats[3] or 0,
                "sessioni_uniche": stats[4] or 0,
                "asl_attive": stats[5] or 0,
                "top_intents": [{"intent": r[0], "count": r[1]} for r in intents],
                "top_asl": [{"asl": r[0], "count": r[1]} for r in asls],
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/recent")
async def chat_log_recent(limit: int = 50, offset: int = 0, asl: Optional[str] = None):
    """
    Ultimi messaggi chat_log.

    Query params:
        limit: numero massimo di record (default: 50, max: 200)
        offset: offset per paginazione
        asl: filtro opzionale per ASL
    """
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    limit = min(limit, 200)

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    id,
                    "when" AS timestamp,
                    session_id,
                    asl,
                    who,
                    ask,
                    intent,
                    slots::text AS slots_json,
                    LEFT(answer, 500) AS answer_preview,
                    response_time_ms,
                    error,
                    tool,
                    two_phase_resp
                FROM chat_log
                WHERE (:asl IS NULL OR asl = :asl)
                ORDER BY "when" DESC NULLS LAST, id DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = conn.execute(query, {"asl": asl, "limit": limit, "offset": offset}).fetchall()

            # Count totale per paginazione
            count_query = text("""
                SELECT COUNT(*) FROM chat_log
                WHERE (:asl IS NULL OR asl = :asl)
            """)
            total = conn.execute(count_query, {"asl": asl}).fetchone()[0]

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "asl_filter": asl,
                "records": [
                    {
                        "id": r[0],
                        "timestamp": r[1] if isinstance(r[1], str) else (r[1].isoformat() if r[1] else None),
                        "session_id": r[2],
                        "asl": r[3],
                        "who": r[4],
                        "ask": r[5],
                        "intent": r[6],
                        "slots": r[7],
                        "answer_preview": r[8],
                        "response_time_ms": r[9],
                        "error": r[10],
                        "tool": r[11],
                        "two_phase_resp": r[12],
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in recent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/by-asl")
async def chat_log_by_asl(days: int = 30):
    """
    Statistiche raggruppate per ASL.

    Query params:
        days: numero di giorni da considerare (default: 30)
    """
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    COALESCE(asl, 'N/D') AS asl,
                    COUNT(*) AS totale,
                    COUNT(*) FILTER (WHERE error IS NOT NULL) AS errori,
                    ROUND(AVG(response_time_ms)) AS tempo_medio_ms,
                    COUNT(DISTINCT session_id) AS sessioni,
                    COUNT(DISTINCT intent) AS intents_diversi
                FROM chat_log
                WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
                   OR "when" IS NULL
                GROUP BY COALESCE(asl, 'N/D')
                ORDER BY totale DESC
            """)
            rows = conn.execute(query, {"days": days}).fetchall()

            return {
                "period_days": days,
                "data": [
                    {
                        "asl": r[0],
                        "totale": r[1],
                        "errori": r[2],
                        "tasso_errore_pct": round(100 * r[2] / max(r[1], 1), 2),
                        "tempo_medio_ms": r[3] or 0,
                        "sessioni": r[4],
                        "intents_diversi": r[5],
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in by-asl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/by-intent")
async def chat_log_by_intent(days: int = 30):
    """
    Statistiche raggruppate per intent.

    Query params:
        days: numero di giorni da considerare (default: 30)
    """
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    COALESCE(intent, 'unknown') AS intent,
                    COUNT(*) AS totale,
                    COUNT(*) FILTER (WHERE error IS NOT NULL) AS errori,
                    ROUND(AVG(response_time_ms)) AS tempo_medio_ms,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) AS p95_ms,
                    tool
                FROM chat_log
                WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
                   OR "when" IS NULL
                GROUP BY COALESCE(intent, 'unknown'), tool
                ORDER BY totale DESC
            """)
            rows = conn.execute(query, {"days": days}).fetchall()

            return {
                "period_days": days,
                "data": [
                    {
                        "intent": r[0],
                        "totale": r[1],
                        "errori": r[2],
                        "tasso_errore_pct": round(100 * r[2] / max(r[1], 1), 2),
                        "tempo_medio_ms": r[3] or 0,
                        "p95_ms": r[4] or 0,
                        "tool": r[5],
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in by-intent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/errors")
async def chat_log_errors(limit: int = 50, days: int = 7):
    """
    Lista errori recenti.

    Query params:
        limit: numero massimo di record (default: 50)
        days: numero di giorni da considerare (default: 7)
    """
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    limit = min(limit, 200)

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    id,
                    "when" AS timestamp,
                    session_id,
                    asl,
                    ask,
                    intent,
                    error,
                    response_time_ms
                FROM chat_log
                WHERE error IS NOT NULL
                  AND ("when"::timestamp >= NOW() - INTERVAL '1 day' * :days OR "when" IS NULL)
                ORDER BY "when" DESC NULLS LAST, id DESC
                LIMIT :limit
            """)
            rows = conn.execute(query, {"days": days, "limit": limit}).fetchall()

            # Raggruppamento errori per tipo
            error_types_query = text("""
                SELECT
                    CASE
                        WHEN error ILIKE '%timeout%' THEN 'timeout'
                        WHEN error ILIKE '%connection%' THEN 'connection'
                        WHEN error ILIKE '%database%' OR error ILIKE '%sql%' THEN 'database'
                        WHEN error ILIKE '%llm%' OR error ILIKE '%ollama%' THEN 'llm'
                        ELSE 'other'
                    END AS error_type,
                    COUNT(*) AS count
                FROM chat_log
                WHERE error IS NOT NULL
                  AND ("when"::timestamp >= NOW() - INTERVAL '1 day' * :days OR "when" IS NULL)
                GROUP BY 1
                ORDER BY count DESC
            """)
            error_types = conn.execute(error_types_query, {"days": days}).fetchall()

            return {
                "period_days": days,
                "total_errors": len(rows),
                "error_types": [{"type": r[0], "count": r[1]} for r in error_types],
                "records": [
                    {
                        "id": r[0],
                        "timestamp": r[1] if isinstance(r[1], str) else (r[1].isoformat() if r[1] else None),
                        "session_id": r[2],
                        "asl": r[3],
                        "ask": r[4],
                        "intent": r[5],
                        "error": r[6],
                        "response_time_ms": r[7],
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in errors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/timeline")
async def chat_log_timeline(days: int = 7, granularity: str = "hour"):
    """
    Timeline messaggi per grafici.

    Query params:
        days: numero di giorni (default: 7)
        granularity: 'hour' o 'day' (default: 'hour')
    """
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    if granularity not in ("hour", "day"):
        granularity = "hour"

    try:
        with engine.connect() as conn:
            if granularity == "hour":
                query = text("""
                    SELECT
                        DATE_TRUNC('hour', "when"::timestamp) AS bucket,
                        COUNT(*) AS count,
                        COUNT(*) FILTER (WHERE error IS NOT NULL) AS errors,
                        ROUND(AVG(response_time_ms)) AS avg_time_ms
                    FROM chat_log
                    WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
                      AND "when" IS NOT NULL
                    GROUP BY DATE_TRUNC('hour', "when"::timestamp)
                    ORDER BY bucket
                """)
            else:
                query = text("""
                    SELECT
                        DATE_TRUNC('day', "when"::timestamp) AS bucket,
                        COUNT(*) AS count,
                        COUNT(*) FILTER (WHERE error IS NOT NULL) AS errors,
                        ROUND(AVG(response_time_ms)) AS avg_time_ms
                    FROM chat_log
                    WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
                      AND "when" IS NOT NULL
                    GROUP BY DATE_TRUNC('day', "when"::timestamp)
                    ORDER BY bucket
                """)

            rows = conn.execute(query, {"days": days}).fetchall()

            return {
                "period_days": days,
                "granularity": granularity,
                "data": [
                    {
                        "timestamp": r[0] if isinstance(r[0], str) else (r[0].isoformat() if r[0] else None),
                        "count": r[1],
                        "errors": r[2],
                        "avg_time_ms": r[3] or 0,
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/quality")
async def chat_log_quality(days: int = 7, asl: str = None, min_severity: str = None):
    """
    Analisi qualita' conversazioni.
    Rileva problemi come fallback loop, domande ripetute, risposte brevi.

    Query params:
        days: numero di giorni da analizzare (default: 7)
        asl: filtra per ASL specifica (opzionale)
        min_severity: severita' minima da includere: low, medium, high, critical (opzionale)
    """
    try:
        from tools.conversation_monitor import run_monitor

        report = run_monitor(
            days=days,
            asl_filter=asl if asl else None,
            use_llm=False,  # No LLM per endpoint API (troppo lento)
            min_severity=min_severity
        )

        return report.to_dict()

    except ImportError as e:
        logger.error(f"[ChatLogAPI] Impossibile importare conversation_monitor: {e}")
        raise HTTPException(status_code=500, detail="Modulo conversation_monitor non disponibile")
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# INTELLIGENT MONITOR API
# =============================================================================

@app.get("/api/monitor/intelligent")
async def intelligent_monitor_analysis(
    days: int = 7,
    use_llm: bool = False,
    min_priority: int = 1
):
    """
    Analisi intelligente completa.

    Combina:
    - Bug detection (errori ricorrenti, slot failures)
    - Root cause analysis (clustering fallback, gap analysis)
    - Trend analysis (confronto settimanale, degradazioni)
    - User intent mining (bisogni non soddisfatti)
    - Suggerimenti actionable con priorita'

    Query params:
        days: numero di giorni da analizzare (default: 7)
        use_llm: abilita analisi semantica LLM (default: false, piu' lento)
        min_priority: priorita' minima suggerimenti 1-5 (default: 1)

    Returns:
        - health_score: score complessivo 0-100 con componenti
        - suggestions: suggerimenti raggruppati per priorita'
        - bugs_detected: bug rilevati automaticamente
        - trend_analysis: confronto settimanale e delta
        - unmet_needs: bisogni utente non soddisfatti
        - root_causes: analisi cause root problemi
    """
    try:
        from tools.intelligent_monitor import IntelligentMonitor

        monitor = IntelligentMonitor()
        report = monitor.run_analysis(
            days=days,
            use_llm=use_llm,
            min_priority=min_priority
        )

        return report.to_dict()

    except ImportError as e:
        logger.error(f"[IntelligentMonitor] Import error: {e}")
        raise HTTPException(status_code=500, detail="Modulo intelligent_monitor non disponibile")
    except Exception as e:
        logger.error(f"[IntelligentMonitor] Error in analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/suggestions")
async def intelligent_monitor_suggestions(
    min_priority: int = 1,
    limit: int = 20,
    suggestion_type: Optional[str] = None
):
    """
    Suggerimenti di miglioramento.

    Query params:
        min_priority: priorita' minima 1-5 (default: 1)
        limit: numero massimo suggerimenti (default: 20, max: 50)
        suggestion_type: filtra per tipo (fix_bug, add_pattern, add_intent, optimize_tool, update_training)

    Returns:
        Array di suggerimenti con:
        - type: tipo suggerimento
        - priority: priorita' 1-5
        - title: titolo breve
        - description: descrizione
        - action: azione da intraprendere
        - evidence: dati a supporto
        - implementation_hint: suggerimento implementazione
    """
    try:
        from tools.intelligent_monitor import IntelligentMonitor

        limit = min(limit, 50)
        monitor = IntelligentMonitor()
        suggestions = monitor.get_suggestions(min_priority=min_priority, limit=limit)

        # Filter by type if specified
        if suggestion_type:
            suggestions = [s for s in suggestions if s.type.value == suggestion_type]

        return {
            "total": len(suggestions),
            "min_priority": min_priority,
            "suggestion_type_filter": suggestion_type,
            "suggestions": [s.to_dict() for s in suggestions],
        }

    except ImportError as e:
        logger.error(f"[IntelligentMonitor] Import error: {e}")
        raise HTTPException(status_code=500, detail="Modulo intelligent_monitor non disponibile")
    except Exception as e:
        logger.error(f"[IntelligentMonitor] Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/health")
async def intelligent_monitor_health():
    """
    Health score del sistema.

    Calcola score complessivo 0-100 basato su:
    - error_rate: tasso errori (peso 25%)
    - fallback_rate: tasso fallback (peso 25%)
    - latency: tempo risposta medio (peso 20%)
    - trend: andamento rispetto settimana precedente (peso 15%)
    - stability: assenza alert degradazione (peso 15%)

    Returns:
        - overall_score: score complessivo 0-100
        - components: scores per singolo componente
        - alerts: lista alert attivi con severity
        - generated_at: timestamp generazione
    """
    try:
        from tools.intelligent_monitor import IntelligentMonitor

        monitor = IntelligentMonitor()
        health = monitor.get_health()

        # Add status interpretation
        status = "healthy"
        if health.overall_score < 40:
            status = "critical"
        elif health.overall_score < 60:
            status = "degraded"
        elif health.overall_score < 80:
            status = "warning"

        result = health.to_dict()
        result["status"] = status
        result["alerts_count"] = len(health.alerts)

        return result

    except ImportError as e:
        logger.error(f"[IntelligentMonitor] Import error: {e}")
        raise HTTPException(status_code=500, detail="Modulo intelligent_monitor non disponibile")
    except Exception as e:
        logger.error(f"[IntelligentMonitor] Error getting health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info("Avvio GiAs-llm API server...")
    logger.info("Endpoint webhook: http://localhost:5005/webhooks/rest/webhook")
    logger.info("Endpoint parse: http://localhost:5005/model/parse")
    logger.info("Endpoint status: http://localhost:5005/status")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5005,
        log_level="info"
    )
