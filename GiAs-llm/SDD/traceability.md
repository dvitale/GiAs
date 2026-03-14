# Matrice di Tracciabilità — Backend (GiAs-llm)

**Generata**: 2026-03-09
**Requisiti totali**: 413
**Tracciati**: 411 | **Non tracciati**: 2

## Legenda

- ✅ TRACCIATO — requisito mappato a codice specifico
- ⚠️ NON TRACCIATO — requisito non associabile a codice specifico

## langgraph-pipeline

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| LG-001 | Struttura grafo con nodi registrati | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | ✅ |
| LG-002 | Entry point nodo classify | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | ✅ |
| LG-003 | Edge classify -> dialogue_manager | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | ✅ |
| LG-004 | Conditional edges post dialogue_manager | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | ✅ |
| LG-005 | Ask user termina il turno (edge END) | `orchestrator/graph.py` | `ConversationGraph._ask_user_node()` | ✅ |
| LG-006 | Fallback tool -> response_generator | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | ✅ |
| LG-007 | Tool -> response_generator -> END | `orchestrator/graph.py` | `ConversationGraph._build_graph()` | ✅ |
| LG-008 | ConversationState tipizzato (TypedDict) | `orchestrator/dialogue_state.py` | `ConversationState` | ✅ |
| LG-009 | Execution path tracking | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | ✅ |
| LG-010 | Node timings tracking in ms | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | ✅ |
| LG-011 | SSE node_timing event | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | ✅ |
| LG-012 | SSE status event su classify | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-013 | SSE reasoning event su classify | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-014 | Menu disambiguazione shortcut (<=3 char) | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-015 | Fallback selection parsing | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-016 | Slot carry-forward guard | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-017 | Topic change detection nel dialogue_manager | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-018 | Confidence source detection (reale/euristica) | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-019 | Raw message type detection | `orchestrator/dialogue_manager.py` | `_is_oppure()`, `_is_refinement()`, `_is_vague()` | ✅ |
| LG-020 | Tool wrapper con event_callback injection | `orchestrator/graph.py` | `ConversationGraph._make_tool_wrapper()` | ✅ |
| LG-021 | Response context propagation | `orchestrator/graph.py` | `ConversationGraph._response_generator_node()` | ✅ |
| LG-022 | Fallback loop prevention (count > 3) | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-023 | Fallback con approssimazioni successive (3 fasi) | `orchestrator/graph.py` | `ConversationGraph._classify_node()` (+ `fallback_recovery.py`) | ✅ |
| LG-024 | Clarification per slot mancanti | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-025 | Caso speciale ask_establishment_history (OR) | `orchestrator/graph.py` | `ConversationGraph._classify_node()` | ✅ |
| LG-026 | Total execution time tracking | `orchestrator/graph.py` | `ConversationGraph.run()` | ✅ |
| LG-027 | Dialogue state passthrough input/output | `orchestrator/graph.py` | `ConversationGraph.run()` | ✅ |
| LG-NF-001 | Singleton grafo compilato | `orchestrator/graph.py` | `ConversationGraph.__init__()` | ✅ |
| LG-NF-002 | Event callback cleanup in finally | `orchestrator/graph.py` | `ConversationGraph.run()` | ✅ |
| LG-NF-003 | Backwards compatibility workflow legacy | `orchestrator/dialogue_state.py` | `ConversationState` | ✅ |

## intent-classification

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| IC-001 | Pipeline a 6 livelli di classificazione | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-002 | 20+1 intent validi in VALID_INTENTS (incl. query_data) | `orchestrator/router.py` | `Router.VALID_INTENTS` | ✅ |
| IC-003 | Set slot keys validi (incl. sezione, macroarea, anno, table, operation, filters, group_by) | `orchestrator/router.py` | `Router.VALID_SLOT_KEYS` | ✅ |
| IC-004 | Required slots per intent | `orchestrator/router.py` | `Router.REQUIRED_SLOTS` | ✅ |
| IC-005 | Flag MINIMAL_HEURISTICS per delegare a LLM | `orchestrator/router.py` | `Router.MINIMAL_HEURISTICS` | ✅ |
| IC-006 | Heuristic confirm esplicito | `orchestrator/router.py` | `Router._try_heuristics()` | ✅ |
| IC-007 | Heuristic confirm breve con detail_context | `orchestrator/router.py` | `Router._try_heuristics()` | ✅ |
| IC-008 | Heuristic decline esplicito | `orchestrator/router.py` | `Router._try_heuristics()` | ✅ |
| IC-009 | Heuristic decline breve con detail_context | `orchestrator/router.py` | `Router._try_heuristics()` | ✅ |
| IC-010 | Disambiguazione rischio - mai controllati | `orchestrator/router.py` | `Router._try_heuristics()` | ✅ |
| IC-011 | Disambiguazione rischio - con sanzioni | `orchestrator/router.py` | `Router._try_heuristics()` | ✅ |
| IC-012 | Regex estrazione piano_code | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-013 | Regex estrazione numero riconoscimento UE | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-014 | Regex estrazione num_registrazione | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-015 | Regex estrazione partita_iva | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-016 | Regex estrazione topic | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-017 | Regex estrazione location e radius_km | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-018 | Regex estrazione categoria NC | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-019 | Regex estrazione tipo_analisi_rischio | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-020 | Regex estrazione ragione_sociale | `orchestrator/router.py` | `Router._extract_slots()` | ✅ |
| IC-021 | Intent cache TTL 3600s | `orchestrator/intent_cache.py` | `IntentCache.__init__()` | ✅ |
| IC-022 | Intent cache max size 1000 con cleanup 20% | `orchestrator/intent_cache.py` | `IntentCache._cleanup_oldest()` | ✅ |
| IC-023 | Intent cache normalizzazione query (MD5) | `orchestrator/intent_cache.py` | `IntentCache._hash_query()` | ✅ |
| IC-024 | Intent cache bypass per fallback | `orchestrator/intent_cache.py` | `IntentCache.set()` | ✅ |
| IC-025 | Intent cache slot override da query corrente | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-026 | Intent cache context awareness (__ctx__) | `orchestrator/router.py` | `Router._build_cache_key()` | ✅ |
| IC-027 | Few-shot retriever singleton con lazy init | `orchestrator/few_shot_retriever.py` | `FewShotRetriever.__new__()` | ✅ |
| IC-028 | Few-shot retriever top_k=6, max 2 per intent | `orchestrator/few_shot_retriever.py` | `FewShotRetriever.retrieve()` | ✅ |
| IC-029 | Few-shot threshold adattivo per lunghezza query | `orchestrator/few_shot_retriever.py` | `FewShotRetriever._adaptive_threshold()` | ✅ |
| IC-030 | Few-shot cache LRU (OrderedDict, max 100) | `orchestrator/few_shot_retriever.py` | `FewShotRetriever.retrieve()` | ✅ |
| IC-031 | Few-shot graceful degradation senza Qdrant | `orchestrator/few_shot_retriever.py` | `FewShotRetriever._ensure_initialized()` | ✅ |
| IC-032 | Condivisione risorse Qdrant/embedding | `orchestrator/few_shot_retriever.py` | `FewShotRetriever._ensure_initialized()` (+ singletons) | ✅ |
| IC-033 | LLM classification prompt V2 semi-dinamico | `orchestrator/router.py` | `Router._build_system_prompt()` | ✅ |
| IC-034 | LLM confidence e alternatives (< 0.85) | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-035 | LLM session context injection | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-036 | LLM few-shot injection nel prompt | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-037 | LLM response parsing (chain di fallback) | `orchestrator/router.py` | `Router._parse_llm_response()` | ✅ |
| IC-038 | Post-LLM: search con piano_code -> stabilimenti | `orchestrator/router.py` | `Router._post_validate()` | ✅ |
| IC-039 | Post-LLM: priority con rischio -> risk_based | `orchestrator/router.py` | `Router._post_validate()` | ✅ |
| IC-040 | Invalid slot filtering (NULL, none, etc.) | `orchestrator/router.py` | `Router._validate_result()` | ✅ |
| IC-041 | Slot key filtering contro VALID_SLOT_KEYS | `orchestrator/router.py` | `Router._validate_result()` | ✅ |
| IC-042 | Gibberish detection (<=15 char, no keywords) | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-043 | Gibberish bypass per pending slots | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-044 | Pending slot fill - location con LLM | `orchestrator/router.py` | `Router._extract_location_with_llm()` | ✅ |
| IC-045 | Pending slot fill - topic change guard | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-046 | Local fallback per LLM-down | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-047 | Confidence clamping 0.0-1.0, default 0.70 | `orchestrator/router.py` | `Router._validate_result()` | ✅ |
| IC-048 | Multi-candidate output (_candidates) | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-049 | Intent metadata registry (INTENT_REGISTRY) | `orchestrator/intent_metadata.py` | `INTENT_REGISTRY` | ✅ |
| IC-050 | Category hierarchy a 2 livelli (7 categorie) | `orchestrator/intent_metadata.py` | `CATEGORY_HIERARCHY` | ✅ |
| IC-051 | Registry validation al caricamento | `orchestrator/intent_metadata.py` | `validate_registry()` | ✅ |
| IC-052 | Slot normalizzazione (uppercase, filtro None) | `orchestrator/router.py` | `Router._normalize_slots()` | ✅ |
| IC-053 | Self-sufficient intents (no slot obbligatori) | `orchestrator/router.py` | `Router.REQUIRED_SLOTS` | ✅ |
| IC-054 | analyze_nc_by_category default HACCP | `orchestrator/router.py` | `Router.classify()` | ✅ |
| IC-055 | Router hot-reload (metadati, prompt, cache) | `orchestrator/router.py` | `Router.reload()` | ✅ |
| IC-NF-001 | Cache HIT ~0.001s senza LLM | `orchestrator/intent_cache.py` | `IntentCache.get()` | ✅ |
| IC-NF-002 | Few-shot retriever lazy loading | `orchestrator/few_shot_retriever.py` | `FewShotRetriever._ensure_initialized()` | ✅ |
| IC-NF-003 | Thread safety cache (Python GIL) | `orchestrator/intent_cache.py` | `IntentCache` | ✅ |
| IC-NF-004 | LLM location extraction timeout 10s | `orchestrator/router.py` | `Router._extract_location_with_llm()` | ✅ |

## dialogue-management

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| DM-001 | Soglie confidence adattive per modello LLM | `orchestrator/dialogue_manager.py` | `_get_thresholds()` | ✅ |
| DM-002 | Regola 0 - Slot continuation | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-003 | Regola 1 - Intent chiaro, slot completi | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-004 | Regola 1bis - Proposta strategia per vaghi | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-005 | Regola 2 - Intent chiaro, slot mancanti | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-006 | Regola 3 - Intent ambiguo (menu disambig.) | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-007 | Regola 4 - Nessun candidato valido -> fallback | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-008 | Regola 5 - Refinement con ri-esecuzione tool | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-009 | Regola 6 - Conferma strategia pendente | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-010 | Regola 7 - "Oppure?" cycling strategie | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-011 | "Oppure?" senza alternative | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-012 | Default - confidence media, esegui se possibile | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-013 | DialogueState TTL 300s | `orchestrator/dialogue_state.py` | `is_state_valid()` | ✅ |
| DM-014 | DialogueState creazione vuoto | `orchestrator/dialogue_state.py` | `create_empty_state()` | ✅ |
| DM-015 | Slot merge (new override existing) | `orchestrator/dialogue_state.py` | `merge_slots()` | ✅ |
| DM-016 | Filter extraction (comune, limit) | `orchestrator/dialogue_manager.py` | `_extract_filters()` | ✅ |
| DM-017 | Turn count increment e timestamp update | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-018 | DialogueState backwards compat (from/to_session) | `orchestrator/dialogue_state.py` | `from_session()`, `to_session()` | ✅ |
| DM-019 | Workflow strategies per 3 intent | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | ✅ |
| DM-020 | 6 intent conversazionali multi-turno | `orchestrator/workflow_strategies.py` | `CONVERSATIONAL_INTENTS` | ✅ |
| DM-021 | Strategy ID validation allowlist | `orchestrator/workflow_strategies.py` | `validate_strategy_id()` | ✅ |
| DM-022 | Multi-candidate menu max 3 opzioni | `orchestrator/dialogue_manager.py` | `_build_disambiguation_question()` | ✅ |
| DM-023 | Caso speciale ask_establishment_history slot | `orchestrator/dialogue_manager.py` | `_build_slot_question()` | ✅ |
| DM-024 | Rilevamento pattern vago (VAGUE_PATTERNS) | `orchestrator/dialogue_manager.py` | `_is_vague()` | ✅ |
| DM-025 | Rilevamento pattern oppure (OPPURE_PATTERNS) | `orchestrator/dialogue_manager.py` | `_is_oppure()` | ✅ |
| DM-026 | Rilevamento pattern refinement | `orchestrator/dialogue_manager.py` | `_is_refinement()` | ✅ |
| DM-NF-001 | Rule-based senza chiamate LLM | `orchestrator/dialogue_manager.py` | `evaluate()` | ✅ |
| DM-NF-002 | DialogueState serializzabile JSON | `orchestrator/dialogue_state.py` | `to_session()` | ✅ |

## tool-execution

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| TE-001 | TOOL_REGISTRY con 19 tool registrati (incl. query_data_tool) | `orchestrator/tool_nodes.py` | `TOOL_REGISTRY` | ✅ |
| TE-002 | INTENT_TO_TOOL mapping completo (incl. query_data) | `orchestrator/tool_nodes.py` | `INTENT_TO_TOOL` | ✅ |
| TE-003 | greet_tool - benvenuto statico | `orchestrator/tool_nodes.py` | `greet_tool()` | ✅ |
| TE-004 | goodbye_tool - arrivederci statico | `orchestrator/tool_nodes.py` | `goodbye_tool()` | ✅ |
| TE-005 | help_tool - DB con fallback hardcoded | `orchestrator/tool_nodes.py` | `help_tool()` | ✅ |
| TE-006 | confirm_details_tool con contesto presente | `orchestrator/tool_nodes.py` | `confirm_details_tool()` | ✅ |
| TE-007 | confirm_details_tool - sessione scaduta | `orchestrator/tool_nodes.py` | `confirm_details_tool()` | ✅ |
| TE-008 | decline_details_tool | `orchestrator/tool_nodes.py` | `decline_details_tool()` | ✅ |
| TE-009 | piano_description_tool (DataRetriever) | `orchestrator/tool_nodes.py` | `piano_description_tool()` | ✅ |
| TE-010 | piano_stabilimenti_tool con two-phase | `orchestrator/tool_nodes.py` | `piano_stabilimenti_tool()` | ✅ |
| TE-011 | piano_statistics_tool con conteggio ASL | `orchestrator/tool_nodes.py` | `piano_statistics_tool()` | ✅ |
| TE-012 | piano_statistics_tool - statistiche aggregate | `orchestrator/tool_nodes.py` | `piano_statistics_tool()` | ✅ |
| TE-013 | search_piani_tool - hybrid search con fallback | `orchestrator/tool_nodes.py` | `search_piani_tool()` | ✅ |
| TE-014 | search_piani_tool con two-phase (>3 risultati) | `orchestrator/tool_nodes.py` | `search_piani_tool()` | ✅ |
| TE-015 | priority_establishment_tool - UOC/UOS auto | `orchestrator/tool_nodes.py` | `priority_establishment_tool()` | ✅ |
| TE-016 | priority_establishment_tool con two-phase | `orchestrator/tool_nodes.py` | `priority_establishment_tool()` | ✅ |
| TE-017 | risk_predictor_tool - disambiguazione tipo | `orchestrator/tool_nodes.py` | `risk_predictor_tool()` | ✅ |
| TE-018 | risk_predictor_tool - mai controllati (ML/stat) | `orchestrator/tool_nodes.py` | `risk_predictor_tool()` | ✅ |
| TE-019 | risk_predictor_tool - con sanzioni | `orchestrator/tool_nodes.py` | `risk_predictor_tool()` | ✅ |
| TE-020 | suggest_controls_tool con two-phase | `orchestrator/tool_nodes.py` | `suggest_controls_tool()` | ✅ |
| TE-021 | delayed_plans_tool - top 10 per ritardo | `orchestrator/tool_nodes.py` | `delayed_plans_tool()` | ✅ |
| TE-022 | check_plan_delayed_tool - verifica piano | `orchestrator/tool_nodes.py` | `check_plan_delayed_tool()` | ✅ |
| TE-023 | establishment_history_tool con two-phase | `orchestrator/tool_nodes.py` | `establishment_history_tool()` | ✅ |
| TE-024 | establishment_history_tool - multi-identifier | `orchestrator/tool_nodes.py` | `establishment_history_tool()` (+ `agents/data_agent.py` `DataRetriever.get_establishment_history()`) | ✅ |
| TE-025 | top_risk_activities_tool (RiskAnalyzer) | `orchestrator/tool_nodes.py` | `top_risk_activities_tool()` (+ `tools/risk_analysis_tools.py`) | ✅ |
| TE-026 | analyze_nc_tool - NC per categoria | `orchestrator/tool_nodes.py` | `analyze_nc_tool()` (+ `tools/risk_tools.py` `analyze_nc_by_category()`) | ✅ |
| TE-027 | info_procedure_tool - RAG | `orchestrator/tool_nodes.py` | `info_procedure_tool()` (+ `tools/procedure_tools.py`) | ✅ |
| TE-028 | nearby_priority_tool - geocodifica | `orchestrator/tool_nodes.py` | `nearby_priority_tool()` (+ `tools/geo_utils.py`) | ✅ |
| TE-029 | nearby_priority_tool - verifica territorio ASL | `orchestrator/tool_nodes.py` | `nearby_priority_tool()` (+ `tools/proximity_tools.py`) | ✅ |
| TE-030 | nearby_priority_tool - filtro prossimita/rischio | `orchestrator/tool_nodes.py` | `nearby_priority_tool()` (+ `tools/proximity_tools.py` `get_nearby_priority()`) | ✅ |
| TE-031 | nearby_priority_tool con two-phase (>10) | `orchestrator/tool_nodes.py` | `nearby_priority_tool()` | ✅ |
| TE-032 | nearby_priority_tool - centro citta fallback | `tools/geo_utils.py` | `GeocodingService.geocode_with_address()` | ✅ |
| TE-033 | predictor_tools - ML con fallback rule-based | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | ✅ |
| TE-034 | predictor_tools - emergency fallback | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | ✅ |
| TE-035 | predictor_tools - normalizzazione score 0-1 | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | ✅ |
| TE-036 | risk_tools - analisi per piano senza ASL | `tools/risk_tools.py` | `_analyze_controlled_establishments_risk()` | ✅ |
| TE-037 | risk_tools - suggerimento categoria NC | `tools/risk_tools.py` | `get_risk_based_priority()` | ✅ |
| TE-038 | SSE reasoning events per tool specifici | `orchestrator/tool_nodes.py` | `piano_stabilimenti_tool()`, `priority_establishment_tool()`, `risk_predictor_tool()`, `nearby_priority_tool()` | ✅ |
| TE-039 | Tool unwrap LangChain decorator (.func) | `orchestrator/tool_nodes.py` | `_unwrap_tool()` | ✅ |
| TE-040 | query_data_tool - interrogazione dati su misura | `orchestrator/tool_nodes.py`, `tools/query_builder_tools.py` | `query_data_tool()`, `build_query_with_llm()` | ✅ |
| TE-041 | Preprocessing filtri con alias colonne | `tools/query_builder_tools.py` | `SafeQueryExecutor._preprocess_filters()` | ✅ |
| TE-042 | Blacklist PII in query_data | `tools/query_builder_tools.py` | `SafeQueryExecutor.execute()` | ✅ |
| TE-043 | Fallback prefisso ATT per indicatori piano | `agents/data_agent.py` | `DataRetriever.get_piano_by_id()` | ✅ |
| TE-NF-001 | Tool output standard {type, data} | `orchestrator/tool_nodes.py` | (tutte le funzioni tool) | ✅ |
| TE-NF-002 | Radius clamping default 5.0 km (1-50) | `tools/proximity_tools.py` | `get_nearby_priority()` | ✅ |
| TE-NF-003 | Limit clamping predictor 1-100 | `tools/predictor_tools.py` | `get_ml_risk_prediction()` | ✅ |

## two-phase-response

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| TP-001 | Soglie two-phase per intent | `orchestrator/two_phase.py` | `TWO_PHASE_THRESHOLDS` | ✅ |
| TP-002 | Attivazione two-phase sopra soglia | `orchestrator/two_phase.py` | `apply_two_phase_check()` | ✅ |
| TP-003 | Suffisso "Vuoi vedere tutti i dettagli?" | `orchestrator/two_phase.py` | `TWO_PHASE_SUFFIX` | ✅ |
| TP-004 | Detail context con full_formatted_response | `orchestrator/two_phase.py` | `apply_two_phase_check()` | ✅ |
| TP-005 | Conferma -> restituisce formatted_response | `orchestrator/tool_nodes.py` | `confirm_details_tool()` | ✅ |
| TP-006 | Rifiuto -> messaggio cortese | `orchestrator/tool_nodes.py` | `decline_details_tool()` | ✅ |
| TP-007 | Sessione scaduta per conferma | `orchestrator/tool_nodes.py` | `confirm_details_tool()` | ✅ |
| TP-008 | Non-attivazione sotto soglia | `orchestrator/two_phase.py` | `apply_two_phase_check()` | ✅ |
| TP-NF-001 | Modifica state in-place | `orchestrator/two_phase.py` | `apply_two_phase_check()` | ✅ |

## response-generation

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| RG-001 | Bypass LLM per formatted_response | `orchestrator/response_node.py` | `response_generator_node()` | ✅ |
| RG-002 | Risposta diretta per DIRECT_RESPONSE_INTENTS | `orchestrator/response_node.py` | `response_generator_node()` | ✅ |
| RG-003 | Generazione risposta LLM come fallback | `orchestrator/response_node.py` | `response_generator_node()` | ✅ |
| RG-004 | System prompt per generazione risposta | `orchestrator/response_node.py` | `RESPONSE_SYSTEM_PROMPT` | ✅ |
| RG-005 | Template utente contestualizzato per intent | `orchestrator/response_node.py` | `build_response_messages()` | ✅ |
| RG-006 | Pulizia newline eccessive (max 2) | `orchestrator/response_node.py` | `clean_excessive_newlines()` | ✅ |
| RG-007 | Gestione errore generazione LLM | `orchestrator/response_node.py` | `response_generator_node()` | ✅ |
| RG-008 | Evento SSE status per response_generator | `orchestrator/response_node.py` | `response_generator_node()` | ✅ |
| RG-009 | Esclusione suggerimenti follow-up | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.should_append()` | ✅ |
| RG-010 | Limite max 3 suggerimenti follow-up | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.get_suggestions()` | ✅ |
| RG-011 | Formato suggerimenti {text, query} | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.get_suggestions()` | ✅ |
| RG-012 | Suggerimenti contestuali per intent (13 handler) | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.get_suggestions()` | ✅ |
| RG-013 | Suggerimenti RAG dinamici da metadati chunk | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine._suggest_info_procedure()` | ✅ |
| RG-014 | Estrazione contesto risposta per anaforica | `orchestrator/response_node.py` | `extract_response_context()` | ✅ |
| RG-015 | Formattazione markdown suggerimenti | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine.format_suggestions()` | ✅ |
| RG-016 | Fallback suggerimenti per info_procedure | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine._fallback_procedure_suggestions()` | ✅ |
| RG-NF-001 | Risparmio latenza con bypass LLM | `orchestrator/response_node.py` | `response_generator_node()` | ✅ |
| RG-NF-002 | Singleton engine follow-up | `orchestrator/followup_suggestions.py` | `FollowUpSuggestionEngine` (module-level) | ✅ |

## fallback-recovery

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| FR-001 | Engine a 3 fasi per recupero fallback | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.suggest_intents()` | ✅ |
| FR-002 | Fase 1 - Keyword Matching con scoring | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._keyword_matching()` | ✅ |
| FR-003 | Esclusione intent interni dal keyword matching | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._score_intent_by_keywords()` | ✅ |
| FR-004 | Cache risultati keyword matching | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._keyword_matching()` | ✅ |
| FR-005 | Fase 2 - LLM Semantic Scoring | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._llm_semantic_scoring()` | ⚠️ |
| FR-006 | Timeout Fase LLM (post-hoc) | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._llm_semantic_scoring()` | ⚠️ |
| FR-007 | Merge suggerimenti keyword + LLM | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.suggest_intents()` | ✅ |
| FR-008 | Fase 3 - Menu categorizzato a 2 livelli | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._category_menu()` | ✅ |
| FR-009 | Suggerimenti con categorie appendate | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._prepare_suggestions_with_categories()` | ✅ |
| FR-010 | Parsing selezione utente numerica e testuale | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.parse_user_selection()` | ✅ |
| FR-011 | Formattazione messaggio suggerimenti | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.format_suggestions_message()` | ✅ |
| FR-012 | Limite max 4 suggerimenti diretti | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.__init__()` | ✅ |
| FR-013 | Registry intent con metadati strutturati | `orchestrator/intent_metadata.py` | `INTENT_REGISTRY` (`IntentMetadata` dataclass) | ✅ |
| FR-014 | Gerarchia categoriale con 7 categorie | `orchestrator/intent_metadata.py` | `CATEGORY_HIERARCHY` | ✅ |
| FR-015 | Validazione registry al caricamento | `orchestrator/intent_metadata.py` | `validate_registry()` | ✅ |
| FR-NF-001 | Latenza target Fase 1 ~50ms | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine._keyword_matching()` | ✅ |
| FR-NF-002 | Configurabilita engine (defaults override) | `orchestrator/fallback_recovery.py` | `FallbackRecoveryEngine.__init__()` | ✅ |

## rag-pipeline

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| RAG-001 | Threshold dinamico per complessita query | `tools/procedure_tools.py` | `_compute_dynamic_threshold()` | ✅ |
| RAG-002 | Score complessita multi-fattore (0-10+) | `tools/procedure_tools.py` | `_compute_dynamic_threshold()` | ✅ |
| RAG-003 | Termini di dominio GISA (~40 termini) | `tools/procedure_tools.py` | `_compute_dynamic_threshold()` | ✅ |
| RAG-004 | Query expansion via LLM (2 riformulazioni) | `tools/procedure_tools.py` | `_expand_query()` | ✅ |
| RAG-005 | Fallback query expansion se LLM fallisce | `tools/procedure_tools.py` | `_expand_query()` | ✅ |
| RAG-006 | Arricchimento query con conversation_context | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-007 | Retrieval multi-variante con deduplicazione | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-008 | BM25 + RRF re-ranking (k=60) | `tools/hybrid_search/bm25_scorer.py` | `rrf_combine()` | ✅ |
| RAG-009 | BM25 scoring con fallback TF | `tools/hybrid_search/bm25_scorer.py` | `BM25Scorer.score_chunks()` | ✅ |
| RAG-010 | Formula RRF combinata | `tools/hybrid_search/bm25_scorer.py` | `rrf_combine()` | ✅ |
| RAG-011 | Post-filtering adattivo | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-012 | Limite max 5 chunk per contesto LLM | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-013 | Deduplicazione contesto (100 char) | `tools/procedure_tools.py` | `_build_rag_context()` | ✅ |
| RAG-014 | Citazioni inline [Fonte N] | `tools/procedure_tools.py` | `_build_rag_context()` | ✅ |
| RAG-015 | Sezione fonti con titolo, file, pagina | `tools/procedure_tools.py` | `_format_sources()` | ✅ |
| RAG-016 | RAG Cache con TTL e max size (singleton) | `tools/rag_cache.py` | `RAGCache` | ✅ |
| RAG-017 | Eviction cache per superamento dimensione | `tools/rag_cache.py` | `RAGCache._cleanup_oldest()` | ✅ |
| RAG-018 | Statistiche cache RAG | `tools/rag_cache.py` | `RAGCache.get_stats()` | ✅ |
| RAG-019 | Fallback chunk grezzi se LLM non disponibile | `tools/procedure_tools.py` | `_format_chunks_fallback()` | ✅ |
| RAG-020 | Risposta per nessun risultato RAG | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-021 | Livello di confidenza risposta RAG | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-022 | Metadati chunk per suggerimenti dinamici | `tools/procedure_tools.py` | `get_procedure_info()` | ✅ |
| RAG-NF-001 | Tokenizzazione BM25 semplificata (regex) | `tools/hybrid_search/bm25_scorer.py` | `BM25Scorer._tokenize()` | ✅ |
| RAG-NF-002 | Performance BM25 on-the-fly (<1ms) | `tools/hybrid_search/bm25_scorer.py` | `BM25Scorer.score_chunks()` | ✅ |
| RAG-NF-003 | RAG System Prompt con regole fondamentali | `tools/procedure_tools.py` | `_generate_rag_response()` | ✅ |
| RAG-NF-004 | Configurabilita cache da config.json | `tools/rag_cache.py` | `get_rag_cache()` | ✅ |

## llm-client

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| LC-001 | Supporto 6 backend LLM | `llm/providers.py` | `OllamaProvider`, `LlamaCppProvider`, `OpenAIProvider`, `AnthropicProvider`, `OpenAICompatProvider` | ✅ |
| LC-002 | Factory method per creazione provider | `llm/client.py` | `LLMClient._create_provider()` | ✅ |
| LC-003 | GDPR gate per provider esterni | `llm/client.py` | `LLMClient._check_gdpr_consent()` | ✅ |
| LC-004 | GDPR consent permissivo in sviluppo | `llm/client.py` | `LLMClient._check_gdpr_consent()` | ✅ |
| LC-005 | Degradazione a stub quando LLM non raggiungibile | `llm/client.py` | `LLMClient.__init__()` | ✅ |
| LC-006 | Degradazione a stub per errori runtime | `llm/client.py` | `LLMClient.query()` | ✅ |
| LC-007 | Metodo sincrono query() | `llm/client.py` | `LLMClient.query()` | ✅ |
| LC-008 | Metodo streaming query_stream() | `llm/client.py` | `LLMClient.query_stream()` | ✅ |
| LC-009 | Streaming stub come fallback | `llm/client.py` | `LLMClient.query_stream()` | ✅ |
| LC-010 | Temperature differenziate da configurazione | `llm/client.py` | `LLMClient.query()` | ✅ |
| LC-011 | Interfaccia ABC per provider (4 metodi) | `llm/provider_base.py` | `LLMProvider` (ABC) | ✅ |
| LC-012 | API key esclusivamente da env var | `configs/config.py` | `LLMBackendConfig.get_api_key()` | ✅ |
| LC-013 | Keep-alive configurabile per Ollama | `llm/providers.py` | `OllamaProvider.query()` | ✅ |
| LC-014 | Health check tramite ping() | `llm/providers.py` | `OllamaProvider.ping()`, `LlamaCppProvider.ping()`, etc. | ✅ |
| LC-015 | JSON mode per provider | `llm/providers.py` | `OllamaProvider.query()`, `AnthropicProvider.query()`, etc. | ✅ |
| LC-016 | Ricostruzione JSON per Anthropic | `llm/providers.py` | `AnthropicProvider.query()` | ✅ |
| LC-017 | Separazione system message per Anthropic | `llm/providers.py` | `AnthropicProvider._extract_system_and_messages()` | ✅ |
| LC-NF-001 | Timeout configurabile per provider | `llm/client.py` | `LLMClient.query()` | ✅ |
| LC-NF-002 | Logging inizializzazione | `llm/client.py` | `LLMClient.__init__()` | ✅ |
| LC-NF-003 | Nessun SDK aggiuntivo per OpenAI-compat | `llm/providers.py` | `OpenAICompatProvider` | ✅ |

## session-management

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SM-001 | Sessioni in-memory con TTL 300s | `app/session_manager.py` | `SessionManager.get_session_context()` | ✅ |
| SM-002 | Thread-safety tramite lock | `app/session_manager.py` | `SessionManager.__init__()` | ✅ |
| SM-003 | Pulizia automatica ogni 100 richieste | `app/session_manager.py` | `SessionManager.periodic_cleanup()` | ✅ |
| SM-004 | Topic change detection | `app/session_manager.py` | `SessionManager.update_session()` | ✅ |
| SM-005 | Propagazione stato conversazionale | `app/session_manager.py` | `SessionManager.update_session()` | ✅ |
| SM-006 | Metadata enrichment per il grafo | `app/session_manager.py` | `SessionManager.get_session_context()` | ✅ |
| SM-007 | Gestione detail_context per two-phase | `app/session_manager.py` | `SessionManager.update_session()` | ✅ |
| SM-008 | Fallback recovery state in sessione | `app/session_manager.py` | `SessionManager._apply_fallback_state()` | ✅ |
| SM-009 | Workflow context in sessione | `app/session_manager.py` | `SessionManager._build_workflow_context()` | ✅ |
| SM-010 | Invalidazione selettiva workflow | `app/session_manager.py` | `SessionManager.invalidate_workflow()` | ✅ |
| SM-011 | Reset completo sessione | `app/session_manager.py` | `SessionManager.clear_session()` | ✅ |
| SM-012 | Contesto risposta per risoluzione anaforica | `app/session_manager.py` | `SessionManager.update_session()` | ✅ |
| SM-013 | SessionContext come NamedTuple immutabile | `app/session_manager.py` | `SessionContext` | ✅ |
| SM-NF-001 | Copia dati per isolamento (.copy()) | `app/session_manager.py` | `SessionManager.get_session_context()` | ✅ |
| SM-NF-002 | Logging operazioni sessione [Session] | `app/session_manager.py` | `SessionManager` (vari metodi) | ✅ |

## api-endpoints

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| API-01 | Chat sincrono POST /api/v1/chat | `app/api.py` | `chat_v1()` | ✅ |
| API-02 | Chat streaming SSE POST /api/v1/chat/stream | `app/api.py` | `chat_stream_v1()` | ✅ |
| API-03 | Parsing NLU POST /api/v1/parse | `app/api.py` | `parse_v1()` | ✅ |
| API-04 | Feedback POST /api/v1/chat/feedback | `app/api.py` | `chat_feedback()` | ✅ |
| API-05 | Feedback loop automatico - rating positivo | `app/api.py` | `_feedback_loop()` | ✅ |
| API-06 | Feedback loop automatico - rating negativo | `app/api.py` | `_feedback_loop()` | ✅ |
| API-07 | Feedback loop - esclusione intent non informativi | `app/api.py` | `_feedback_loop()` | ✅ |
| API-08 | Reset sessione POST /api/v1/session/reset | `app/api.py` | `session_reset()` | ✅ |
| API-09 | Health check GET / | `app/api.py` | `health_check()` | ✅ |
| API-10 | Status dettagliato GET /status | `app/api.py` | `status()` | ✅ |
| API-11 | Configurazione GET /config | `app/api.py` | `get_config_info()` | ✅ |
| API-12 | Chat log - statistiche aggregate | `app/api.py` | `chat_log_stats()` | ✅ |
| API-13 | Chat log - messaggi recenti | `app/api.py` | `chat_log_recent()` | ✅ |
| API-14 | Chat log - statistiche per ASL | `app/api.py` | `chat_log_by_asl()` | ✅ |
| API-15 | Chat log - statistiche per intent | `app/api.py` | `chat_log_by_intent()` | ✅ |
| API-16 | Chat log - errori recenti con classificazione | `app/api.py` | `chat_log_errors()` | ✅ |
| API-17 | Chat log - timeline (hour/day) | `app/api.py` | `chat_log_timeline()` | ✅ |
| API-18 | Chat log - conversazioni utente | `app/api.py` | `chat_log_user_conversations()` | ✅ |
| API-19 | Chat log - singola conversazione | `app/api.py` | `chat_log_conversation()` | ✅ |
| API-20 | Qualita conversazioni (monitor) | `app/api.py` | `chat_log_quality()` | ✅ |
| API-21 | Monitor intelligente (analisi completa) | `app/api.py` | `intelligent_monitor_analysis()` | ✅ |
| API-22 | Monitor - health score 0-100 | `app/api.py` | `intelligent_monitor_health()` | ✅ |
| API-23 | Admin - domande RAG CRUD | `app/api.py` | (GET/POST/DELETE `/api/admin/domande-rag`) | ✅ |
| API-24 | Logging chat in background thread daemon | `app/api.py` | `log_chat()` | ✅ |
| API-25 | Modelli Pydantic tipizzati per contratto API | `app/models.py` | `ChatMessage`, `ChatResponse`, `ChatResult`, etc. | ✅ |
| API-26 | Guided learning nel fallback | `app/api.py` | `chat_v1()` (+ `_build_chat_result()`) | ✅ |
| API-27 | Admin schema metadata lista | `app/api.py` | `admin_schema_metadata_list()` | ✅ |
| API-28 | Admin schema metadata dettaglio | `app/api.py` | `admin_schema_metadata_detail()` | ✅ |
| API-29 | Admin schema metadata aggiornamento | `app/api.py` | `admin_schema_metadata_update()` | ✅ |
| API-30 | Admin schema metadata reload | `app/api.py` | `admin_schema_metadata_reload()` | ✅ |
| API-NF01 | CORS permissivo allow_origins=["*"] | `app/api.py` | `lifespan()` (CORSMiddleware) | ✅ |
| API-NF02 | Timeout esecuzione grafo 50s | `app/api.py` | `chat_v1()` | ✅ |
| API-NF03 | Singleton ConversationGraph | `app/api.py` | `lifespan()` | ✅ |
| API-NF04 | Precaricamento dati al startup | `app/api.py` | `lifespan()` | ✅ |
| API-NF05 | Cleanup risorse allo shutdown | `app/api.py` | `lifespan()` | ✅ |
| API-NF06 | Risoluzione automatica UOC/UOS | `app/api.py` | `chat_v1()` | ✅ |
| API-NF07 | Validazione workflow context | `app/api.py` | `chat_v1()` (+ `orchestrator/workflow_validator.py`) | ✅ |
| API-NF08 | SSE headers anti-buffering | `app/api.py` | `chat_stream_v1()` | ✅ |
| API-NF09 | Formato who per chat_log | `app/api.py` | `log_chat()` | ✅ |
| API-10 | Campi GPS in UserMetadata | `app/models.py` | `UserMetadata` (latitude, longitude, gps_accuracy_m) | ✅ |

## data-layer

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| DL-01 | Factory pattern con singleton | `data_sources/factory.py` | `get_data_source()` | ✅ |
| DL-02 | Intercambiabilita CSV/PostgreSQL | `data_sources/csv_source.py`, `data_sources/postgresql_source.py` | `CSVDataSource`, `PostgreSQLDataSource` | ✅ |
| DL-03 | Selezione data source da configurazione | `data_sources/factory.py` | `get_data_source()` | ✅ |
| DL-04 | Connection pooling SQLAlchemy (QueuePool) | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.__init__()` | ✅ |
| DL-05 | Cache DataFrame class-level condivisa | `data_sources/postgresql_source.py` | `PostgreSQLDataSource._load_table()` | ✅ |
| DL-06 | Deduplicazione piani PostgreSQL | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.load_piani()` | ✅ |
| DL-07 | Deduplicazione attivita PostgreSQL | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.load_attivita()` | ✅ |
| DL-08 | Filtro personale per anno corrente | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.load_personale()` | ✅ |
| DL-09 | Fallback psycopg2 | `data_sources/postgresql_source.py` | `PostgreSQLDataSource._get_connection()` | ✅ |
| DL-10 | Precaricamento completo (preload_all_data) | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.preload_all_data()` | ✅ |
| DL-11 | DataRetriever con metodi statici | `agents/data_agent.py` | `DataRetriever` | ✅ |
| DL-12 | Pesi categorie NC per business logic | `agents/data_agent.py` | `BusinessLogic` (NC_CATEGORY_WEIGHTS) | ✅ |
| DL-13 | get_piano_by_id fallback prefisso ATT | `agents/data_agent.py` | `DataRetriever.get_piano_by_id()` | ✅ |
| DL-NF01 | CSV low_memory=False | `data_sources/csv_source.py` | `CSVDataSource._load_csv()` | ✅ |
| DL-NF02 | Gestione errori graceful (DataFrame vuoto) | `data_sources/csv_source.py`, `data_sources/postgresql_source.py` | `_load_csv()`, `_load_table()` | ✅ |
| DL-NF03 | Cleanup cache (clear_cache, dispose engine) | `data_sources/postgresql_source.py` | `PostgreSQLDataSource.clear_cache()`, `dispose_engine()` | ✅ |

## risk-analysis

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| RA-01 | Predittore ML XGBoost V4 (6 feature) | `predictor_ml/predictor.py` | `RiskPredictor._load_model()`, `RiskPredictor.predict()` | ✅ |
| RA-02 | Soglia decisionale 0.40 (ALTO/MEDIO/BASSO) | `predictor_ml/predictor.py` | `RiskPredictor._process_predictions()` | ✅ |
| RA-03 | Predittore statistico rule-based | `tools/risk_tools.py` | `risk_tool()` | ✅ |
| RA-04 | Configurazione tipo predittore (env>config) | `configs/config.py` | `RiskPredictorConfig.get_predictor_type()` | ✅ |
| RA-05 | Auto-degradazione senza XGBoost | `predictor_ml/predictor.py` | `RiskPredictor._load_model()` | ✅ |
| RA-06 | Fallback su errore predizione | `predictor_ml/predictor.py` | `RiskPredictor._fallback_prediction()` | ✅ |
| RA-07 | Taxonomy map con fallback hardcoded | `predictor_ml/predictor.py` | `RiskPredictor._load_taxonomy_mappings()` | ✅ |
| RA-08 | Top risk activities con soglie calibrate | `tools/risk_analysis_tools.py` | `get_top_risk_activities()` (+ `agents/data_agent.py` `RiskAnalyzer`) | ✅ |
| RA-09 | Analisi NC per categoria (11 categorie) | `tools/risk_tools.py` | `analyze_nc_by_category()` | ✅ |
| RA-10 | Stabilimenti con piu sanzioni | `tools/risk_tools.py` | `get_establishments_with_sanctions()` | ✅ |
| RA-NF01 | Normalizzazione ASL bidirezionale (7 ASL) | `predictor_ml/predictor.py` | `RiskPredictor._normalize_asl_for_filter()`, `_normalize_asl_for_ml()` | ✅ |
| RA-NF02 | Spiegazioni interpretabili (euristiche) | `predictor_ml/predictor.py` | `RiskPredictor._generate_explanations()` | ✅ |

## geocoding-proximity

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| GP-01 | Geocodifica Nominatim (OpenStreetMap) | `tools/geo_utils.py` | `GeocodingService.geocode()` | ✅ |
| GP-02 | SimpleRequestsAdapter fix SSL | `tools/geo_utils.py` | `SimpleRequestsAdapter` | ✅ |
| GP-03 | Strategia city-first per capoluoghi | `tools/geo_utils.py` | `GeocodingService.geocode_with_address()` | ✅ |
| GP-04 | Strategia city-first per comuni generici | `tools/geo_utils.py` | `GeocodingService.geocode_with_address()` | ✅ |
| GP-05 | Fallback centro citta | `tools/geo_utils.py` | `GeocodingService.geocode_with_address()` | ✅ |
| GP-06 | Cache LRU geocodifica (maxsize=500) | `tools/geo_utils.py` | `GeocodingService.geocode_with_address()` (@lru_cache) | ✅ |
| GP-07 | Rate limiter Nominatim (1 req/s) | `tools/geo_utils.py` | `GeocodingService.__init__()` | ✅ |
| GP-08 | Validazione territorio ASL (7 ASL campane) | `tools/proximity_tools.py` | `get_nearby_priority()` | ✅ |
| GP-09 | Coordinate da database (latitudine/longitudine) | `tools/geo_utils.py` | `filter_by_proximity()` | ✅ |
| GP-10 | Limite batch geocodifica (max 100 righe) | `tools/geo_utils.py` | `filter_by_proximity()` | ✅ |
| GP-11 | Ordinamento distanza + rischio | `tools/proximity_tools.py` | `get_nearby_priority()` | ✅ |
| GP-12 | Clamping raggio (default 5.0 km) | `tools/proximity_tools.py` | `get_nearby_priority()` | ✅ |
| GP-NF01 | Singleton GeocodingService (__new__) | `tools/geo_utils.py` | `GeocodingService.__new__()` | ✅ |
| GP-NF02 | Eccezioni custom gerarchiche + geocode_safe | `tools/geo_utils.py` | `GeocodingError`, `AddressNotFoundError`, `GeocodingTimeoutError`, `geocode_safe()` | ✅ |
| GP-NF03 | Fallback haversine senza geopy | `tools/geo_utils.py` | `calculate_distance_km()` | ✅ |
| GP-NF04 | Pulizia warning nell'output | `tools/geo_utils.py` | `GeocodingService.geocode_with_address()` | ✅ |
| GP-13 | GPS device diretto per proximity | `tools/proximity_tools.py`, `orchestrator/tool_nodes.py` | `get_nearby_priority(device_lat, device_lon)`, `nearby_priority_tool()` | ✅ |
| GP-14 | Slot location preservato con GPS | `tools/proximity_tools.py` | `get_nearby_priority()` | ✅ |
| GP-15 | Validazione bounding box Campania | `tools/proximity_tools.py` | `get_nearby_priority()` | ✅ |

## qdrant-embeddings

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| QE-01 | Singleton QdrantClient file-based | `agents/qdrant_singleton.py` | `get_qdrant_client()` | ✅ |
| QE-02 | Lazy initialization QdrantClient | `agents/qdrant_singleton.py` | `get_qdrant_client()` | ✅ |
| QE-03 | Ritorno None se storage non disponibile | `agents/qdrant_singleton.py` | `get_qdrant_client()` | ✅ |
| QE-04 | Singleton modello embedding (MiniLM-L12-v2) | `agents/embedding_singleton.py` | `get_embedding_model()` | ✅ |
| QE-05 | Lazy loading modello embedding (384 dim) | `agents/embedding_singleton.py` | `get_embedding_model()` | ✅ |
| QE-NF01 | Condivisione tra DataRetriever e FewShot | `agents/qdrant_singleton.py`, `agents/embedding_singleton.py` | `get_qdrant_client()`, `get_embedding_model()` | ✅ |

## hybrid-search

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| HS-01 | Tre modalita di ricerca (VECTOR/HYBRID/LLM) | `tools/hybrid_search/hybrid_engine.py` | `SearchMode`, `HybridSearchEngine.search()` | ✅ |
| HS-02 | Smart routing - gate cpu_mode | `tools/hybrid_search/smart_router.py` | `SmartRouter._is_cpu_mode()` | ✅ |
| HS-03 | Smart routing - exact_code -> VECTOR_ONLY | `tools/hybrid_search/smart_router.py` | `SmartRouter._apply_routing_rules()` | ✅ |
| HS-04 | Smart routing - alta complessita -> HYBRID | `tools/hybrid_search/smart_router.py` | `SmartRouter._apply_routing_rules()` | ✅ |
| HS-05 | Smart routing - bassa complessita -> VECTOR | `tools/hybrid_search/smart_router.py` | `SmartRouter._apply_routing_rules()` | ✅ |
| HS-06 | Smart routing - alto carico -> declassa | `tools/hybrid_search/smart_router.py` | `SmartRouter._adjust_for_system_state()` | ✅ |
| HS-07 | Analisi complessita query (0-1) | `tools/hybrid_search/query_analyzer.py` | `QueryAnalyzer.analyze()` | ✅ |
| HS-08 | LLM reranker con timeout e min candidates | `tools/hybrid_search/llm_reranker.py` | `LLMReranker.rerank_candidates()` | ✅ |
| HS-09 | Fallback chain LLM reranker | `tools/hybrid_search/llm_reranker.py` | `LLMReranker._call_llm_with_fallback()` | ✅ |
| HS-10 | Validazione alias piani nei risultati | `tools/hybrid_search/hybrid_engine.py` | `HybridSearchEngine._validate_plan_aliases()` | ✅ |
| HS-NF01 | Performance tracker (statistiche routing) | `tools/hybrid_search/smart_router.py` | `SmartRouter.get_routing_stats()` | ✅ |
| HS-NF02 | Emergency fallback (keyword base) | `tools/hybrid_search/hybrid_engine.py` | `HybridSearchEngine._execute_emergency_fallback()` | ✅ |
| HS-NF03 | Deduplicazione candidati per alias | `tools/hybrid_search/hybrid_engine.py` | `HybridSearchEngine._merge_candidate_lists()` | ✅ |
| HS-NF04 | Parsing JSON robusto LLM response | `tools/hybrid_search/llm_reranker.py` | `LLMReranker._parse_llm_response()` | ✅ |

## configuration

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| CF-01 | Priorita risoluzione: env > config.json > default | `configs/config.py` | `LLMBackendConfig.get_backend_type()`, `AppConfig` | ✅ |
| CF-02 | Sei modelli locali preconfigurati | `configs/config.py` | `ModelConfig.AVAILABLE_MODELS` | ✅ |
| CF-03 | Sei backend LLM supportati | `configs/config.py` | `LLMBackendConfig` | ✅ |
| CF-04 | API key solo da variabili ambiente | `configs/config.py` | `LLMBackendConfig.get_api_key()` | ✅ |
| CF-05 | GDPR gate per provider esterni | `configs/config.py` | `LLMBackendConfig.is_external_provider()` (+ `llm/client.py`) | ✅ |
| CF-06 | Configurazione risk predictor (ml/statistical) | `configs/config.py` | `RiskPredictorConfig` | ✅ |
| CF-07 | Configurazione hybrid search (cpu_mode) | `configs/config.py` | `AppConfig` (+ `configs/config.json`) | ✅ |
| CF-08 | Configurazione data source (csv/postgresql) | `configs/config.py` | `AppConfig` (+ `configs/config.json`) | ✅ |
| CF-09 | Configurazione RAG documents | `configs/config.py` | `AppConfig` (+ `configs/config.json`) | ✅ |
| CF-10 | Config loader singleton (get_config) | `configs/config_loader.py` | `get_config()` | ✅ |
| CF-NF01 | Fallback recovery configurabile da config.json | `configs/config.py` | `AppConfig.get_fallback_config()` | ✅ |
| CF-NF02 | Guided learning configurabile | `configs/config.py` | `AppConfig.is_guided_learning_enabled()` | ✅ |
| CF-NF03 | Streaming configurabile (enabled, max, heartbeat) | `configs/config.py` | `AppConfig` (+ `configs/config.json`) | ✅ |
| CF-NF04 | Cambio modello a runtime | `configs/config.py` | `set_model()` | ✅ |

## workflow-strategies

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| WS-01 | Strategie ask_suggest_controls (3 opzioni) | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | ✅ |
| WS-02 | Strategie ask_priority_establishment (2 opzioni) | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | ✅ |
| WS-03 | Strategie ask_risk_based_priority (2 opzioni) | `orchestrator/workflow_strategies.py` | `WORKFLOW_STRATEGIES` | ✅ |
| WS-04 | STRATEGY_TO_INTENT_MAP allowlist | `orchestrator/workflow_strategies.py` | `STRATEGY_TO_INTENT_MAP` | ✅ |
| WS-05 | Nonce validation anti-spoofing (256 bit) | `orchestrator/workflow_validator.py` | `WorkflowValidator.create_workflow_nonce()` | ✅ |
| WS-06 | Validazione workflow context (TTL, whitelist) | `orchestrator/workflow_validator.py` | `WorkflowValidator.validate_workflow_context()` | ✅ |
| WS-07 | Validazione filtri whitelist (comuni, ASL, etc.) | `orchestrator/workflow_validator.py` | `WorkflowValidator.validate_filters()` | ✅ |
| WS-08 | Validazione strategy_id per workflow | `orchestrator/workflow_validator.py` | `WorkflowValidator.validate_strategy_id()` | ✅ |
| WS-NF01 | Set intent conversazionali (6 intent) | `orchestrator/workflow_strategies.py` | `CONVERSATIONAL_INTENTS`, `is_conversational_intent()` | ✅ |
| WS-NF02 | Pattern estrazione filtri (regex) | `orchestrator/workflow_strategies.py` | `get_supported_filters()` | ✅ |
| WS-NF03 | Sicurezza trust boundary (workflow non trusted) | `orchestrator/workflow_validator.py` | `WorkflowValidator.validate_workflow_context()` | ✅ |

## schema-query-data

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SQ-01 | Tabella schema_metadata in PostgreSQL | `sql/create_schema_metadata.sql` | DDL + INSERT 7 tabelle | ✅ |
| SQ-02 | SchemaCatalog singleton con lazy loading | `orchestrator/schema_catalog.py` | `SchemaCatalog`, `get_schema_catalog()` | ✅ |
| SQ-03 | Catalogo compatto per prompt classificazione | `orchestrator/schema_catalog.py` | `SchemaCatalog.get_compact_catalog()` | ✅ |
| SQ-04 | Schema completo per query builder | `orchestrator/schema_catalog.py` | `SchemaCatalog.get_full_schema()` | ✅ |
| SQ-05 | Blacklist PII da schema_metadata | `orchestrator/schema_catalog.py` | `SchemaCatalog.get_pii_columns()`, `get_all_pii_columns()` | ✅ |
| SQ-06 | Hot-reload SchemaCatalog | `orchestrator/schema_catalog.py` | `SchemaCatalog.reload()` | ✅ |
| SQ-07 | Intent query_data - Operation Descriptor | `tools/query_builder_tools.py` | `build_query_with_llm()`, `query_data_tool()` | ✅ |
| SQ-08 | QueryDescriptor - validazione struttura | `tools/query_builder_tools.py` | `QueryDescriptor`, `SafeQueryExecutor.execute()` | ✅ |
| SQ-09 | SafeQueryExecutor - preprocessing filtri | `tools/query_builder_tools.py` | `SafeQueryExecutor._preprocess_filters()` | ✅ |
| SQ-10 | SafeQueryExecutor - filtri datetime-aware | `tools/query_builder_tools.py` | `SafeQueryExecutor._apply_filters()` | ✅ |
| SQ-11 | Regole disambiguazione query_data | `orchestrator/router.py` | `_CLASSIFICATION_PROMPT_TEMPLATE`, `_CLASSIFICATION_PROMPT_FALLBACK` | ✅ |
| SQ-12 | Pagina admin schema metadata | `gchat/template/admin_schema.html`, `gchat/app/main.go` | route GET /admin/schema | ✅ |
| SQ-NF01 | Budget token schema nel prompt (~400 token) | `orchestrator/router.py` | `_build_system_prompt()` | ✅ |
| SQ-NF02 | Diagnostica risultati vuoti | `tools/query_builder_tools.py` | `SafeQueryExecutor.execute()` | ✅ |
| SQ-NF03 | Limite righe risultato (100) | `tools/query_builder_tools.py` | `MAX_RESULT_ROWS`, `QueryDescriptor` | ✅ |
