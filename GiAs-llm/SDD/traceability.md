# Matrice di Tracciabilita' — Backend (GiAs-llm)

**Generata**: 2026-03-16
**Requisiti totali**: 254
**Tracciati**: 252 | **Non tracciati**: 2

## Legenda

- TRACCIATO — requisito mappato a codice specifico
- NON TRACCIATO — requisito non associabile a codice specifico

## langgraph-pipeline

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| LG-001 | Struttura grafo con nodi, entry point classify, edge classify->dialogue_manager, conditional edges | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | TRACCIATO |
| LG-005 | Conditional edges: ask_user->END, fallback_tool->response_generator, tool->response_generator->END | `orchestrator/graph.py` | `ConversationGraph._ask_user_node()` | TRACCIATO |
| LG-008 | ConversationState tipizzato (TypedDict) con ~35 campi | `orchestrator/dialogue_state.py` | `ConversationState` | TRACCIATO |
| LG-009 | Execution path e node timings tracking in ms | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | TRACCIATO |
| LG-011 | SSE events: node_timing, status su classify, reasoning su intent | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | TRACCIATO |
| LG-014 | Menu shortcut (<=3 char) e fallback parsing da suggerimenti | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | TRACCIATO |
| LG-016 | Slot carry-forward con guardia anti-topic-change e reset DialogueState | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | TRACCIATO |
| LG-018 | Tool wrapper auto-inject event_callback e response context propagation | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | TRACCIATO |
| LG-020 | Fallback loop prevention (max 3), fallback a fasi, slot clarification con SLOT_PROMPTS | `orchestrator/graph.py` | `ConversationGraph._dialogue_manager_node()` | TRACCIATO |
| LG-025 | Caso speciale ask_establishment_history: slot OR logic | `orchestrator/graph.py` | `ConversationGraph._dialogue_manager_node()` | TRACCIATO |
| LG-026 | Total execution time (total_execution_ms) | `orchestrator/graph.py` | `ConversationGraph.run()` | TRACCIATO |
| LG-027 | Dialogue state passthrough input/output per multi-turno stateless | `orchestrator/graph.py` | `ConversationGraph.run()` | TRACCIATO |
| LG-NF-001 | Singleton grafo compilato, event cleanup, backwards compat campi workflow legacy | `orchestrator/graph.py` | `ConversationGraph.__init__()` | TRACCIATO |

## intent-classification

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| IC-001 | Pipeline classificazione a 6 livelli | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-002 | 20+1 valid intents | `orchestrator/router.py` | `Router.VALID_INTENTS` | TRACCIATO |
| IC-003 | Valid slot keys whitelist | `orchestrator/router.py` | `Router.VALID_SLOT_KEYS` | TRACCIATO |
| IC-004 | Required slots per intent | `orchestrator/router.py` | `Router.REQUIRED_SLOTS` | TRACCIATO |
| IC-005 | MINIMAL_HEURISTICS flag (default True) | `orchestrator/router.py` | `Router.MINIMAL_HEURISTICS` | TRACCIATO |
| IC-006 | Heuristic confirm_show_details: pattern espliciti e brevi | `orchestrator/router.py` | `Router._check_confirm_decline()` | TRACCIATO |
| IC-008 | Heuristic decline_show_details: pattern espliciti e brevi | `orchestrator/router.py` | `Router._check_confirm_decline()` | TRACCIATO |
| IC-010 | Disambiguazione rischio: mai controllati | `orchestrator/router.py` | `Router._check_risk_disambiguation()` | TRACCIATO |
| IC-011 | Disambiguazione rischio: con sanzioni | `orchestrator/router.py` | `Router._check_risk_disambiguation()` | TRACCIATO |
| IC-012 | Regex estrazione slot: piano_code, topic, location, radius_km, categoria NC, tipo_analisi_rischio | `orchestrator/router.py` | `Router._extract_slots()` | TRACCIATO |
| IC-013 | Regex estrazione identificativi stabilimento: num_ric, num_reg, p.iva, ragione_sociale | `orchestrator/router.py` | `Router._extract_slots()` | TRACCIATO |
| IC-021 | Cache intent con TTL 3600s, max 1000, normalizzazione MD5, bypass fallback | `orchestrator/intent_cache.py` | `IntentCache` | TRACCIATO |
| IC-025 | Cache context-aware con slot override e chiave ctx | `orchestrator/intent_cache.py` | `IntentCache.get()` | TRACCIATO |
| IC-027 | Few-shot retriever singleton, top_k=6, max 2/intent, threshold adattivo | `orchestrator/few_shot_retriever.py` | `FewShotRetriever.retrieve()` | TRACCIATO |
| IC-030 | Few-shot cache LRU, graceful degradation, condivisione risorse Qdrant/embedding | `orchestrator/few_shot_retriever.py` | `FewShotRetriever.retrieve()` | TRACCIATO |
| IC-033 | LLM classification prompt V2 semi-dinamico da IntentMetadataService | `orchestrator/router.py` | `Router._build_system_prompt()` | TRACCIATO |
| IC-034 | LLM confidence e alternatives (< 0.85) | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-035 | LLM session context injection | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-036 | LLM few-shot injection nel prompt | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-037 | LLM response parsing con chain di fallback JSON | `orchestrator/router.py` | `Router._parse_llm_response()` | TRACCIATO |
| IC-038 | Post-LLM validation: semantic correction, slot filtering, key filtering | `orchestrator/router.py` | `Router._post_validate()` | TRACCIATO |
| IC-042 | Gibberish detection con bypass per pending slots | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-044 | Pending slot fill con location LLM e topic change guard | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-046 | Local fallback per LLM-down (greet, goodbye, ask_help) | `orchestrator/router.py` | `Router._local_fallback()` | TRACCIATO |
| IC-047 | Confidence clamping 0.0-1.0, default 0.70 | `orchestrator/router.py` | `Router._validate_result()` | TRACCIATO |
| IC-048 | Multi-candidate output con max 2 alternative valide | `orchestrator/router.py` | `Router.classify()` | TRACCIATO |
| IC-052 | Slot normalizzazione (uppercase piano_code, asl, categoria) | `orchestrator/router.py` | `Router._validate_result()` | TRACCIATO |
| IC-053 | Self-sufficient intents senza slot obbligatori | `orchestrator/router.py` | `Router.REQUIRED_SLOTS` | TRACCIATO |
| IC-054 | analyze_nc_by_category default HACCP | `orchestrator/router.py` | `Router._validate_result()` | RIMOSSO |
| IC-055 | Router hot-reload (metadati, prompt, cache) | `orchestrator/router.py` | `Router.reload()` | TRACCIATO |
| IC-NF-001 | Performance cache ~0.001s, lazy loading thread-safe | `orchestrator/intent_cache.py` | `IntentCache` | TRACCIATO |
| IC-NF-004 | LLM location extraction timeout 10s, max_tokens 150 | `orchestrator/router.py` | `Router._extract_location_with_llm()` | TRACCIATO |

## dialogue-management

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| DM-001 | Soglie confidence adattive per modello LLM | `orchestrator/dialogue_manager.py` | `_MODEL_CONFIDENCE_THRESHOLDS` | TRACCIATO |
| DM-002 | Regole 0-1: slot continuation e intent chiaro con confidence alta | `orchestrator/dialogue_manager.py` | `DialogueManager.decide()` | TRACCIATO |
| DM-004 | Regole 1bis-3: proposta strategia, slot mancanti, ambiguita' con menu | `orchestrator/dialogue_manager.py` | `DialogueManager.decide()` | TRACCIATO |
| DM-007 | Regole 4-5: nessun candidato (fallback) e refinement | `orchestrator/dialogue_manager.py` | `DialogueManager.decide()` | TRACCIATO |
| DM-009 | Regole 6-7: conferma strategia e oppure cycling | `orchestrator/dialogue_manager.py` | `DialogueManager.decide()` | TRACCIATO |
| DM-012 | Default confidence media: esegui tool o chiedi slot | `orchestrator/dialogue_manager.py` | `DialogueManager.decide()` | TRACCIATO |
| DM-013 | DialogueState con TTL 300s e creazione vuota | `orchestrator/dialogue_state.py` | `DialogueState` | TRACCIATO |
| DM-015 | Slot merge (new override), filter extraction (comune, limit), turn count | `orchestrator/dialogue_manager.py` | `DialogueManager._merge_slots()` | TRACCIATO |
| DM-018 | DialogueState backwards compatibility (from_session, to_session) | `orchestrator/dialogue_state.py` | `DialogueState` | TRACCIATO |
| DM-022 | Multi-candidate menu max 3 opzioni con label/description | `orchestrator/dialogue_manager.py` | `DialogueManager._build_disambiguation_menu()` | TRACCIATO |
| DM-023 | Caso speciale ask_establishment_history: messaggio slot specifico | `orchestrator/dialogue_manager.py` | `DialogueManager._build_slot_question()` | TRACCIATO |
| DM-024 | Pattern detection: vago, oppure, refinement | `orchestrator/dialogue_manager.py` | `DialogueManager._is_vague()` | TRACCIATO |
| DM-NF-001 | Rule-based senza chiamate LLM | `orchestrator/dialogue_manager.py` | `DialogueManager` | TRACCIATO |
| DM-NF-002 | DialogueState serializzabile JSON | `orchestrator/dialogue_state.py` | `DialogueState` | TRACCIATO |

## tool-execution

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| TE-001 | TOOL_REGISTRY con 19 tool registrati | `orchestrator/tool_nodes.py` | `TOOL_REGISTRY` | TRACCIATO |
| TE-002 | INTENT_TO_TOOL mapping 20 intent -> tool | `orchestrator/tool_nodes.py` | `INTENT_TO_TOOL` | TRACCIATO |
| TE-003 | Tool conversazionali: greet, goodbye, help (con fallback hardcoded) | `orchestrator/tool_nodes.py` | `greet_tool()`, `goodbye_tool()`, `help_tool()` | TRACCIATO |
| TE-006 | Tool two-phase confirm/decline con sessione scaduta | `orchestrator/tool_nodes.py` | `confirm_details_tool()`, `decline_details_tool()` | TRACCIATO |
| TE-009 | piano_description_tool | `tools/piano_tools.py` | `get_piano_description()` | TRACCIATO |
| TE-010 | piano_stabilimenti_tool con two-phase | `tools/piano_tools.py` | `get_piano_stabilimenti()` | TRACCIATO |
| TE-011 | piano_statistics_tool: conteggio e statistiche aggregate | `tools/piano_tools.py` | `get_piano_statistics()` | TRACCIATO |
| TE-013 | search_piani_tool: hybrid search con fallback ILIKE | `tools/search_tools.py` | `search_piani_by_topic()` | TRACCIATO |
| TE-014 | search_piani_tool: risultati multipli con two-phase | `tools/search_tools.py` | `search_piani_by_topic()` | TRACCIATO |
| TE-015 | priority_establishment_tool: UOC/UOS auto-detection | `tools/priority_tools.py` | `get_priority_establishment()` | TRACCIATO |
| TE-016 | priority_establishment_tool: risultati multipli con two-phase | `tools/priority_tools.py` | `get_priority_establishment()` | TRACCIATO |
| TE-017 | risk_predictor_tool: disambiguazione, mai controllati, con sanzioni | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | TRACCIATO |
| TE-020 | suggest_controls_tool: risultati multipli con two-phase | `tools/priority_tools.py` | `suggest_controls()` | TRACCIATO |
| TE-021 | delayed_plans_tool: top 10 piani per ritardo decrescente | `tools/priority_tools.py` | `get_delayed_plans()` | TRACCIATO |
| TE-022 | check_plan_delayed_tool: verifica piano + matching sottopiani | `tools/priority_tools.py` | `check_plan_delayed()` | TRACCIATO |
| TE-023 | establishment_history_tool: risultati multipli con two-phase | `tools/establishment_tools.py` | `get_establishment_history()` | TRACCIATO |
| TE-024 | establishment_history_tool: multi-identifier + limite 50 | `tools/establishment_tools.py` | `get_establishment_history()` | TRACCIATO |
| TE-025 | top_risk_activities_tool: top N con soglie calibrate | `tools/risk_analysis_tools.py` | `get_top_risk_activities()` | TRACCIATO |
| TE-026 | analyze_nc_tool: NC per categoria con top 3 stabilimenti critici | `tools/risk_analysis_tools.py` | `analyze_nc_by_category()` | RIMOSSO |
| TE-027 | info_procedure_tool: RAG con contesto conversazionale | `tools/procedure_tools.py` | `get_procedure_info()` | TRACCIATO |
| TE-028 | nearby_priority_tool: geocodifica, verifica ASL, filtro prossimita' + rischio | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| TE-031 | nearby_priority_tool: risultati multipli con two-phase | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| TE-032 | nearby_priority_tool: centro citta' fallback con warning | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| TE-033 | predictor_tools: ML con fallback rule-based e normalizzazione score | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | TRACCIATO |
| TE-036 | risk_tools: analisi per piano e suggerimento categoria NC | `tools/risk_tools.py` | `risk_tool()` | TRACCIATO |
| TE-038 | SSE reasoning events per tool (piano, priority, risk, nearby) | `orchestrator/tool_nodes.py` | `_make_tool_wrapper()` | TRACCIATO |
| TE-039 | Tool unwrap LangChain @tool decorator (.func) | `orchestrator/tool_nodes.py` | `_unwrap_tool()` | TRACCIATO |
| TE-NF-001 | Standard output format, radius clamping 1-50km, limit clamping 1-100 | `orchestrator/tool_nodes.py` | `_make_tool_wrapper()` | TRACCIATO |

## session-management

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SM-001 | Sessioni in-memory con TTL 300s | `app/session_manager.py` | `SessionManager` | TRACCIATO |
| SM-002 | Thread-safety tramite lock (threading.Lock) | `app/session_manager.py` | `SessionManager` | TRACCIATO |
| SM-003 | Pulizia automatica sessioni scadute ogni 100 richieste | `app/session_manager.py` | `SessionManager._maybe_cleanup()` | TRACCIATO |
| SM-004 | Topic change detection con reset context | `app/session_manager.py` | `SessionManager.update_session()` | TRACCIATO |
| SM-005 | Propagazione stato conversazionale e metadata enrichment | `app/session_manager.py` | `SessionManager.update_session()` | TRACCIATO |
| SM-007 | Contesto detail, fallback recovery e workflow in sessione | `app/session_manager.py` | `SessionManager.update_session()` | TRACCIATO |
| SM-010 | Invalidazione selettiva workflow e reset completo sessione | `app/session_manager.py` | `SessionManager.invalidate_workflow()`, `clear_session()` | TRACCIATO |
| SM-012 | Contesto risposta per risoluzione anaforica | `app/session_manager.py` | `SessionManager.update_session()` | TRACCIATO |
| SM-013 | SessionContext come NamedTuple immutabile | `app/session_manager.py` | `SessionContext` | TRACCIATO |
| SM-NF-001 | Isolamento dati (.copy()) e logging [Session] | `app/session_manager.py` | `SessionManager.get_session()` | TRACCIATO |

## llm-client

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| LC-001 | Supporto 6 backend LLM (Ollama, llama.cpp, OpenAI, Anthropic, OpenAI-compat, OpenRouter) | `llm/client.py` | `LLMClient.__init__()` | TRACCIATO |
| LC-002 | Factory method per creazione provider basato su backend_type | `llm/client.py` | `LLMClient._create_provider()` | TRACCIATO |
| LC-003 | GDPR gate per provider esterni e degradazione in dev mode | `llm/client.py` | `LLMClient.__init__()` | TRACCIATO |
| LC-005 | Degradazione stub su ping fallito e fallback a runtime | `llm/client.py` | `LLMClient.__init__()`, `query()` | TRACCIATO |
| LC-007 | Query sincrona e streaming con temperature configurabile | `llm/client.py` | `LLMClient.query()`, `query_stream()` | TRACCIATO |
| LC-010 | Temperature differenziate: classificazione 0.1, risposta 0.3, RAG 0.3 | `llm/client.py` | `LLMClient.query()` | TRACCIATO |
| LC-011 | Interfaccia ABC LLMProvider con 4 metodi astratti | `llm/provider_base.py` | `LLMProvider` | TRACCIATO |
| LC-012 | API key esclusivamente da variabili ambiente (os.getenv) | `llm/providers.py` | Provider implementations | TRACCIATO |
| LC-013 | Adattamento provider-specifico: keep-alive, JSON mode, Anthropic system/prefill | `llm/providers.py` | Provider implementations | TRACCIATO |
| LC-014 | Health check ping() per ogni provider | `llm/providers.py` | Provider `ping()` methods | TRACCIATO |
| LC-NF-001 | Timeout configurabile, logging inizializzazione, zero SDK extra per OpenAI-compat | `llm/client.py` | `LLMClient.__init__()` | TRACCIATO |

## api-endpoints

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| API-01 | Chat sincrono POST /api/v1/chat | `app/api.py` | `chat_v1()` | TRACCIATO |
| API-02 | Chat streaming SSE POST /api/v1/chat/stream | `app/api.py` | `chat_stream_v1()` | TRACCIATO |
| API-03 | Parsing NLU POST /api/v1/parse | `app/api.py` | `parse_v1()` | TRACCIATO |
| API-04 | Feedback utente POST /api/v1/chat/feedback | `app/api.py` | `feedback_v1()` | TRACCIATO |
| API-05 | Feedback loop: background logging, rating auto-insert domande_risposte | `app/api.py` | `feedback_v1()` | TRACCIATO |
| API-08 | Reset sessione POST /api/v1/session/reset | `app/api.py` | `reset_session()` | TRACCIATO |
| API-09 | Health check GET / | `app/api.py` | `health_check()` | TRACCIATO |
| API-10 | Status dettagliato GET /status | `app/api.py` | `status()` | TRACCIATO |
| API-10 | Campi GPS in UserMetadata (latitude, longitude, gps_accuracy_m) | `app/models.py` | `UserMetadata` | TRACCIATO |
| API-11 | Configurazione GET /config | `app/api.py` | `get_config()` | TRACCIATO |
| API-12 | Chat log analytics: stats, recent, by-asl, by-intent | `app/api.py` | `chat_log_stats()` | TRACCIATO |
| API-16 | Chat log timeline: errors, timeline, user-conversations, conversation/{sid} | `app/api.py` | `chat_log_errors()` | TRACCIATO |
| API-20 | Qualita' conversazioni GET /api/chat-log/quality | `app/api.py` | `chat_log_quality()` | TRACCIATO |
| API-21 | Monitor intelligente GET /api/monitor/intelligent | `app/api.py` | `monitor_intelligent()` | TRACCIATO |
| API-22 | Monitor health score GET /api/monitor/health | `app/api.py` | `monitor_health()` | TRACCIATO |
| API-23 | Admin domande RAG CRUD | `app/api.py` | `admin_domande_rag()` | TRACCIATO |
| API-24 | Logging chat in background thread daemon | `app/api.py` | `_log_chat_async()` | TRACCIATO |
| API-25 | Modelli Pydantic tipizzati e guided learning fallback_intents | `app/models.py` | `ChatResult`, `FallbackIntentSuggestion` | TRACCIATO |
| API-27 | Admin schema metadata CRUD: GET/PUT/POST reload | `app/api.py` | `admin_schema_metadata()` | TRACCIATO |
| API-NF01 | CORS, singleton ConversationGraph, timeout 50s ThreadPoolExecutor | `app/api.py` | `app` setup | TRACCIATO |
| API-NF04 | Precaricamento startup, shutdown dispose, UOC/UOS da user_id | `app/api.py` | `lifespan()` | TRACCIATO |
| API-NF07 | Validazione workflow context | `app/api.py` | `chat_v1()` | TRACCIATO |
| API-NF08 | SSE headers anti-buffering | `app/api.py` | `chat_stream_v1()` | TRACCIATO |
| API-NF09 | Formato who "asl-user_id-codice_fiscale" per chat_log | `app/api.py` | `_log_chat_async()` | TRACCIATO |

## qdrant-embeddings

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| QE-01 | Singleton QdrantClient file-based con lazy init e fallback None | `agents/qdrant_singleton.py` | `get_qdrant_client()` | TRACCIATO |
| QE-04 | Singleton embedding model paraphrase-multilingual-MiniLM-L12-v2 con lazy loading | `agents/embedding_singleton.py` | `get_embedding_model()` | TRACCIATO |
| QE-NF01 | Condivisione istanze tra DataRetriever e FewShotRetriever | `agents/qdrant_singleton.py` | `get_qdrant_client()` | TRACCIATO |

## data-layer

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| DL-01 | Factory pattern singleton con connection pooling SQLAlchemy | `data_sources/factory.py` | `get_data_source()` | TRACCIATO |
| DL-02 | Intercambiabilita' CSV/PostgreSQL con stessa interfaccia DataSource | `data_sources/csv_source.py`, `postgresql_source.py` | `DataSource` | TRACCIATO |
| DL-04 | Connection pooling SQLAlchemy (pool_size=5, max_overflow=10) | `data_sources/postgresql_source.py` | `PostgreSQLDataSource._engine` | TRACCIATO |
| DL-05 | Cache DataFrame class-level con copie | `data_sources/postgresql_source.py` | `PostgreSQLDataSource._dataframe_cache` | TRACCIATO |
| DL-06 | Deduplicazione piani e attivita' da PostgreSQL | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.load_piani()` | TRACCIATO |
| DL-08 | Filtro personale per anno corrente e deduplicazione user_id | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.load_personale()` | TRACCIATO |
| DL-09 | Fallback psycopg2 se SQLAlchemy non disponibile | `data_sources/postgresql_source.py` | `PostgreSQLDataSource` | TRACCIATO |
| DL-10 | Precaricamento completo tramite preload_all_data() | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.preload_all_data()` | TRACCIATO |
| DL-11 | DataRetriever con metodi statici per recupero dati puro | `agents/data_agent.py` | `DataRetriever` | TRACCIATO |
| DL-12 | Pesi categorie NC (11 categorie, HACCP=1.0 a ETICHETTATURA=0.3) | `agents/data_agent.py` | `NC_CATEGORY_WEIGHTS` | TRACCIATO |
| DL-13 | get_piano_by_id fallback prefisso ATT per indicatori | `agents/data_agent.py` | `DataRetriever.get_piano_by_id()` | TRACCIATO |
| DL-14 | Distinzione piano/attivita' con prefix match e strip ATT in controlli | `agents/data_agent.py`, `orchestrator/router.py` | `DataRetriever.get_piano_by_id()`, `get_controlli_by_piano()`, `Router._extract_slots()` | TRACCIATO |
| DL-NF01 | low_memory=False, DataFrame vuoto su errore, clear_cache/dispose | `data_sources/csv_source.py` | `CSVDataSource` | TRACCIATO |

## response-generation

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| RG-001 | Bypass LLM per formatted_response e intent diretti | `orchestrator/response_node.py` | `response_generator_node()` | TRACCIATO |
| RG-003 | Generazione risposta LLM con system prompt, template, pulizia newline | `orchestrator/response_node.py` | `response_generator_node()` | TRACCIATO |
| RG-006 | Pulizia newline eccessive (max 2 consecutive) | `orchestrator/response_node.py` | `response_generator_node()` | TRACCIATO |
| RG-007 | Gestione errore generazione LLM | `orchestrator/response_node.py` | `response_generator_node()` | TRACCIATO |
| RG-008 | Evento SSE status "Generando risposta..." | `orchestrator/response_node.py` | `response_generator_node()` | TRACCIATO |
| RG-009 | Suggerimenti follow-up: esclusioni, max 3, formato text/query, 13 handler | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.generate()` | TRACCIATO |
| RG-013 | Suggerimenti contestuali per info_procedure da metadati chunk RAG | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine._suggest_info_procedure()` | TRACCIATO |
| RG-014 | Estrazione contesto risposta per risoluzione anaforica | `orchestrator/response_node.py` | `_extract_response_context()` | TRACCIATO |
| RG-015 | Formattazione markdown suggerimenti con header e link | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.format_suggestions()` | TRACCIATO |
| RG-NF-001 | Risparmio latenza ~800ms-1.5s con bypass LLM | `orchestrator/response_node.py` | `response_generator_node()` | TRACCIATO |
| RG-NF-002 | Singleton engine follow-up a livello di modulo | `orchestrator/followup_suggestions.py` | `_engine` | TRACCIATO |

## risk-analysis

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| RA-01 | Predittore ML XGBoost V4 con 6 feature e soglia 0.40 | `predictor_ml/predictor.py` | `MLRiskPredictor.predict()` | TRACCIATO |
| RA-03 | Predittore statistico rule-based: P(NC) x Impatto x 100 | `tools/risk_tools.py` | `risk_tool()` | TRACCIATO |
| RA-04 | Configurazione tipo predittore (env > config.json > default ml) | `configs/config.py` | `RiskPredictorConfig.get_predictor_type()` | TRACCIATO |
| RA-05 | Auto-degradazione ML -> rule-based e fallback su eccezione | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | TRACCIATO |
| RA-07 | Taxonomy map con fallback hardcoded | `predictor_ml/predictor.py` | `MLRiskPredictor._load_taxonomy()` | TRACCIATO |
| RA-08 | Top risk activities con soglie calibrate P90/P75/P50 | `tools/risk_analysis_tools.py` | `get_top_risk_activities()` | TRACCIATO |
| RA-09 | Analisi NC per categoria con top 5 stabilimenti critici | `tools/risk_analysis_tools.py` | `analyze_nc_by_category()` | RIMOSSO |
| RA-10 | Stabilimenti con piu' sanzioni con gravita' visiva | `tools/risk_analysis_tools.py` | `get_establishments_with_sanctions()` | TRACCIATO |
| RA-NF01 | Normalizzazione ASL bidirezionale (7 ASL campane) | `predictor_ml/predictor.py` | `MLRiskPredictor._normalize_asl_*()` | TRACCIATO |
| RA-NF02 | Spiegazioni interpretabili euristiche (explain=True) | `predictor_ml/predictor.py` | `MLRiskPredictor._generate_explanation()` | TRACCIATO |

## configuration

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| CF-01 | Priorita' risoluzione: env > config.json > default hardcoded | `configs/config.py` | `AppConfig` | TRACCIATO |
| CF-02 | Sei modelli locali preconfigurati (falcon, velvet, mistral-nemo, llama3.1, llama3.2, ministral) | `configs/config.py` | `ModelConfig.AVAILABLE_MODELS` | TRACCIATO |
| CF-03 | Sei backend LLM supportati | `configs/config.py` | `LLMBackendConfig` | TRACCIATO |
| CF-04 | API key solo da variabili ambiente (mai in config.json) | `configs/config.py` | `LLMBackendConfig` | TRACCIATO |
| CF-07 | Configurazione sottosistemi: hybrid search, data source, RAG | `configs/config.json` | (config file) | TRACCIATO |
| CF-10 | Config loader singleton con fallback | `configs/config_loader.py` | `get_config()` | TRACCIATO |
| CF-NF01 | Configurazione fallback_recovery, guided_learning, streaming | `configs/config.json` | (config file) | TRACCIATO |
| CF-NF04 | Cambio modello a runtime tramite set_model() | `configs/config.py` | `set_model()` | TRACCIATO |

## two-phase-response

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| TP-001 | Attivazione two-phase per soglia con suffisso e detail_context | `orchestrator/two_phase.py` | `check_two_phase()` | TRACCIATO |
| TP-004 | Detail context con full_formatted_response | `orchestrator/two_phase.py` | `check_two_phase()` | TRACCIATO |
| TP-005 | Risposta conferma, rifiuto e sessione scaduta | `orchestrator/tool_nodes.py` | `confirm_details_tool()` | TRACCIATO |
| TP-008 | Non-attivazione sotto soglia | `orchestrator/two_phase.py` | `check_two_phase()` | TRACCIATO |
| TP-NF-001 | Modifica in-place senza copie | `orchestrator/two_phase.py` | `check_two_phase()` | TRACCIATO |

## workflow-strategies

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| WS-01 | Strategie multi-turno per ask_suggest_controls (3 strategie) | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | TRACCIATO |
| WS-02 | Strategie multi-turno per ask_priority_establishment (2 strategie) | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | TRACCIATO |
| WS-03 | Strategie multi-turno per ask_risk_based_priority (2 strategie) | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | TRACCIATO |
| WS-04 | STRATEGY_TO_INTENT_MAP allowlist | `orchestrator/workflow_strategies.py` | `STRATEGY_TO_INTENT_MAP` | TRACCIATO |
| WS-05 | Validazione nonce crittografico e workflow context (TTL, whitelist, stage) | `orchestrator/workflow_validator.py` | `WorkflowValidator.validate_workflow_context()` | TRACCIATO |
| WS-07 | Validazione filtri whitelist (comune, ASL, limit, UOC, piano_code, date, categoria) | `orchestrator/workflow_strategies.py` | `validate_filter()` | TRACCIATO |
| WS-08 | Validazione strategy_id per workflow_type | `orchestrator/workflow_validator.py` | `WorkflowValidator.validate_strategy_id()` | TRACCIATO |
| WS-NF01 | Set CONVERSATIONAL_INTENTS (6 intent) e is_conversational_intent() | `orchestrator/workflow_strategies.py` | `CONVERSATIONAL_INTENTS` | TRACCIATO |
| WS-NF02 | Pattern estrazione filtri regex e trust boundary workflow_context | `orchestrator/workflow_strategies.py` | `FILTER_PATTERNS` | TRACCIATO |

## hybrid-search

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| HS-01 | Tre modalita' di ricerca: VECTOR_ONLY, HYBRID, LLM_ONLY | `tools/hybrid_search/hybrid_engine.py` | `HybridSearchEngine` | TRACCIATO |
| HS-02 | Smart routing rules con priorita': cpu_mode, exact_code, complexity, load | `tools/hybrid_search/smart_router.py` | `SmartRouter.select_strategy()` | TRACCIATO |
| HS-07 | Analisi complessita' query: complexity_score, query_type, domain_terms | `tools/hybrid_search/query_analyzer.py` | `QueryAnalyzer.analyze()` | TRACCIATO |
| HS-08 | LLM reranker con timeout, fallback prompt semplificato, fallback vector order | `tools/hybrid_search/llm_reranker.py` | `LLMReranker.rerank()` | TRACCIATO |
| HS-10 | Validazione alias piani nei risultati (filtro allucinazioni LLM) | `tools/hybrid_search/hybrid_engine.py` | `HybridSearchEngine._validate_results()` | TRACCIATO |
| HS-NF01 | Performance tracker e emergency fallback keyword | `tools/hybrid_search/performance_tracker.py` | `PerformanceTracker` | TRACCIATO |
| HS-NF03 | Deduplicazione risultati e JSON parsing robusto | `tools/hybrid_search/hybrid_engine.py` | `HybridSearchEngine._deduplicate()` | TRACCIATO |

## rag-pipeline

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| RAG-001 | Threshold e complessita' dinamici (4 livelli: low/medium/high/very_high) | `tools/procedure_tools.py` | `_compute_dynamic_threshold()` | TRACCIATO |
| RAG-004 | Query expansion LLM con contesto conversazionale e fallback | `tools/procedure_tools.py` | `_expand_query()` | TRACCIATO |
| RAG-007 | Retrieval multi-variante con deduplicazione chunk (80/100 char) | `tools/procedure_tools.py` | `get_procedure_info()` | TRACCIATO |
| RAG-008 | BM25 + RRF re-ranking (BM25Okapi con fallback TF, k=60) | `tools/hybrid_search/bm25_scorer.py` | `BM25Scorer`, `rrf_combine()` | TRACCIATO |
| RAG-011 | Post-filtering adattivo per complessita' | `tools/procedure_tools.py` | `get_procedure_info()` | TRACCIATO |
| RAG-012 | Limite massimo 5 chunk per contesto LLM | `tools/procedure_tools.py` | `get_procedure_info()` | TRACCIATO |
| RAG-014 | Citazioni inline [Fonte N] e sezione fonti/documenti scaricabili | `tools/procedure_tools.py` | `_build_rag_context()` | TRACCIATO |
| RAG-016 | Cache RAG singleton thread-safe con TTL, eviction 80%, statistiche | `tools/rag_cache.py` | `RAGCache` | TRACCIATO |
| RAG-019 | Fallback chunk grezzi, messaggio no_results, confidenza avg_score | `tools/procedure_tools.py` | `get_procedure_info()` | TRACCIATO |
| RAG-022 | Metadati chunk per suggerimenti dinamici follow-up | `tools/procedure_tools.py` | `get_procedure_info()` | TRACCIATO |
| RAG-NF-001 | Tokenizzazione BM25 semplificata (lowercase, regex >=2 char) | `tools/hybrid_search/bm25_scorer.py` | `BM25Scorer._tokenize()` | TRACCIATO |
| RAG-NF-002 | Performance BM25 on-the-fly < 1ms | `tools/hybrid_search/bm25_scorer.py` | `BM25Scorer` | NON TRACCIATO |
| RAG-NF-003 | RAG System Prompt con regole fondamentali | `tools/procedure_tools.py` | `RAG_SYSTEM_PROMPT` | TRACCIATO |
| RAG-NF-004 | Configurabilita' cache da config.json (ttl, max_size) | `tools/rag_cache.py` | `RAGCache.__init__()` | TRACCIATO |

## fallback-recovery

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| FR-001 | Engine a 3 fasi: keyword, LLM semantic, menu categorizzato | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine` | TRACCIATO |
| FR-002 | Fase 1: keyword matching con scoring ponderato, esclusioni e cache | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._keyword_matching()` | TRACCIATO |
| FR-005 | Fase 2: LLM Semantic Scoring | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._llm_scoring()` | PARZIALE |
| FR-006 | Timeout Fase LLM (post-hoc check) | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._llm_scoring()` | PARZIALE |
| FR-007 | Merge suggerimenti keyword + LLM | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.recover()` | TRACCIATO |
| FR-008 | Parsing selezione utente e formattazione suggerimenti | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.parse_selection()` | TRACCIATO |
| FR-010 | Limite 4 suggerimenti e menu 2 livelli con categorie | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._format_suggestions()` | TRACCIATO |
| FR-013 | INTENT_REGISTRY con gerarchia categoriale e validazione | `orchestrator/intent_metadata.py` | `INTENT_REGISTRY`, `CATEGORY_HIERARCHY` | TRACCIATO |
| FR-NF-001 | Latenza target ~50ms Fase 1 keyword | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._keyword_matching()` | NON TRACCIATO |
| FR-NF-002 | Configurabilita' engine (enabled, thresholds, limits) | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.__init__()` | TRACCIATO |

## geocoding-proximity

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| GP-01 | Geocodifica Nominatim con user-agent e timeout 10s | `tools/geo_utils.py` | `GeocodingService.geocode()` | TRACCIATO |
| GP-02 | SimpleRequestsAdapter fix SSL (bypass ssl_context) | `tools/geo_utils.py` | `SimpleRequestsAdapter` | TRACCIATO |
| GP-03 | Strategia city-first: capoluoghi hardcoded, comuni generici, fallback centro citta' | `tools/geo_utils.py` | `GeocodingService.geocode()` | TRACCIATO |
| GP-06 | Cache LRU 500 e rate limiting 1 req/s Nominatim | `tools/geo_utils.py` | `GeocodingService` | TRACCIATO |
| GP-08 | Validazione territorio ASL (mapping 7 ASL -> province) | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| GP-09 | Coordinate da database (latitudine_stab, longitudine_stab) | `tools/proximity_tools.py` | `filter_by_proximity()` | TRACCIATO |
| GP-10 | Limite batch geocodifica max 100 righe | `tools/proximity_tools.py` | `filter_by_proximity()` | TRACCIATO |
| GP-11 | Ordinamento distanza crescente + rischio decrescente | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| GP-12 | Clamping raggio (default 5.0 km) | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| GP-13 | GPS device integration: coordinate dirette, skip geocoding, validazione Campania | `tools/proximity_tools.py` | `nearby_priority()` | TRACCIATO |
| GP-NF01 | Singleton GeocodingService e eccezioni custom gerarchiche | `tools/geo_utils.py` | `GeocodingService.__new__()` | TRACCIATO |
| GP-NF03 | Fallback haversine e pulizia warning "CENTRO CITTA'" | `tools/proximity_tools.py` | `_haversine()`, `_clean_address()` | TRACCIATO |

## schema-query-data

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SQ-01 | Tabella schema_metadata in PostgreSQL (table_key PK, JSONB columns) | `sql/create_schema_metadata.sql` | (SQL DDL) | TRACCIATO |
| SQ-02 | SchemaCatalog singleton con lazy loading, fallback statico e hot-reload | `orchestrator/schema_catalog.py` | `SchemaCatalog` | TRACCIATO |
| SQ-03 | Catalogo compatto ~300 token per prompt classificazione | `orchestrator/schema_catalog.py` | `SchemaCatalog.get_compact_catalog()` | TRACCIATO |
| SQ-04 | Schema completo per query builder (colonne, tipi, sample_values, relazioni) | `orchestrator/schema_catalog.py` | `SchemaCatalog.get_full_schema()` | TRACCIATO |
| SQ-05 | Blacklist PII da schema_metadata.pii_columns | `orchestrator/schema_catalog.py` | `SchemaCatalog.get_pii_columns()` | TRACCIATO |
| SQ-07 | QueryDescriptor validazione Pydantic e SafeQueryExecutor su DataFrame | `tools/query_builder_tools.py` | `QueryDescriptor`, `SafeQueryExecutor` | TRACCIATO |
| SQ-09 | Preprocessing filtri: alias colonne, anno->date range, ASL normalizzazione, fuzzy match | `tools/query_builder_tools.py` | `SafeQueryExecutor._preprocess_filters()` | TRACCIATO |
| SQ-10 | Filtri datetime-aware con conversione pd.Timestamp | `tools/query_builder_tools.py` | `SafeQueryExecutor._apply_filters()` | TRACCIATO |
| SQ-11 | Regole disambiguazione query_data nel prompt (confidence max 0.80) | `orchestrator/router.py` | `CLASSIFICATION_SYSTEM_PROMPT` | TRACCIATO |
| SQ-12 | Pagina admin schema metadata /gias/webchat/admin/schema | `app/api.py` | `admin_schema_metadata()` | TRACCIATO |
| SQ-NF01 | Budget ~400 token, diagnostica zero risultati, limite 100 righe | `tools/query_builder_tools.py` | `SafeQueryExecutor` | TRACCIATO |

## cross-cutting-nf

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| XNF-BE-01 | Singleton pattern lazy loading (9 componenti) | (multipli) | Vari singleton | TRACCIATO |
| XNF-BE-02 | Thread-safety tramite lock (sessioni, cache intent, cache RAG) | `app/session_manager.py`, `orchestrator/intent_cache.py`, `tools/rag_cache.py` | threading.Lock | TRACCIATO |
| XNF-BE-03 | Copia dati per isolamento (.copy() su sessioni) | `app/session_manager.py` | `SessionManager.get_session()` | TRACCIATO |
| XNF-BE-04 | Graceful degradation su errore (LLM, Qdrant, ML, hybrid) | (multipli) | Vari fallback | TRACCIATO |
| XNF-BE-05 | Logging strutturato con prefissi componente | (multipli) | Vari moduli | TRACCIATO |
| XNF-BE-06 | Fallback recovery chain a cascata per componenti critici | (multipli) | Vari fallback chain | TRACCIATO |
| XNF-BE-07 | JSON parsing robusto con 3 livelli fallback | `orchestrator/router.py`, `tools/hybrid_search/llm_reranker.py` | `_parse_llm_response()` | TRACCIATO |
| XNF-BE-08 | Cache con TTL e eviction 20% (intent, RAG, keyword, geocoding) | `orchestrator/intent_cache.py`, `tools/rag_cache.py` | IntentCache, RAGCache | TRACCIATO |
| XNF-BE-09 | Configurabilita' config.json con fallback a default hardcoded | `configs/config_loader.py`, `configs/config.py` | `get_config()`, `AppConfig` | TRACCIATO |
| XNF-BE-10 | Precaricamento dati al startup (DataFrame, metadati, catalogo) | `app/api.py` | `lifespan()` | TRACCIATO |
