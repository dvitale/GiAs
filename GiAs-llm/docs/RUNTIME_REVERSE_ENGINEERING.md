# GiAs-llm Backend Runtime - Reverse Engineering Document

> **Scopo**: Ricostruzione completa del sistema di runtime del backend, partendo dallo script di avvio fino ai singoli handler API. Documento pensato per la navigazione parallela con VSCode (ogni riferimento include `file:linea`).
>
> **Ultimo aggiornamento**: Febbraio 2026

---

## Indice

1. [Panoramica Architetturale](#1-panoramica-architetturale)
2. [Fase 1: Bootstrap Shell](#2-fase-1-bootstrap-shell)
3. [Fase 2: Bootstrap Python (FastAPI Lifespan)](#3-fase-2-bootstrap-python-fastapi-lifespan)
4. [Fase 3: Albero Dipendenze Configurazione](#4-fase-3-albero-dipendenze-configurazione)
5. [Fase 4: Caricamento Dati](#5-fase-4-caricamento-dati)
6. [Fase 5: Inizializzazione LLM Client](#6-fase-5-inizializzazione-llm-client)
7. [Fase 6: Costruzione Grafo LangGraph](#7-fase-6-costruzione-grafo-langgraph)
8. [API Endpoints - Albero Dipendenze Completo](#8-api-endpoints---albero-dipendenze-completo)
9. [Flusso Runtime di una Richiesta Chat](#9-flusso-runtime-di-una-richiesta-chat)
10. [Session Management](#10-session-management)
11. [Mappa Completa Intent → Tool → Modulo](#11-mappa-completa-intent--tool--modulo)
12. [Diagramma Dipendenze Globale](#12-diagramma-dipendenze-globale)
13. [Glossario Quick-Reference](#13-glossario-quick-reference)

---

## 1. Panoramica Architetturale

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PROCESSO DI AVVIO                            │
│                                                                     │
│  server.sh ──exec──▶ start_server.sh ──python3──▶ app/api.py      │
│                          │                            │             │
│                   [verifica LLM backend]        [FastAPI + Uvicorn] │
│                   [pre-carica modello]                │             │
│                   [seleziona modello]           lifespan()          │
│                                                      │             │
│                                          ┌───────────┼──────────┐  │
│                                          │           │          │  │
│                                     agents/data  ConversationGraph  │
│                                     (DataFrame)  (LangGraph)    │  │
│                                          │           │          │  │
│                                     data_sources/  orchestrator/ │  │
│                                     factory.py    graph.py      │  │
│                                          │           │          │  │
│                                     PostgreSQL    Router        │  │
│                                     (gias_db)    LLMClient     │  │
│                                                  TOOL_REGISTRY  │  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Fase 1: Bootstrap Shell

### Entry point: `scripts/server.sh`

> **File**: `scripts/server.sh:1-322`

Script wrapper unificato con comandi `start|stop|restart|status|logs|test`.

Il comando `start` (`:117-131`) fa solo un check `is_running()` e poi delega:

```
cmd_start() → exec "$SCRIPT_DIR/start_server.sh"
```

### Script di avvio effettivo: `scripts/start_server.sh`

> **File**: `scripts/start_server.sh:1-322`

**Sequenza operazioni** (in ordine):

| Step | Linee | Operazione | Dettaglio |
|------|-------|-----------|-----------|
| 1 | `:7-14` | Risoluzione path | `SCRIPT_PATH → SCRIPT_DIR → PROJECT_ROOT` |
| 2 | `:17-19` | Attivazione venv | `source /opt/lang-env/bin/activate` |
| 3 | `:21-25` | Setup directory log | `runtime/logs/` |
| 4 | `:27-36` | Check processo esistente | Legge `api-server.pid`, verifica con `ps -p` |
| 5 | `:40-45` | Verifica dataset CSV | Conta file in `data/dataset.10/*.csv` |
| 6 | `:50-61` | Determina backend LLM | Priorità: `GIAS_LLM_BACKEND` env → `config.json` → default `ollama` |
| 7 | `:64-77` | Configura Ollama host | Solo per backend locali (ollama/llamacpp) |
| 8 | `:117-248` | Verifica/avvio backend LLM | Branch per tipo backend (vedi sotto) |
| 9 | `:254` | **Avvio processo Python** | `python3 "$PROJECT_ROOT/app/api.py" > "$API_LOG" 2>&1 &` |
| 10 | `:257` | Salva PID | `echo $API_PID > "$PID_FILE"` |
| 11 | `:259-287` | Health check polling | Polling `curl http://localhost:5005/status` ogni 1s, timeout 30s |

**Branch backend LLM** (step 8):

```
GIAS_LLM_BACKEND
├── "openai" | "anthropic" | "openai_compat"  → :117-153 (Provider esterno)
│   ├── Legge modello e host da config.json
│   ├── Verifica API key da env var
│   └── Verifica GDPR gate (allow_external_llm)
│
├── "llamacpp"  → :155-174 (llama.cpp locale)
│   └── curl health check su porta 11435
│
└── "ollama" (default)  → :176-248 (Ollama locale)
    ├── Selezione interattiva modello (se GIAS_LLM_MODEL non settato)
    │   └── select_model_interactive()  → :80-115 (menu 1-5 con timeout 10s)
    ├── Mapping nome modello → nome Ollama  → :195-209
    ├── Verifica modello disponibile (curl /api/tags)  → :215-228
    └── Pre-caricamento modello in RAM (curl /api/generate "ready")  → :231-248
```

**Punto critico**: La riga `:254` è dove il controllo passa al mondo Python:

```bash
python3 "$PROJECT_ROOT/app/api.py" > "$API_LOG" 2>&1 &
```

---

## 3. Fase 2: Bootstrap Python (FastAPI Lifespan)

### Entry point Python: `app/api.py`

> **File**: `app/api.py:1741-1754`

Il blocco `__main__` avvia Uvicorn:

```python
uvicorn.run(app, host="0.0.0.0", port=5005, log_level="info")
```

L'oggetto `app` è creato a `:238-243` con il **lifespan context manager**.

### Lifespan: startup e shutdown

> **File**: `app/api.py:174-236`

**Startup** (eseguito da Uvicorn prima di accettare connessioni):

| Step | Linee | Operazione | Import Chain |
|------|-------|-----------|--------------|
| 1 | `:188-189` | Carica configurazione | `configs.config_loader.get_config()` |
| 2 | `:193-194` | Import modulo dati | `from agents import data as agents_data` |
| 3 | `:197` | Verifica dati caricati | `from agents.data import piani_df, controlli_df, osa_mai_controllati_df` |
| 4 | `:204-206` | Check cache PostgreSQL | `PostgreSQLDataSource._dataframe_cache` |
| 5 | `:211-213` | **Init ConversationGraph singleton** | `_conversation_graph = ConversationGraph()` |
| 6 | `:216` | Carica metadata intent | `_load_intent_metadata()` → query tabella `intents` |

**Shutdown** (`:229-235`):
- Chiude engine SQLAlchemy: `PostgreSQLDataSource.dispose_engine()`

### Variabili globali critiche

> **File**: `app/api.py:30-53`

```python
_data_preloaded = False           # Flag: dati caricati?
_conversation_graph = None        # Singleton ConversationGraph
_session_store: Dict = {}         # Store sessioni in-memory
_session_lock = threading.Lock()  # Lock per accesso concorrente
SESSION_TTL = 300                 # 5 minuti TTL sessione
GRAPH_INVOKE_TIMEOUT = 50         # Timeout esecuzione grafo (< 60s Go)
_intent_metadata_cache: Dict = {} # Cache metadata intent da DB
```

---

## 4. Fase 3: Albero Dipendenze Configurazione

### Gerarchia configurazione

```
configs/
├── config.json          ← Fonte di verità per runtime config
│   ├── current_year
│   ├── llm_backend.type (ollama|llamacpp|openai|anthropic|openai_compat)
│   ├── llm_backend.<type>.{host, model, api_key_env, timeout_seconds}
│   ├── gdpr.allow_external_llm
│   ├── risk_predictor.type (ml|statistical)
│   ├── data_source.type (csv|postgresql)
│   ├── data_source.postgresql.{host, port, database, user, password, tables}
│   ├── data_source.csv.{directory, files}
│   ├── hybrid_search.{cpu_mode, default_strategy}
│   ├── rag_documents.{enabled, documents_dir, ...}
│   ├── streaming.{enabled, max_duration_seconds}
│   └── fallback_recovery.{enabled, keyword_threshold, ...}
│
├── config.py            ← Classi Python con logica di risoluzione
│   ├── ModelConfig        → AVAILABLE_MODELS, get_model_name()
│   ├── LLMBackendConfig   → get_backend_type(), get_backend_config(), get_api_key()
│   ├── RiskPredictorConfig → get_predictor_type()
│   └── AppConfig          → aggregatore: LLM_MODEL, LLM_BACKEND, temperature, timeout
│
└── config_loader.py     ← Singleton Config con factory get_config()
    └── Config             → _load_config(), get_data_source_type(), get_postgresql_config()
```

### Ordine di priorità per ogni impostazione

```
Variabile ambiente  >  config.json  >  Default hardcoded

Esempio per LLM_BACKEND:
  GIAS_LLM_BACKEND env  >  config.json["llm_backend"]["type"]  >  "llamacpp"
```

> **File chiave**: `configs/config.py:113-137` (LLMBackendConfig.get_backend_type)

---

## 5. Fase 4: Caricamento Dati

### Catena di import al momento del `from agents import data`

> **File**: `agents/data.py:1-37`

```
agents/data.py
  └── data_sources/factory.py::get_data_source()        ← Singleton
       ├── configs/config_loader.py::get_config()        ← Singleton
       │    └── configs/config.json                       (lettura file)
       │
       └── (branch per tipo data_source)
            ├── "postgresql" → PostgreSQLDataSource(pg_config)
            │    └── data_sources/postgresql_source.py
            │         ├── SQLAlchemy create_engine() con QueuePool
            │         ├── pd.read_sql_query() per ogni tabella
            │         └── _dataframe_cache (class-level, condiviso)
            │
            └── "csv" → CSVDataSource(csv_config)
                 └── data_sources/csv_source.py
                      └── pd.read_csv() per ogni file
```

### DataFrame globali risultanti

> **File**: `agents/data.py:20-26`

| Variabile | Tabella PostgreSQL | Contenuto |
|-----------|-------------------|-----------|
| `piani_df` | `piani_monitoraggio` | Piani di controllo (alias, descrizione, indicatori) |
| `attivita_df` | `masterlist` | Anagrafica stabilimenti |
| `controlli_df` | `cu_eseguiti` | Controlli ufficiali eseguiti |
| `osa_mai_controllati_df` | `osa_mai_controllati` | Stabilimenti mai controllati |
| `ocse_df` | `ocse_isp_semp` | Storico non conformità (2016-2025) |
| `diff_prog_eseg_df` | `cu_diff_programmati_eseguiti` | Delta programmati vs eseguiti |
| `personale_df` | `personale` | Struttura organizzativa utenti (ASL, UOC) |

---

## 6. Fase 5: Inizializzazione LLM Client

### Catena di costruzione

> **File**: `orchestrator/graph.py:101-104`

```python
class ConversationGraph:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or LLMClient()   # ← creazione client
        self.router = Router(self.llm_client)           # ← router usa il client
        self.graph = self._build_graph()                # ← costruzione grafo
```

### LLMClient init

> **File**: `llm/client.py:27-84`

```
LLMClient.__init__()
  ├── LLMBackendConfig.get_backend_type()      → determina backend
  ├── LLMBackendConfig.get_backend_config()     → config specifica del backend
  ├── Risoluzione modello:
  │    ├── llamacpp → model_name da config
  │    ├── openai/anthropic/openai_compat → model da config
  │    └── ollama → AppConfig.get_model_name()
  ├── _check_gdpr_consent()                     → (solo provider esterni)
  │    └── Legge config.json["gdpr"]["allow_external_llm"]
  └── _create_provider()                        → Factory Method
       └── llm/providers.py
            ├── OllamaProvider(model, config, keep_alive)
            ├── LlamaCppProvider(model, config)
            ├── OpenAIProvider(model, config)     ← richiede `pip install openai`
            ├── AnthropicProvider(model, config)  ← richiede `pip install anthropic`
            └── OpenAICompatProvider(model, config) ← zero dipendenze extra
```

### Architettura Provider (Strategy Pattern)

> **File**: `llm/provider_base.py` (ABC), `llm/providers.py` (implementazioni)

```
LLMProvider (ABC)
├── query(messages, temperature, max_tokens, json_mode, timeout) → str
├── query_stream(messages, ...) → Generator[str]
└── ping() → bool

Implementazioni:
├── OllamaProvider      → POST {base_url}/api/chat         (formato nativo Ollama)
├── LlamaCppProvider    → POST {base_url}/v1/chat/completions (OpenAI-compat)
├── OpenAIProvider      → openai.ChatCompletion.create()    (SDK)
├── AnthropicProvider   → anthropic.Messages.create()       (SDK)
└── OpenAICompatProvider → POST {host}/v1/chat/completions  (requests diretto)
```

### Fallback Stub

> **File**: `llm/client.py:182-362`

Se il provider non è raggiungibile, `LLMClient` cade in modalità **stub**:
- `_mock_classification()`: pattern matching regex per intent comuni
- `_mock_response_generation()`: estrae `formatted_response` dal prompt

---

## 7. Fase 6: Costruzione Grafo LangGraph

### `_build_graph()`

> **File**: `orchestrator/graph.py:113-167`

```
StateGraph(ConversationState)

NODI:
  ┌──────────────────┐
  │    classify       │  → _classify_node()
  │    (entry point)  │
  └────────┬─────────┘
           │ (edge)
  ┌────────▼─────────┐
  │ dialogue_manager  │  → _dialogue_manager_node()
  └────────┬─────────┘
           │ (conditional edges via _dm_router)
     ┌─────┼──────────────────┐
     │     │                  │
     ▼     ▼                  ▼
  ask_user  fallback_tool    <tool_node>  (×19 tool registrati)
     │      │                  │
     │      ▼                  ▼
     │  response_generator  response_generator
     │      │                  │
     ▼      ▼                  ▼
    END    END                END
```

### Nodi registrati dinamicamente

> **File**: `orchestrator/graph.py:126-128`

```python
for name, func in TOOL_REGISTRY.items():
    workflow.add_node(name, self._make_tool_wrapper(name, func))
```

I 19 tool node sono wrappati in `_make_tool_wrapper()` (`:169-191`) che:
1. Misura timing del nodo
2. Aggiorna `execution_path` e `node_timings`
3. Emette evento SSE se `_event_callback` è presente

### ConversationState

> **File**: `orchestrator/graph.py:50-93`

TypedDict con ~35 campi. I campi critici per il flusso:

| Campo | Tipo | Prodotto da | Consumato da |
|-------|------|------------|--------------|
| `message` | str | api.py (input) | classify |
| `metadata` | Dict | api.py (input) | tutti |
| `intent` | str | classify | dialogue_manager, tool_nodes |
| `slots` | Dict | classify | tool_nodes |
| `_classification_confidence` | float | classify | dialogue_manager |
| `dm_action` | str | dialogue_manager | _dm_router |
| `dm_target_tool` | str | dialogue_manager | _dm_router |
| `dm_question` | str | dialogue_manager | ask_user |
| `tool_output` | Any | tool_nodes | response_generator |
| `final_response` | str | response_generator/ask_user | api.py (output) |
| `has_more_details` | bool | two_phase | api.py (session) |
| `detail_context` | Dict | two_phase | api.py (session) |
| `dialogue_state` | Dict | dialogue_manager | sessione inter-turno |
| `execution_path` | List[str] | tutti i nodi | api.py (debug) |
| `node_timings` | Dict | tutti i nodi | api.py (debug) |

---

## 8. API Endpoints - Albero Dipendenze Completo

### 8.1 `GET /` — Health Check

> **File**: `app/api.py:275-282`

```
GET /
  └── return {"status": "ok", "version": "1.0.0", "model_loaded": True}

Dipendenze: nessuna (risposta statica)
```

---

### 8.2 `POST /webhooks/rest/webhook` — Chat Principale

> **File**: `app/api.py:285-651`

Questo è l'endpoint principale. Albero dipendenze completo:

```
POST /webhooks/rest/webhook
  │
  ├── Input: RasaMessage {sender, message, metadata}
  │
  ├── [1] Metadata enrichment (api.py:313-331)
  │    ├── Default user_id = sender
  │    ├── agents.data.get_uoc_from_user_id()
  │    │    └── personale_df lookup
  │    └── Log warning se manca ASL
  │
  ├── [2] Session recovery (api.py:349-412)
  │    ├── _session_store[sender] → sender_session
  │    ├── TTL check (300s)
  │    ├── Inject in metadata:
  │    │    ├── _session_last_intent
  │    │    ├── _session_last_slots
  │    │    ├── _session_summary
  │    │    ├── _session_last_response_context
  │    │    ├── _fallback_suggestions / _fallback_phase / _fallback_count
  │    │    └── _fallback_selected_category
  │    └── WorkflowValidator.validate_workflow_context()
  │         └── orchestrator/workflow_validator.py
  │
  ├── [3] Graph execution (api.py:418-435) ★ CORE ★
  │    ├── ThreadPoolExecutor(max_workers=1)
  │    ├── _conversation_graph.run() con timeout 50s
  │    │    └── → [Vedi sezione 9: Flusso Runtime]
  │    └── Catch FuturesTimeoutError → risposta timeout
  │
  ├── [4] Session update (api.py:446-598)
  │    ├── Branch: has_more_details → salva detail_context
  │    ├── Branch: confirm/decline → clear detail_context
  │    ├── Branch: altro → update conversational memory
  │    ├── Topic change detection → reset context
  │    ├── Workflow context save/clear
  │    └── Fallback recovery state save/clear
  │
  ├── [5] Response construction (api.py:600-611)
  │    └── result["response"] | error | default fallback
  │
  ├── [6] Chat logging (api.py:614-623)
  │    └── log_chat() → threading.Thread(daemon=True)
  │         └── INSERT INTO chat_log (ask, intent, tool, who, when, answer, ...)
  │              └── data_sources/postgresql_source.py::_engine
  │
  └── Output: [RasaResponse {text, recipient_id, custom}]
       └── custom: {execution_path, node_timings, total_execution_ms, intent, slots, suggestions}
```

---

### 8.3 `POST /webhooks/rest/webhook/stream` — Chat Streaming SSE

> **File**: `app/api.py:653-1004`

Stessa logica del webhook sincrono, ma con streaming Server-Sent Events:

```
POST /webhooks/rest/webhook/stream
  │
  ├── StreamingResponse(event_generator(), media_type="text/event-stream")
  │
  └── event_generator():
       ├── yield SSE "status" (connessione stabilita)
       ├── Session recovery (stessa logica webhook sincrono)
       ├── event_callback → Queue thread-safe
       ├── run_graph() in thread separato via loop.run_in_executor()
       │    └── _conversation_graph.run(event_callback=event_callback)
       ├── while True: poll queue → yield SSE events
       │    ├── "status": stato nodo corrente
       │    ├── "reasoning": ragionamento sistema
       │    ├── "node_timing": timing per nodo
       │    └── None: completamento
       ├── Session update (stessa logica webhook)
       ├── Chat logging
       └── yield SSE "final" (risposta completa)
```

**Formato evento SSE**:
```
event: <type>
data: {"type":"<type>","timestamp":<ms>,"message":"..."}
```

---

### 8.4 `POST /model/parse` — NLU Debug

> **File**: `app/api.py:1007-1069`

```
POST /model/parse
  ├── Input: RasaParseRequest {text, metadata}
  ├── _conversation_graph.router.classify(message, metadata)
  │    └── orchestrator/router.py::Router.classify()
  └── Output: {text, intent{name,confidence}, entities[], slots{}, needs_clarification}

Dipendenze: Solo Router (no tool execution, no LLM response generation)
```

---

### 8.5 `GET /status` — Status Dettagliato

> **File**: `app/api.py:1089-1123`

```
GET /status
  ├── agents.data.{piani_df, controlli_df, osa_mai_controllati_df}  → conteggi
  ├── configs.config_loader.get_config()  → current_year
  ├── configs.config.AppConfig.get_model_name()  → nome modello
  ├── configs.config.AppConfig.LLM_MODEL  → chiave modello
  ├── configs.config.AppConfig.LLM_BACKEND  → tipo backend
  └── llm.client.LLMClient().use_real_llm  → "real" o "stub"
```

---

### 8.6 `GET /config` — Info Configurazione

> **File**: `app/api.py:1126-1137`

```
GET /config
  └── configs.config_loader.get_config()
       ├── .get_current_year()
       └── .get_data_source_type()
```

---

### 8.7 `GET /conversations/{id}/tracker` — Rasa Compat Stub

> **File**: `app/api.py:1072-1086`

```
GET /conversations/{conversation_id}/tracker
  └── return stub JSON (Rasa compatibility, no real state)
```

---

### 8.8 Chat Log Analytics API

Tutti gli endpoint sotto `/api/chat-log/` e `/api/monitor/` seguono lo stesso pattern:

```
GET /api/chat-log/<endpoint>
  ├── _get_db_engine()
  │    └── data_sources/postgresql_source.py::PostgreSQLDataSource._engine
  ├── sqlalchemy.text(SQL_QUERY)
  └── engine.connect() → execute → fetchall → JSON response
```

| Endpoint | File:Linea | Descrizione | Dipendenze extra |
|----------|-----------|-------------|-----------------|
| `/api/chat-log/stats` | `:1153-1229` | Statistiche aggregate (N giorni) | — |
| `/api/chat-log/recent` | `:1232-1307` | Ultimi messaggi con paginazione | — |
| `/api/chat-log/by-asl` | `:1310-1359` | Raggruppamento per ASL | — |
| `/api/chat-log/by-intent` | `:1362-1411` | Raggruppamento per intent | — |
| `/api/chat-log/errors` | `:1414-1490` | Lista errori recenti | — |
| `/api/chat-log/timeline` | `:1493-1557` | Timeline per grafici | — |
| `/api/chat-log/quality` | `:1560-1588` | Analisi qualità conversazioni | `tools/conversation_monitor.py` |
| `/api/monitor/intelligent` | `:1595-1641` | Analisi intelligente completa | `tools/intelligent_monitor.py` |
| `/api/monitor/suggestions` | `:1644-1691` | Suggerimenti miglioramento | `tools/intelligent_monitor.py` |
| `/api/monitor/health` | `:1694-1738` | Health score 0-100 | `tools/intelligent_monitor.py` |

---

## 9. Flusso Runtime di una Richiesta Chat

### `ConversationGraph.run()`

> **File**: `orchestrator/graph.py:663-764`

```
run(message, metadata, detail_context, workflow_context, event_callback, dialogue_state)
  │
  ├── Costruzione initial_state (ConversationState)  → :691-726
  │    ├── message, metadata (con detail_context iniettato)
  │    ├── dialogue_state (da sessione precedente)
  │    ├── workflow_* (da sessione, legacy)
  │    ├── fallback_* (da metadata._fallback_*)
  │    └── execution_path=[], node_timings={}
  │
  ├── self.graph.invoke(initial_state)  → :728
  │    │
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  NODO 1: _classify_node()                        │
  │    │  │  → orchestrator/graph.py:197-307                  │
  │    │  │                                                    │
  │    │  │  [a] Check fallback_suggestions (selezione utente) │
  │    │  │      → _parse_user_selection()                     │
  │    │  │      → fallback_recovery.py                        │
  │    │  │                                                    │
  │    │  │  [b] Classificazione standard:                     │
  │    │  │      router.classify(message, metadata)            │
  │    │  │      └── Router.classify()                         │
  │    │  │           ├── [L1] Heuristics essenziali           │
  │    │  │           │    (confirm/decline, greet, goodbye,   │
  │    │  │           │     ask_help, ask_delayed_plans, ...)  │
  │    │  │           ├── [L2] Pre-parsing slot (regex)        │
  │    │  │           │    (piano_code, location, ...)         │
  │    │  │           ├── [L3] Cache MD5+TTL                   │
  │    │  │           │    └── intent_cache.py                 │
  │    │  │           └── [L4] LLM classification              │
  │    │  │                ├── Few-shot retrieval               │
  │    │  │                │    └── few_shot_retriever.py       │
  │    │  │                │         └── Qdrant "intent_examples"│
  │    │  │                ├── Prompt V2 con JSON output        │
  │    │  │                ├── LLMClient.query(json_mode=True)  │
  │    │  │                └── Parse JSON response              │
  │    │  │                     └── {intent, slots, confidence} │
  │    │  │                                                    │
  │    │  │  [c] Slot carry-forward (se stesso intent)         │
  │    │  │  [d] Update state: intent, slots, confidence       │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  NODO 2: _dialogue_manager_node()                │
  │    │  │  → orchestrator/graph.py:313-421                  │
  │    │  │                                                    │
  │    │  │  [a] Load/create DialogueState                     │
  │    │  │      └── dialogue_state.py                         │
  │    │  │  [b] Topic change detection                        │
  │    │  │      (reset DS se intent diverso da sessione)      │
  │    │  │  [c] Costruzione candidate list                    │
  │    │  │      [{intent, confidence, slots}]                 │
  │    │  │  [d] Calcolo raw_message_type                      │
  │    │  │      (oppure/refinement/vague/continuation/query)  │
  │    │  │  [e] dm_evaluate()                                 │
  │    │  │      └── dialogue_manager.py::evaluate()           │
  │    │  │           ├── Confidence thresholds (per modello)  │
  │    │  │           ├── Check SELF_SUFFICIENT_INTENTS         │
  │    │  │           ├── Check REQUIRED_SLOTS                  │
  │    │  │           └── → DialogueManagerResult               │
  │    │  │                {action, intent, slots, question,    │
  │    │  │                 target_tool, updated_state}         │
  │    │  │  [f] Update state: dm_action, dm_target_tool       │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  ROUTING: _dm_router()                            │
  │    │  │  → orchestrator/graph.py:423-437                   │
  │    │  │                                                    │
  │    │  │  dm_action == "ask_user"  → nodo ask_user          │
  │    │  │  dm_action == "execute"   → nodo dm_target_tool    │
  │    │  │  dm_action == "fallback"  → nodo fallback_tool     │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │    │  (branch A: ask_user)
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  NODO 3A: _ask_user_node()                       │
  │    │  │  → orchestrator/graph.py:443-469                   │
  │    │  │  state["final_response"] = dm_question             │
  │    │  │  → END                                             │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │    │  (branch B: tool execution)
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  NODO 3B: <tool_node> (uno dei 19 registrati)    │
  │    │  │  → orchestrator/tool_nodes.py                      │
  │    │  │                                                    │
  │    │  │  Esempio: piano_stabilimenti_tool()                │
  │    │  │  ├── Estrae slots dallo state                      │
  │    │  │  ├── Chiama tool function                          │
  │    │  │  │    └── tools/piano_tools.py::piano_tool()       │
  │    │  │  │         ├── agents/data_agent.py::DataRetriever │
  │    │  │  │         └── agents/response_agent.py::Formatter │
  │    │  │  ├── Two-phase check (se soglia superata)          │
  │    │  │  │    └── orchestrator/two_phase.py                │
  │    │  │  └── state["tool_output"] = {type, data}           │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │    │  (branch C: fallback)
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  NODO 3C: _fallback_tool()                       │
  │    │  │  → orchestrator/graph.py:518-598                   │
  │    │  │  ├── Slot mancanti → clarification message         │
  │    │  │  ├── Loop prevention (max 3 fallback consecutivi)  │
  │    │  │  └── FallbackRecoveryEngine.suggest_intents()      │
  │    │  │       └── fallback_recovery.py (3 fasi)            │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │    │  ┌──────────────────────────────────────────────────┐
  │    │  │  NODO 4: _response_generator_node()              │
  │    │  │  → orchestrator/graph.py:631-657                   │
  │    │  │  → orchestrator/response_node.py                   │
  │    │  │                                                    │
  │    │  │  [a] DIRECT_RESPONSE_INTENTS (greet, goodbye,     │
  │    │  │      fallback, confirm, decline):                  │
  │    │  │      → usa formatted_response direttamente         │
  │    │  │                                                    │
  │    │  │  [b] Tool con formatted_response:                  │
  │    │  │      → usa formatted_response (no LLM call)        │
  │    │  │                                                    │
  │    │  │  [c] Dati complessi senza formatted_response:      │
  │    │  │      → LLM response generation                     │
  │    │  │      ├── RESPONSE_SYSTEM_PROMPT                    │
  │    │  │      ├── RESPONSE_USER_TEMPLATE                    │
  │    │  │      └── LLMClient.query()                         │
  │    │  │                                                    │
  │    │  │  [d] FollowUpSuggestionEngine.suggest()            │
  │    │  │      └── followup_suggestions.py                   │
  │    │  │      → state["suggestions"] = [...]                │
  │    │  │                                                    │
  │    │  │  → state["final_response"] = testo finale          │
  │    │  │  → END                                             │
  │    │  └──────────────────────────────────────────────────┘
  │    │
  │
  └── Return dict con: response, intent, slots, execution_path,
      node_timings, total_execution_ms, dialogue_state,
      has_more_details, detail_context, workflow_*, fallback_*, ...
```

---

## 10. Session Management

### Architettura sessioni

> **File**: `app/api.py:39-47`

Le sessioni sono **in-memory** (dict Python), non persistite su DB.

```
_session_store: Dict[str, Dict] = {
    "sender_id_1": {
        "detail_context": {...},        # Two-phase: dettagli da mostrare
        "last_intent": "ask_...",       # Ultimo intent classificato
        "last_slots": {...},            # Ultimi slot estratti
        "conversation_summary": "...",  # Sommario testuale
        "timestamp": 1708123456.789,    # Timestamp ultimo aggiornamento
        "dialogue_state": {...},        # DialogueState (DST multi-turno)
        "last_response_context": "...", # Per risoluzione anaforica
        "workflow_context": {...},      # Workflow multi-step (legacy)
        "fallback_suggestions": [...],  # Suggerimenti fallback attivi
        "fallback_phase": 1,            # Fase fallback (1-3)
        "fallback_count": 0,            # Contatore fallback consecutivi
        "fallback_selected_category": null  # Categoria selezionata
    }
}
```

### Ciclo di vita sessione

```
Request N:
  1. Leggi sessione (con _session_lock)
  2. Verifica TTL (300s)
  3. Inject session context in metadata
  4. Valida workflow_context (WorkflowValidator)
  5. Esegui grafo
  6. Aggiorna sessione con risultato (con _session_lock)

Cleanup: ogni 100 richieste (_CLEANUP_EVERY_N_REQUESTS)
  → _cleanup_expired_sessions() rimuove sessioni > 2*TTL
```

### Topic change detection

> **File**: `app/api.py:534-549`

Se l'intent cambia tra turni (es. `ask_piano_description` → `ask_delayed_plans`), il sistema:
- Resetta `last_response_context` (evita risoluzione anaforica errata)
- Resetta `detail_context` (evita "vuoi dettagli?" di un turno precedente)

---

## 11. Mappa Completa Intent → Tool → Modulo

| Intent | Tool Node | Tool Function | Modulo Python | Required Slots |
|--------|-----------|--------------|---------------|----------------|
| `greet` | `greet_tool` | (inline) | `tool_nodes.py:54` | — |
| `goodbye` | `goodbye_tool` | (inline) | `tool_nodes.py:64` | — |
| `ask_help` | `help_tool` | (inline) | `tool_nodes.py:74` | — |
| `ask_piano_description` | `piano_description_tool` | `piano_tool(action="description")` | `tools/piano_tools.py` | `piano_code` |
| `ask_piano_stabilimenti` | `piano_stabilimenti_tool` | `piano_tool(action="stabilimenti")` | `tools/piano_tools.py` | `piano_code` |
| `ask_piano_statistics` | `piano_statistics_tool` | `get_piano_statistics()` | `tools/piano_tools.py` | — (opz. `piano_code`) |
| `search_piani_by_topic` | `search_piani_tool` | `search_tool()` | `tools/search_tools.py` | `topic` |
| `ask_priority_establishment` | `priority_establishment_tool` | `priority_tool()` | `tools/priority_tools.py` | — |
| `ask_risk_based_priority` | `risk_predictor_tool` | `risk_tool()` / `get_ml_risk_prediction()` | `tools/risk_tools.py` / `tools/predictor_tools.py` | — |
| `ask_suggest_controls` | `suggest_controls_tool` | `suggest_controls()` | `tools/priority_tools.py` | — |
| `ask_nearby_priority` | `nearby_priority_tool` | `get_nearby_priority()` | `tools/proximity_tools.py` | `location` |
| `ask_delayed_plans` | `delayed_plans_tool` | `priority_tool(asl, "delayed")` | `tools/priority_tools.py` | — |
| `check_if_plan_delayed` | `check_plan_delayed_tool` | `priority_tool(asl, "check", piano)` | `tools/priority_tools.py` | `piano_code` |
| `ask_establishment_history` | `establishment_history_tool` | `get_establishment_history()` | `tools/establishment_tools.py` | almeno 1 tra `num_registrazione`, `partita_iva`, `ragione_sociale` |
| `ask_top_risk_activities` | `top_risk_activities_tool` | `get_top_risk_activities()` | `tools/risk_analysis_tools.py` | — |
| `analyze_nc_by_category` | `analyze_nc_tool` | `analyze_nc_by_category()` | `tools/risk_tools.py` | `categoria` |
| `info_procedure` | `info_procedure_tool` | (RAG retrieve + LLM) | `tools/procedure_tools.py` | — |
| `confirm_show_details` | `confirm_details_tool` | (inline) | `tool_nodes.py:111` | — |
| `decline_show_details` | `decline_details_tool` | (inline) | `tool_nodes.py:144` | — |

### Catena tipo per un tool con dati (es. `ask_piano_stabilimenti`)

```
tool_nodes.py::piano_stabilimenti_tool()
  ├── state["slots"]["piano_code"]         ← estratto dal Router
  ├── piano_tool(action="stabilimenti", piano_code=...)
  │    └── tools/piano_tools.py
  │         ├── agents/data_agent.py::DataRetriever.get_piano_info()
  │         │    └── agents/data.py::piani_df  (DataFrame globale)
  │         ├── agents/data_agent.py::DataRetriever.get_controlli_by_piano()
  │         │    └── agents/data.py::controlli_df
  │         ├── agents/data_agent.py::BusinessLogic.correlate_piano_stabilimenti()
  │         └── agents/response_agent.py::ResponseFormatter.format_stabilimenti_analysis()
  ├── two_phase.py::apply_two_phase_check()
  │    └── Se > 3 stabilimenti → summary + "Vuoi vedere tutti i dettagli?"
  └── state["tool_output"] = {"type": "piano_stabilimenti", "data": result}
```

---

## 12. Diagramma Dipendenze Globale

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                             app/api.py                                       │
│  FastAPI + Uvicorn (porta 5005)                                              │
│                                                                              │
│  Endpoints:                                                                  │
│  ├── GET  /                          (health check)                          │
│  ├── POST /webhooks/rest/webhook     (chat sincrona)                         │
│  ├── POST /webhooks/rest/webhook/stream (chat SSE)                           │
│  ├── POST /model/parse               (NLU debug)                             │
│  ├── GET  /status                    (stato sistema)                         │
│  ├── GET  /config                    (info config)                           │
│  ├── GET  /conversations/{id}/tracker (Rasa compat stub)                     │
│  └── GET  /api/chat-log/*            (analytics)                             │
│      GET  /api/monitor/*             (intelligent monitor)                   │
└──────┬───────────────────────────┬───────────────────────────────────────────┘
       │                           │
       ▼                           ▼
┌──────────────────┐    ┌──────────────────────────────────────────────┐
│  configs/         │    │  orchestrator/graph.py                       │
│  ├── config.json  │    │  ConversationGraph (singleton)               │
│  ├── config.py    │◄───┤                                              │
│  └── config_loader│    │  ┌───────────┐  ┌─────────────────────┐     │
└──────────────────┘    │  │ Router     │  │ LLMClient           │     │
                        │  │ (classify) │  │ (query/stream/ping) │     │
                        │  └─────┬─────┘  └──────────┬──────────┘     │
                        │        │                     │                │
                        │        ▼                     ▼                │
                        │  ┌───────────┐  ┌──────────────────────┐    │
                        │  │few_shot_  │  │ llm/providers.py     │    │
                        │  │retriever  │  │ ├── OllamaProvider   │    │
                        │  │(Qdrant)   │  │ ├── LlamaCppProvider │    │
                        │  └───────────┘  │ ├── OpenAIProvider   │    │
                        │                  │ ├── AnthropicProvider│    │
                        │  StateGraph:     │ └── OpenAICompatProv.│    │
                        │  classify →      └──────────────────────┘    │
                        │  dialogue_mgr →                              │
                        │  <tool_node> →                               │
                        │  response_gen →                              │
                        │  END                                         │
                        └──────────────────────┬───────────────────────┘
                                               │
                          ┌────────────────────┼─────────────────────┐
                          │                    │                     │
                          ▼                    ▼                     ▼
                ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
                │ orchestrator/     │  │ tools/        │  │ agents/           │
                │ ├── router.py     │  │ ├── piano_    │  │ ├── data_agent.py │
                │ ├── dialogue_     │  │ ├── priority_ │  │ │   DataRetriever  │
                │ │   manager.py    │  │ ├── risk_     │  │ │   BusinessLogic  │
                │ ├── tool_nodes.py │  │ ├── search_   │  │ │   RiskAnalyzer   │
                │ ├── response_     │  │ ├── establ._  │  │ ├── response_      │
                │ │   node.py       │  │ ├── predictor_│  │ │   agent.py       │
                │ ├── two_phase.py  │  │ ├── proximty_ │  │ │   ResponseFmt    │
                │ ├── fallback_     │  │ ├── procedure_│  │ │   SuggestionGen  │
                │ │   recovery.py   │  │ ├── risk_an._ │  │ └── data.py        │
                │ ├── dialogue_     │  │ └── hybrid_   │  │     (DataFrame     │
                │ │   state.py      │  │     search/   │  │      globali)      │
                │ ├── followup_     │  └──────────────┘  └────────┬───────────┘
                │ │   suggestions   │                              │
                │ ├── intent_       │                              │
                │ │   metadata.py   │                              │
                │ ├── intent_cache  │                              │
                │ └── workflow_*    │                              │
                └──────────────────┘                              │
                                                                   ▼
                                                    ┌──────────────────────────┐
                                                    │ data_sources/             │
                                                    │ ├── factory.py (singleton)│
                                                    │ ├── postgresql_source.py  │
                                                    │ │   (SQLAlchemy + Pool)   │
                                                    │ └── csv_source.py         │
                                                    └────────────┬─────────────┘
                                                                 │
                                              ┌──────────────────┼───────────┐
                                              ▼                  ▼           ▼
                                        PostgreSQL          CSV files    Qdrant
                                        (gias_db)          (dataset.10/) (vector)
                                        porta 5432                      porta 6333
```

---

## 13. Glossario Quick-Reference

| Termine | Significato | File chiave |
|---------|------------|-------------|
| `ConversationGraph` | Singleton LangGraph, orchestratore principale | `orchestrator/graph.py:96` |
| `ConversationState` | TypedDict ~35 campi, stato del grafo | `orchestrator/graph.py:50` |
| `Router` | Classificatore intent ibrido (heuristics + LLM) | `orchestrator/router.py:21` |
| `DialogueManager` | Decisore rule-based (execute/ask_user/fallback) | `orchestrator/dialogue_manager.py` |
| `DialogueState` | Stato multi-turno (confirmed_intent, missing_slots) | `orchestrator/dialogue_state.py` |
| `TOOL_REGISTRY` | Dict nome_tool → funzione (19 entries) | `orchestrator/tool_nodes.py:576` |
| `INTENT_TO_TOOL` | Dict intent → nome_tool (19 entries) | `orchestrator/tool_nodes.py:599` |
| `LLMClient` | Facade LLM con Strategy Pattern multi-provider | `llm/client.py:14` |
| `LLMProvider` | ABC per provider backends (5 implementazioni) | `llm/provider_base.py` |
| `DataRetriever` | Accesso dati puro (DataFrame queries) | `agents/data_agent.py` |
| `BusinessLogic` | Aggregazioni, correlazioni, ranking | `agents/data_agent.py` |
| `ResponseFormatter` | Dati → testo italiano formattato | `agents/response_agent.py` |
| `TWO_PHASE_THRESHOLDS` | Soglie per risposta sommario + dettagli | `orchestrator/two_phase.py:11` |
| `FallbackRecoveryEngine` | Recovery 3 fasi (keyword → LLM → menu) | `orchestrator/fallback_recovery.py` |
| `FewShotRetriever` | Recupero esempi simili da Qdrant per prompt | `orchestrator/few_shot_retriever.py` |
| `WorkflowValidator` | Validazione sicurezza workflow context | `orchestrator/workflow_validator.py` |
| `_session_store` | Dict in-memory per sessioni utente (TTL 5min) | `app/api.py:39` |
| `_intent_metadata_cache` | Cache metadata intent da tabella DB `intents` | `app/api.py:53` |
| `GRAPH_INVOKE_TIMEOUT` | 50s timeout esecuzione grafo | `app/api.py:50` |
| `SESSION_TTL` | 300s (5 minuti) durata sessione | `app/api.py:43` |

---

## Note per la Navigazione VSCode

### Ricerca rapida per componente

| Cosa cerco | Comando VSCode (Ctrl+Shift+F) |
|-----------|-------------------------------|
| Dove un intent viene classificato | Cerca `"ask_piano_description"` in `orchestrator/` |
| Dove un tool viene eseguito | Cerca nome funzione (es. `piano_tool`) in `tools/` |
| Dove i dati vengono letti | Cerca `DataRetriever.get_` in `agents/data_agent.py` |
| Dove la risposta viene formattata | Cerca `ResponseFormatter.format_` in `agents/response_agent.py` |
| Dove un endpoint è definito | Cerca `@app.get` o `@app.post` in `app/api.py` |
| Config di un backend LLM | Cerca il nome backend in `configs/config.json` |

### Navigazione call stack tipica (F12 → Go to Definition)

```
api.py:webhook()
  → graph.py:ConversationGraph.run()
    → graph.py:_classify_node()
      → router.py:Router.classify()
    → graph.py:_dialogue_manager_node()
      → dialogue_manager.py:evaluate()
    → tool_nodes.py:<tool_function>()
      → tools/<tool_file>.py:<tool_impl>()
        → agents/data_agent.py:DataRetriever.<method>()
        → agents/response_agent.py:ResponseFormatter.<method>()
    → response_node.py:response_generator_node()
      → llm/client.py:LLMClient.query()  (solo se dati complessi)
```

### File da tenere aperti in split view

Per il debug di una richiesta chat, consiglio di tenere aperti in 3 tab:

1. **`app/api.py`** — Entry point, session management
2. **`orchestrator/graph.py`** — Flusso del grafo, nodi
3. **`orchestrator/tool_nodes.py`** — Mapping intent → tool execution

Per il debug della classificazione:

1. **`orchestrator/router.py`** — Heuristics + LLM classification
2. **`orchestrator/dialogue_manager.py`** — Decision engine
3. **`llm/client.py`** — LLM query/stub fallback
