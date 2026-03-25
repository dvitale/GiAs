# Pipeline LangGraph

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/graph.py`, `orchestrator/dialogue_state.py`

## Requisiti Funzionali

### LG-001 Struttura grafo con nodi e entry point
- **Pattern EARS**: Il sistema DEVE implementare un grafo LangGraph con i nodi: classify, dialogue_manager, ask_user, fallback_tool, response_generator, e tutti i tool registrati in TOOL_REGISTRY. Il sistema DEVE utilizzare il nodo "classify" come entry point del grafo. QUANDO il nodo classify completa l'esecuzione, il sistema DEVE passare sempre al nodo dialogue_manager. QUANDO il dialogue_manager completa, il sistema DEVE instradare verso "ask_user" (se action="ask_user"), "fallback_tool" (se action="fallback"), o il tool specifico (se action="execute" e target_tool presente in TOOL_REGISTRY).
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-001, LG-002, LG-003, LG-004

### LG-005 Conditional edges e routing tool
- **Pattern EARS**: QUANDO il nodo ask_user viene eseguito, il sistema DEVE impostare final_response con la domanda di chiarimento, needs_clarification=True, e terminare il grafo (edge verso END). QUANDO il nodo fallback_tool completa, il sistema DEVE passare al nodo response_generator. QUANDO un qualsiasi tool registrato completa, il sistema DEVE passare al nodo response_generator, il quale termina verso END.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-005, LG-006, LG-007

### LG-008 ConversationState tipizzato
- **Pattern EARS**: Il sistema DEVE definire ConversationState come TypedDict con i campi: message, metadata, intent, slots, tool_output, final_response, needs_clarification, error, has_more_details, detail_context, _classification_confidence, _intent_candidates, dialogue_state, dm_action, dm_target_tool, dm_question, response_context, execution_path, node_timings, execution_start_ms, suggestions, fallback_suggestions, fallback_phase, fallback_count, fallback_selected_category, e campi workflow legacy.
- **Status**: IMPLEMENTATO

### LG-009 Execution path e node timings tracking
- **Pattern EARS**: MENTRE il grafo esegue, il sistema DEVE registrare ogni nodo visitato nella lista execution_path dello state e misurare la durata di ogni nodo in millisecondi nel dizionario node_timings dello state.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-009, LG-010

### LG-011 SSE events (node_timing, status, reasoning)
- **Pattern EARS**: QUANDO un nodo completa e un event_callback e' presente, il sistema DEVE emettere un evento SSE di tipo "node_timing" con node e duration_ms. QUANDO il nodo classify inizia, il sistema DEVE emettere un evento SSE di tipo "status" con messaggio "Analizzando la richiesta...". QUANDO il nodo classify identifica un intent, il sistema DEVE emettere un evento SSE di tipo "reasoning" con il nome dell'intent rilevato.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-011, LG-012, LG-013

### LG-014 Menu shortcut e fallback parsing
- **Pattern EARS**: QUANDO il messaggio utente ha lunghezza <= 3 caratteri e il dialogue_state contiene intent_candidates, il sistema DEVE interpretare il messaggio come selezione numerica dal menu. QUANDO lo state contiene fallback_suggestions e l'utente invia un messaggio, il sistema DEVE tentare di parsare la selezione come scelta intent o scelta categoria prima della classificazione standard.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-014, LG-015

### LG-016 Slot carry-forward e topic change guards
- **Pattern EARS**: QUANDO il router segnala needs_clarification e la sessione contiene slot precedenti, il sistema DEVE eseguire carry-forward degli slot SOLO se l'intent corrente corrisponde a _session_last_intent, per evitare "memory bleed" tra topic diversi. QUANDO l'intent corrente differisce da _session_last_intent e non e' "fallback", il sistema DEVE resettare slots, confirmed_intent, confirmed_strategy, confirmed_strategy_id e missing_slots nel DialogueState.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-016, LG-017

### LG-018 Tool wrapper e response context propagation
- **Pattern EARS**: Il sistema DEVE wrappare ogni tool registrato per iniettare automaticamente event_callback e tracciare timing di esecuzione. QUANDO il response_generator produce un response_context, il sistema DEVE propagarlo nel dialogue_state come last_response_context per supportare risoluzione anaforica nei turni successivi.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-018, LG-019 (ex LG-020, LG-021)

### LG-020 Fallback loop prevention e slot clarification
- **Pattern EARS**: QUANDO il fallback_count supera 3, il sistema DEVE interrompere il ciclo di fallback, resettare tutti i contatori e mostrare il testo di aiuto completo. Il sistema DEVE supportare un fallback a fasi (phase 1, 2, 3) con selezione per categoria, usando FallbackRecoveryEngine con lazy init. QUANDO l'intent richiede slot mancanti e il tool corrente e' il fallback, il sistema DEVE generare un messaggio di chiarimento usando SLOT_PROMPTS.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-020, LG-021, LG-022 (ex LG-022, LG-023, LG-024)

### LG-025 Caso speciale ask_establishment_history
- **Pattern EARS**: QUANDO l'intent e' ask_establishment_history, il sistema DEVE richiedere almeno UNO tra num_registrazione, numero_riconoscimento, partita_iva, ragione_sociale (logica OR anziche' AND).
- **Status**: IMPLEMENTATO

### LG-026 Total execution time
- **Pattern EARS**: Il sistema DEVE calcolare e restituire il tempo totale di esecuzione del grafo (total_execution_ms) nella risposta.
- **Status**: IMPLEMENTATO

### LG-027 Dialogue state passthrough
- **Pattern EARS**: Il sistema DEVE accettare un dialogue_state dal turno precedente in input e restituire il dialogue_state aggiornato in output per supportare conversazioni multi-turno stateless (HTTP).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### LG-NF-001 Singleton grafo, event cleanup, backwards compat
- **Pattern EARS**: Il sistema DEVE compilare il grafo LangGraph una sola volta al momento dell'init e riusare l'istanza compilata per tutte le invocazioni. Il sistema DEVE ripulire _event_callback a None nel blocco finally di run() per evitare memory leak. Il sistema DEVE mantenere i campi workflow legacy (workflow_stage, workflow_id, workflow_nonce, workflow_type, workflow_context, pending_question, available_options, workflow_history, accumulated_filters) in input e output per compatibilita' con il vecchio protocollo.
- **Status**: IMPLEMENTATO
- **Accorpa**: LG-NF-001, LG-NF-002, LG-NF-003
