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

### LP-04 HandleChat Parse Request
- **Pattern EARS**: QUANDO una richiesta POST arriva a `/chat`, il sistema DEVE parsare il body JSON in una struttura `ChatRequest` con campi message, sender, asl, asl_id, user_id, codice_fiscale, username, uoc e uos.
- **Status**: IMPLEMENTATO

### LP-05 HandleChat Default Sender
- **Pattern EARS**: SE il campo sender nella richiesta e' vuoto, il sistema DEVE impostarlo a `"user"`.
- **Status**: IMPLEMENTATO

### LP-06 HandleChat Health Check
- **Pattern EARS**: QUANDO si gestisce una richiesta chat, il sistema DEVE eseguire un health check del backend prima di inviare il messaggio, restituendo 503 Service Unavailable se il backend non e' disponibile.
- **Status**: IMPLEMENTATO

### LP-07 HandleChat Priorita' ASL
- **Pattern EARS**: QUANDO si costruisce il contesto per il backend, il sistema DEVE dare priorita' al campo `asl` (nome ASL) rispetto ad `asl_id`, includendo solo uno dei due.
- **Status**: IMPLEMENTATO

### LP-08 HandleChat Concatenazione Risposte
- **Pattern EARS**: QUANDO il backend risponde con successo, il sistema DEVE estrarre il testo dalla risposta V1, le suggestions e i fallback_intents, e restituirli al client in un `ChatResponse`.
- **Status**: IMPLEMENTATO

### LP-09 HandleChatStream SSE Headers
- **Pattern EARS**: QUANDO si avvia una risposta streaming, il sistema DEVE impostare gli header `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive` e `X-Accel-Buffering: no`.
- **Status**: IMPLEMENTATO

### LP-10 HandleChatStream Event Channel
- **Pattern EARS**: QUANDO si avvia lo streaming, il sistema DEVE creare un canale di eventi SSE con buffer di 10 elementi e avviare la comunicazione con il backend in una goroutine separata.
- **Status**: IMPLEMENTATO

### LP-11 HandleChatStream Flush Immediato
- **Pattern EARS**: QUANDO un evento SSE e' ricevuto dal backend, il sistema DEVE scriverlo al client nel formato `event: {type}\ndata: {json}\n\n` e fare flush immediato del buffer.
- **Status**: IMPLEMENTATO

### LP-12 SendToLLMStreamV1 SSE Parsing
- **Pattern EARS**: QUANDO si riceve uno stream SSE dal backend, il sistema DEVE parsare le linee `event:` e `data:`, riconoscere l'evento `final` come evento V1 con campo `result`, e convertire suggestions e fallback_intents nel formato compatibile con il frontend.
- **Status**: IMPLEMENTATO

### LP-13 CheckLLMServerHealth Cache Successo
- **Pattern EARS**: QUANDO l'health check ha successo, il sistema DEVE cachare il risultato positivo per 30 secondi usando un RWMutex.
- **Status**: IMPLEMENTATO

### LP-14 CheckLLMServerHealth Cache Fallimento
- **Pattern EARS**: QUANDO l'health check fallisce, il sistema DEVE cachare il risultato negativo per 5 secondi per fail-fast.
- **Status**: IMPLEMENTATO

### LP-15 UOC Auto-Resolve da CSV
- **Pattern EARS**: QUANDO il campo UOC non e' fornito nella richiesta e il user_id e' presente, il sistema DEVE cercare il record nel CSV del personale e usare il campo `DescrizioneAreaStrutturaComplessa`.
- **Status**: IMPLEMENTATO

### LP-16 UOC Fallback da Descrizione
- **Pattern EARS**: SE il campo `DescrizioneAreaStrutturaComplessa` e' vuoto o uguale a `"NULL"`, il sistema DEVE estrarre la UOC dal secondo segmento del campo `Descrizione` (separato da `->`) come fallback.
- **Status**: IMPLEMENTATO

### LP-17 UOS Auto-Resolve da CSV
- **Pattern EARS**: QUANDO il campo UOS non e' fornito nella richiesta e il record personale ha UOS non vuota, il sistema DEVE utilizzare la UOS dal record CSV.
- **Status**: IMPLEMENTATO

### LP-18 Sanitizzazione PII Codice Fiscale
- **Pattern EARS**: QUANDO si loggano dati sensibili, il sistema DEVE troncare il codice fiscale mostrando solo i primi 3 e l'ultimo carattere con asterischi intermedi (formato `XXX***X`).
- **Status**: IMPLEMENTATO

### LP-19 Sanitizzazione PII User ID
- **Pattern EARS**: QUANDO si loggano dati sensibili, il sistema DEVE mascherare completamente il user_id con `***`.
- **Status**: IMPLEMENTATO

### LP-20 Debug Log File
- **Pattern EARS**: DOVE la configurazione `log.enable_debug` e' attiva, il sistema DEVE scrivere i comandi curl e i dati delle richieste (con PII sanitizzati) in un file di debug separato.
- **Status**: IMPLEMENTATO

### LP-21 Debug Log Rotazione
- **Pattern EARS**: QUANDO il file di debug supera 10MB, il sistema DEVE ruotare il file rinominandolo con suffisso `.old`.
- **Status**: IMPLEMENTATO

### LP-22 generateCurlCommand
- **Pattern EARS**: QUANDO si genera un comando curl di debug, il sistema DEVE costruire un comando completo con URL, header e payload, con escape delle singole apici nel payload per compatibilita' shell.
- **Status**: IMPLEMENTATO

### LP-23 HandleDebugChat Dual Call
- **Pattern EARS**: QUANDO si gestisce una richiesta debug, il sistema DEVE eseguire sia la chiamata Parse (`/api/v1/parse`) sia la chiamata Chat (`/api/v1/chat`) e combinare i risultati in una `DebugChatResponse`.
- **Status**: IMPLEMENTATO

### LP-24 HandleDebugChat Default Sender
- **Pattern EARS**: SE il sender nella richiesta debug e' vuoto, il sistema DEVE impostarlo a `"debug_user"`.
- **Status**: IMPLEMENTATO

### LP-25 ExecutionPath Priorita'
- **Pattern EARS**: QUANDO si costruisce la risposta debug, il sistema DEVE usare l'execution_path dal backend V1 se disponibile, altrimenti generare un path simulato basato sull'intent tramite `determineExecutionPath`.
- **Status**: IMPLEMENTATO

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
