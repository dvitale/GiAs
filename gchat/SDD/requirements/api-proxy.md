# API Proxy

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/llm_client.go (ProxyChatLogAPI, ProxyAdminAPI, ProxySessionReset), app/main.go (route proxy)

## Requisiti Funzionali

### AP-01 ProxyChatLogAPI Solo GET
- **Pattern EARS**: QUANDO una richiesta GET arriva su `/api/chat-log/*`, il sistema DEVE proxarla al backend Python usando solo il metodo GET, ricostruendo il path dall'indice `/api/chat-log/` nel path originale.
- **Status**: IMPLEMENTATO

### AP-02 ProxyChatLogAPI Route user-conversations
- **Pattern EARS**: QUANDO una richiesta GET arriva su `/gias/webchat/api/chat-log/user-conversations`, il sistema DEVE proxarla a `{BACKEND_URL}/api/chat-log/user-conversations` con i query string parameters.
- **Status**: IMPLEMENTATO

### AP-03 ProxyChatLogAPI Route conversation
- **Pattern EARS**: QUANDO una richiesta GET arriva su `/gias/webchat/api/chat-log/conversation/:sessionId`, il sistema DEVE proxarla a `{BACKEND_URL}/api/chat-log/conversation/{sessionId}` con i query string parameters.
- **Status**: IMPLEMENTATO

### AP-04 ProxyAdminAPI Multi-Method
- **Pattern EARS**: QUANDO una richiesta arriva su `/api/admin/*`, il sistema DEVE supportare i metodi GET, POST e DELETE, e restituire 405 Method Not Allowed per altri metodi.
- **Status**: IMPLEMENTATO

### AP-05 ProxyAdminAPI Content-Disposition Forwarding
- **Pattern EARS**: QUANDO il backend restituisce un header `Content-Disposition`, il sistema DEVE inoltrarlo al client per supportare il download di file.
- **Status**: IMPLEMENTATO

### AP-06 ProxyAdminAPI Domande RAG CRUD
- **Pattern EARS**: Il sistema DEVE proxare le seguenti route admin per la gestione domande RAG: GET `/api/admin/domande-rag`, POST `/api/admin/domande-rag`, DELETE `/api/admin/domande-rag/:id`, POST `/api/admin/domande-rag/reindex`.
- **Status**: IMPLEMENTATO

### AP-07 ProxyAdminAPI Intents
- **Pattern EARS**: QUANDO una richiesta GET arriva su `/api/admin/intents`, il sistema DEVE proxarla al backend per ottenere la lista degli intent disponibili.
- **Status**: IMPLEMENTATO

### AP-08 ProxyAdminAPI Documents
- **Pattern EARS**: Il sistema DEVE proxare GET `/api/admin/documents` per la lista documenti e GET `/api/admin/documents/:filename` per il download di un singolo documento.
- **Status**: IMPLEMENTATO

### AP-09 ProxyAdminAPI Guided Learn
- **Pattern EARS**: QUANDO una richiesta POST arriva su `/api/admin/guided-learn`, il sistema DEVE proxarla al backend per salvare l'associazione domanda-intent appresa dall'utente.
- **Status**: IMPLEMENTATO

### AP-10 ProxySessionReset Backend + Cookie
- **Pattern EARS**: QUANDO una richiesta POST arriva su `/session/reset`, il sistema DEVE proxare la richiesta al backend su `/api/v1/session/reset` E cancellare il cookie di sessione locale.
- **Status**: IMPLEMENTATO

### AP-11 Backend Non Disponibile 502
- **Pattern EARS**: SE il backend non e' raggiungibile durante una chiamata proxy, il sistema DEVE restituire 502 Bad Gateway con messaggio `"Backend not available"`.
- **Status**: IMPLEMENTATO

### AP-12 ProxyAdminAPI Content-Type Default
- **Pattern EARS**: SE il backend non restituisce un header Content-Type, il sistema DEVE impostarlo a `application/json` come default.
- **Status**: IMPLEMENTATO

### AP-13 ProxyChatLogAPI Query String Forwarding
- **Pattern EARS**: QUANDO la richiesta originale contiene query string parameters, il sistema DEVE inoltrarli al backend aggiungendoli all'URL ricostruito.
- **Status**: IMPLEMENTATO

### AP-14 ProxyChatLogAPI Invalid Path
- **Pattern EARS**: SE il path della richiesta non contiene `/api/chat-log/`, il sistema DEVE restituire 400 Bad Request con messaggio `"Invalid API path"`.
- **Status**: IMPLEMENTATO

### AP-15 ProxyAdminAPI Invalid Path
- **Pattern EARS**: SE il path della richiesta non contiene `/api/admin/`, il sistema DEVE restituire 400 Bad Request con messaggio `"Invalid API path"`.
- **Status**: IMPLEMENTATO

### AP-16 ProxyAdminAPI POST Body Forwarding
- **Pattern EARS**: QUANDO il metodo e' POST, il sistema DEVE leggere il body della richiesta originale e inoltrarlo al backend con Content-Type `application/json`.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### AP-NF01 Logging Proxy
- **Pattern EARS**: Il sistema DEVE loggare ogni richiesta proxy con prefisso CHATLOG_PROXY_ o ADMIN_PROXY_ indicando il path originale e l'URL di destinazione.
- **Status**: IMPLEMENTATO

### AP-NF02 Timeout Proxy
- **Pattern EARS**: Il sistema DEVE applicare il timeout configurato in config.json a tutte le richieste proxy verso il backend.
- **Status**: IMPLEMENTATO
