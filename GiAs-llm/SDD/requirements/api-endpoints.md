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

### API-05 Feedback loop (background logging, rating, health)
- **Pattern EARS**: QUANDO un feedback ha rating >= 4, il sistema DEVE inserire automaticamente la domanda nella tabella domande_risposte come variazione (example_type='variation', source='feedback_auto', active=TRUE) con ON CONFLICT DO NOTHING. QUANDO un feedback ha rating <= 2, il sistema DEVE inserire la domanda come variazione negativa (example_type='variation', source='feedback_negative', active=FALSE) per revisione manuale. Il sistema DEVE escludere dall'inserimento in domande_risposte gli intent greet, goodbye, ask_help, fallback, confirm_show_details, decline_show_details.
- **Status**: IMPLEMENTATO
- **Accorpa**: API-05, API-06, API-07

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

### API-12 Chat log analytics per ASL/intent
- **Pattern EARS**: Il sistema DEVE esporre endpoint di analytics per chat log: GET `/api/chat-log/stats` con parametro days (totale messaggi, errori, tasso errore, tempo medio, P95, sessioni uniche, ASL attive, top 10 intent e ASL); GET `/api/chat-log/recent` con limit (max 200), offset e asl opzionale (ultimi messaggi con preview troncata a 500 caratteri e conteggio totale); GET `/api/chat-log/by-asl` (statistiche raggruppate per ASL: totale, errori, tasso errore, tempo medio, sessioni, intent diversi); GET `/api/chat-log/by-intent` (statistiche raggruppate per intent con tool associato, P95 e tasso errore).
- **Status**: IMPLEMENTATO
- **Accorpa**: API-12, API-13, API-14, API-15

### API-16 Chat log timeline e conversazioni
- **Pattern EARS**: Il sistema DEVE esporre: GET `/api/chat-log/errors` (errori recenti con classificazione automatica per tipo: timeout, connection, database, llm, other); GET `/api/chat-log/timeline` con granularita' hour o day (conteggi messaggi, errori e tempo medio per bucket temporale); GET `/api/chat-log/user-conversations` con codice_fiscale obbligatorio (lista conversazioni raggruppate per session_id con titolo, conteggio messaggi e timestamp); GET `/api/chat-log/conversation/{session_id}` con codice_fiscale per verifica ownership (tutti i messaggi ordinati cronologicamente).
- **Status**: IMPLEMENTATO
- **Accorpa**: API-16, API-17, API-18, API-19

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

### API-25 Modelli Pydantic, guided learning e singleton engine
- **Pattern EARS**: Il sistema DEVE utilizzare modelli Pydantic tipizzati per il contratto API: ChatMessage, ChatResponse, ChatResult (con text, intent, slots, suggestions, fallback_intents, execution, needs_clarification, has_more_details, error, message_id), FeedbackRequest, ParseRequest, ParseResult, SSEFinalEvent. QUANDO l'intent classificato e' "fallback" E il risultato contiene fallback_suggestions E il guided_learning e' abilitato in config.json, il sistema DEVE convertire i suggerimenti in FallbackIntentSuggestion nel campo fallback_intents della risposta.
- **Status**: IMPLEMENTATO
- **Accorpa**: API-25, API-26

### API-27 Admin schema metadata CRUD
- **Pattern EARS**: Il sistema DEVE esporre endpoint per la gestione schema metadata: GET `/api/admin/schema-metadata` (lista tutte le tabelle con tutti i campi); GET `/api/admin/schema-metadata/{key}` (dettaglio completo, 404 se non esiste); PUT `/api/admin/schema-metadata/{key}` (aggiornamento campi modificabili con updated_at a NOW()); POST `/api/admin/schema-metadata/reload` (ricarica SchemaCatalog singleton e ricostruzione prompt classificazione Router).
- **Status**: IMPLEMENTATO
- **Accorpa**: API-27, API-28, API-29, API-30

## Requisiti Non Funzionali

### API-NF01 Modelli Pydantic, guided learning e singleton engine
- **Pattern EARS**: Il sistema DEVE configurare CORS con allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]. Il sistema DEVE mantenere un'istanza singleton globale di ConversationGraph per evitare la re-inizializzazione. Il sistema DEVE eseguire il grafo conversazionale con timeout di 50 secondi (GRAPH_INVOKE_TIMEOUT) tramite ThreadPoolExecutor.
- **Status**: IMPLEMENTATO
- **Accorpa**: API-NF01, API-NF02, API-NF03

### API-NF04 Precaricamento, background thread e UOC/UOS
- **Pattern EARS**: QUANDO il server si avvia (lifespan startup), il sistema DEVE precaricare tutti i dataset, inizializzare il ConversationGraph singleton e il IntentMetadataService. QUANDO il server si arresta (lifespan shutdown), il sistema DEVE eseguire dispose dell'engine SQLAlchemy. QUANDO il metadata non contiene uoc o uos ma contiene user_id, il sistema DEVE tentare di risolvere UOC e UOS tramite get_uoc_from_user_id e get_uos_from_user_id.
- **Status**: IMPLEMENTATO
- **Accorpa**: API-NF04, API-NF05, API-NF06

### API-NF07 Validazione workflow context
- **Pattern EARS**: QUANDO viene processata una richiesta chat, il sistema DEVE validare il workflow_context tramite WorkflowValidator.validate_workflow_context, invalidando il workflow se la validazione fallisce.
- **Status**: IMPLEMENTATO

### API-NF08 SSE headers anti-buffering
- **Pattern EARS**: Il sistema DEVE impostare headers Cache-Control: no-cache, Connection: keep-alive e X-Accel-Buffering: no nelle risposte streaming SSE.
- **Status**: IMPLEMENTATO

### API-NF09 Formato who per chat_log
- **Pattern EARS**: Il sistema DEVE comporre il campo who nel formato "asl-user_id-codice_fiscale" concatenando i valori disponibili con separatore trattino, usando "anonymous" se nessun campo e' disponibile.
- **Status**: IMPLEMENTATO

### API-10 Campi GPS in UserMetadata
- **Pattern EARS**: Il modello `UserMetadata` in `app/models.py` DEVE includere i campi opzionali `latitude: Optional[float]`, `longitude: Optional[float]`, `gps_accuracy_m: Optional[float]` per ricevere coordinate GPS dal device dell'utente.
- **Status**: IMPLEMENTATO
