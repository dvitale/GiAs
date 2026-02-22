# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GiAs-llm** is a LangGraph-based conversational AI system for veterinary monitoring in Regione Campania (Italy). It uses a pure LLM + LangGraph architecture with multi-model support (Almawave/Velvet, Mistral-Nemo, LLaMA 3.1) and an advanced hybrid search system combining vector similarity and LLM semantic reasoning.

**Domain**: ASL (Azienda Sanitaria Locale) operators query veterinary control plans, identify inspection priorities based on risk analysis and delayed schedules, and discover establishments requiring urgent checks.

## Architecture

### 3-Layer Separation

The system follows a strict architectural separation:

1. **Data Layer** (`agents/data_agent.py`):
   - `DataRetriever`: Pure CSV data access
   - `BusinessLogic`: Aggregations, correlations, statistical ranking
   - `RiskAnalyzer`: Risk scoring based on historical non-conformities (NC)
   - **No text generation, only returns DataFrames/dicts**

2. **Response Layer** (`agents/response_agent.py`):
   - `ResponseFormatter`: Structured data → formatted Italian text
   - `SuggestionGenerator`: Dynamic follow-up suggestions
   - **Template-based, no domain logic**

3. **Tool Layer** (`tools/`):
   - `piano_tools.py`: Plan descriptions, establishments, correlations
   - `priority_tools.py`: Priority establishments, delayed plans, control suggestions
   - `risk_tools.py`: Risk-based priority analysis
   - `risk_analysis_tools.py`: Top risk activities analysis
   - `search_tools.py`: Semantic search for plans (integrated with hybrid search system)
   - `establishment_tools.py`: Establishment history and controls
   - **NEW**: `hybrid_search/` - Advanced search orchestration system (v1.0.0)
   - **All decorated with `@tool`, accept explicit parameters, return serializable dicts**

### Orchestration Flow (LangGraph)

**Entry point**: `orchestrator/graph.py` → `ConversationGraph`

```
User Message
    ↓
[1] classify (Router: heuristics → pre-parsing → cache → LLM)
    ↓
[2] dialogue_manager (rule-based, decide azione)
    ↓ (conditional edges)
    ├── ask_user → END (chiede chiarimenti, attende prossimo turno)
    ├── fallback_tool → response_generator → END
    └── tool_node → response_generator → END
```

**State**: `ConversationState` (TypedDict, ~35 campi) tracks:
- `message`, `metadata` — input (metadata: `{asl, asl_id, user_id, codice_fiscale}`)
- `intent`, `slots`, `needs_clarification` — output del Router
- `_classification_confidence` — confidence reale dal router (0.0-1.0), usata dal dialogue manager al posto di valori hardcoded
- `tool_output` — risultato del tool node (dict con `type` e `data`)
- `final_response` — testo generato dal response node
- `dialogue_state` — `DialogueState` per tracking multi-turno
- `dm_action`, `dm_target_tool`, `dm_question` — output del dialogue manager
- `has_more_details`, `detail_context` — supporto two-phase (sommario + dettagli)
- `workflow_*`, `fallback_*` — stato legacy workflow/fallback (backwards compat)
- `error` — messaggi errore

**Confidence propagation** (`graph.py`):
- `_classify_node`: salva `classification.get("confidence", 0.70)` in `_classification_confidence`
- `_dialogue_manager_node`: usa confidence reale se disponibile, fallback a euristica (0.90/0.55/0.30) se assente
- Soglie dialogue manager in `dialogue_manager.py` (`_MODEL_CONFIDENCE_THRESHOLDS["ministral"]`): high=0.65, min=0.40

**Topic change detection** (`graph.py._dialogue_manager_node`):
- Se `_session_last_intent != intent` corrente, resetta `DialogueState` (slots, confirmed_intent, confirmed_strategy)
- Evita "memory bleed" quando l'utente cambia argomento tra turni

**Slot carry-forward** (`graph.py._classify_node`):
- Carry-forward da sessione solo se `_session_last_intent == intent` corrente (guardia anti-topic-change)

### Intent Classification

**Router** (`orchestrator/router.py`):
- Router ibrido LLM-first a 3 livelli: heuristics essenziali → pre-parsing slot → LLM con few-shot dinamico
- **Feature flag**: `MINIMAL_HEURISTICS = True` (default) delega la classificazione all'LLM; `False` riattiva tutte le heuristic legacy
- **Prompt V2**: output JSON con `reasoning`, `confidence` (0.0-1.0), intent raggruppati per categoria, regole di disambiguazione esplicite, ~20 esempi critici
- **Few-shot dinamico**: `FewShotRetriever` recupera 6 esempi simili da Qdrant (`intent_examples`, 384 dim) e li inietta nel prompt
- Returns JSON: `{reasoning, intent, slots, needs_clarification, confidence}`
- Validates against 20 valid intents
- **Confidence reale**: propagata dal router al dialogue manager via `_classification_confidence` nello state LangGraph
- Fallback on parsing errors
- Supports 3 LLM models with performance profiles

**Heuristics essenziali** (sempre attive, anche con `MINIMAL_HEURISTICS=True`):
- `confirm_show_details` / `decline_show_details` — pattern espliciti e brevi (con detail_context)
- Disambiguazione rischio: `mai_controllati`, `con_sanzioni` → `ask_risk_based_priority`
- `greet` (< 20 char), `goodbye` (< 30 char), `ask_help`
- `ask_delayed_plans` — "piani in ritardo" senza codice piano (disambigua da `check_if_plan_delayed`)
- `ask_nearby_priority` — pattern prossimita' geografica

**Valid Intents** (20):
- `greet`, `goodbye`, `ask_help`
- `ask_piano_description`, `ask_piano_stabilimenti`, `ask_piano_statistics`
- `search_piani_by_topic`
- `ask_priority_establishment` (based on delayed schedules)
- `ask_risk_based_priority` (based on historical NC data)
- `ask_suggest_controls`, `ask_delayed_plans`, `check_if_plan_delayed`
- `ask_establishment_history`, `ask_top_risk_activities`
- `analyze_nc_by_category`
- `info_procedure` (RAG su documentazione procedure operative)
- `ask_nearby_priority` (ricerca per prossimita' geografica con geocoding)
- `confirm_show_details`, `decline_show_details` (two-phase flow)
- `fallback`

**Required Slots**:
- `ask_piano_description`, `ask_piano_stabilimenti`, `check_if_plan_delayed`: `[piano_code]`
- `search_piani_by_topic`: `[topic]`
- `ask_establishment_history`: almeno uno tra `[num_registrazione, partita_iva, ragione_sociale]`
- `analyze_nc_by_category`: `[categoria]`
- `ask_nearby_priority`: `[location]` (obbligatorio), `[radius_km]` (opzionale, default 5)

**Slot fill location via LLM** (`_extract_location_with_llm`):
- Quando il sistema chiede "Dove ti trovi?" (LAYER 1 pending slot fill), l'estrazione usa una chiamata LLM dedicata (`temperature=0.0, max_tokens=150, json_mode=True, timeout=10s`)
- Output JSON: `{"address": "Via Colombo, Sant'Angelo a Cupolo"}` o `{"address": null}`
- Fallback automatico a regex (`_clean_location_from_message`) se LLM fallisce
- Impatto performance: +1 chiamata LLM solo nel percorso slot fill, non nel flusso normale

### Response Generation

**Prompt structure** (`_build_response_prompt`):
1. Explain results in clear Italian
2. **Motivate priorities** (WHY certain establishments/plans are critical)
3. Provide operational value (interpret data, suggest actions)
4. Propose 1-2 follow-up questions

Uses `formatted_response` from `ResponseFormatter` when available, falls back to raw data.

## Data Dependencies

**Expected CSV files** (referenced in `agents/data_agent.py`):
- `piani_df`: Control plans (columns: `alias`, `alias_indicatore`, `sezione`, `descrizione`, `descrizione-2`)
- `controlli_df`: 2025 executed controls (columns: `descrizione_piano`, `macroarea_cu`, `aggregazione_cu`, `attivita_cu`)
- `osa_mai_controllati_df`: Never-controlled establishments (columns: `asl`, `comune`, `indirizzo`, `macroarea`, `aggregazione`, `attivita`, `num_riconoscimento`)
- `ocse_df`: Historical non-conformities (columns: `macroarea_sottoposta_a_controllo`, `numero_nc_gravi`, `numero_nc_non_gravi`)
- `diff_prog_eseg_df`: Scheduled vs executed (columns: `descrizione_uoc`, `indicatore`, `programmati`, `eseguiti`)
- `personale.csv`: User organizational structure (columns: `user_id`, `asl`, `descrizione`, `descrizione_area_struttura_complessa`)

**Data Loading**:
- **Active Dataset**: `dataset.10/` (updated format, 323,146 records)
- **Import location**: `from ..data import <dataframe_name>`
- **Data Sources**: Configurable CSV/PostgreSQL via `config.json`
- **Vector Index**: Qdrant storage con 2 collection:
  - `piani_monitoraggio`: 730 vettori (384 dim) per ricerca semantica piani
  - `intent_examples`: ~150 vettori (384 dim) per few-shot intent classification
- **Qdrant Singleton** (`agents/qdrant_singleton.py`): Qdrant in local (file-based) mode acquisisce un lock esclusivo sulla directory. `get_qdrant_client()` fornisce una singola istanza `QdrantClient` condivisa tra `DataRetriever` e `FewShotRetriever`. Lazy-initialized, ritorna `None` se storage non disponibile.
- **Embedding Singleton** (`agents/embedding_singleton.py`): `get_embedding_model()` fornisce un'istanza condivisa del modello sentence-transformers per evitare caricamento multiplo in memoria.
- **Rebuild index**: `python tools/indexing/build_intent_examples_index.py` (ricostruire quando cambiano intent o esempi)

## Key Concepts

**ASL**: Azienda Sanitaria Locale (Local Health Authority)
**UOC/UOS**: Unità Operative (Organizational units within ASL)
**Piano**: Alphanumeric control plan code (e.g., A1, A32, B2)
**OSA**: Operatore del Settore Alimentare (Food Business Operator / establishment)
**NC**: Non Conformità (Non-conformity: grave=severe, non grave=minor)
**Risk Score (Statistical)**: `P(NC) × Impatto × 100` where P(NC) = (total NC) / (controls), Impatto = (severe NC) / (controls)
**ML Score**: XGBoost predicted probability of NC (0.0-1.0), threshold: HIGH > 0.70, MEDIUM > 0.40

## Architecture Notes

- **Tool functions**: Pure functions with explicit parameters (no side effects)
- **Intent classification**: LLM-based (Router) with hybrid heuristics
- **Response generation**: LLM-based (response_generator_node) with template fallback
- **State management**: LangGraph `ConversationState` (TypedDict)

**Agent files**: Business logic is in `agents/data_agent.py` and `agents/response_agent.py`.

## LLM Client

**Implementation**: `llm/client.py` contiene `LLMClient` con Strategy Pattern per delegare a provider backends.

**Architettura Provider** (`llm/`):
- `provider_base.py`: ABC con interfaccia `query()`, `query_stream()`, `ping()`
- `providers.py`: 5 implementazioni (Ollama, LlamaCpp, OpenAI, Anthropic, OpenAICompat)
- `client.py`: Facade pubblica invariata, delega internamente al provider selezionato
- `client_stub.py`: Stub per testing (pattern matching rule-based)

**Backend supportati** (`config.json` -> `llm_backend.type`):
- `ollama`: Ollama locale (API nativa `/api/chat`)
- `llamacpp`: llama.cpp locale (OpenAI-compatible `/v1/chat/completions`)
- `openai`: OpenAI API via SDK (GPT-4o, GPT-4o-mini). Richiede `pip install openai`
- `anthropic`: Anthropic API via SDK (Claude). Richiede `pip install anthropic`
- `openai_compat`: Endpoint generico OpenAI-compatible (Mistral, Groq, Together, etc.). Zero dipendenze aggiuntive

**Switching backend**: `GIAS_LLM_BACKEND` env var > `config.json` type > default. API key via env var (mai in config.json).

**GDPR gate**: Per provider esterni, `gdpr.allow_external_llm` in `config.json` deve essere `true`. Default: `false` (hard block).

**Modelli locali**:
- **Default**: Almawave/Velvet:latest (14B, GDPR-compliant)
- **Alternative**: mistral-nemo:latest, llama3.1:8b, llama3.2:3b, ministral-3:3b
- **Performance**: Velvet: 4.2s avg (7.2GB VRAM), LLaMA 3.2: 0.8s avg (2GB VRAM)
- **Temperature**: Classification: 0.1, Response Generation: 0.3
- **Keep-Alive**: Configurabile via `OLLAMA_KEEP_ALIVE` (-1 = persistent)

**Variabili ambiente provider esterni**:
- `OPENAI_API_KEY`: per backend `openai`
- `ANTHROPIC_API_KEY`: per backend `anthropic`
- `MISTRAL_API_KEY` / `GIAS_LLM_API_KEY`: per backend `openai_compat`

## File Organization

```
GiAs-llm/
├── agents/                     # Core agent implementations
│   ├── data_agent.py          # DataRetriever, BusinessLogic, RiskAnalyzer
│   ├── response_agent.py      # ResponseFormatter, SuggestionGenerator
│   ├── cached_data_agent.py   # Caching layer
│   ├── qdrant_singleton.py    # Singleton QdrantClient condiviso (evita file-lock conflict)
│   ├── embedding_singleton.py # Singleton sentence-transformers embedding model
│   ├── data.py                # Data loading utilities
│   └── utils.py               # Shared utilities
├── app/                        # FastAPI server (unchanged)
│   ├── main.py                # Entry point stub
│   ├── api.py                 # FastAPI server (API V1 nativa)
│   ├── session_manager.py     # SessionManager centralizzato (thread-safe)
│   └── models.py              # Modelli Pydantic API (ChatMessage, ChatResult, ParseResult, etc.)
├── orchestrator/               # LangGraph workflow
│   ├── graph.py                # ConversationGraph, _build_graph(), entry point run()
│   ├── graph_legacy.py         # Backup vecchio grafo lineare (pre-refactoring)
│   ├── router.py               # Router ibrido LLM-first 3-livelli, MINIMAL_HEURISTICS, prompt V2
│   ├── few_shot_retriever.py   # FewShotRetriever singleton - recupero esempi Qdrant per classificazione
│   ├── dialogue_manager.py     # Decision engine rule-based (nessuna chiamata LLM)
│   ├── dialogue_state.py       # DialogueState TypedDict per tracking multi-turno
│   ├── tool_nodes.py           # Tool node functions, TOOL_REGISTRY, INTENT_TO_TOOL
│   ├── response_node.py        # Response generator, DIRECT_RESPONSE_INTENTS
│   ├── two_phase.py            # Logica sommario + "vuoi dettagli?"
│   ├── followup_suggestions.py # Suggerimenti follow-up contestuali post-risposta
│   ├── intent_metadata.py      # INTENT_REGISTRY con keywords, examples per intent
│   ├── intent_cache.py         # Cache MD5+TTL per classificazioni
│   ├── fallback_recovery.py    # Recovery 3 fasi (keyword → LLM → menu categorie)
│   ├── workflow_strategies.py  # Strategie multi-turno, FILTER_PATTERNS, VALID_COMUNI
│   └── workflow_validator.py   # Validazione sicurezza workflow
├── tools/                      # Tool implementations (unchanged)
│   ├── piano_tools.py          # @tool decorators for plan queries
│   ├── priority_tools.py       # @tool for priority/delayed plans
│   ├── risk_tools.py           # @tool for statistical risk analysis
│   ├── predictor_tools.py      # @tool for ML risk prediction
│   ├── risk_analysis_tools.py  # @tool for top risk activities
│   ├── establishment_tools.py  # @tool for establishment history
│   ├── search_tools.py         # @tool for hybrid semantic search
│   ├── procedure_tools.py      # @tool RAG per procedure operative (retrieve + LLM)
│   ├── proximity_tools.py      # @tool per ricerca stabilimenti per prossimità
│   ├── geo_utils.py            # Geocoding service (Nominatim + SimpleRequestsAdapter)
│   ├── hybrid_search/          # Advanced search system (v1.0.0)
│   │   ├── hybrid_engine.py    # Main search orchestrator
│   │   ├── smart_router.py     # Strategy selection (vector/LLM/hybrid)
│   │   ├── query_analyzer.py   # Query complexity analysis
│   │   ├── llm_reranker.py     # LLM-powered result reranking
│   │   ├── performance_tracker.py # Performance monitoring
│   │   └── config_manager.py   # Dynamic configuration management
│   └── indexing/
│       ├── build_qdrant_index.py  # Indexing piani monitoraggio
│       ├── build_intent_examples_index.py  # Indexing esempi intent per few-shot retrieval
│       ├── build_docs_index.py    # Indexing documenti procedure (RAG)
│       └── doc_chunker.py         # Chunker documenti (PDF/DOCX/TXT)
├── llm/                        # LLM client con Strategy Pattern multi-provider
│   ├── client.py              # LLMClient facade (delega a provider)
│   ├── provider_base.py       # ABC per provider backends
│   ├── providers.py           # Implementazioni: Ollama, LlamaCpp, OpenAI, Anthropic, OpenAICompat
│   └── client_stub.py         # Fallback implementation (pattern matching)
├── predictor_ml/               # ML predictor (unchanged)
│   ├── predictor.py           # MLRiskPredictor class (XGBoost)
│   ├── production_assets/     # Trained model and data
│   │   ├── risk_model_v4.json # XGBoost model weights
│   │   └── training_data_v4.parquet # Training dataset
│   └── mappings/
│       └── taxonomy_map.json  # Activity taxonomy mappings
├── data_sources/               # Data source abstraction layer
│   ├── csv_source.py          # CSV data source implementation
│   ├── postgresql_source.py   # PostgreSQL support (production)
│   └── factory.py             # Data source factory pattern
├── configs/                    # Configuration files
│   ├── config.py              # Enhanced multi-model configuration
│   ├── config.json            # Data source and hybrid search configuration
│   └── config_loader.py       # Configuration factory
├── models/                     # Model management
│   └── model_manager.py       # LLM model management utilities
├── data/                       # Data storage
│   ├── dataset.10/            # Active dataset (CSV files)
│   ├── dataset.2025/          # 2025 dataset
│   └── qdrant_storage/        # Vector database storage (3.3 MB)
├── runtime/                    # Runtime files
│   └── logs/                  # Application logs
├── tests/                      # Test suite v4.0 (pytest.ini in tests/)
│   ├── pytest.ini             # Config: testpaths = e2e integration unit (esclude legacy)
│   ├── conftest.py            # Fixture condivise (server_url, asl, session, http_client)
│   ├── run_all_tests.py       # Test runner script con report HTML/JSON
│   ├── unit/                  # Unit test con mock, no server richiesto
│   │   ├── test_greeting_recognition.py  # Pattern greeting/goodbye
│   │   └── test_llm_providers.py         # Test provider system multi-backend
│   ├── integration/           # Test con componenti reali, no server running
│   │   ├── test_ml_predictor_real.py     # ML predictor XGBoost
│   │   ├── test_rag_consistency.py       # Consistenza RAG/vector search
│   │   ├── test_router_real.py           # Router con LLM reale
│   │   ├── test_search_real.py           # Hybrid search reale
│   │   └── test_tools_real.py            # Tool con dati reali
│   ├── e2e/                   # End-to-end, richiedono server :5005 attivo
│   │   ├── test_api_endpoints.py         # Endpoint API
│   │   ├── test_api_webhook.py           # Chat V1 endpoint
│   │   ├── test_fallback.py              # Fallback recovery
│   │   ├── test_intents.py               # Copertura 20/20 intent
│   │   ├── test_metadata.py              # Metadata utente
│   │   ├── test_sessions.py              # Gestione sessioni
│   │   ├── test_streaming.py             # SSE streaming
│   │   └── test_two_phase.py             # Two-phase flow
│   └── legacy/                # Test vecchi, esclusi da pytest.ini
│       ├── test_graph.py, test_router.py, test_tools.py, ...
│       └── (12 file legacy mantenuti per riferimento)
├── scripts/                    # Shell scripts + utility Python scripts
│   ├── start_server.sh        # Server startup script
│   ├── stop_server.sh         # Server stop script
│   ├── server.sh              # Server management script
│   └── *.py                   # Utility scripts
├── benchmarks/                 # Benchmark scripts
│   └── *.py                   # Performance benchmarking
├── debug/                      # Debug scripts
│   └── *.py                   # Debugging utilities
├── docs/                       # Documentation
│   ├── CLAUDE.md              # This file
│   ├── README.md              # Project overview
│   └── INSTALLATION.md        # Setup instructions
├── sql/                        # SQL files
│   └── *.sql                  # Database scripts
├── artifacts/                  # Build artifacts
│   └── predictor.tar.gz       # Predictor package
├── requirements.txt            # Python dependencies
├── README.md                   # Symlink to docs/README.md
├── start_server.sh             # Symlink to scripts/start_server.sh
└── stop_server.sh              # Symlink to scripts/stop_server.sh
```

## Common Patterns

### Adding a New Tool

1. Create function in appropriate `tools/*.py` file
2. Decorate with `@tool("tool_name")`
3. Accept explicit parameters (no tracker/dispatcher)
4. Call `DataRetriever`/`BusinessLogic`/`RiskAnalyzer` methods
5. Use `ResponseFormatter` for Italian text
6. Return serializable dict with `formatted_response` key
7. Add tool node in `graph.py` → `_build_graph()`
8. Add intent to `Router.VALID_INTENTS`
9. Add conditional edge in graph

### Adding a New Intent

1. Aggiungere l'intent a `VALID_INTENTS` in `orchestrator/router.py`
2. Aggiungere metadata in `INTENT_REGISTRY` in `orchestrator/intent_metadata.py` (keywords, examples, required_slots)
3. Creare il tool function in `tools/` e registrarlo in `orchestrator/tool_nodes.py` (`TOOL_REGISTRY` + `INTENT_TO_TOOL`)
4. Se richiede slot, aggiungere a `REQUIRED_SLOTS` in `orchestrator/router.py`
5. Aggiornare le domande di esempio in `help_tool()` in `orchestrator/tool_nodes.py`
6. Se e' un intent a risposta diretta (senza LLM), aggiungere a `DIRECT_RESPONSE_INTENTS` in `orchestrator/response_node.py`
7. Aggiungere mapping suggerimenti follow-up in `orchestrator/followup_suggestions.py` (metodo `_suggest_<intent>` + entry in dispatch dict)
8. Aggiungere esempi al prompt V2 in `CLASSIFICATION_SYSTEM_PROMPT` (router.py) e/o alle disambiguation pairs in `build_intent_examples_index.py`
9. Ricostruire indice few-shot: `python tools/indexing/build_intent_examples_index.py`

### Working with Data

**Always use**:
- `DataRetriever.get_*()` for data access
- `BusinessLogic.*()` for aggregations/correlations
- `RiskAnalyzer.*()` for risk scoring
- `ResponseFormatter.format_*()` for Italian text output

**Never**:
- Access CSVs directly in tools
- Mix data logic with text formatting
- Import data modules outside the 3-layer separation

## Hybrid Search System (v1.0.0)

**Status**: ✅ **OPERATIONAL** (Completed 2026-01-09)

The system implements intelligent query routing between three search strategies:

### Search Strategies

1. **Vector-Only**: Fast exact matching for simple queries and plan codes
   - Use case: `piano A1`, `bovini`, simple keywords
   - Latency: 15-30ms
   - Data source: Qdrant vector database (730 vectors, 384 dimensions)

2. **LLM-Only**: Full semantic reasoning for complex queries
   - Use case: `"quali piani riguardano il benessere animale e la sicurezza?"`
   - Provides contextual understanding and query expansion

3. **Hybrid**: Vector retrieval + LLM reranking for optimal precision/recall
   - Use case: `"piani correlati alla sicurezza alimentare"`
   - Combines speed of vector search with LLM semantic precision

### Smart Routing Rules (Priority-based)

1. **exact_code_queries** (Priority 10): `query_type == "exact_code"` → `vector_only`
2. **high_load_fallback** (Priority 9): `system_load >= 0.8` → `vector_only`
3. **high_complexity_semantic** (Priority 8): `complexity_score >= 0.7` → `llm_only`
4. **simple_keywords** (Priority 6): `complexity_score <= 0.3` → `vector_only`
5. **default_hybrid** (Priority 5): Default fallback → `hybrid`

### Components

- **QueryAnalyzer**: Classifies query complexity and type
- **SmartRouter**: Selects optimal strategy based on routing rules
- **HybridEngine**: Orchestrates search execution with fallback mechanisms
- **LLMReranker**: Improves result precision using LLM semantic understanding
- **PerformanceTracker**: Monitors strategy performance in real-time
- **ConfigManager**: Dynamic configuration updates without restart

### Integration

The hybrid system is fully integrated with existing tools:
- `search_tools.py`: Main interface with `search_piani_by_topic()` function
- `DataRetriever`: Vector candidate retrieval
- `ResponseFormatter`: Consistent Italian response formatting
- `LLMClient`: Multi-model semantic processing

## Data Source Architecture

**Enhanced Configuration System** with factory pattern:

- **CSV Source**: Primary data source (323,146 records from dataset.10/)
- **PostgreSQL Source**: Ready for production migration
- **Configuration**: `config.json` with data source selection
- **Factory Pattern**: `data_sources/factory.py` for source abstraction

## Configuration Management

**Multiple Configuration Layers**:

1. **Environment Variables**: `GIAS_LLM_MODEL`, `GIAS_RISK_PREDICTOR`, `OLLAMA_KEEP_ALIVE`
2. **config.py**: Core application settings, model profiles, and `RiskPredictorConfig`
3. **config.json**: Data sources, hybrid search, and risk predictor configuration
4. **config_loader.py**: Configuration factory with fallback defaults

### Risk Predictor Configuration

The system supports two risk prediction strategies for the `ask_risk_based_priority` intent:

| Predictor | Description | Output |
|-----------|-------------|--------|
| **ml** | XGBoost model trained on historical NC data (2016-2025) | Individual score per establishment (0.0-1.0), predicted NC counts |
| **statistical** | Rule-based: `Risk Score = P(NC) × Impatto × 100` | Risk score by activity type (regional aggregation) |

**Configuration Methods** (priority order):

1. **Environment Variable**:
   ```bash
   export GIAS_RISK_PREDICTOR=ml        # or "statistical"
   ```

2. **config.json**:
   ```json
   {
     "risk_predictor": {
       "type": "ml",
       "options": ["ml", "statistical"]
     }
   }
   ```

3. **Default**: `ml`

**Implementation**:
- `config.py`: `RiskPredictorConfig` class with `get_predictor_type()`, `is_ml_predictor()`, `is_statistical_predictor()`
- `orchestrator/graph.py`: `_risk_predictor_tool()` node dynamically selects predictor
- `tools/risk_tools.py`: Statistical predictor (`risk_tool()` → `get_risk_based_priority()`)
- `tools/predictor_tools.py`: ML predictor (`get_ml_risk_prediction()`)

**Comparison**:

| Aspect | Statistical | ML |
|--------|-------------|-----|
| Granularity | Activity type (regional) | Individual establishment |
| Features | NC history by macroarea/aggregazione | 6 features (type, normativa, ASL, age, category) |
| High-risk output | ~5,800 establishments | ~20 establishments (more selective) |
| Interpretability | Simple formula | Feature importance + SHAP values |
| Use case | Broad category prioritization | Targeted inspection planning |

## Testing Infrastructure

**Test Suite v4.0** - struttura a 4 directory con `pytest.ini` in `tests/`:

### Struttura
- **`unit/`**: Test con mock, nessun server richiesto (2 file)
- **`integration/`**: Test con componenti reali, no server running (5 file)
- **`e2e/`**: End-to-end, richiedono server :5005 attivo (8 file)
- **`legacy/`**: Test vecchi esclusi da `pytest.ini` (12 file, mantenuti per riferimento)

### Configurazione (`tests/pytest.ini`)
- `testpaths = e2e integration unit` (legacy escluso via `norecursedirs`)
- Markers: `e2e`, `integration`, `unit`, `slow`, `streaming`, `rag`
- Timeout default: 120s
- Report: JUnit XML + HTML (`tests/reports/`)

### Copertura Intent
- **20/20 intent testati** (100%) in `e2e/test_intents.py`
- Heuristics test per pattern essenziali + confidence validation

### Comandi
```bash
python -m pytest tests/ -v                  # Tutti (e2e + integration + unit)
python -m pytest tests/unit/ -v             # Solo unit
python -m pytest tests/e2e/ -v              # Solo e2e (richiede server)
python -m pytest tests/integration/ -v      # Solo integration
python -m pytest tests/legacy/ -v           # Solo legacy (esclusi per default)
```

## Production Deployment

**FastAPI Server** (Port 5005):
- API V1 nativa per integrazione GChat
- `start_server.sh` for production deployment
- Health checks and monitoring endpoints
- Graceful fallback mechanisms for system resilience

## Geocoding Service

**Implementation**: `tools/geo_utils.py`

Il sistema usa Nominatim (OpenStreetMap) per geocodificare indirizzi in coordinate geografiche, utilizzato dall'intent `ask_nearby_priority`.

### Configurazione

- **Servizio**: Nominatim (gratuito, richiede rispetto ToS)
- **Rate Limiter**: 1 richiesta/secondo (obbligatorio per ToS)
- **Cache**: LRU con 500 entries
- **Fallback**: Coordinate hardcoded per capoluoghi campani

### Fix SSL Context (geopy 2.4+)

**Problema**: geopy 2.4.x usa un `ssl_context` personalizzato che causa errore HTTP 509 con il CDN Varnish di Nominatim (TLS fingerprinting).

**Soluzione**: `SimpleRequestsAdapter` - adapter custom che non usa ssl_context:

```python
class SimpleRequestsAdapter(BaseSyncAdapter):
    """Adapter senza ssl_context custom per evitare 509."""
    def __init__(self, *, proxies, ssl_context, **kwargs):
        super().__init__(proxies=proxies, ssl_context=None)
        self.session = requests.Session()
        # Usa HTTPAdapter standard senza ssl_context
        adapter = HTTPAdapter(max_retries=2)
        self.session.mount('https://', adapter)
```

### Strategia City-First (geocodifica)

La geocodifica usa una strategia "city-first" a 2 livelli:

1. **Capoluoghi** (coordinate hardcoded): Napoli, Salerno, Caserta, Avellino, Benevento → usa coordinate pre-definite come centro, poi cerca la via con viewbox
2. **Comuni generici**: per indirizzi tipo "Via X, Comune Y", splitta sulla virgola, geocodifica prima il comune via Nominatim, poi cerca la via con viewbox centrato sul comune. Se la via non si trova, usa il centro del comune come fallback con warning

Questo risolve la geocodifica per comuni piccoli (Sant'Angelo a Cupolo, Montesarchio, etc.) che prima fallivano con la ricerca Nominatim generica.

**Attenzione apostrofi**: i nomi di comuni con apostrofo (Sant'Angelo, Sant'Agata, etc.) sono gestiti correttamente nel parsing del warning di fallback (`proximity_tools.py`)

## Follow-up Suggestions

**Implementation**: `orchestrator/followup_suggestions.py` + `orchestrator/response_node.py`

I suggerimenti di follow-up vengono generati contestualmente e passati al frontend come **array strutturato** (non più come markdown nel testo).

### Formato Suggerimenti

```python
# Backend genera:
state["suggestions"] = [
    {"text": "Tutti i piani in ritardo", "query": "piani in ritardo"},
    {"text": "Stabilimenti prioritari", "query": "stabilimenti prioritari"}
]

# API passa nel custom payload:
{"suggestions": [...]}

# Frontend renderizza come link cliccabili
```

### Comportamento UI

- **Click normale**: popola il campo input con la query
- **Ctrl+Click**: invia direttamente la domanda

## Terminology

When writing prompts or responses, use correct Italian veterinary terms:
- **Piano di controllo** (not "control plan")
- **Stabilimento** (not "establishment" in Italian text)
- **Controllo ufficiale** (official inspection)
- **Non conformità** (non-conformity)
- **Programmazione** (scheduling)
- **Ritardo** (delay)
- **Rischio storico** (historical risk)

## Current System Status

**Production Ready** ✅:
- Multi-model LLM support with performance profiles
- Hybrid search system with intelligent routing
- Vector database with 730 indexed plans + collection `intent_examples` per few-shot retrieval
- 20-intent classification LLM-first con confidence reale e few-shot dinamico
- **NLU migliorato**: prompt V2 con disambiguazione, `MINIMAL_HEURISTICS=True`, `FewShotRetriever` Qdrant
- Test suite v4.0: unit/integration/e2e/legacy (100% intent coverage)
- FastAPI deployment con API V1 nativa
- 323,146 veterinary records processed
- **Configurable risk predictor** (ML or statistical) via `GIAS_RISK_PREDICTOR`

**Last Updated**: February 2026 (LLM multi-provider, singleton Qdrant/embedding, test suite v4.0, CORS proxy chat-log)

## Regole di manutenzione

Questo file e' la **fonte di verita' unica** per i dettagli architetturali del backend. Vedere le regole complete in `../../CLAUDE.md` (sezione "Regole di manutenzione documentazione").

Quando modifichi il backend, aggiorna questo file se tocchi:
- `VALID_INTENTS` o `REQUIRED_SLOTS` → aggiornare sezione "Intent Classification"
- `TOOL_REGISTRY` o `INTENT_TO_TOOL` → aggiornare sezione "Common Patterns" e file tree
- File in `orchestrator/` → aggiornare file tree
- Nuovo intent → aggiungere mapping suggerimenti in `followup_suggestions.py` + ricostruire indice few-shot
- Flusso del grafo (`_build_graph`) → aggiornare sezione "Orchestration Flow"
- `ConversationState` → aggiornare sezione "State"
- Configurazione risk predictor → aggiornare sezione "Risk Predictor Configuration"
- `CLASSIFICATION_SYSTEM_PROMPT` o heuristics essenziali → aggiornare sezione "Intent Classification"
- `MINIMAL_HEURISTICS` flag → aggiornare sezione "Intent Classification"
