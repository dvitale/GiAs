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

**Confidence**: router propaga confidence reale → dialogue manager. Soglie in `dialogue_manager.py` (`_MODEL_CONFIDENCE_THRESHOLDS`): high=0.80, min=0.50 (default), adattive per modello.

**Dialogue Manager** (`orchestrator/dialogue_manager.py`): rule engine con funzioni regola separate: `_rule_slot_continuation`, `_rule_oppure`, `_rule_refinement`, `_rule_strategy_confirmation`, `_rule_high_confidence_execute`, `_rule_ambiguous`. `evaluate()` le invoca in sequenza. Helper pubblici: `is_oppure()`, `is_refinement()`, `is_vague()`.

**Topic change**: se `_session_last_intent != intent`, resetta `DialogueState`. Slot carry-forward solo se stesso intent.

### Intent Registry (DB-driven)

**Singola fonte di verita'**: la tabella `intents` in PostgreSQL contiene tutti i metadati di ogni intent. L'`IntentMetadataService` (singleton, DB-first con fallback Python) li espone all'orchestratore.

**Metadati gestiti dal DB** (non piu' costanti Python sparse):

| Metadato | Colonna DB | Consumatore |
|----------|-----------|-------------|
| Lista intent validi | `intent` (PK) | Router.VALID_INTENTS |
| Slot obbligatori | `required_slots` (jsonb) | Router.REQUIRED_SLOTS, DialogueManager |
| Mapping intent→tool | `graph_node` | INTENT_TO_TOOL (tool_nodes.py) |
| Soglie two-phase | `two_phase_threshold` | TWO_PHASE_THRESHOLDS (two_phase.py) |
| Intent self-sufficient | `self_sufficient` (bool) | SELF_SUFFICIENT_INTENTS (dialogue_manager.py) |
| Risposta diretta | `is_direct_response` (bool) | DIRECT_RESPONSE_INTENTS (response_node.py) |
| Escluso da follow-up | `followup_excluded` (bool) | EXCLUDED_INTENTS (followup_suggestions.py) |
| Keywords/categoria | `keywords`, `category`, `emoji` | Fallback classifier, help, prompt |

Ogni modulo Python mantiene un fallback hardcoded per il boot senza DB, ma al primo utilizzo carica i valori dal servizio.

### Intent Classification

**Router** (`orchestrator/router.py`): LLM-first a 6 layer (gibberish detection → pending slot fill → heuristics → cache → LLM con few-shot dinamico → fallback locale). Metodo `classify()` orchestra i layer, con logica estratta in `_fill_pending_slots()`, `_llm_classify()`, `_build_session_context()`. Output JSON: `{reasoning, intent, slots, needs_clarification, confidence}`.

### Response Generation

Prompt in `_build_response_prompt`: spiega risultati in italiano, motiva priorita', suggerisce azioni, propone follow-up. Usa `formatted_response` da `ResponseFormatter` quando disponibile.

## Data Dependencies

**DataFrame** (in `agents/data_agent.py`): `piani_df`, `controlli_df` (da cu_eseguiti_nc, con NC inline), `osa_mai_controllati_df`, `diff_prog_eseg_df`, `personale_df`. Import: `from ..data import <df>`.

**`osa_mai_controllati`**: sincronizzata da mdgm (`chatbot.osa_mai_controllati`) con `scripts/sync_osa_mai_controllati.py`. Include `ragione_sociale` — usata come identificativo primario nelle risposte di `ask_risk_based_priority`, `ask_priority_establishment` e relative sintesi two-phase. Whitelist in `data_sources/base.py` (`KEEP_COLUMNS`).

**Qdrant**: 2 collection — `piani_monitoraggio` (730 vettori, 384 dim), `intent_examples` (~150 vettori, 384 dim). Singleton in `agents/qdrant_singleton.py`. Rebuild: `python tools/indexing/build_intent_examples_index.py`.

## Key Concepts

- **ASL**: Azienda Sanitaria Locale — **UOC/UOS**: Unita' Operative
- **Piano**: Codice piano alfanumerico (A1, A32, B2) — **OSA**: Operatore del Settore Alimentare
- **NC**: Non Conformita' (grave/non grave)
- **Risk Score**: `P(NC) x Impatto x 100` — **ML Score**: XGBoost probability (0.0-1.0), HIGH > 0.70

## LLM Client

**Strategy Pattern** in `llm/`: `client.py` (facade) → `providers.py` (Ollama, LlamaCpp, OpenAI, Anthropic, OpenAICompat). Fallback quando LLM non disponibile: `fallback_classifier.py` (classificazione data-driven con pattern→intent mapping).

**Backend**: `GIAS_LLM_BACKEND` env > `config.json` `llm_backend.type` > default. GDPR: `gdpr.allow_external_llm` in config.json (default false).

**Env vars**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY` / `GIAS_LLM_API_KEY`. Temperature: classification 0.1, response 0.3.

## File Organization

```
agents/          # DataRetriever, ResponseFormatter, qdrant/embedding singletons
app/             # FastAPI: api.py, session_manager.py, models.py
orchestrator/    # graph.py, router.py, dialogue_manager.py, tool_nodes.py,
                 # response_node.py, two_phase.py, followup_suggestions.py,
                 # intent_metadata_service.py (broker DB-first, singola fonte di verita'),
                 # intent_metadata.py (fallback Python), schema_catalog.py,
                 # fallback_recovery.py, workflow_strategies.py,
                 # few_shot_retriever.py, intent_cache.py,
                 # constants.py (SLOT_PROMPTS condivisi)
tools/           # piano_, priority_, risk_, search_, establishment_, procedure_,
                 # query_builder_, proximity_tools.py, geo_utils.py, rag_cache.py
  hybrid_search/ # hybrid_engine, smart_router, query_analyzer, llm_reranker, bm25_scorer
  indexing/      # build_qdrant_index, build_intent_examples_index, build_docs_index
llm/             # client.py, provider_base.py, providers.py, fallback_classifier.py
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
4. Registra in `tool_nodes.py` (`TOOL_REGISTRY`)
5. Aggiungi tool node e conditional edge in `graph.py`

### Adding a New Intent

La tabella `intents` in PostgreSQL e' la **singola fonte di verita'**. La procedura si riduce a 4 step obbligatori + 2 opzionali:

**Step obbligatori:**

1. **DB**: `INSERT INTO intents (...)` con tutti i metadati (vedi guida sotto)
2. **Tool**: funzione tool in `tools/*.py` → wrapper in `tool_nodes.py` → `TOOL_REGISTRY`
3. **Esempi**: `INSERT INTO intent_examples (...)` per classificazione few-shot
4. **Fallback**: pattern in `llm/fallback_classifier.py` (funzionamento senza LLM)

**Step opzionali (se applicabili):**

5. Se slot richiesti → `SLOT_PROMPTS` in `orchestrator/constants.py`
6. Follow-up contestuali → factory in `followup_suggestions.py`

**Non piu' necessario** toccare: `router.py` (VALID_INTENTS/REQUIRED_SLOTS), `dialogue_manager.py` (SELF_SUFFICIENT_INTENTS), `response_node.py` (DIRECT_RESPONSE_INTENTS), `two_phase.py` (TWO_PHASE_THRESHOLDS), `intent_metadata.py` (INTENT_REGISTRY). Tutti leggono dal DB via `IntentMetadataService`.

Rebuild indice dopo aggiunta esempi: `python tools/indexing/build_intent_examples_index.py`

### Working with Data

**Usa**: `DataRetriever.get_*()`, `BusinessLogic.*()`, `RiskAnalyzer.*()`, `ResponseFormatter.format_*()`

**Mai**: accesso diretto CSV nei tools, mix data logic con text formatting, import fuori dal 3-layer.

## RAG Pipeline (`procedure_tools.py`)

Intent `info_procedure`. Cache RAG (TTL 30min, max 200). Parent-child chunking (child 600 char per retrieval, parent 1800 char per contesto LLM). BM25+RRF re-ranking. Admin reindex: `POST /api/admin/documents/reindex`.

## Schema-Aware Query Data (`query_builder_tools.py`)

Intent `query_data`: interrogazioni ad-hoc su 6 tabelle. `SchemaCatalog` (singleton, DB-first) inietta metadati nel prompt. `QueryDescriptor` (Pydantic) + `SafeQueryExecutor` su DataFrame pandas.

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

## Intent Registry: tabella `intents`

La tabella `intents` e' la **singola fonte di verita'** per i metadati degli intent. L'`IntentMetadataService` (`orchestrator/intent_metadata_service.py`) la carica come singleton DB-first e la espone a tutti i consumatori.

**Colonne principali**:

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `intent` | varchar PK | Identificativo intent |
| `title` | varchar | Nome user-friendly |
| `category` | varchar | Categoria (Piano di Controllo, Priorita' e Rischio, ...) |
| `emoji` | varchar | Emoji per UI |
| `graph_node` | varchar | Nome funzione in tool_nodes.py (es. `delayed_plans_tool`) |
| `required_slots` | jsonb | Slot obbligatori (es. `["piano_code"]`) |
| `two_phase_threshold` | int | Soglia per risposta two-phase (null = disabilitato) |
| `self_sufficient` | bool | Non richiede slot per esecuzione |
| `is_direct_response` | bool | Risposta diretta senza passaggio LLM |
| `followup_excluded` | bool | Escluso dai suggerimenti follow-up |
| `keywords` | text[] | Keyword per fallback classifier |
| `section_number` | int | Ordine nel catalogo |

**INSERT template** per nuovo intent:

```sql
INSERT INTO intents (
    intent, section_number, title, category, emoji,
    graph_node, required_slots, two_phase_threshold,
    self_sufficient, is_direct_response, followup_excluded,
    keywords, context_keywords, negative_keywords
) VALUES (
    'nuovo_intent', 21, 'Titolo Intent', 'Categoria', '📋',
    'nuovo_intent_tool', '["slot1"]', 3,
    false, false, false,
    ARRAY['keyword1', 'keyword2'], ARRAY['ctx1'], ARRAY['neg1']
);
```

**Verifica**: `SELECT COUNT(*) FROM intents;` deve corrispondere al numero di intent attesi.

## Guida: aggiungere un nuovo intent

Esempio pratico: aggiunta di un ipotetico intent `ask_plan_coverage` (copertura territoriale di un piano).

### Step 1 — Registra nel DB

```sql
INSERT INTO intents (
    intent, section_number, title, category, emoji,
    graph_node, required_slots, two_phase_threshold,
    self_sufficient, is_direct_response, followup_excluded,
    keywords, context_keywords, negative_keywords
) VALUES (
    'ask_plan_coverage',
    21,                              -- progressivo (SELECT MAX(section_number)+1 FROM intents)
    'Copertura Territoriale Piano',
    'Piano di Controllo',
    '🗺️',
    'plan_coverage_tool',            -- nome della funzione wrapper in tool_nodes.py
    '["piano_code"]',                -- slot obbligatori (jsonb). [] se nessuno
    5,                               -- soglia two-phase (null = disabilitato)
    false,                           -- self_sufficient: true se non richiede slot
    false,                           -- is_direct_response: true se skip LLM (es. greet)
    false,                           -- followup_excluded: true per intent triviali
    ARRAY['copertura', 'territorio', 'comuni', 'zone'],
    ARRAY['piano', 'dove'],
    ARRAY['statistiche', 'rischio']
);

-- Esempi per classificazione few-shot
INSERT INTO intent_examples (intent, text, example_type, display_order) VALUES
    ('ask_plan_coverage', 'In quali comuni si applica il piano A1?', 'few_shot', 1),
    ('ask_plan_coverage', 'Copertura territoriale del piano B2', 'few_shot', 2),
    ('ask_plan_coverage', 'Dove si applica il piano A1?', 'help', 1);
```

### Step 2 — Scrivi il tool

**`tools/coverage_tools.py`** (logica di dominio):

```python
from agents.data_agent import DataRetriever
from agents.response_agent import ResponseFormatter

def get_plan_coverage(piano_code: str, asl: str = None) -> dict:
    controlli = DataRetriever.get_controlli_by_piano(piano_code)
    if controlli is None or controlli.empty:
        return {"formatted_response": f"Nessun dato trovato per il piano {piano_code}."}
    # ... logica di aggregazione per comune/zona ...
    return {"coverage": [...], "formatted_response": "..."}
```

**`orchestrator/tool_nodes.py`** (wrapper + registrazione):

```python
# Import
from tools.coverage_tools import get_plan_coverage

# Wrapper
def plan_coverage_tool(state, **_):
    piano_code = state["slots"].get("piano_code")
    asl = state["metadata"].get("asl")
    result = get_plan_coverage(piano_code=piano_code, asl=asl)
    # Two-phase (opzionale)
    if result.get("total_comuni", 0) > TWO_PHASE_THRESHOLDS.get("ask_plan_coverage", 5):
        result = apply_two_phase_check(state, "ask_plan_coverage", result, ...)
    state["tool_output"] = {"type": "plan_coverage", "data": result}
    return state

# Aggiungere a TOOL_REGISTRY:
TOOL_REGISTRY["plan_coverage_tool"] = plan_coverage_tool
```

### Step 3 — Fallback classifier

**`llm/fallback_classifier.py`** — aggiungere pattern per funzionamento senza LLM:

```python
# Nel dizionario _PATTERNS
"ask_plan_coverage": ["copertura", "territorio", "quali comuni", "zone del piano"],
```

### Step 4 (opzionale) — Slot prompt

Se l'intent ha slot obbligatori, aggiungere in **`orchestrator/constants.py`**:

```python
SLOT_PROMPTS["piano_code"] = "Quale piano? (es. A1, B2, C3)"  # gia' presente
```

### Step 5 (opzionale) — Follow-up contestuali

**`orchestrator/followup_suggestions.py`** — aggiungere factory:

```python
def _suggest_plan_coverage(intent, slots, data):
    piano = slots.get("piano_code", "")
    return [{"text": f"Statistiche piano {piano}", "query": f"statistiche piano {piano}"}]
```

### Step 6 — Rebuild e verifica

```bash
# Rebuild indice few-shot
python tools/indexing/build_intent_examples_index.py

# Verifica
python -m pytest tests/unit/ -v

# Test manuale
curl -X POST http://localhost:5005/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"copertura territoriale piano A1","metadata":{"asl":"NAPOLI"}}'
```

### Checklist riassuntiva

- [ ] `INSERT INTO intents` con tutti i campi
- [ ] `INSERT INTO intent_examples` (almeno 2-3 few_shot + 1 help)
- [ ] Funzione tool in `tools/*.py`
- [ ] Wrapper + `TOOL_REGISTRY` in `tool_nodes.py`
- [ ] Pattern in `llm/fallback_classifier.py`
- [ ] (se slot) `SLOT_PROMPTS` in `orchestrator/constants.py`
- [ ] (se follow-up) Factory in `followup_suggestions.py`
- [ ] Rebuild indice: `python tools/indexing/build_intent_examples_index.py`
- [ ] Test: `python -m pytest tests/unit/ -v`

## Regole di manutenzione

Questo file e' la **fonte di verita' unica** per i dettagli architetturali del backend. Regole complete in `../CLAUDE.md`.

Aggiorna questo file quando tocchi:
- `SLOT_PROMPTS` → `orchestrator/constants.py` (fonte unica, importato da graph.py e dialogue_manager.py)
- `TOOL_REGISTRY` → sezione Common Patterns
- Flusso del grafo (`_build_graph`) → sezione Orchestration Flow
- `ConversationState` → sezione State
- Nuovo endpoint API → tabella Endpoint API
- Nuovo intent → `INSERT INTO intents` + tool + esempi + fallback classifier
- Nuovo requisito → `SDD/traceability.md` e `SDD/requirements/`
