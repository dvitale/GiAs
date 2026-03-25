# CLAUDE.md

## Project Overview

**GiAs-llm**: LangGraph conversational AI per monitoraggio veterinario in Regione Campania. LLM multi-model + hybrid search (Qdrant vector + LLM semantic reasoning).

**Dominio**: Operatori ASL interrogano piani di controllo, priorita' ispezioni (rischio + ritardi), stabilimenti da controllare.

## Architecture

### 3-Layer Separation

1. **Data Layer** (`agents/data_agent.py`): `DataRetriever` (CSV access), `BusinessLogic` (aggregazioni), `RiskAnalyzer` (risk scoring). No text generation, solo DataFrames/dicts.
2. **Response Layer** (`agents/response_agent.py`): `ResponseFormatter` (data → testo italiano), `SuggestionGenerator`. Template-based, no domain logic.
3. **Tool Layer** (`tools/`): Funzioni `@tool` con parametri espliciti, return serializable dict con `formatted_response` key. Include `hybrid_search/` per ricerca avanzata.

### Orchestration Flow (LangGraph)

**Entry point**: `orchestrator/graph.py` → `ConversationGraph`

```
User Message → [1] classify (Router) → [2] dialogue_manager (rule-based)
    ├── ask_user → END
    ├── fallback_tool → response_generator → END
    └── tool_node → response_generator → END
```

**ConversationState** (TypedDict, ~35 campi): `message`, `metadata` (asl, asl_id, user_id, codice_fiscale), `intent`, `slots`, `needs_clarification`, `_classification_confidence` (0.0-1.0), `tool_output`, `final_response`, `dialogue_state`, `dm_action`, `dm_target_tool`, `dm_question`, `has_more_details`, `detail_context`, `error`.

**Confidence**: router propaga confidence reale → dialogue manager. Soglie in `dialogue_manager.py` (`_MODEL_CONFIDENCE_THRESHOLDS`): high=0.65, min=0.40.

**Topic change**: se `_session_last_intent != intent`, resetta `DialogueState`. Slot carry-forward solo se stesso intent.

### Intent Classification

**Router** (`orchestrator/router.py`): LLM-first a 3 livelli (heuristics essenziali → pre-parsing slot → LLM con few-shot dinamico). `MINIMAL_HEURISTICS = True` (default). Output JSON: `{reasoning, intent, slots, needs_clarification, confidence}`.

**Valid Intents** (21): `greet`, `goodbye`, `ask_help`, `ask_piano_description`, `ask_piano_stabilimenti`, `ask_piano_statistics`, `search_piani_by_topic`, `ask_priority_establishment`, `ask_risk_based_priority`, `ask_suggest_controls`, `ask_delayed_plans`, `check_if_plan_delayed`, `ask_establishment_history`, `ask_top_risk_activities`, `analyze_nc_by_category`, `info_procedure`, `query_data`, `ask_nearby_priority`, `confirm_show_details`, `decline_show_details`, `fallback`

**Required Slots**:
- `ask_piano_description`, `ask_piano_stabilimenti`, `check_if_plan_delayed`: `[piano_code]`
- `search_piani_by_topic`: `[topic]`
- `ask_establishment_history`: almeno uno tra `[num_registrazione, partita_iva, ragione_sociale]`
- `analyze_nc_by_category`: `[categoria]`
- `ask_nearby_priority`: `[location]` (obbligatorio), `[radius_km]` (opzionale, default 5)
- `query_data`: nessun slot obbligatorio

### Response Generation

Prompt in `_build_response_prompt`: spiega risultati in italiano, motiva priorita', suggerisce azioni, propone follow-up. Usa `formatted_response` da `ResponseFormatter` quando disponibile.

## Data Dependencies

**CSV** (in `agents/data_agent.py`): `piani_df`, `controlli_df`, `osa_mai_controllati_df`, `ocse_df`, `diff_prog_eseg_df`, `personale.csv`. Dataset attivo: `dataset.10/`. Import: `from ..data import <df>`.

**Qdrant**: 2 collection — `piani_monitoraggio` (730 vettori, 384 dim), `intent_examples` (~150 vettori, 384 dim). Singleton in `agents/qdrant_singleton.py`. Rebuild: `python tools/indexing/build_intent_examples_index.py`.

## Key Concepts

- **ASL**: Azienda Sanitaria Locale — **UOC/UOS**: Unita' Operative
- **Piano**: Codice piano alfanumerico (A1, A32, B2) — **OSA**: Operatore del Settore Alimentare
- **NC**: Non Conformita' (grave/non grave)
- **Risk Score**: `P(NC) x Impatto x 100` — **ML Score**: XGBoost probability (0.0-1.0), HIGH > 0.70

## LLM Client

**Strategy Pattern** in `llm/`: `client.py` (facade) → `providers.py` (Ollama, LlamaCpp, OpenAI, Anthropic, OpenAICompat).

**Backend**: `GIAS_LLM_BACKEND` env > `config.json` `llm_backend.type` > default. GDPR: `gdpr.allow_external_llm` in config.json (default false).

**Env vars**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY` / `GIAS_LLM_API_KEY`. Temperature: classification 0.1, response 0.3.

## File Organization

```
agents/          # DataRetriever, ResponseFormatter, qdrant/embedding singletons
app/             # FastAPI: api.py, session_manager.py, models.py
orchestrator/    # graph.py, router.py, dialogue_manager.py, tool_nodes.py,
                 # response_node.py, two_phase.py, followup_suggestions.py,
                 # intent_metadata.py, schema_catalog.py, fallback_recovery.py,
                 # workflow_strategies.py, few_shot_retriever.py, intent_cache.py
tools/           # piano_, priority_, risk_, search_, establishment_, procedure_,
                 # query_builder_, proximity_tools.py, geo_utils.py, rag_cache.py
  hybrid_search/ # hybrid_engine, smart_router, query_analyzer, llm_reranker, bm25_scorer
  indexing/      # build_qdrant_index, build_intent_examples_index, build_docs_index
llm/             # client.py, provider_base.py, providers.py, client_stub.py
predictor_ml/    # MLRiskPredictor (XGBoost), production_assets/, mappings/
data_sources/    # csv_source, postgresql_source, factory (CSV/PostgreSQL abstraction)
configs/         # config.py, config.json, config_loader.py
tests/           # pytest.ini in tests/. Dir: unit/, integration/, e2e/, legacy/
```

## Common Patterns

### Adding a New Tool

1. Funzione in `tools/*.py` con `@tool("name")`, parametri espliciti
2. Chiama `DataRetriever`/`BusinessLogic`/`RiskAnalyzer`, usa `ResponseFormatter`
3. Return serializable dict con `formatted_response` key
4. Registra in `tool_nodes.py` (`TOOL_REGISTRY` + `INTENT_TO_TOOL`)
5. Aggiungi tool node e conditional edge in `graph.py`

### Adding a New Intent

1. `VALID_INTENTS` in `router.py` + `INTENT_REGISTRY` in `intent_metadata.py`
2. Tool in `tools/` → registra in `tool_nodes.py`
3. Se slot richiesti → `REQUIRED_SLOTS` in `router.py`
4. Domande esempio in `help_tool()` (`tool_nodes.py`)
5. Se risposta diretta → `DIRECT_RESPONSE_INTENTS` in `response_node.py`
6. Follow-up in `followup_suggestions.py`
7. Esempi nel prompt V2 (`CLASSIFICATION_SYSTEM_PROMPT`) e/o `build_intent_examples_index.py`
8. Rebuild indice: `python tools/indexing/build_intent_examples_index.py`
9. **Sync DB**: aggiornare tabella `intents` in PostgreSQL

### Working with Data

**Usa**: `DataRetriever.get_*()`, `BusinessLogic.*()`, `RiskAnalyzer.*()`, `ResponseFormatter.format_*()`

**Mai**: accesso diretto CSV nei tools, mix data logic con text formatting, import fuori dal 3-layer.

## RAG Pipeline (`procedure_tools.py`)

Intent `info_procedure`. Cache RAG (TTL 30min, max 200). Parent-child chunking (child 600 char per retrieval, parent 1800 char per contesto LLM). BM25+RRF re-ranking. Admin reindex: `POST /api/admin/documents/reindex`.

## Schema-Aware Query Data (`query_builder_tools.py`)

Intent `query_data`: interrogazioni ad-hoc su 7 tabelle. `SchemaCatalog` (singleton, DB-first) inietta metadati nel prompt. `QueryDescriptor` (Pydantic) + `SafeQueryExecutor` su DataFrame pandas.

**Sicurezza**: whitelist tabelle (7), operazioni (7: count, sum, mean, filter, group_count, top_n, distinct), operatori filtro (7), blacklist PII, limite 100 righe.

**Post-validation**: "piu' controllati" corretto deterministicamente a `query_data` in `_post_validate`.

## Risk Predictor

Due strategie per `ask_risk_based_priority`: **ml** (XGBoost, per stabilimento) o **statistical** (formula P(NC)xImpatto, per tipo attivita'). Config: `GIAS_RISK_PREDICTOR` env > `config.json` > default `ml`.

## Terminology

Nei prompt/risposte usare: **Piano di controllo**, **Stabilimento**, **Controllo ufficiale**, **Non conformita'**, **Programmazione**, **Ritardo**, **Rischio storico**.

## Comandi

```bash
# Server
scripts/server.sh start|stop|restart|status|logs|test
GIAS_LLM_MODEL=velvet scripts/server.sh start
GIAS_LLM_BACKEND=openai_compat MISTRAL_API_KEY=sk-xxx scripts/server.sh start

# Test (pytest.ini in tests/)
python -m pytest tests/ -v                    # Tutti
python -m pytest tests/unit/ -v               # Unit (mock, no server)
python -m pytest tests/e2e/ -v               # E2E (richiede server :5005)
python -m pytest tests/integration/ -v       # Integration (componenti reali, no server)
python -m pytest tests/e2e/test_intents.py::TestIntents::test_help -v  # Singolo

# API manuale
curl -X POST http://localhost:5005/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"piani in ritardo","metadata":{"asl":"AVELLINO"}}'
```

## Endpoint API (:5005)

| Endpoint | Metodo |
|----------|--------|
| `/` | GET (health) |
| `/status` | GET |
| `/api/v1/chat` | POST |
| `/api/v1/chat/stream` | POST (SSE) |
| `/api/v1/chat/feedback` | POST |
| `/api/v1/parse` | POST |
| `/api/chat-log/user-conversations` | GET |
| `/api/chat-log/conversation/{sid}` | GET |
| `/api/admin/documents/reindex` | POST |
| `/api/admin/documents/reindex/status` | GET |
| `/api/admin/schema-metadata` | GET |
| `/api/admin/schema-metadata/{key}` | GET/PUT |
| `/api/admin/schema-metadata/reload` | POST |

## Sincronizzazione tabella intents nel database

**REGOLA OBBLIGATORIA**: Ogni modifica a `VALID_INTENTS` in `router.py` → aggiornare tabella `intents` in PostgreSQL. Verificare: `SELECT COUNT(*) FROM intents;` == `len(VALID_INTENTS)`.

## Regole di manutenzione

Questo file e' la **fonte di verita' unica** per i dettagli architetturali del backend. Regole complete in `../CLAUDE.md`.

Aggiorna questo file quando tocchi:
- `VALID_INTENTS` o `REQUIRED_SLOTS` → sezione Intent Classification + sync DB
- `TOOL_REGISTRY` o `INTENT_TO_TOOL` → sezione Common Patterns
- Flusso del grafo (`_build_graph`) → sezione Orchestration Flow
- `ConversationState` → sezione State
- Nuovo endpoint API → tabella Endpoint API
- Nuovo intent → followup_suggestions + rebuild indice few-shot
- Nuovo requisito → `SDD/traceability.md` e `SDD/requirements/`
