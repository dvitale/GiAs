# Pipeline LangGraph

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/graph.py`, `orchestrator/dialogue_state.py`

## Requisiti Funzionali

### LG-001 Struttura del grafo
- **Pattern EARS**: Il sistema DEVE implementare un grafo LangGraph con i nodi: classify, dialogue_manager, ask_user, fallback_tool, response_generator, e tutti i tool registrati in TOOL_REGISTRY.
- **Status**: IMPLEMENTATO

### LG-002 Entry point
- **Pattern EARS**: Il sistema DEVE utilizzare il nodo "classify" come entry point del grafo.
- **Status**: IMPLEMENTATO

### LG-003 Edge classify -> dialogue_manager
- **Pattern EARS**: QUANDO il nodo classify completa l'esecuzione, il sistema DEVE passare sempre al nodo dialogue_manager.
- **Status**: IMPLEMENTATO

### LG-004 Conditional edges post dialogue_manager
- **Pattern EARS**: QUANDO il dialogue_manager completa, il sistema DEVE instradare verso "ask_user" (se action="ask_user"), "fallback_tool" (se action="fallback"), o il tool specifico (se action="execute" e target_tool presente in TOOL_REGISTRY).
- **Status**: IMPLEMENTATO

### LG-005 Ask user termina il turno
- **Pattern EARS**: QUANDO il nodo ask_user viene eseguito, il sistema DEVE impostare final_response con la domanda di chiarimento, needs_clarification=True, e terminare il grafo (edge verso END).
- **Status**: IMPLEMENTATO

### LG-006 Fallback tool -> response_generator
- **Pattern EARS**: QUANDO il nodo fallback_tool completa, il sistema DEVE passare al nodo response_generator.
- **Status**: IMPLEMENTATO

### LG-007 Tool -> response_generator -> END
- **Pattern EARS**: QUANDO un qualsiasi tool registrato completa, il sistema DEVE passare al nodo response_generator, il quale termina verso END.
- **Status**: IMPLEMENTATO

### LG-008 ConversationState tipizzato
- **Pattern EARS**: Il sistema DEVE definire ConversationState come TypedDict con i campi: message, metadata, intent, slots, tool_output, final_response, needs_clarification, error, has_more_details, detail_context, _classification_confidence, _intent_candidates, dialogue_state, dm_action, dm_target_tool, dm_question, response_context, execution_path, node_timings, execution_start_ms, suggestions, fallback_suggestions, fallback_phase, fallback_count, fallback_selected_category, e campi workflow legacy.
- **Status**: IMPLEMENTATO

### LG-009 Execution path tracking
- **Pattern EARS**: MENTRE il grafo esegue, il sistema DEVE registrare ogni nodo visitato nella lista execution_path dello state.
- **Status**: IMPLEMENTATO

### LG-010 Node timings tracking
- **Pattern EARS**: MENTRE il grafo esegue, il sistema DEVE misurare la durata di ogni nodo in millisecondi e registrarla nel dizionario node_timings dello state.
- **Status**: IMPLEMENTATO

### LG-011 SSE node_timing event
- **Pattern EARS**: QUANDO un nodo completa e un event_callback e' presente, il sistema DEVE emettere un evento SSE di tipo "node_timing" con node, duration_ms.
- **Status**: IMPLEMENTATO

### LG-012 SSE status event su classify
- **Pattern EARS**: QUANDO il nodo classify inizia e un event_callback e' presente, il sistema DEVE emettere un evento SSE di tipo "status" con messaggio "Analizzando la richiesta...".
- **Status**: IMPLEMENTATO

### LG-013 SSE reasoning event su classify
- **Pattern EARS**: QUANDO il nodo classify identifica un intent e un event_callback e' presente, il sistema DEVE emettere un evento SSE di tipo "reasoning" con il nome dell'intent rilevato.
- **Status**: IMPLEMENTATO

### LG-014 Menu disambiguazione shortcut
- **Pattern EARS**: QUANDO il messaggio utente ha lunghezza <= 3 caratteri e il dialogue_state contiene intent_candidates, il sistema DEVE interpretare il messaggio come selezione numerica dal menu, selezionando il candidato corrispondente e saltando la classificazione standard.
- **Status**: IMPLEMENTATO

### LG-015 Fallback selection parsing
- **Pattern EARS**: QUANDO lo state contiene fallback_suggestions e l'utente invia un messaggio, il sistema DEVE tentare di parsare la selezione come scelta intent (tipo "intent") o scelta categoria (tipo "category") prima della classificazione standard.
- **Status**: IMPLEMENTATO

### LG-016 Slot carry-forward guard
- **Pattern EARS**: QUANDO il router segnala needs_clarification e la sessione contiene slot precedenti, il sistema DEVE eseguire carry-forward degli slot SOLO se l'intent corrente corrisponde a _session_last_intent, per evitare "memory bleed" tra topic diversi.
- **Status**: IMPLEMENTATO

### LG-017 Topic change detection nel dialogue_manager
- **Pattern EARS**: QUANDO l'intent corrente differisce da _session_last_intent e l'intent corrente non e' "fallback", il sistema DEVE resettare slots, confirmed_intent, confirmed_strategy, confirmed_strategy_id e missing_slots nel DialogueState.
- **Status**: IMPLEMENTATO

### LG-018 Confidence source detection
- **Pattern EARS**: QUANDO il router fornisce _classification_confidence, il sistema DEVE usare il valore reale; ALTRIMENTI il sistema DEVE usare un'euristica (0.90 senza clarification, 0.55 con clarification, 0.30 per fallback).
- **Status**: IMPLEMENTATO

### LG-019 Raw message type detection
- **Pattern EARS**: QUANDO il dialogue_manager riceve un messaggio, il sistema DEVE classificare il tipo tra: "oppure", "refinement", "vague_request", "continuation", "specific_query" usando le funzioni _is_oppure, _is_refinement, _is_vague.
- **Status**: IMPLEMENTATO

### LG-020 Tool wrapper con event_callback injection
- **Pattern EARS**: Il sistema DEVE wrappare ogni tool registrato per iniettare automaticamente event_callback e tracciare timing di esecuzione.
- **Status**: IMPLEMENTATO

### LG-021 Response context propagation
- **Pattern EARS**: QUANDO il response_generator produce un response_context, il sistema DEVE propagarlo nel dialogue_state come last_response_context per supportare risoluzione anaforica nei turni successivi.
- **Status**: IMPLEMENTATO

### LG-022 Fallback loop prevention
- **Pattern EARS**: QUANDO il fallback_count supera 3, il sistema DEVE interrompere il ciclo di fallback, resettare tutti i contatori e mostrare il testo di aiuto completo con le operazioni disponibili.
- **Status**: IMPLEMENTATO

### LG-023 Fallback con approssimazioni successive
- **Pattern EARS**: Il sistema DEVE supportare un fallback a fasi (phase 1, 2, 3) con selezione per categoria, usando FallbackRecoveryEngine con lazy init.
- **Status**: IMPLEMENTATO

### LG-024 Clarification per slot mancanti
- **Pattern EARS**: QUANDO l'intent richiede slot mancanti e il tool corrente e' il fallback, il sistema DEVE generare un messaggio di chiarimento usando SLOT_PROMPTS con prompt specifici per ciascun slot.
- **Status**: IMPLEMENTATO

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

### LG-NF-001 Singleton grafo
- **Pattern EARS**: Il sistema DEVE compilare il grafo LangGraph una sola volta al momento dell'init di ConversationGraph e riusare l'istanza compilata per tutte le invocazioni.
- **Status**: IMPLEMENTATO

### LG-NF-002 Event callback cleanup
- **Pattern EARS**: Il sistema DEVE ripulire _event_callback a None nel blocco finally di run() per evitare memory leak tra invocazioni.
- **Status**: IMPLEMENTATO

### LG-NF-003 Backwards compatibility workflow legacy
- **Pattern EARS**: Il sistema DEVE mantenere i campi workflow legacy (workflow_stage, workflow_id, workflow_nonce, workflow_type, workflow_context, pending_question, available_options, workflow_history, accumulated_filters) in input e output per compatibilita' con il vecchio protocollo.
- **Status**: IMPLEMENTATO
