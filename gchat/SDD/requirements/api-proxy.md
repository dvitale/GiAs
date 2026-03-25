# API Proxy

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/llm_client.go (ProxyChatLogAPI, ProxyAdminAPI, ProxySessionReset), app/main.go (route proxy)

## Requisiti Funzionali

### AP-01 ProxyChatLogAPI GET-only
- **Pattern EARS**: QUANDO una richiesta GET arriva su `/api/chat-log/*`, il sistema DEVE proxarla al backend Python usando solo il metodo GET, ricostruendo il path dall'indice `/api/chat-log/` nel path originale. DEVE supportare le route `user-conversations` e `conversation/:sessionId`, inoltrando i query string parameters al backend. SE il path non contiene `/api/chat-log/`, DEVE restituire 400 Bad Request con messaggio `"Invalid API path"`.
- **Status**: IMPLEMENTATO
- **Accorpa**: AP-01, AP-02, AP-03, AP-13, AP-14

### AP-04 ProxyAdminAPI multi-metodo
- **Pattern EARS**: QUANDO una richiesta arriva su `/api/admin/*`, il sistema DEVE supportare i metodi GET, POST e DELETE, restituendo 405 Method Not Allowed per altri metodi. DEVE inoltrare l'header `Content-Disposition` dal backend per supportare download di file. DEVE proxare le route per gestione domande RAG (GET/POST/DELETE `/api/admin/domande-rag`), reindicizzazione (`POST /api/admin/domande-rag/reindex`), intents (`GET /api/admin/intents`), documenti (`GET /api/admin/documents`), e guided learn (`POST /api/admin/guided-learn`). SE il path non contiene `/api/admin/`, DEVE restituire 400 Bad Request. QUANDO il metodo e' POST, DEVE leggere e inoltrare il body con Content-Type `application/json`.
- **Status**: IMPLEMENTATO
- **Accorpa**: AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-15, AP-16

### AP-10 ProxySessionReset Backend + Cookie
- **Pattern EARS**: QUANDO una richiesta POST arriva su `/session/reset`, il sistema DEVE proxare la richiesta al backend su `/api/v1/session/reset` E cancellare il cookie di sessione locale.
- **Status**: IMPLEMENTATO

### AP-11 Gestione errori proxy
- **Pattern EARS**: SE il backend non e' raggiungibile durante una chiamata proxy, il sistema DEVE restituire 502 Bad Gateway con messaggio `"Backend not available"`. SE il backend non restituisce un header Content-Type, il sistema DEVE impostarlo a `application/json` come default.
- **Status**: IMPLEMENTATO
- **Accorpa**: AP-11, AP-12

## Requisiti Non Funzionali

### AP-NF01 Logging Proxy
- **Pattern EARS**: Il sistema DEVE loggare ogni richiesta proxy con prefisso CHATLOG_PROXY_ o ADMIN_PROXY_ indicando il path originale e l'URL di destinazione.
- **Status**: IMPLEMENTATO

### AP-NF02 Timeout Proxy
- **Pattern EARS**: Il sistema DEVE applicare il timeout configurato in config.json a tutte le richieste proxy verso il backend.
- **Status**: IMPLEMENTATO
