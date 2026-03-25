# Chat Network

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/js/chat.js (sendToServer, sendToServerWithRetry)

## Requisiti Funzionali

### CN-01 Retry con exponential backoff e timeout
- **Pattern EARS**: QUANDO si invia una richiesta al server, il sistema DEVE utilizzare un AbortController con timeout di 75000ms (75 secondi). SE una richiesta fallisce con errore HTTP o di rete, DEVE ritentare fino a 3 volte con exponential backoff (1s, 2s, max 5s). SE l'errore e' di tipo timeout (AbortError o messaggio contenente "Timeout:" o "timeout"), DEVE non ritentare e lanciare l'errore immediatamente.
- **Status**: IMPLEMENTATO
- **Accorpa**: CN-01, CN-02, CN-03, CN-04

### CN-05 Messaggi errore specifici per tipo
- **Pattern EARS**: Il sistema DEVE mostrare messaggi di errore specifici: per timeout client (>75s) "La richiesta ha impiegato troppo tempo. Il sistema potrebbe essere sovraccarico. Riprova tra qualche minuto.", per errore 5xx "Il server non e' disponibile al momento. Riprova piu' tardi.", per errore 408 "Il server ha impiegato troppo tempo a elaborare la richiesta. Riprova con una domanda piu' semplice.", per errore generico "Non riesco a connettermi al server. Verifica la tua connessione e riprova."
- **Status**: IMPLEMENTATO
- **Accorpa**: CN-05, CN-06, CN-07, CN-08

### CN-09 Payload struttura JSON e status indicator
- **Pattern EARS**: QUANDO si invia una richiesta, il sistema DEVE costruire un payload JSON con campi message, sender, asl (da asl_name), asl_id, user_id, codice_fiscale, username dai queryParams. MENTRE il sistema ritenta una richiesta, DEVE aggiornare il typing indicator mostrando "Tentativo N/3..." durante l'invio e "Riconnessione in corso..." durante l'attesa.
- **Status**: IMPLEMENTATO
- **Accorpa**: CN-09, CN-10

### CN-11 Endpoint chat sincrono e streaming
- **Pattern EARS**: QUANDO lo streaming non e' abilitato o non supportato, il sistema DEVE inviare messaggi via POST a `{basePath}/chat` con Content-Type `application/json`. QUANDO lo streaming e' abilitato, DEVE inviare messaggi via POST a `{basePath}/chat/stream` con header Accept `text/event-stream`.
- **Status**: IMPLEMENTATO
- **Accorpa**: CN-11, CN-12

## Requisiti Non Funzionali

### CN-NF01 Timeout Chain
- **Pattern EARS**: Il sistema DEVE mantenere la catena di timeout: JavaScript (75s) > Go Server (60s) > Backend (configurabile), dove il client ha sempre un timeout maggiore del server.
- **Status**: IMPLEMENTATO
