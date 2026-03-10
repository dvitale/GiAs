# API Endpoints

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `app/api.py`, `app/models.py`

## Requisiti Funzionali

### API-01 Chat sincrono
- **Pattern EARS**: QUANDO il client invia un POST a `/api/v1/chat` con un `ChatMessage` (sender, message, metadata opzionale), il sistema DEVE eseguire il grafo conversazionale e restituire un `ChatResponse` contenente un `ChatResult` con testo, intent, slots, suggestions, execution info e message_id.
- **Status**: IMPLEMENTATO

### API-02 Chat streaming SSE
- **Pattern EARS**: QUANDO il client invia un POST a `/api/v1/chat/stream`, il sistema DEVE restituire una `StreamingResponse` con media_type `text/event-stream`, inviando eventi SSE progressivi (status, node progress) e un evento finale di tipo `SSEFinalEvent` contenente un `ChatResult` completo.
- **Status**: IMPLEMENTATO

### API-03 Parsing NLU
- **Pattern EARS**: QUANDO il client invia un POST a `/api/v1/parse` con un `ParseRequest` (text, metadata opzionale), il sistema DEVE classificare l'intent e restituire un `ParseResult` con intent, confidence reale dal router, slots e flag needs_clarification.
- **Status**: IMPLEMENTATO

### API-04 Feedback utente
- **Pattern EARS**: QUANDO il client invia un POST a `/api/v1/chat/feedback` con un `FeedbackRequest` (message_id, rating 1-5, feedback opzionale), il sistema DEVE aggiornare la riga corrispondente in chat_log impostando rating e user_feedback.
- **Status**: IMPLEMENTATO

### API-05 Feedback loop automatico - rating positivo
- **Pattern EARS**: QUANDO un feedback ha rating >= 4, il sistema DEVE inserire automaticamente la domanda nella tabella domande_risposte come variazione (example_type='variation', source='feedback_auto', active=TRUE) con ON CONFLICT DO NOTHING.
- **Status**: IMPLEMENTATO

### API-06 Feedback loop automatico - rating negativo
- **Pattern EARS**: QUANDO un feedback ha rating <= 2, il sistema DEVE inserire automaticamente la domanda nella tabella domande_risposte come variazione negativa (example_type='variation', source='feedback_negative', active=FALSE) per revisione manuale.
- **Status**: IMPLEMENTATO

### API-07 Feedback loop - esclusione intent non informativi
- **Pattern EARS**: QUANDO l'intent del messaggio e' uno tra greet, goodbye, ask_help, fallback, confirm_show_details, decline_show_details, il sistema DEVE saltare l'inserimento in domande_risposte.
- **Status**: IMPLEMENTATO

### API-08 Reset sessione
- **Pattern EARS**: QUANDO il client invia un POST a `/api/v1/session/reset`, il sistema DEVE cancellare il contesto sessione (slots, workflow, detail_context, dialogue_state) per il sender specificato.
- **Status**: IMPLEMENTATO

### API-09 Health check
- **Pattern EARS**: Il sistema DEVE esporre un endpoint GET `/` che restituisce status "ok", versione e stato del modello.
- **Status**: IMPLEMENTATO

### API-10 Status dettagliato
- **Pattern EARS**: QUANDO il client richiede GET `/status`, il sistema DEVE restituire informazioni su dati caricati (conteggio piani, controlli, osa), backend LLM attivo (modello, modo real/stub), anno corrente, framework e statistiche RAG cache.
- **Status**: IMPLEMENTATO

### API-11 Configurazione
- **Pattern EARS**: QUANDO il client richiede GET `/config`, il sistema DEVE restituire anno corrente e tipo data source configurato.
- **Status**: IMPLEMENTATO

### API-12 Chat log - statistiche aggregate
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/stats` con parametro days, il sistema DEVE restituire totale messaggi, totale errori, tasso errore, tempo medio risposta, P95, sessioni uniche, ASL attive, top 10 intent e top 10 ASL per il periodo specificato.
- **Status**: IMPLEMENTATO

### API-13 Chat log - messaggi recenti
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/recent` con limit (max 200), offset e asl opzionale, il sistema DEVE restituire gli ultimi messaggi con preview risposta troncata a 500 caratteri e conteggio totale per paginazione.
- **Status**: IMPLEMENTATO

### API-14 Chat log - statistiche per ASL
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/by-asl`, il sistema DEVE restituire statistiche raggruppate per ASL (totale, errori, tasso errore, tempo medio, sessioni, intent diversi).
- **Status**: IMPLEMENTATO

### API-15 Chat log - statistiche per intent
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/by-intent`, il sistema DEVE restituire statistiche raggruppate per intent con tool associato, inclusi P95 e tasso errore.
- **Status**: IMPLEMENTATO

### API-16 Chat log - errori recenti
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/errors`, il sistema DEVE restituire gli errori recenti con classificazione automatica per tipo (timeout, connection, database, llm, other).
- **Status**: IMPLEMENTATO

### API-17 Chat log - timeline
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/timeline` con granularita' hour o day, il sistema DEVE restituire conteggi messaggi, errori e tempo medio raggruppati per bucket temporale.
- **Status**: IMPLEMENTATO

### API-18 Chat log - conversazioni utente
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/user-conversations` con codice_fiscale obbligatorio, il sistema DEVE restituire la lista conversazioni raggruppate per session_id con titolo (prima domanda), conteggio messaggi e timestamp inizio/fine.
- **Status**: IMPLEMENTATO

### API-19 Chat log - singola conversazione
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/conversation/{session_id}` con codice_fiscale per verifica ownership, il sistema DEVE restituire tutti i messaggi della conversazione ordinati cronologicamente, filtrando per who LIKE '%codice_fiscale'.
- **Status**: IMPLEMENTATO

### API-20 Qualita' conversazioni
- **Pattern EARS**: QUANDO il client richiede GET `/api/chat-log/quality`, il sistema DEVE eseguire il conversation_monitor per rilevare problemi come fallback loop, domande ripetute, risposte brevi, con filtro opzionale per ASL e severita' minima.
- **Status**: IMPLEMENTATO

### API-21 Monitor intelligente
- **Pattern EARS**: QUANDO il client richiede GET `/api/monitor/intelligent`, il sistema DEVE eseguire un'analisi completa combinando bug detection, root cause analysis, trend analysis, user intent mining e suggerimenti actionable con priorita'.
- **Status**: IMPLEMENTATO

### API-22 Monitor - health score
- **Pattern EARS**: QUANDO il client richiede GET `/api/monitor/health`, il sistema DEVE calcolare uno score complessivo 0-100 basato su error_rate (25%), fallback_rate (25%), latency (20%), trend (15%) e stability (15%), con interpretazione stato (healthy/warning/degraded/critical).
- **Status**: IMPLEMENTATO

### API-23 Admin - domande RAG CRUD
- **Pattern EARS**: Il sistema DEVE esporre endpoint CRUD per la tabella domande_risposte: GET `/api/admin/domande-rag` (lista attive), POST `/api/admin/domande-rag` (crea), DELETE `/api/admin/domande-rag/{id}` (elimina).
- **Status**: IMPLEMENTATO

### API-24 Logging chat in background thread
- **Pattern EARS**: QUANDO una richiesta chat viene completata (sincrona o streaming), il sistema DEVE inserire un record in chat_log in un thread daemon separato (threading.Thread daemon=True) per non bloccare la risposta, includendo ask, intent, answer, who, session_id, asl, slots (JSONB), response_time_ms, error, message_id (UUID) e metadata intent (tool, dataretriever_class, two_phase_resp, sql).
- **Status**: IMPLEMENTATO

### API-25 Modelli Pydantic tipizzati
- **Pattern EARS**: Il sistema DEVE utilizzare modelli Pydantic tipizzati per il contratto API: ChatMessage (sender, message, metadata UserMetadata), ChatResponse (result ChatResult, sender), ChatResult (text, intent, slots, suggestions List[Suggestion], fallback_intents List[FallbackIntentSuggestion], execution ExecutionInfo, needs_clarification, has_more_details, error, message_id), FeedbackRequest (message_id, rating int 1-5, feedback), ParseRequest, ParseResult, SSEFinalEvent.
- **Status**: IMPLEMENTATO

### API-26 Guided learning nel fallback
- **Pattern EARS**: QUANDO l'intent classificato e' "fallback" E il risultato contiene fallback_suggestions E il guided_learning e' abilitato in config.json, il sistema DEVE convertire i suggerimenti in FallbackIntentSuggestion (intent, label, description, emoji, category) nel campo fallback_intents della risposta.
- **Status**: IMPLEMENTATO

### API-27 Admin - schema metadata lista
- **Pattern EARS**: QUANDO il client richiede GET `/api/admin/schema-metadata`, il sistema DEVE restituire la lista di tutte le tabelle dalla tabella schema_metadata con tutti i campi (table_key, table_name, description_it, columns, relationships, valid_values, pii_columns, row_count_approx, is_active).
- **Status**: IMPLEMENTATO

### API-28 Admin - schema metadata dettaglio
- **Pattern EARS**: QUANDO il client richiede GET `/api/admin/schema-metadata/{key}`, il sistema DEVE restituire i dettagli completi della tabella specificata; SE la chiave non esiste, DEVE restituire 404.
- **Status**: IMPLEMENTATO

### API-29 Admin - schema metadata aggiornamento
- **Pattern EARS**: QUANDO il client invia PUT `/api/admin/schema-metadata/{key}`, il sistema DEVE aggiornare i campi modificabili (description_it, columns, valid_values, pii_columns, row_count_approx, is_active) e impostare updated_at a NOW().
- **Status**: IMPLEMENTATO

### API-30 Admin - schema metadata reload
- **Pattern EARS**: QUANDO il client invia POST `/api/admin/schema-metadata/reload`, il sistema DEVE ricaricare il SchemaCatalog singleton e ricostruire il prompt di classificazione del Router, restituendo conferma con source e conteggio tabelle.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### API-NF01 CORS permissivo
- **Pattern EARS**: Il sistema DEVE configurare CORS con allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"].
- **Status**: IMPLEMENTATO

### API-NF02 Timeout esecuzione grafo
- **Pattern EARS**: Il sistema DEVE eseguire il grafo conversazionale con timeout di 50 secondi (GRAPH_INVOKE_TIMEOUT) tramite ThreadPoolExecutor, restituendo un errore timeout se superato.
- **Status**: IMPLEMENTATO

### API-NF03 Singleton ConversationGraph
- **Pattern EARS**: Il sistema DEVE mantenere un'istanza singleton globale di ConversationGraph per evitare la re-inizializzazione di LLMClient e Router ad ogni richiesta.
- **Status**: IMPLEMENTATO

### API-NF04 Precaricamento dati al startup
- **Pattern EARS**: QUANDO il server si avvia (lifespan startup), il sistema DEVE precaricare tutti i dataset da PostgreSQL/CSV in memoria, inizializzare il ConversationGraph singleton e il IntentMetadataService.
- **Status**: IMPLEMENTATO

### API-NF05 Cleanup risorse allo shutdown
- **Pattern EARS**: QUANDO il server si arresta (lifespan shutdown), il sistema DEVE eseguire dispose dell'engine SQLAlchemy per chiudere tutte le connessioni nel pool.
- **Status**: IMPLEMENTATO

### API-NF06 Risoluzione automatica UOC/UOS
- **Pattern EARS**: QUANDO il metadata non contiene uoc o uos ma contiene user_id, il sistema DEVE tentare di risolvere UOC e UOS tramite get_uoc_from_user_id e get_uos_from_user_id dal modulo agents.data.
- **Status**: IMPLEMENTATO

### API-NF07 Validazione workflow context
- **Pattern EARS**: QUANDO viene processata una richiesta chat, il sistema DEVE validare il workflow_context tramite WorkflowValidator.validate_workflow_context, invalidando il workflow se la validazione fallisce.
- **Status**: IMPLEMENTATO

### API-NF08 SSE headers anti-buffering
- **Pattern EARS**: Il sistema DEVE impostare headers Cache-Control: no-cache, Connection: keep-alive e X-Accel-Buffering: no nelle risposte streaming SSE.
- **Status**: IMPLEMENTATO

### API-NF09 Formato who per chat_log
- **Pattern EARS**: Il sistema DEVE comporre il campo who nel formato "asl-user_id-codice_fiscale" concatenando i valori disponibili con separatore trattino, usando "anonymous" se nessun campo e' disponibile.
- **Status**: IMPLEMENTATO
