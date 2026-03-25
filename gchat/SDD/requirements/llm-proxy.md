# LLM Proxy

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/llm_client.go, app/config.go

## Requisiti Funzionali

### LP-01 SendToLLMV1 Invio Messaggio
- **Pattern EARS**: QUANDO un messaggio deve essere inviato al backend, il sistema DEVE costruire un `NativeChatMessage` con sender, message e metadata tipizzato (`NativeUserMetadata`), e inviarlo via POST a `{LLM_URL}/api/v1/chat`.
- **Status**: IMPLEMENTATO

### LP-02 NativeUserMetadata Struttura
- **Pattern EARS**: Il sistema DEVE includere nel metadata i campi opzionali: ASL, ASLID, UserID, CodiceFiscale, Username, UOC e UOS.
- **Status**: IMPLEMENTATO

### LP-03 Timeout HTTP Configurabile
- **Pattern EARS**: Il sistema DEVE applicare il timeout configurato in config.json (`llm_server.timeout`) a tutte le richieste HTTP verso il backend.
- **Status**: IMPLEMENTATO

### LP-04 HandleChat request processing
- **Pattern EARS**: QUANDO una richiesta POST arriva a `/chat`, il sistema DEVE: (1) parsare il body JSON in una struttura `ChatRequest` con campi message, sender, asl, asl_id, user_id, codice_fiscale, username, uoc e uos, (2) impostare sender a `"user"` se vuoto, (3) eseguire un health check del backend restituendo 503 se non disponibile, (4) dare priorita' al campo `asl` rispetto ad `asl_id`, (5) estrarre il testo dalla risposta V1 con suggestions e fallback_intents e restituirli al client in un `ChatResponse`.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-04, LP-05, LP-06, LP-07, LP-08

### LP-09 HandleChatStream SSE
- **Pattern EARS**: QUANDO si avvia una risposta streaming, il sistema DEVE: (1) impostare gli header `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive` e `X-Accel-Buffering: no`, (2) creare un canale di eventi SSE con buffer di 10 elementi e avviare la comunicazione in una goroutine separata, (3) scrivere ogni evento al client nel formato `event: {type}\ndata: {json}\n\n` con flush immediato, (4) parsare le linee `event:` e `data:` dal backend, riconoscere l'evento `final` e convertire suggestions e fallback_intents nel formato frontend.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-09, LP-10, LP-11, LP-12

### LP-13 Health check con cache adattiva
- **Pattern EARS**: QUANDO l'health check ha successo, il sistema DEVE cachare il risultato positivo per 30 secondi usando un RWMutex. QUANDO l'health check fallisce, il sistema DEVE cachare il risultato negativo per 5 secondi per fail-fast.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-13, LP-14

### LP-15 UOC/UOS auto-resolve da CSV
- **Pattern EARS**: QUANDO il campo UOC non e' fornito nella richiesta e il user_id e' presente, il sistema DEVE cercare il record nel CSV del personale e usare il campo `DescrizioneAreaStrutturaComplessa`. SE il campo e' vuoto o uguale a `"NULL"`, DEVE estrarre la UOC dal secondo segmento del campo `Descrizione` (separato da `->`) come fallback. QUANDO il campo UOS non e' fornito e il record personale ha UOS non vuota, DEVE utilizzare la UOS dal record CSV.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-15, LP-16, LP-17

### LP-18 Sanitizzazione PII nei log
- **Pattern EARS**: QUANDO si loggano dati sensibili, il sistema DEVE troncare il codice fiscale mostrando solo i primi 3 e l'ultimo carattere con asterischi intermedi (formato `XXX***X`), e DEVE mascherare completamente il user_id con `***`.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-18, LP-19

### LP-20 Debug logging con rotazione
- **Pattern EARS**: DOVE la configurazione `log.enable_debug` e' attiva, il sistema DEVE scrivere i comandi curl e i dati delle richieste (con PII sanitizzati) in un file di debug separato. QUANDO il file supera 10MB, DEVE ruotare il file rinominandolo con suffisso `.old`. Il comando curl generato DEVE includere URL, header e payload con escape delle singole apici.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-20, LP-21, LP-22

### LP-23 HandleDebugChat dual call
- **Pattern EARS**: QUANDO si gestisce una richiesta debug, il sistema DEVE eseguire sia la chiamata Parse (`/api/v1/parse`) sia la chiamata Chat (`/api/v1/chat`) e combinare i risultati in una `DebugChatResponse`. SE il sender e' vuoto, DEVE impostarlo a `"debug_user"`. DEVE usare l'execution_path dal backend V1 se disponibile, altrimenti generare un path simulato basato sull'intent tramite `determineExecutionPath`.
- **Status**: IMPLEMENTATO
- **Accorpa**: LP-23, LP-24, LP-25

### LP-26 HandlePredefinedQuestions
- **Pattern EARS**: QUANDO un client richiede GET `/api/predefined-questions`, il sistema DEVE restituire la lista di domande predefinite dalla configurazione JSON.
- **Status**: IMPLEMENTATO

### LP-27 Gestione Errori HTTP
- **Pattern EARS**: SE la richiesta JSON e' malformata, il sistema DEVE restituire 400 Bad Request. SE il backend non risponde, il sistema DEVE restituire 503 Service Unavailable. SE la comunicazione fallisce, il sistema DEVE restituire 500 Internal Server Error.
- **Status**: IMPLEMENTATO

### LP-28 Logging Strutturato LLM
- **Pattern EARS**: Il sistema DEVE loggare ogni fase della comunicazione con il backend usando prefissi strutturati: LLM_V1_REQUEST, LLM_V1_SEND, LLM_V1_SUCCESS, LLM_V1_ERROR, LLM_HEALTH_CHECK, LLM_HEALTH_OK, LLM_HEALTH_CACHE, CHAT_REQUEST, CHAT_STREAM_REQUEST, etc.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### LP-NF01 Concorrenza Health Check
- **Pattern EARS**: Il sistema DEVE utilizzare `sync.RWMutex` per proteggere la cache dello health check da accessi concorrenti.
- **Status**: IMPLEMENTATO

### LP-NF02 Configurazione Default
- **Pattern EARS**: SE il file config.json non esiste o e' malformato, il sistema DEVE utilizzare una configurazione di default con URL `http://localhost:5005` e timeout 30 secondi.
- **Status**: IMPLEMENTATO
