# Chat Network

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/js/chat.js (sendToServer, sendToServerWithRetry)

## Requisiti Funzionali

### CN-01 AbortController Timeout 75s
- **Pattern EARS**: QUANDO si invia una richiesta al server, il sistema DEVE utilizzare un AbortController con timeout di 75000ms (75 secondi), maggiore del timeout del server Go (60s).
- **Status**: IMPLEMENTATO

### CN-02 Retry 3 Tentativi
- **Pattern EARS**: SE una richiesta fallisce con errore HTTP o di rete, il sistema DEVE ritentare fino a 3 volte con exponential backoff.
- **Status**: IMPLEMENTATO

### CN-03 Exponential Backoff
- **Pattern EARS**: QUANDO si ritenta una richiesta, il sistema DEVE attendere con backoff esponenziale: 1s al primo retry, 2s al secondo, con un massimo di 5s.
- **Status**: IMPLEMENTATO

### CN-04 No Retry su Timeout
- **Pattern EARS**: SE l'errore e' di tipo timeout (AbortError o messaggio contenente "Timeout:" o "timeout"), il sistema DEVE non ritentare e lanciare l'errore immediatamente.
- **Status**: IMPLEMENTATO

### CN-05 Messaggio Errore Timeout Client
- **Pattern EARS**: SE la richiesta viene abortita per timeout client (>75s), il sistema DEVE mostrare: "La richiesta ha impiegato troppo tempo. Il sistema potrebbe essere sovraccarico. Riprova tra qualche minuto."
- **Status**: IMPLEMENTATO

### CN-06 Messaggio Errore Server 5xx
- **Pattern EARS**: SE il server restituisce un errore 5xx, il sistema DEVE mostrare: "Il server non e' disponibile al momento. Riprova piu' tardi."
- **Status**: IMPLEMENTATO

### CN-07 Messaggio Errore Server 408
- **Pattern EARS**: SE il server restituisce un errore 408, il sistema DEVE mostrare: "Il server ha impiegato troppo tempo a elaborare la richiesta. Riprova con una domanda piu' semplice."
- **Status**: IMPLEMENTATO

### CN-08 Messaggio Errore Generico
- **Pattern EARS**: SE la connessione fallisce per motivi non specifici, il sistema DEVE mostrare: "Non riesco a connettermi al server. Verifica la tua connessione e riprova."
- **Status**: IMPLEMENTATO

### CN-09 Payload Struttura
- **Pattern EARS**: QUANDO si invia una richiesta, il sistema DEVE costruire un payload JSON con campi: message, sender, asl (da asl_name), asl_id, user_id, codice_fiscale, username dai queryParams.
- **Status**: IMPLEMENTATO

### CN-10 Status Indicator Retry
- **Pattern EARS**: MENTRE il sistema ritenta una richiesta, il sistema DEVE aggiornare il typing indicator mostrando "Tentativo N/3..." durante l'invio e "Riconnessione in corso..." durante l'attesa.
- **Status**: IMPLEMENTATO

### CN-11 Endpoint Chat Sincrono
- **Pattern EARS**: QUANDO lo streaming non e' abilitato o non supportato, il sistema DEVE inviare messaggi via POST a `{basePath}/chat` con Content-Type `application/json`.
- **Status**: IMPLEMENTATO

### CN-12 Endpoint Chat Streaming
- **Pattern EARS**: QUANDO lo streaming e' abilitato, il sistema DEVE inviare messaggi via POST a `{basePath}/chat/stream` con header Accept `text/event-stream`.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### CN-NF01 Timeout Chain
- **Pattern EARS**: Il sistema DEVE mantenere la catena di timeout: JavaScript (75s) > Go Server (60s) > Backend (configurabile), dove il client ha sempre un timeout maggiore del server.
- **Status**: IMPLEMENTATO
