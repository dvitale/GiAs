# Requisiti Non Funzionali Trasversali

**Componente**: Frontend (gchat)
**Provenienza**: Consolidamento da requisiti cross-file, 2026-03-16

## Requisiti Non Funzionali Trasversali

### XNF-FE-01 Tema persistente localStorage cross-page
- **Pattern EARS**: Il sistema DEVE persistere la preferenza tema (light/dark) in localStorage e ripristinarla al caricamento su tutte le pagine (index, history, debug, debug_langgraph, analytics, monitor, admin_rag), evitando flash of unstyled content con inizializzazione precoce.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: TS-NF01 (theme-system), DT-NF01 (debug-tools), HP-NF01 (history-page)

### XNF-FE-02 HTML escape prevenzione XSS
- **Pattern EARS**: Il sistema DEVE applicare HTML escape su tutti i dati dinamici inseriti nel DOM (messaggi utente, risposte, parametri query, dati da API) per prevenire attacchi XSS.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: AM-24 (admin-analytics-monitor), HP-14 (history-page), CU-26 (chat-ui), SR-15 (server-routing)

### XNF-FE-03 Query params propagazione cross-page
- **Pattern EARS**: Il sistema DEVE estrarre i parametri query (user_id, asl_id, asl_name, codice_fiscale, username) e propagarli a tutti i template e link di navigazione tra pagine.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: HP-13 (history-page), DT-11 (debug-tools), AM-25 (admin-analytics-monitor), SR-20 (server-routing)

### XNF-FE-04 Logging strutturato con prefissi
- **Pattern EARS**: Il sistema DEVE utilizzare logging strutturato con prefissi specifici per componente (INDEX_, DEBUG_, LANGGRAPH_DEBUG_, ANALYTICS_, MONITOR_, HISTORY_, ADMIN_RAG_, LLM_, SESSION_, PERSONALE_CACHE_) per facilitare il debug e il monitoraggio.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: SR-22 (server-routing), AP-NF01 (api-proxy), LP-28 (llm-proxy), SM-NF02 (session-management), PD-NF01 (personnel-data)

### XNF-FE-05 Timeout configurabile richieste backend
- **Pattern EARS**: Il sistema DEVE applicare timeout configurabili alle richieste verso il backend Python, con valori default appropriati per ogni tipo di operazione (chat: 75s, health check: 5s, API: configurabile).
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: AP-NF02 (api-proxy), LP-03 (llm-proxy), CN-NF01 (chat-network)

### XNF-FE-06 Concorrenza sicura RWMutex
- **Pattern EARS**: Il sistema DEVE garantire accesso thread-safe alle risorse condivise (cache personale, health check cache) tramite sync.RWMutex con pattern double-check lock.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: PD-NF02 (personnel-data), LP-NF01 (llm-proxy)

### XNF-FE-07 Responsive layout breakpoints
- **Pattern EARS**: Il sistema DEVE adattare il layout alle dimensioni dello schermo con breakpoint a 768px (mobile: sidebar drawer, layout singola colonna) e 1200px (desktop: sidebar fissa, grid multi-colonna).
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: CU-NF02 (chat-ui), AM-NF02 (admin-analytics-monitor), DT-10 (debug-tools)

### XNF-FE-08 Palette dark admin consistente
- **Pattern EARS**: Le pagine admin/analytics/monitor DEVONO utilizzare esclusivamente tema dark con palette dedicata (--bg-primary: #0f172a, gradiente indaco/slate) e variabili CSS consistenti tra le pagine.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: AM-NF01 (admin-analytics-monitor), AM-NF03 (admin-analytics-monitor)
