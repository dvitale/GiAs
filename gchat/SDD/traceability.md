# Matrice di Tracciabilita' — Frontend (gchat)

**Generata**: 2026-03-16
**Requisiti totali**: 147
**Tracciati**: 147 | **Non tracciati**: 0

## Legenda

- ✅ TRACCIATO — requisito mappato a codice specifico
- ⚠️ NON TRACCIATO — requisito non associabile a codice specifico

## server-routing

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SR-01 | Base path /gias/webchat per reverse proxy | `app/main.go` | `main()` | ✅ |
| SR-02 | Route pagine HTML con template data injection | `app/main.go` | `main()` (handler pagine) | ✅ |
| SR-10 | Servizio file statici /static | `app/main.go` | `api.Static("/static", "./statics")` | ✅ |
| SR-11 | Template function json | `app/main.go` | `r.SetFuncMap` in `main()` | ✅ |
| SR-12 | Caricamento template LoadHTMLGlob | `app/main.go` | `r.LoadHTMLGlob("template/*")` | ✅ |
| SR-13 | Gestione dati utente e hierarchy HTML | `app/main.go` | `loadUserData()`, `buildHierarchyHTML()` | ✅ |
| SR-16 | Anno dinamico dal backend con fallback | `app/config.go` | `GetCurrentYearFromServer()` | ✅ |
| SR-19 | Query params estrazione e propagazione | `app/main.go` | `parseQueryParams()`, handler pagine | ✅ |
| SR-21 | Porta server configurabile | `app/main.go` | `main()` (config.Server.Port) | ✅ |
| SR-22 | Logging richieste pagine con prefissi | `app/main.go` | handler pagine (log.Printf) | ✅ |
| SR-NF01 | Framework web Gin | `app/main.go` | `gin.Default()` in `main()` | ✅ |
| SR-NF02 | Timeout 5s recupero anno | `app/config.go` | `GetCurrentYearFromServer()` | ✅ |

## session-management

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SM-01 | Session store cookie-based gias_session | `app/main.go` | `main()` (sessions.Sessions) | ✅ |
| SM-02 | TTL sessione 300 secondi | `app/session.go` | `SessionTTL` const | ✅ |
| SM-03 | Configurazione sicura cookie (path, HttpOnly, SameSite) | `app/main.go` | `main()` (store.Options) | ✅ |
| SM-06 | Cookie Secure (parziale) | `app/main.go` | `main()` (store.Options) | ✅ |
| SM-07 | Chiave segreta hardcoded | `app/main.go` | `main()` (cookie.NewStore) | ✅ |
| SM-08 | SessionMiddleware verifica TTL | `app/session.go` | `SessionMiddleware()` | ✅ |
| SM-09 | SaveUserSession parametri non vuoti | `app/session.go` | `SaveUserSession()` | ✅ |
| SM-10 | MergeSessionParams con priorita' e parsing | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-14 | Double-write pattern lettura+scrittura | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-NF01 | Type assertion sicura | `app/session.go` | `GetUserSession()` (getString helper) | ✅ |
| SM-NF02 | Logging sessione con prefissi | `app/session.go` | `SaveUserSession()`, `SessionMiddleware()` | ✅ |

## llm-proxy

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| LP-01 | SendToLLMV1 invio messaggio | `app/llm_client.go` | `SendToLLMV1()` | ✅ |
| LP-02 | NativeUserMetadata struttura | `app/llm_client.go` | `NativeUserMetadata` struct | ✅ |
| LP-03 | Timeout HTTP configurabile | `app/llm_client.go` | `SendToLLMV1()` (http.Client Timeout) | ✅ |
| LP-04 | HandleChat request processing completo | `app/llm_client.go` | `HandleChat()` | ✅ |
| LP-09 | HandleChatStream SSE completo | `app/llm_client.go` | `HandleChatStream()` | ✅ |
| LP-13 | Health check con cache adattiva 30s/5s | `app/llm_client.go` | `CheckLLMServerHealth()` | ✅ |
| LP-15 | UOC/UOS auto-resolve da CSV | `app/llm_client.go` | `HandleChat()` (GetPersonaleByUserID) | ✅ |
| LP-18 | Sanitizzazione PII nei log | `app/llm_client.go` | `sanitizePII()` | ✅ |
| LP-20 | Debug logging con rotazione 10MB | `app/llm_client.go` | `logCurlCommand()` | ✅ |
| LP-23 | HandleDebugChat dual call Parse+Chat | `app/llm_client.go` | `HandleDebugChat()` | ✅ |
| LP-26 | HandlePredefinedQuestions | `app/llm_client.go` | `HandlePredefinedQuestions()` | ✅ |
| LP-27 | Gestione errori HTTP 400/503/500 | `app/llm_client.go` | `HandleChat()` | ✅ |
| LP-28 | Logging strutturato LLM con prefissi | `app/llm_client.go` | `SendToLLMV1()`, `HandleChat()`, etc. | ✅ |
| LP-NF01 | Concorrenza health check sync.RWMutex | `app/llm_client.go` | `healthCheckCache` struct | ✅ |
| LP-NF02 | Configurazione default fallback | `app/config.go` | `getDefaultConfig()` | ✅ |

## api-proxy

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| AP-01 | ProxyChatLogAPI GET-only con route e query forwarding | `app/llm_client.go` | `ProxyChatLogAPI()` | ✅ |
| AP-04 | ProxyAdminAPI multi-metodo con CRUD e forwarding | `app/llm_client.go` | `ProxyAdminAPI()` | ✅ |
| AP-10 | ProxySessionReset backend + cookie | `app/llm_client.go` | `ProxySessionReset()` | ✅ |
| AP-11 | Gestione errori proxy 502 e Content-Type default | `app/llm_client.go` | `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |
| AP-NF01 | Logging proxy con prefissi | `app/llm_client.go` | `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |
| AP-NF02 | Timeout proxy configurabile | `app/llm_client.go` | `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |

## chat-ui

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| CU-01 | Classe ChatBot assegnata a window.chatBot | `statics/js/chat.js` | `ChatBot` class, `window.chatBot = new ChatBot()` | ✅ |
| CU-02 | Welcome screen e transizione a chat | `statics/js/chat.js` | `ChatBot` constructor, `switchToChatMode()` | ✅ |
| CU-04 | Sender ID generazione unica | `statics/js/chat.js` | `ChatBot` constructor (this.senderId) | ✅ |
| CU-05 | Greeting dinamico per ora | `statics/js/chat.js` | `ChatBot` constructor (getTimeBasedGreeting) | ✅ |
| CU-06 | Quick actions da API con click e Ctrl+Click | `statics/js/chat.js` | `loadPredefinedQuestions()`, `renderQuickActions()` | ✅ |
| CU-09 | Streaming SSE con fallback sincrono | `statics/js/chat.js` | `sendMessage()`, `sendMessageStreaming()`, `handleSSEEvent()` | ✅ |
| CU-10 | Thinking indicator con fade-out | `statics/js/chat.js` | `sendMessageStreaming()` (thinkingDiv) | ✅ |
| CU-12 | Download conversazione TXT | `statics/js/chat.js` | `downloadConversation()` | ✅ |
| CU-13 | Download escluso per fallback | `statics/js/chat.js` | `isFallbackMessage()` | ✅ |
| CU-14 | Liste collassabili oltre 10 elementi | `statics/js/chat.js` | `formatMessage()` (COLLAPSE_THRESHOLD) | ✅ |
| CU-15 | Guided learning buttons con auto-dismiss | `statics/js/chat.js` | `createGuidedLearningContainer()` | ✅ |
| CU-17 | Question links [[text]] e document links [text](url) | `statics/js/chat.js` | `formatMessage()` (regex replace) | ✅ |
| CU-19 | Session reset (+ Nuova Chat) | `statics/js/chat.js` | `resetSession()` | ✅ |
| CU-20 | Suggestions chip cliccabili | `statics/js/chat.js` | `createSuggestionsContainer()` | ✅ |
| CU-21 | Shortcut navigazione debug via logo (Ctrl+Click, Shift+Click) | `statics/js/chat.js` | `ChatBot` constructor (logo click handler) | ✅ |
| CU-23 | Accessibilita' role=log aria-live | `template/index.html` | messages container attributes | ✅ |
| CU-24 | Scroll-to-bottom button visibile/nascosto >100px | `statics/js/chat.js` | `scrollToBottom()`, scroll event listener | ✅ |
| CU-26 | Rendering markdown-to-HTML con escape | `statics/js/chat.js` | `formatMessage()` (escapeHtml, headers, bold, lists, fields) | ✅ |
| CU-31 | Input comportamento (typing, resize, send, enter) | `statics/js/chat.js` | `showTypingIndicator()`, `autoResizeTextarea()`, keydown handler | ✅ |
| CU-35 | Window variables injection nel template | `template/index.html` | script block (window.basePath, etc.) | ✅ |
| CU-36 | History link con query params | `template/index.html` | link cronologia (JS href build) | ✅ |
| CU-38 | Download nome file gias-{timestamp}.txt | `statics/js/chat.js` | `downloadConversation()` | ✅ |
| CU-39 | Payload ASL priorita' asl_name | `statics/js/chat.js` | `sendToServer()` (payload build) | ✅ |
| CU-40 | Guided learning disabilita bottoni | `statics/js/chat.js` | `createGuidedLearningContainer()` (disabled) | ✅ |
| CU-42 | EscapeHtml utility | `statics/js/chat.js` | `escapeHtml()` | ✅ |
| CU-NF01 | Smooth scroll | `statics/js/chat.js` | `scrollToBottom()` (behavior: smooth) | ✅ |
| CU-NF02 | Responsive layout <768px e <480px | `statics/css/style.css` | media queries 768px, 480px | ✅ |

## chat-network

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| CN-01 | Retry con exponential backoff e timeout 75s | `statics/js/chat.js` | `sendToServer()`, `sendToServerWithRetry()` | ✅ |
| CN-05 | Messaggi errore specifici per tipo | `statics/js/chat.js` | `sendMessage()`, `sendToServer()` (error handling) | ✅ |
| CN-09 | Payload struttura JSON e status indicator retry | `statics/js/chat.js` | `sendToServer()` (payload build), `sendToServerWithRetry()` | ✅ |
| CN-11 | Endpoint chat sincrono e streaming | `statics/js/chat.js` | `sendToServer()`, `sendMessageStreaming()` | ✅ |
| CN-NF01 | Timeout chain JS>Go>Backend | `statics/js/chat.js` | `sendToServer()` (75s timeout) | ✅ |

## theme-system

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| TS-01 | Sistema temi light/dark con CSS variables | `statics/css/style.css` | `body.dark-theme` selettore | ✅ |
| TS-03 | Persistenza e ripristino tema da localStorage | `statics/js/chat.js` | `toggleTheme()`, `initializeTheme()` | ✅ |
| TS-05 | Transizioni, icona toggle e header gradients | `statics/css/style.css` | transition rules, `.sun-icon`, `.moon-icon`, `.header` | ✅ |
| TS-08 | Tema consistente tra pagine | `statics/js/chat.js` | `initializeTheme()` (+history.js `initTheme()`) | ✅ |
| TS-09 | Admin/Analytics/Monitor dark-only | `template/analytics.html` | CSS inline (palette dark, +monitor.html, admin_rag.html) | ✅ |
| TS-10 | Dark theme ASL badge viola | `statics/css/style.css` | `body.dark-theme .asl-badge` | ✅ |
| TS-NF01 | No flash of unstyled content | `statics/js/chat.js` | `initializeTheme()` in constructor | ✅ |

## history-page

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| HP-01 | Codice fiscale obbligatorio | `statics/js/history.js` | `ChatHistory` constructor | ✅ |
| HP-02 | Caricamento conversazioni API | `statics/js/history.js` | `loadConversations()` | ✅ |
| HP-03 | Paginazione con load more (limit 50) | `statics/js/history.js` | `ChatHistory` constructor, `loadMore()` | ✅ |
| HP-05 | Ricerca con debounce 300ms e filtro client-side | `statics/js/history.js` | constructor (setTimeout), `filterConversations()` | ✅ |
| HP-07 | Formattazione date relative e risposte | `statics/js/history.js` | `formatDate()`, `renderMessages()` | ✅ |
| HP-08 | Caricamento messaggi conversazione | `statics/js/history.js` | `loadConversation()` | ✅ |
| HP-10 | Layout sidebar responsive (300px desktop, drawer mobile) | `statics/css/style.css` | `.history-sidebar`, media query | ✅ |
| HP-13 | Propagazione query params e sicurezza HTML | `template/history.html` | link navigation, `escapeHtml()`, `escapeJs()` | ✅ |
| HP-15 | Conversazione attiva highlight | `statics/js/history.js` | `renderList()` (active class) | ✅ |
| HP-NF01 | Tema condiviso da localStorage | `statics/js/history.js` | `initTheme()` | ✅ |

## debug-tools

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| DT-01 | Dual call Parse + Chat | `app/llm_client.go` | `HandleDebugChat()` | ✅ |
| DT-02 | Pannelli debug (intent, entities, agents, state) | `statics/js/debug_langgraph.js` | `sendToDebugServer()` | ✅ |
| DT-06 | Mappings intent/tool-agent con descrizioni e categorie | `statics/js/debug_langgraph.js` | `intentDescriptions`, `categoryColors`, `pathToAgent` | ✅ |
| DT-08 | Execution path con priorita' e fallback simulato | `statics/js/debug_langgraph.js` | `sendToDebugServer()`, `determineExecutionPath()` | ✅ |
| DT-10 | Responsive grid debug 2 colonne >1200px | `template/debug.html` | CSS grid layout (inline styles) | ✅ |
| DT-11 | Query params preservazione tra pagine | `template/debug.html` | nav links (queryParams, +debug_langgraph.html) | ✅ |
| DT-12 | Architecture badge framework+model | `template/debug.html` | header badge (framework + llmModel) | ✅ |
| DT-13 | Timeout 75s debug AbortController | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (AbortController 75000) | ✅ |
| DT-14 | LangGraph SVG visualizer con tab e history | `statics/js/debug_langgraph_visualizer.js` | `LangGraphDebugVisualizer`, tab system, query history | ✅ |
| DT-17 | Sender ID debug stabile per sessione | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` constructor (senderId) | ✅ |
| DT-18 | Initial state loading da queryParams | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` constructor | ✅ |
| DT-19 | User context display nell'header | `template/debug.html` | header user info section | ✅ |
| DT-20 | Dark theme debug page | `template/debug.html` | CSS dark theme styles (inline) | ✅ |
| DT-NF01 | Tema persistente da localStorage | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` constructor | ✅ |

## admin-analytics-monitor

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| AM-01 | Dashboard analytics con metriche, grafici e tabelle | `template/analytics.html` | summary cards, top intents, top ASL (JS inline) | ✅ |
| AM-02 | Analytics auto-refresh 60s | `template/analytics.html` | setInterval 60000 (JS inline) | ✅ |
| AM-03 | Analytics chiamate dirette backend | `template/analytics.html` | fetch(backendUrl + ...) (JS inline) | ✅ |
| AM-04 | Analytics timeline bar chart CSS | `template/analytics.html` | timeline chart div (JS inline) | ✅ |
| AM-09 | Monitor problemi, severita' e distribuzione tipi | `template/monitor.html` | problem/severity definitions, cards, distribution (JS inline) | ✅ |
| AM-12 | Monitor filtri periodo/ASL/severita' e auto-refresh 120s | `template/monitor.html` | filter controls, setInterval 120000 (JS inline) | ✅ |
| AM-14 | Monitor card, raccomandazioni, tabella e riepilogo | `template/monitor.html` | problem cards, recommendations, table, summary (JS inline) | ✅ |
| AM-19 | Admin RAG dark-only con CRUD e reindicizzazione | `template/admin_rag.html` | CSS dark, form, table, documents, reindex (JS inline) | ✅ |
| AM-23 | Nessuna autenticazione admin | `app/main.go` | handler `/admin/rag` (no auth) | ✅ |
| AM-24 | HTML escape dati dinamici anti-XSS | `template/analytics.html` | escapeHtml function (+monitor.html, admin_rag.html) | ✅ |
| AM-25 | Navigazione cross-page con queryParams | `template/analytics.html` | nav menu links (+monitor.html, debug.html) | ✅ |
| AM-26 | Analytics ASL filter dropdown dinamico | `template/analytics.html` | ASL dropdown (JS inline) | ✅ |
| AM-NF01 | Palette dark consistente | `template/analytics.html` | CSS variables (--bg-primary, +monitor.html, admin_rag.html) | ✅ |
| AM-NF02 | Responsive panels grid 2 col >1000px | `template/analytics.html` | CSS grid layout (+monitor.html) | ✅ |
| AM-NF03 | Scrollbar personalizzata dark | `template/admin_rag.html` | CSS ::-webkit-scrollbar (+monitor.html) | ✅ |

## speech-to-text

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| ST-01 | Feature flag transcription.enabled | `app/config.go` | `TranscriptionConfig` struct | ✅ |
| ST-02 | Comunicazione Whisper (endpoint, timeout, lingua, cleanup) | `app/transcribe.go` | `TranscribeHandler()`, `callWhisper()` | ✅ |
| ST-06 | Profiling logging per fase | `app/transcribe.go` | `TranscribeHandler()` (PROFILE_*) | ✅ |
| ST-07 | Mic button pulsating red recording | `statics/css/style.css` | `.mic-button.recording` | ✅ |
| ST-08 | Toast notification trascrizione | `statics/js/chat.js` | transcription toast handler | ✅ |
| ST-NF01 | Profiling e diagnostica trascrizione (multipart, trim) | `app/transcribe.go` | `callWhisper()` (multipart.Writer, strings.TrimSpace) | ✅ |

## personnel-data

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| PD-01 | CSV loading con parsing PersonaleRecord completo | `app/personale.go` | `LoadPersonaleData()` | ✅ |
| PD-02 | Cache basata su ModTime file | `app/personale.go` | `LoadPersonaleData()` | ✅ |
| PD-03 | Double-check lock con sync.RWMutex | `app/personale.go` | `LoadPersonaleData()` | ✅ |
| PD-08 | GetPersonaleByUserID lookup | `app/personale.go` | `GetPersonaleByUserID()` | ✅ |
| PD-NF01 | Logging e concorrenza cache personale | `app/personale.go` | `LoadPersonaleData()` (log.Printf, sync.RWMutex) | ✅ |

## pwa-geolocation

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| PG-01 | Configurazione PWA manifest, meta tag e Service Worker | `statics/manifest.webmanifest`, `template/index.html`, `statics/sw.js` | — | ✅ |
| PG-04 | Service Worker caching, offline fallback e install banner | `statics/sw.js`, `statics/offline.html`, `statics/js/chat.js` | fetch handler, `ChatBot.initPWAInstall()` | ✅ |
| PG-NF01 | Caricamento < 2s da cache | `statics/sw.js` | cache-first strategy | ✅ |
| PG-07 | GPS on-demand con coordinate nel payload | `statics/js/chat.js` | `ChatBot.acquireGPS()`, `ChatBot.sendToServer()` | ✅ |
| PG-09 | Funzionamento senza GPS, indicatore, struct Go e inoltro | `statics/js/chat.js`, `app/llm_client.go` | `acquireGPS()`, `updateGPSIndicator()`, `ChatRequest`, `NativeUserMetadata` | ✅ |
| PG-13 | GPS non in sessione cookie e non loggato (GDPR) | `app/llm_client.go` | `HandleChat()` context map, log.Printf | ✅ |

## cross-cutting-nf

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| XNF-FE-01 | Tema persistente localStorage cross-page | `statics/js/chat.js` | `initializeTheme()` (+history.js, debug_langgraph.js) | ✅ |
| XNF-FE-02 | HTML escape prevenzione XSS | `statics/js/chat.js` | `escapeHtml()` (+analytics.html, monitor.html, admin_rag.html) | ✅ |
| XNF-FE-03 | Query params propagazione cross-page | `app/main.go` | `parseQueryParams()`, handler pagine, template nav links | ✅ |
| XNF-FE-04 | Logging strutturato con prefissi | `app/main.go` | handler pagine (+llm_client.go, session.go, personale.go) | ✅ |
| XNF-FE-05 | Timeout configurabile richieste backend | `app/llm_client.go` | `SendToLLMV1()`, `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |
| XNF-FE-06 | Concorrenza sicura RWMutex | `app/personale.go` | `personaleCache` (+llm_client.go `healthCheckCache`) | ✅ |
| XNF-FE-07 | Responsive layout breakpoints 768px/1200px | `statics/css/style.css` | media queries (+analytics.html, debug.html) | ✅ |
| XNF-FE-08 | Palette dark admin consistente | `template/analytics.html` | CSS variables (--bg-primary, +monitor.html, admin_rag.html) | ✅ |
