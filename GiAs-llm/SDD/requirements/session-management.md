# Gestione Sessioni

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `app/session_manager.py`

## Requisiti Funzionali

### SM-001 Sessioni in-memory con TTL
- **Pattern EARS**: Il sistema DEVE mantenere sessioni conversazionali in-memory con TTL di 300 secondi (5 minuti). QUANDO una sessione supera il TTL, il sistema DEVE considerarla non valida e restituire contesto vuoto.
- **Status**: IMPLEMENTATO

### SM-002 Thread-safety tramite lock
- **Pattern EARS**: Il sistema DEVE garantire accesso thread-safe allo store sessioni tramite threading.Lock per tutte le operazioni di lettura e scrittura.
- **Status**: IMPLEMENTATO

### SM-003 Pulizia automatica sessioni scadute
- **Pattern EARS**: QUANDO il contatore richieste raggiunge un multiplo di 100 (_CLEANUP_EVERY_N_REQUESTS), il sistema DEVE eseguire pulizia delle sessioni scadute da piu' di 2x TTL (600 secondi), rimuovendole dallo store.
- **Status**: IMPLEMENTATO

### SM-004 Topic change detection
- **Pattern EARS**: QUANDO l'intent corrente e' diverso dal last_intent in sessione e l'intent corrente non e' un CONTINUATION_INTENT (confirm_show_details, decline_show_details, fallback), il sistema DEVE rilevare un cambio topic e resettare last_response_context e detail_context dalla sessione.
- **Status**: IMPLEMENTATO

### SM-005 Propagazione stato conversazionale e metadata enrichment
- **Pattern EARS**: Il sistema DEVE propagare nella sessione i seguenti campi dal risultato del grafo: last_intent, last_slots, conversation_summary (formato "intent={intent}, slots={slots}"), timestamp, dialogue_state, last_response_context. QUANDO viene recuperato il contesto sessione, il sistema DEVE costruire un dizionario metadata_enrichment contenente (se presenti e sessione valida): _session_last_intent, _session_last_slots, _session_summary, _session_last_response_context, _fallback_suggestions, _fallback_phase, _fallback_count, _fallback_selected_category.
- **Status**: IMPLEMENTATO
- **Accorpa**: SM-005, SM-006

### SM-007 Contesto detail, fallback recovery e workflow in sessione
- **Pattern EARS**: QUANDO il risultato ha has_more_details=True e detail_context, il sistema DEVE salvare il detail_context nella sessione; su confirm/decline, DEVE rimuoverlo. QUANDO il risultato contiene fallback_suggestions, il sistema DEVE salvare nella sessione: fallback_suggestions, fallback_phase, fallback_count, fallback_selected_category; quando l'intent non e' "fallback", DEVE rimuovere tutti i campi fallback. QUANDO il risultato contiene un workflow_id, il sistema DEVE salvare un workflow_context strutturato; quando non ha workflow_id, DEVE rimuovere il workflow_context.
- **Status**: IMPLEMENTATO
- **Accorpa**: SM-007, SM-008, SM-009

### SM-010 Invalidazione selettiva workflow e reset completo
- **Pattern EARS**: Il sistema DEVE esporre un metodo `invalidate_workflow()` che rimuove solo il workflow_context di un sender senza toccare il resto della sessione. Il sistema DEVE esporre un metodo `clear_session()` che rimuove completamente la sessione per un sender, loggando l'operazione.
- **Status**: IMPLEMENTATO
- **Accorpa**: SM-010, SM-011

### SM-012 Contesto risposta per risoluzione anaforica
- **Pattern EARS**: QUANDO viene aggiornata la sessione, il sistema DEVE estrarre il last_response_context da: (1) dialogue_state.last_response_context, oppure (2) result.response_context. Il contesto viene preservato tra turni a meno di un topic change.
- **Status**: IMPLEMENTATO

### SM-013 SessionContext come NamedTuple immutabile
- **Pattern EARS**: Il sistema DEVE restituire il contesto sessione come NamedTuple (SessionContext) con campi: detail_context, workflow_context, dialogue_state, metadata_enrichment, session_valid, session_timestamp, raw_session.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### SM-NF-001 Isolamento dati e logging sessione
- **Pattern EARS**: QUANDO viene recuperata una sessione, il sistema DEVE restituire una copia dei dati (.copy()) per evitare modifiche concorrenti. Il sistema DEVE loggare con prefisso "[Session]" le operazioni significative: salvataggio/pulizia detail_context, topic change, pulizia sessioni scadute, rimozione sessione.
- **Status**: IMPLEMENTATO
- **Accorpa**: SM-NF-001, SM-NF-002
