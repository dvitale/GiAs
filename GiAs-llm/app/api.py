"""
FastAPI wrapper per GiAs-llm
API nativa per GChat (protocollo v1)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, AsyncGenerator
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
from app.session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to track if data has been preloaded
_data_preloaded = False

# Global ConversationGraph singleton for better performance
# Avoids re-initializing LLMClient and Router on every request
_conversation_graph = None

# Singleton SessionManager (sostituisce _session_store, _session_lock, _request_count)
_session_mgr = SessionManager()

# Timeout per esecuzione grafo (deve essere < timeout Go frontend 60s)
GRAPH_INVOKE_TIMEOUT = 50

# Intent metadata via IntentMetadataService (singleton, lazy loading)
_intent_metadata_service = None


def _get_intent_metadata_service():
    """Lazy accessor per IntentMetadataService singleton."""
    global _intent_metadata_service
    if _intent_metadata_service is None:
        try:
            from orchestrator.intent_metadata_service import get_intent_metadata_service
            _intent_metadata_service = get_intent_metadata_service()
            logger.info(f"[ChatLog] IntentMetadataService initialized (source: {_intent_metadata_service.source})")
        except Exception as e:
            logger.warning(f"[ChatLog] Could not init IntentMetadataService: {e}")
    return _intent_metadata_service


def log_chat(
    ask: str,
    intent: str,
    answer: str,
    metadata: Dict[str, Any],
    session_id: str = "",
    slots: Optional[Dict[str, Any]] = None,
    response_time_ms: Optional[int] = None,
    error: Optional[str] = None,
    message_id: Optional[str] = None,
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
        message_id: UUID per tracking feedback utente
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

            service = _get_intent_metadata_service()
            intent_meta = service.get_intent_metadata_for_chatlog(intent) if service else {}
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
                     session_id, asl, slots, response_time_ms, error, message_id)
                    VALUES
                    (:ask, :intent, :tool, :two_phase_resp, :dataretriever_class, :sql, :who, NOW(), :answer,
                     :session_id, :asl, CAST(:slots AS jsonb), :response_time_ms, :error,
                     CAST(:message_id AS uuid))"""
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
                    "message_id": message_id,
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

            # Init IntentMetadataService (lazy, carica da DB alla prima chiamata)
            _get_intent_metadata_service()

            # Pre-calcola risk scores per evitare cold-start sulla prima query utente
            try:
                from agents.data_agent import RiskAnalyzer
                risk_start = time.time()
                risk_df = RiskAnalyzer.calculate_risk_scores()
                risk_time = time.time() - risk_start
                logger.info(f"[Startup] ✓ Risk scores pre-computed: {len(risk_df)} activities in {risk_time:.2f}s")
            except Exception as e:
                logger.warning(f"[Startup] Risk scores pre-computation failed (will compute on first request): {e}")

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



async def format_sse_event(event: Dict[str, Any]) -> str:
    """Formatta evento in formato SSE (Server-Sent Events)"""
    event_type = event.get("type", "status")
    data = json_module.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "model_loaded": True
    }


# =============================================================================
# API V1 — Endpoint nativi
# =============================================================================

from app.models import (
    ChatMessage, ChatResponse as ChatResponseV1, ChatResult,
    ExecutionInfo, Suggestion, FallbackIntentSuggestion,
    ParseRequest, ParseResult, SSEFinalEvent,
    FeedbackRequest,
)


def _metadata_to_dict(meta) -> Dict[str, Any]:
    """Converte UserMetadata (o None) in dict per il grafo."""
    if meta is None:
        return {}
    return {k: v for k, v in meta.model_dump().items() if v is not None}


def _build_chat_result(result: Dict[str, Any]) -> ChatResult:
    """Mappa il result dict di graph.run() a ChatResult tipizzato."""
    # Converti suggestions dal formato grafo [{text, query}, ...] a Suggestion
    raw_suggestions = result.get("suggestions") or []
    suggestions = []
    for s in raw_suggestions:
        if isinstance(s, dict):
            suggestions.append(Suggestion(text=s.get("text", ""), query=s.get("query")))
        elif isinstance(s, str):
            suggestions.append(Suggestion(text=s))

    execution = ExecutionInfo(
        execution_path=result.get("execution_path", []),
        node_timings=result.get("node_timings", {}),
        total_execution_ms=result.get("total_execution_ms"),
    )

    response_text = result.get("response", "")
    error = result.get("error", "")
    if error:
        response_text = f"❌ Errore: {error}" if not response_text else response_text

    # Guided learning: converti fallback_suggestions in FallbackIntentSuggestion
    fallback_intents = []
    from configs.config import AppConfig
    if (result.get("intent") == "fallback"
            and result.get("fallback_suggestions")
            and AppConfig.is_guided_learning_enabled()):
        for fs in result["fallback_suggestions"]:
            if isinstance(fs, dict) and fs.get("type") == "intent" and fs.get("intent"):
                fallback_intents.append(FallbackIntentSuggestion(
                    intent=fs["intent"],
                    label=fs.get("label", fs["intent"]),
                    description=fs.get("description", ""),
                    emoji=fs.get("emoji", ""),
                    category=fs.get("category", ""),
                    type="intent",
                ))

    return ChatResult(
        text=response_text or "Non ho capito la tua richiesta. Puoi riformularla?",
        intent=result.get("intent", ""),
        slots=result.get("slots", {}),
        suggestions=suggestions,
        fallback_intents=fallback_intents,
        execution=execution,
        needs_clarification=result.get("needs_clarification", False),
        has_more_details=result.get("has_more_details", False),
        error=error if error else None,
    )


@app.post("/api/v1/chat")
async def chat_v1(message: ChatMessage) -> ChatResponseV1:
    """
    Endpoint chat nativo. Sostituisce /webhooks/rest/webhook.

    Differenze dal formato Rasa:
    - metadata tipizzato (UserMetadata vs Dict)
    - Risposta singola ChatResult vs List[RasaResponse]
    - Tutti i campi del grafo esposti
    - suggestions tipizzato come List[Suggestion]
    """
    try:
        logger.info(f"[V1Chat] Ricevuto messaggio da {message.sender}: {message.message}")

        # Converti UserMetadata in dict per il grafo
        metadata = _metadata_to_dict(message.metadata)
        if not metadata.get('user_id'):
            metadata['user_id'] = message.sender

        # Risolvi UOC
        if not metadata.get('uoc') and metadata.get('user_id'):
            try:
                from agents.data import get_uoc_from_user_id
                resolved_uoc = get_uoc_from_user_id(metadata['user_id'])
                if resolved_uoc:
                    metadata['uoc'] = resolved_uoc
            except Exception:
                pass

        # Risolvi UOS
        if not metadata.get('uos') and metadata.get('user_id'):
            try:
                from agents.data import get_uos_from_user_id
                resolved_uos = get_uos_from_user_id(metadata['user_id'])
                if resolved_uos:
                    metadata['uos'] = resolved_uos
            except Exception:
                pass

        global _conversation_graph
        if _conversation_graph is None:
            _conversation_graph = ConversationGraph()

        _session_mgr.periodic_cleanup()

        # Recupera contesto sessione
        ctx = _session_mgr.get_session_context(message.sender)
        metadata.update(ctx.metadata_enrichment)

        # Valida workflow_context
        workflow_context = WorkflowValidator.validate_workflow_context(
            ctx.workflow_context, ctx.session_timestamp
        )
        if ctx.workflow_context and not workflow_context:
            _session_mgr.invalidate_workflow(message.sender)

        # Esegui il grafo con timeout
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _conversation_graph.run,
                message=message.message,
                metadata=metadata,
                detail_context=ctx.detail_context,
                workflow_context=workflow_context,
                dialogue_state=ctx.dialogue_state,
            )
            try:
                result = future.result(timeout=GRAPH_INVOKE_TIMEOUT)
            except FuturesTimeoutError:
                logger.error(f"[V1Chat] Graph timeout after {GRAPH_INVOKE_TIMEOUT}s for {message.sender}")
                return ChatResponseV1(
                    sender=message.sender,
                    result=ChatResult(
                        text="⏱️ La richiesta ha impiegato troppo tempo. Riprova con una domanda più specifica.",
                        error="timeout",
                    )
                )

        # Aggiorna sessione
        _session_mgr.update_session(message.sender, result)

        # Genera message_id per tracking feedback
        import uuid
        msg_id = str(uuid.uuid4())

        # Log
        chat_result = _build_chat_result(result)
        chat_result.message_id = msg_id
        log_chat(
            ask=message.message,
            intent=result.get("intent", ""),
            answer=chat_result.text,
            metadata=metadata,
            session_id=message.sender,
            slots=result.get("slots"),
            response_time_ms=result.get("total_execution_ms"),
            error=result.get("error") if result.get("error") else None,
            message_id=msg_id,
        )

        return ChatResponseV1(sender=message.sender, result=chat_result)

    except Exception as e:
        logger.exception(f"[V1Chat] Eccezione non gestita: {e}")
        return ChatResponseV1(
            sender=message.sender,
            result=ChatResult(
                text=f"❌ Errore interno del sistema: {str(e)}",
                error=str(e),
            )
        )


@app.post("/api/v1/session/reset")
async def session_reset(req: ChatMessage):
    """Reset sessione utente: rimuove contesto, slot, stato fallback."""
    sender = req.sender
    _session_mgr.clear_session(sender)
    logger.info(f"[SessionReset] Session cleared for sender={sender}")
    return {"status": "ok", "sender": sender}


@app.post("/api/v1/chat/feedback")
async def chat_feedback(req: FeedbackRequest):
    """Registra il feedback utente (rating 1-5) su una risposta."""
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="Rating deve essere tra 1 e 5")

    engine = _get_db_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(
                """UPDATE chat_log
                   SET rating = :rating, user_feedback = :feedback
                   WHERE message_id = CAST(:message_id AS uuid)"""
            ), {
                "message_id": req.message_id,
                "rating": req.rating,
                "feedback": req.feedback,
            })
            conn.commit()

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="message_id non trovato")

        # Feedback loop automatico: alimenta domande_risposte
        try:
            _feedback_loop(engine, req.message_id, req.rating)
        except Exception as fl_err:
            logger.warning(f"[Feedback] Feedback loop errore (non bloccante): {fl_err}")

        logger.info(f"[Feedback] message_id={req.message_id}, rating={req.rating}")
        return {"status": "ok", "message_id": req.message_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Feedback] Errore: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _feedback_loop(engine, message_id: str, rating: int):
    """Feedback loop automatico: inserisce in domande_risposte basandosi sul rating."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Recupera ask e intent dal chat_log
        row = conn.execute(text(
            """SELECT ask, intent FROM chat_log
               WHERE message_id = CAST(:message_id AS uuid)"""
        ), {"message_id": message_id}).fetchone()

        if not row or not row[0] or not row[1]:
            return

        ask, intent = row[0], row[1]
        if intent in ("greet", "goodbye", "ask_help", "fallback",
                       "confirm_show_details", "decline_show_details"):
            return

        if rating >= 4:
            conn.execute(text("""
                INSERT INTO domande_risposte (domanda, intent, example_type, source, active)
                VALUES (:domanda, :intent, 'variation', 'feedback_auto', TRUE)
                ON CONFLICT (domanda, intent) DO NOTHING
            """), {"domanda": ask, "intent": intent})
            conn.commit()
            logger.info(f"[FeedbackLoop] rating={rating}, inserita variazione: '{ask[:50]}' → {intent}")
        elif rating <= 2:
            conn.execute(text("""
                INSERT INTO domande_risposte (domanda, intent, example_type, source, active)
                VALUES (:domanda, :intent, 'variation', 'feedback_negative', FALSE)
                ON CONFLICT (domanda, intent) DO NOTHING
            """), {"domanda": ask, "intent": intent})
            conn.commit()
            logger.info(f"[FeedbackLoop] rating={rating}, segnalata per revisione: '{ask[:50]}' → {intent}")


@app.post("/api/v1/chat/stream")
async def chat_stream_v1(message: ChatMessage):
    """
    Endpoint chat streaming nativo. Sostituisce /webhooks/rest/webhook/stream.

    L'evento SSE finale contiene un ChatResult completo (stesso schema del sincrono).
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        event_queue = Queue()
        result_container = {"result": None, "exception": None}

        try:
            logger.info(f"[V1Stream] Ricevuto messaggio da {message.sender}: {message.message}")

            metadata = _metadata_to_dict(message.metadata)
            if not metadata.get('user_id'):
                metadata['user_id'] = message.sender

            if not metadata.get('uoc') and metadata.get('user_id'):
                try:
                    from agents.data import get_uoc_from_user_id
                    resolved_uoc = get_uoc_from_user_id(metadata['user_id'])
                    if resolved_uoc:
                        metadata['uoc'] = resolved_uoc
                except Exception:
                    pass

            if not metadata.get('uos') and metadata.get('user_id'):
                try:
                    from agents.data import get_uos_from_user_id
                    resolved_uos = get_uos_from_user_id(metadata['user_id'])
                    if resolved_uos:
                        metadata['uos'] = resolved_uos
                except Exception:
                    pass

            def event_callback(event: Dict[str, Any]):
                event["timestamp"] = int(time.time() * 1000)
                event_queue.put(event)

            yield await format_sse_event({
                "type": "status",
                "timestamp": int(time.time() * 1000),
                "message": "Connessione stabilita, elaborazione in corso..."
            })

            global _conversation_graph
            if _conversation_graph is None:
                _conversation_graph = ConversationGraph()

            ctx = _session_mgr.get_session_context(message.sender)
            metadata.update(ctx.metadata_enrichment)

            workflow_context = WorkflowValidator.validate_workflow_context(
                ctx.workflow_context, ctx.session_timestamp
            )
            if ctx.workflow_context and not workflow_context:
                _session_mgr.invalidate_workflow(message.sender)

            def run_graph():
                try:
                    result = _conversation_graph.run(
                        message=message.message,
                        metadata=metadata,
                        detail_context=ctx.detail_context,
                        workflow_context=workflow_context,
                        event_callback=event_callback,
                        dialogue_state=ctx.dialogue_state,
                    )
                    result_container["result"] = result
                    event_queue.put(None)
                except Exception as e:
                    result_container["exception"] = e
                    event_queue.put(None)

            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, run_graph)

            while True:
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, event_queue.get, True, 0.5
                    )
                except Exception:
                    continue
                if event is None:
                    break
                yield await format_sse_event(event)

            if result_container["exception"]:
                raise result_container["exception"]

            result = result_container["result"]
            _session_mgr.update_session(message.sender, result)

            chat_result = _build_chat_result(result)

            log_chat(
                ask=message.message,
                intent=result.get("intent", ""),
                answer=chat_result.text,
                metadata=metadata,
                session_id=message.sender,
                slots=result.get("slots"),
                response_time_ms=result.get("total_execution_ms"),
                error=result.get("error") if result.get("error") else None,
            )

            # Evento finale con ChatResult completo (stesso formato del sincrono)
            final_event = SSEFinalEvent(
                timestamp=int(time.time() * 1000),
                result=chat_result,
            )
            yield await format_sse_event(final_event.model_dump())

        except Exception as e:
            logger.exception(f"[V1Stream] Eccezione non gestita: {e}")
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
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/parse")
async def parse_v1(request: ParseRequest) -> ParseResult:
    """
    Endpoint parsing NLU nativo. Sostituisce /model/parse.
    Ritorna confidence reale dal router (non hardcoded 0.95).
    """
    try:
        global _conversation_graph
        if _conversation_graph is None:
            _conversation_graph = ConversationGraph()

        metadata = _metadata_to_dict(request.metadata)
        router = _conversation_graph.router
        result = router.classify(message=request.text, metadata=metadata)

        return ParseResult(
            text=request.text,
            intent=result.get("intent", "fallback"),
            confidence=result.get("confidence", 0.5),
            slots=result.get("slots", {}),
            needs_clarification=result.get("needs_clarification", False),
        )

    except Exception as e:
        logger.exception(f"[V1Parse] Errore: {e}")
        return ParseResult(
            text=request.text,
            intent="fallback",
            confidence=0.0,
            slots={},
        )


@app.get("/status")
async def status():
    """Status endpoint con informazioni sul modello"""
    from agents.data import piani_df, controlli_df, osa_mai_controllati_df
    from configs.config_loader import get_config
    from configs.config import AppConfig
    from llm.client import LLMClient

    config = get_config()

    # Check actual LLM availability — usa il modello dal client reale
    llm_backend = AppConfig.LLM_BACKEND
    try:
        test_client = LLMClient()
        llm_mode = "real" if test_client.use_real_llm else "stub"
        llm_model = test_client.model  # modello effettivo dal provider
        llm_model_key = test_client.model_key
    except Exception:
        llm_mode = "stub"
        llm_model = AppConfig.get_model_name()
        llm_model_key = AppConfig.LLM_MODEL
    llm_status = f"{llm_model} ({llm_mode})"

    # RAG cache stats
    rag_cache_stats = {}
    try:
        from tools.rag_cache import get_rag_cache
        rag_cache_stats = get_rag_cache().get_stats()
    except Exception:
        pass

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
        "llm": llm_status,
        "llm_model_key": llm_model_key,
        "llm_backend": llm_backend,
        "rag_cache": rag_cache_stats,
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


@app.get("/api/chat-log/user-conversations")
async def chat_log_user_conversations(codice_fiscale: str = None, limit: int = 50, offset: int = 0):
    """
    Lista conversazioni di un utente, raggruppate per session_id.

    Query params:
        codice_fiscale: codice fiscale utente (required)
        limit: max conversazioni (default: 50)
        offset: offset per paginazione (default: 0)
    """
    if not codice_fiscale:
        raise HTTPException(status_code=400, detail="codice_fiscale obbligatorio")

    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            # Conteggio totale conversazioni
            count_query = text("""
                SELECT COUNT(DISTINCT session_id)
                FROM chat_log
                WHERE who LIKE '%' || :cf
                  AND session_id IS NOT NULL
            """)
            total = conn.execute(count_query, {"cf": codice_fiscale}).scalar() or 0

            # Lista conversazioni con prima domanda come titolo
            query = text("""
                SELECT
                    session_id,
                    MIN(ask) FILTER (WHERE ask IS NOT NULL) AS title,
                    COUNT(*) AS message_count,
                    MIN("when") AS started_at,
                    MAX("when") AS ended_at,
                    MAX(asl) AS asl
                FROM chat_log
                WHERE who LIKE '%' || :cf
                  AND session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY MAX("when") DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = conn.execute(query, {"cf": codice_fiscale, "limit": limit, "offset": offset}).fetchall()

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "conversations": [
                    {
                        "session_id": r[0],
                        "title": r[1] or "(senza titolo)",
                        "message_count": r[2],
                        "started_at": r[3] if isinstance(r[3], str) else (r[3].isoformat() if r[3] else None),
                        "ended_at": r[4] if isinstance(r[4], str) else (r[4].isoformat() if r[4] else None),
                        "asl": r[5],
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in user-conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-log/conversation/{session_id}")
async def chat_log_conversation(session_id: str, codice_fiscale: str = None):
    """
    Messaggi di una singola conversazione.

    Path params:
        session_id: ID sessione
    Query params:
        codice_fiscale: codice fiscale utente (per verifica ownership)
    """
    if not codice_fiscale:
        raise HTTPException(status_code=400, detail="codice_fiscale obbligatorio")

    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT id, ask, answer, "when", intent, tool, response_time_ms, error
                FROM chat_log
                WHERE session_id = :sid
                  AND who LIKE '%' || :cf
                ORDER BY "when" ASC, id ASC
            """)
            rows = conn.execute(query, {"sid": session_id, "cf": codice_fiscale}).fetchall()

            return {
                "session_id": session_id,
                "messages": [
                    {
                        "id": r[0],
                        "ask": r[1],
                        "answer": r[2],
                        "timestamp": r[3] if isinstance(r[3], str) else (r[3].isoformat() if r[3] else None),
                        "intent": r[4],
                        "tool": r[5],
                        "response_time_ms": r[6],
                        "error": r[7],
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[ChatLogAPI] Error in conversation: {e}")
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


# =============================================================================
# ADMIN - DOMANDE RAG
# =============================================================================

from pydantic import BaseModel

class DomandaRAGCreate(BaseModel):
    domanda: str
    risposta: Optional[str] = None
    intent: str = "info_procedure"
    example_type: str = "few_shot"
    confused_with: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


@app.get("/api/admin/domande-rag")
async def admin_list_domande_rag():
    """Lista domande attive dalla tabella domande_risposte."""
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, domanda, risposta, intent, example_type, confused_with,
                       source, notes, created_at, updated_at
                FROM domande_risposte
                WHERE active = TRUE
                ORDER BY created_at DESC
            """)).fetchall()

            return {
                "total": len(rows),
                "records": [
                    {
                        "id": r[0],
                        "domanda": r[1],
                        "risposta": r[2],
                        "intent": r[3],
                        "example_type": r[4],
                        "confused_with": r[5],
                        "source": r[6],
                        "notes": r[7],
                        "created_at": r[8].isoformat() if r[8] else None,
                        "updated_at": r[9].isoformat() if r[9] else None,
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"[AdminRAG] Error listing domande: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/domande-rag")
async def admin_create_domanda_rag(payload: DomandaRAGCreate):
    """Inserisce una nuova domanda nella tabella domande_risposte."""
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    if not payload.domanda.strip():
        raise HTTPException(status_code=400, detail="Il campo 'domanda' è obbligatorio")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO domande_risposte (domanda, risposta, intent, example_type, confused_with, source, notes)
                VALUES (:domanda, :risposta, :intent, :example_type, :confused_with, :source, :notes)
                RETURNING id, created_at
            """), {
                "domanda": payload.domanda.strip(),
                "risposta": payload.risposta.strip() if payload.risposta else None,
                "intent": payload.intent,
                "example_type": payload.example_type,
                "confused_with": payload.confused_with,
                "source": payload.source.strip() if payload.source else None,
                "notes": payload.notes.strip() if payload.notes else None,
            })
            row = result.fetchone()
            conn.commit()

            logger.info(f"[AdminRAG] Nuova domanda id={row[0]}: {payload.domanda[:80]}")
            return {
                "status": "ok",
                "id": row[0],
                "created_at": row[1].isoformat() if row[1] else None,
            }
    except Exception as e:
        logger.error(f"[AdminRAG] Error creating domanda: {e}")
        if "uq_domande_risposte_domanda_intent" in str(e):
            raise HTTPException(status_code=409, detail="Domanda già esistente per questo intent")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/domande-rag/{domanda_id}")
async def admin_delete_domanda_rag(domanda_id: int):
    """Disattiva una domanda (soft delete: active=FALSE)."""
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                UPDATE domande_risposte
                SET active = FALSE, updated_at = NOW()
                WHERE id = :id AND active = TRUE
            """), {"id": domanda_id})
            conn.commit()

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Domanda non trovata o già disattivata")

            logger.info(f"[AdminRAG] Domanda id={domanda_id} disattivata")
            return {"status": "ok", "id": domanda_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AdminRAG] Error deleting domanda {domanda_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/domande-rag/reindex")
async def admin_reindex_domande_rag():
    """Esegue sync domande_risposte -> intent_examples -> Qdrant."""
    import subprocess

    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sync_script = os.path.join(script_dir, "scripts", "sync_domande_risposte.py")

    if not os.path.exists(sync_script):
        raise HTTPException(status_code=500, detail="Script sync_domande_risposte.py non trovato")

    try:
        result = subprocess.run(
            [sys.executable, sync_script],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=script_dir,
        )

        logger.info(f"[AdminRAG] Reindex completato: rc={result.returncode}")

        # Auto-reload router dopo reindex riuscito
        reload_status = None
        if result.returncode == 0:
            try:
                reload_status = _do_router_reload()
                logger.info("[AdminRAG] Auto-reload router completato post-reindex")
            except Exception as rl_err:
                reload_status = {"error": str(rl_err)}
                logger.warning(f"[AdminRAG] Auto-reload fallito (non bloccante): {rl_err}")

        resp = {
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if reload_status:
            resp["router_reload"] = reload_status
        return resp

    except subprocess.TimeoutExpired:
        logger.error("[AdminRAG] Reindex timeout (120s)")
        raise HTTPException(status_code=504, detail="Reindicizzazione timeout (120s)")
    except Exception as e:
        logger.error(f"[AdminRAG] Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _do_router_reload() -> dict:
    """Esegue reload di IntentMetadataService + Router + FewShotRetriever."""
    global _conversation_graph, _intent_metadata_service

    stats = {}

    # 1. Reload IntentMetadataService
    if _intent_metadata_service:
        _intent_metadata_service.reload()
        stats["intent_metadata"] = "reloaded"

    # 2. Reload Router (prompt + cache)
    if _conversation_graph and hasattr(_conversation_graph, 'router'):
        _conversation_graph.router.reload()
        stats["router"] = "reloaded"

    # 3. Clear FewShotRetriever cache
    try:
        from orchestrator.few_shot_retriever import get_few_shot_retriever
        retriever = get_few_shot_retriever()
        retriever.clear_cache()
        stats["few_shot_cache"] = "cleared"
    except Exception as e:
        stats["few_shot_cache"] = f"error: {e}"

    return stats


@app.post("/api/admin/router/reload")
async def admin_router_reload():
    """Hot-reload: ricarica metadati intent, ricostruisce prompt, svuota cache."""
    try:
        stats = _do_router_reload()
        logger.info(f"[AdminReload] Reload completato: {stats}")
        return {"status": "ok", **stats}
    except Exception as e:
        logger.error(f"[AdminReload] Errore: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Guided Learning ──────────────────────────────────────────────────

_guided_reindex_running = False


class GuidedLearnRequest(BaseModel):
    domanda: str
    intent: str
    session_id: Optional[str] = None


@app.post("/api/admin/guided-learn")
async def admin_guided_learn(payload: GuidedLearnRequest):
    """Salva associazione domanda→intent appresa dall'utente e lancia reindex FSIC."""
    from configs.config import AppConfig
    if not AppConfig.is_guided_learning_enabled():
        raise HTTPException(status_code=403, detail="Guided learning non abilitato")

    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    if not payload.domanda.strip() or not payload.intent.strip():
        raise HTTPException(status_code=400, detail="domanda e intent sono obbligatori")

    from sqlalchemy import text

    inserted = False
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO domande_risposte (domanda, intent, source, example_type, active)
                VALUES (:domanda, :intent, 'guided_learning', 'variation', TRUE)
                ON CONFLICT (domanda, intent) DO NOTHING
                RETURNING id
            """), {
                "domanda": payload.domanda.strip(),
                "intent": payload.intent.strip(),
            })
            row = result.fetchone()
            conn.commit()
            inserted = row is not None
    except Exception as e:
        logger.error(f"[GuidedLearn] DB error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Reindex FSIC in background (con debounce)
    reindex_status = "skipped"
    global _guided_reindex_running
    if inserted and not _guided_reindex_running:
        import threading
        _guided_reindex_running = True

        def _background_reindex():
            global _guided_reindex_running
            try:
                import subprocess
                script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sync_script = os.path.join(script_dir, "scripts", "sync_domande_risposte.py")
                if os.path.exists(sync_script):
                    subprocess.run(
                        [sys.executable, sync_script],
                        capture_output=True, text=True, timeout=120,
                        cwd=script_dir,
                    )
                    logger.info("[GuidedLearn] Reindex completato")
                try:
                    _do_router_reload()
                    logger.info("[GuidedLearn] Router reload completato")
                except Exception as rl_err:
                    logger.warning(f"[GuidedLearn] Router reload fallito: {rl_err}")
            except Exception as e:
                logger.error(f"[GuidedLearn] Reindex error: {e}")
            finally:
                _guided_reindex_running = False

        threading.Thread(target=_background_reindex, daemon=True).start()
        reindex_status = "started_background"

    logger.info(f"[GuidedLearn] domanda='{payload.domanda[:80]}', intent={payload.intent}, inserted={inserted}")
    return {
        "status": "ok",
        "inserted": inserted,
        "domanda": payload.domanda,
        "intent": payload.intent,
        "reindex": reindex_status,
    }


@app.get("/api/admin/intents")
async def admin_list_intents():
    """Lista intent disponibili con descrizione."""
    from orchestrator.intent_metadata import INTENT_REGISTRY
    result = []
    for intent_id, meta in INTENT_REGISTRY.items():
        result.append({
            "intent": intent_id,
            "label": meta.label,
            "description": meta.description,
            "category": meta.category,
        })
    return {"intents": result}


@app.get("/api/admin/documents")
async def admin_list_documents():
    """Lista PDF nella directory data/documents/."""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "documents")

    if not os.path.isdir(docs_dir):
        return {"documents": []}

    files = []
    for fname in sorted(os.listdir(docs_dir)):
        if fname.lower().endswith(".pdf"):
            fpath = os.path.join(docs_dir, fname)
            stat = os.stat(fpath)
            files.append({
                "filename": fname,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    return {"documents": files}


@app.get("/api/admin/documents/{filename}")
async def admin_get_document(filename: str):
    """Serve un file PDF dalla directory data/documents/."""
    from fastapi.responses import FileResponse

    # Sicurezza: impedisci path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome file non valido")

    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "documents")
    file_path = os.path.join(docs_dir, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File non trovato")

    return FileResponse(file_path, media_type="application/pdf", filename=filename)


# =============================================================================
# ADMIN - Re-indicizzazione documenti RAG
# =============================================================================

_reindex_state = {
    "status": "idle",  # idle | running | completed | error
    "last_run": None,
    "documents_count": 0,
    "chunks_count": 0,
    "error": None,
}
_reindex_lock = threading.Lock()


@app.post("/api/admin/documents/reindex")
async def admin_reindex_documents():
    """Lancia re-indicizzazione documenti in background thread."""
    with _reindex_lock:
        if _reindex_state["status"] == "running":
            raise HTTPException(status_code=409, detail="Re-indicizzazione gia' in corso")
        _reindex_state["status"] = "running"
        _reindex_state["error"] = None

    def _do_reindex():
        try:
            from tools.indexing.build_docs_index import run_indexing
            result = run_indexing()

            with _reindex_lock:
                _reindex_state["status"] = result.get("status", "error")
                _reindex_state["last_run"] = datetime.now().isoformat()
                _reindex_state["documents_count"] = result.get("documents_count", 0)
                _reindex_state["chunks_count"] = result.get("chunks_count", 0)
                _reindex_state["error"] = result.get("error")

            # Svuota RAG cache dopo re-indicizzazione riuscita
            if result.get("status") == "completed":
                try:
                    from tools.rag_cache import get_rag_cache
                    cleared = get_rag_cache().clear_all()
                    logger.info(f"[Reindex] RAG cache svuotata: {cleared} entry rimosse")
                except Exception:
                    pass

            logger.info(f"[Reindex] Completato: {result}")
        except Exception as e:
            logger.error(f"[Reindex] Errore: {e}")
            with _reindex_lock:
                _reindex_state["status"] = "error"
                _reindex_state["error"] = str(e)
                _reindex_state["last_run"] = datetime.now().isoformat()

    threading.Thread(target=_do_reindex, daemon=True).start()
    return {"status": "started", "message": "Re-indicizzazione avviata in background"}


@app.get("/api/admin/documents/reindex/status")
async def admin_reindex_status():
    """Ritorna lo stato corrente della re-indicizzazione."""
    with _reindex_lock:
        return dict(_reindex_state)


# ── Schema Metadata Admin ────────────────────────────────────────────


def _schema_row_to_dict(r) -> dict:
    """Converte riga schema_metadata in dict (singola fonte di verità)."""
    return {
        "table_key": r[0],
        "table_name": r[1],
        "df_variable": r[2],
        "description_it": r[3],
        "columns": r[4],
        "relationships": r[5],
        "valid_values": r[6],
        "pii_columns": list(r[7]) if r[7] else [],
        "row_count_approx": r[8],
        "is_active": r[9],
        "updated_at": r[10].isoformat() if r[10] else None,
    }


@app.get("/api/admin/schema-metadata")
async def admin_list_schema_metadata():
    """Lista tutte le tabelle schema_metadata attive."""
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT table_key, table_name, df_variable, description_it,
                       columns, relationships, valid_values, pii_columns,
                       row_count_approx, is_active, updated_at
                FROM schema_metadata
                ORDER BY table_key
            """)).fetchall()

            return {
                "total": len(rows),
                "records": [_schema_row_to_dict(r) for r in rows]
            }
    except Exception as e:
        logger.error(f"[AdminSchema] Error listing schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/schema-metadata/{table_key}")
async def admin_get_schema_metadata(table_key: str):
    """Dettaglio singola tabella schema_metadata."""
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT table_key, table_name, df_variable, description_it,
                       columns, relationships, valid_values, pii_columns,
                       row_count_approx, is_active, updated_at
                FROM schema_metadata
                WHERE table_key = :key
            """), {"key": table_key}).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Tabella '{table_key}' non trovata")

            return _schema_row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AdminSchema] Error getting schema {table_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/schema-metadata/{table_key}")
async def admin_update_schema_metadata(table_key: str, payload: dict):
    """Aggiorna schema di una tabella in schema_metadata."""
    engine = _get_db_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database non disponibile")

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            # Aggiorna solo i campi forniti nel payload
            update_fields = []
            params = {"key": table_key}

            updatable = {
                "description_it": "description_it",
                "columns": "columns",
                "relationships": "relationships",
                "valid_values": "valid_values",
                "pii_columns": "pii_columns",
                "row_count_approx": "row_count_approx",
                "is_active": "is_active",
            }

            for field, col in updatable.items():
                if field in payload:
                    value = payload[field]
                    if field in ("columns", "relationships", "valid_values"):
                        # JSONB: converti a stringa JSON
                        params[field] = json_module.dumps(value)
                        update_fields.append(f"{col} = :{field}::jsonb")
                    elif field == "pii_columns":
                        params[field] = value if isinstance(value, list) else []
                        update_fields.append(f"{col} = :{field}")
                    else:
                        params[field] = value
                        update_fields.append(f"{col} = :{field}")

            if not update_fields:
                return {"status": "ok", "message": "Nessun campo da aggiornare"}

            update_fields.append("updated_at = NOW()")
            sql = f"UPDATE schema_metadata SET {', '.join(update_fields)} WHERE table_key = :key"
            result = conn.execute(text(sql), params)
            conn.commit()

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Tabella '{table_key}' non trovata")

            logger.info(f"[AdminSchema] Schema '{table_key}' aggiornato: {list(payload.keys())}")
            return {"status": "ok", "table_key": table_key}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AdminSchema] Error updating schema {table_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/schema-metadata/reload")
async def admin_reload_schema_catalog():
    """Ricarica il catalogo schema in memoria dal DB."""
    try:
        from orchestrator.schema_catalog import get_schema_catalog
        catalog = get_schema_catalog()
        catalog.reload()

        # Ricostruisci anche il prompt del router con il nuovo schema
        global _conversation_graph
        if _conversation_graph and hasattr(_conversation_graph, 'router'):
            _conversation_graph.router.reload()

        logger.info("[AdminSchema] Schema catalog ricaricato")
        return {
            "status": "ok",
            "tables_count": len(catalog.get_full_schema()),
            "message": "Catalogo schema ricaricato e prompt aggiornato"
        }
    except Exception as e:
        logger.error(f"[AdminSchema] Error reloading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/personale/{user_id}")
async def get_personale(user_id: str):
    """Ritorna i dati del personale per un dato user_id."""
    try:
        from agents.data import personale_df
        import pandas as pd

        if personale_df.empty:
            raise HTTPException(status_code=404, detail="Dati personale non disponibili")

        user_id_str = str(user_id).replace('.0', '')
        user_row = personale_df[
            personale_df['user_id'].astype(str).str.replace('.0', '', regex=False) == user_id_str
        ]

        if user_row.empty:
            raise HTTPException(status_code=404, detail=f"Utente {user_id} non trovato")

        row = user_row.iloc[0]

        def safe_str(val):
            if pd.isna(val) or str(val).strip().upper() == 'NULL':
                return ""
            return str(val).strip()

        asl = safe_str(row.get('asl', ''))
        descrizione_uoc = safe_str(row.get('descrizione_uoc', ''))
        descrizione_uos = safe_str(row.get('descrizione_uos', ''))
        descrizione_asl = safe_str(row.get('descrizione_asl', ''))

        # Ricostruisci campo descrizione (gerarchia con "->") per compatibilita' frontend
        desc_parts = [p for p in [descrizione_asl, descrizione_uoc, descrizione_uos] if p]
        descrizione = "->".join(desc_parts)

        return {
            "asl": asl,
            "descrizione_area_struttura_complessa": descrizione_uoc,
            "descrizione": descrizione,
            "namefirst": safe_str(row.get('namefirst', '')),
            "namelast": safe_str(row.get('namelast', '')),
            "codice_fiscale": safe_str(row.get('codice_fiscale', '')),
            "user_id": int(float(user_id_str)) if user_id_str.isdigit() else user_id_str,
            "uos": descrizione_uos,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Personale] Errore lookup user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info("Avvio GiAs-llm API server...")
    logger.info("Endpoint chat: http://localhost:5005/api/v1/chat")
    logger.info("Endpoint parse: http://localhost:5005/api/v1/parse")
    logger.info("Endpoint status: http://localhost:5005/status")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5005,
        log_level="info"
    )
