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

# Intent metadata cache (loaded once from DB)
_intent_metadata_cache: Dict[str, Dict[str, Any]] = {}


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
    ExecutionInfo, Suggestion, ParseRequest, ParseResult, SSEFinalEvent,
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

    return ChatResult(
        text=response_text or "Non ho capito la tua richiesta. Puoi riformularla?",
        intent=result.get("intent", ""),
        slots=result.get("slots", {}),
        suggestions=suggestions,
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

        # Log
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
                except:
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
        "llm_backend": llm_backend
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
