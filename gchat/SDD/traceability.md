# Matrice di Tracciabilita' — Frontend (gchat)

**Generata**: 2026-03-09
**Requisiti totali**: 242
**Tracciati**: 242 | **Non tracciati**: 0

## Legenda

- ✅ TRACCIATO — requisito mappato a codice specifico
- ⚠️ NON TRACCIATO — requisito non associabile a codice specifico

## server-routing

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SR-01 | Base path /gias/webchat per reverse proxy | `app/main.go` | `main()` | ✅ |
| SR-02 | Pagina principale GET | `app/main.go` | `indexHandler` (closure in `main()`) | ✅ |
| SR-03 | Pagina principale POST | `app/main.go` | `indexHandler` (closure in `main()`) | ✅ |
| SR-04 | Pagina debug GET | `app/main.go` | handler anonimo `/debug` | ✅ |
| SR-05 | Pagina LangGraph debugger GET | `app/main.go` | handler anonimo `/debug/langgraph` | ✅ |
| SR-06 | Pagina analytics GET | `app/main.go` | handler anonimo `/analytics` | ✅ |
| SR-07 | Pagina monitor GET | `app/main.go` | handler anonimo `/monitor` | ✅ |
| SR-08 | Pagina history GET | `app/main.go` | handler anonimo `/history` | ✅ |
| SR-09 | Pagina admin RAG GET | `app/main.go` | handler anonimo `/admin/rag` | ✅ |
| SR-10 | Servizio file statici /static | `app/main.go` | `api.Static("/static", "./statics")` | ✅ |
| SR-11 | Template function json | `app/main.go` | `r.SetFuncMap` in `main()` | ✅ |
| SR-12 | Caricamento template LoadHTMLGlob | `app/main.go` | `r.LoadHTMLGlob("template/*")` | ✅ |
| SR-13 | loadUserData da CSV per user_id | `app/main.go` | `loadUserData()` | ✅ |
| SR-14 | Priorita' asl_name su CSV | `app/main.go` | `loadUserData()` | ✅ |
| SR-15 | buildHierarchyHTML con HTML escape | `app/main.go` | `buildHierarchyHTML()` | ✅ |
| SR-16 | Anno dinamico dal backend | `app/config.go` | `GetCurrentYearFromServer()` | ✅ |
| SR-17 | Fallback anno dinamico | `app/main.go` | `indexHandler` (blocco if err != nil) | ✅ |
| SR-18 | Sostituzione anno nel welcome message | `app/main.go` | `indexHandler` (strings.ReplaceAll) | ✅ |
| SR-19 | parseQueryParams estrazione parametri | `app/main.go` | `parseQueryParams()` | ✅ |
| SR-20 | Propagazione queryParams ai template | `app/main.go` | `indexHandler` + tutti gli handler pagina | ✅ |
| SR-21 | Porta server configurabile | `app/main.go` | `main()` (config.Server.Port) | ✅ |
| SR-22 | Logging richieste pagine con prefissi | `app/main.go` | handler pagine (log.Printf) | ✅ |
| SR-NF01 | Framework web Gin | `app/main.go` | `gin.Default()` in `main()` | ✅ |
| SR-NF02 | Timeout 5s recupero anno | `app/config.go` | `GetCurrentYearFromServer()` | ✅ |

## session-management

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| SM-01 | Session store cookie-based gias_session | `app/main.go` | `main()` (sessions.Sessions) | ✅ |
| SM-02 | TTL sessione 300 secondi | `app/session.go` | `SessionTTL` const | ✅ |
| SM-03 | Cookie path /gias/webchat | `app/main.go` | `main()` (store.Options) | ✅ |
| SM-04 | Cookie HttpOnly true | `app/main.go` | `main()` (store.Options) | ✅ |
| SM-05 | Cookie SameSite Lax | `app/main.go` | `main()` (store.Options) | ✅ |
| SM-06 | Cookie Secure (parziale) | `app/main.go` | `main()` (store.Options) | ✅ |
| SM-07 | Chiave segreta hardcoded | `app/main.go` | `main()` (cookie.NewStore) | ✅ |
| SM-08 | SessionMiddleware verifica TTL | `app/session.go` | `SessionMiddleware()` | ✅ |
| SM-09 | SaveUserSession parametri non vuoti | `app/session.go` | `SaveUserSession()` | ✅ |
| SM-10 | MergeSessionParams priorita' POST>Query>Session | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-11 | MergeSessionParams POST JSON | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-12 | MergeSessionParams POST Form | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-13 | Username ignorato da POST form | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-14 | Double-write pattern lettura+scrittura | `app/session.go` | `MergeSessionParams()` | ✅ |
| SM-NF01 | Type assertion sicura | `app/session.go` | `GetUserSession()` (getString helper) | ✅ |
| SM-NF02 | Logging sessione con prefissi | `app/session.go` | `SaveUserSession()`, `SessionMiddleware()` | ✅ |

## llm-proxy

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| LP-01 | SendToLLMV1 invio messaggio | `app/llm_client.go` | `SendToLLMV1()` | ✅ |
| LP-02 | NativeUserMetadata struttura | `app/llm_client.go` | `NativeUserMetadata` struct | ✅ |
| LP-03 | Timeout HTTP configurabile | `app/llm_client.go` | `SendToLLMV1()` (http.Client Timeout) | ✅ |
| LP-04 | HandleChat parse request | `app/llm_client.go` | `HandleChat()` | ✅ |
| LP-05 | HandleChat default sender "user" | `app/llm_client.go` | `HandleChat()` | ✅ |
| LP-06 | HandleChat health check | `app/llm_client.go` | `HandleChat()` (CheckLLMServerHealth) | ✅ |
| LP-07 | HandleChat priorita' ASL | `app/llm_client.go` | `HandleChat()` (context build) | ✅ |
| LP-08 | HandleChat concatenazione risposte | `app/llm_client.go` | `HandleChat()` (v1Resp.Result.Text) | ✅ |
| LP-09 | HandleChatStream SSE headers | `app/llm_client.go` | `HandleChatStream()` | ✅ |
| LP-10 | HandleChatStream event channel buffer 10 | `app/llm_client.go` | `HandleChatStream()` | ✅ |
| LP-11 | HandleChatStream flush immediato | `app/llm_client.go` | `HandleChatStream()` (flusher.Flush) | ✅ |
| LP-12 | SendToLLMStreamV1 SSE parsing | `app/llm_client.go` | `SendToLLMStreamV1()` | ✅ |
| LP-13 | CheckLLMServerHealth cache successo 30s | `app/llm_client.go` | `CheckLLMServerHealth()` | ✅ |
| LP-14 | CheckLLMServerHealth cache fallimento 5s | `app/llm_client.go` | `CheckLLMServerHealth()` | ✅ |
| LP-15 | UOC auto-resolve da CSV | `app/llm_client.go` | `HandleChat()` (GetPersonaleByUserID) | ✅ |
| LP-16 | UOC fallback da Descrizione | `app/llm_client.go` | `HandleChat()` (parts[1] fallback) | ✅ |
| LP-17 | UOS auto-resolve da CSV | `app/llm_client.go` | `HandleChat()` (personale.UOS) | ✅ |
| LP-18 | Sanitizzazione PII codice fiscale | `app/llm_client.go` | `sanitizePII()` | ✅ |
| LP-19 | Sanitizzazione PII user_id | `app/llm_client.go` | `sanitizePII()` | ✅ |
| LP-20 | Debug log file | `app/llm_client.go` | `logCurlCommand()` | ✅ |
| LP-21 | Debug log rotazione 10MB | `app/llm_client.go` | `logCurlCommand()` | ✅ |
| LP-22 | generateCurlCommand | `app/llm_client.go` | `generateCurlCommand()` | ✅ |
| LP-23 | HandleDebugChat dual call Parse+Chat | `app/llm_client.go` | `HandleDebugChat()` | ✅ |
| LP-24 | HandleDebugChat default sender debug_user | `app/llm_client.go` | `HandleDebugChat()` | ✅ |
| LP-25 | ExecutionPath priorita' backend/fallback | `app/llm_client.go` | `HandleDebugChat()`, `determineExecutionPath()` | ✅ |
| LP-26 | HandlePredefinedQuestions | `app/llm_client.go` | `HandlePredefinedQuestions()` | ✅ |
| LP-27 | Gestione errori HTTP 400/503/500 | `app/llm_client.go` | `HandleChat()` | ✅ |
| LP-28 | Logging strutturato LLM con prefissi | `app/llm_client.go` | `SendToLLMV1()`, `HandleChat()`, etc. | ✅ |
| LP-NF01 | Concorrenza health check sync.RWMutex | `app/llm_client.go` | `healthCheckCache` struct | ✅ |
| LP-NF02 | Configurazione default fallback | `app/config.go` | `getDefaultConfig()` | ✅ |

## api-proxy

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| AP-01 | ProxyChatLogAPI solo GET | `app/llm_client.go` | `ProxyChatLogAPI()` | ✅ |
| AP-02 | ProxyChatLogAPI route user-conversations | `app/main.go` | route GET `/api/chat-log/user-conversations` | ✅ |
| AP-03 | ProxyChatLogAPI route conversation/:id | `app/main.go` | route GET `/api/chat-log/conversation/:sessionId` | ✅ |
| AP-04 | ProxyAdminAPI multi-method GET/POST/DELETE | `app/llm_client.go` | `ProxyAdminAPI()` | ✅ |
| AP-05 | ProxyAdminAPI Content-Disposition forwarding | `app/llm_client.go` | `ProxyAdminAPI()` | ✅ |
| AP-06 | ProxyAdminAPI domande RAG CRUD | `app/main.go` | routes `/api/admin/domande-rag*` | ✅ |
| AP-07 | ProxyAdminAPI intents | `app/main.go` | route GET `/api/admin/intents` | ✅ |
| AP-08 | ProxyAdminAPI documents | `app/main.go` | routes `/api/admin/documents*` | ✅ |
| AP-09 | ProxyAdminAPI guided learn | `app/main.go` | route POST `/api/admin/guided-learn` | ✅ |
| AP-10 | ProxySessionReset backend + cookie | `app/llm_client.go` | `ProxySessionReset()` | ✅ |
| AP-11 | Backend non disponibile 502 | `app/llm_client.go` | `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |
| AP-12 | ProxyAdminAPI Content-Type default json | `app/llm_client.go` | `ProxyAdminAPI()` | ✅ |
| AP-13 | ProxyChatLogAPI query string forwarding | `app/llm_client.go` | `ProxyChatLogAPI()` | ✅ |
| AP-14 | ProxyChatLogAPI invalid path 400 | `app/llm_client.go` | `ProxyChatLogAPI()` | ✅ |
| AP-15 | ProxyAdminAPI invalid path 400 | `app/llm_client.go` | `ProxyAdminAPI()` | ✅ |
| AP-16 | ProxyAdminAPI POST body forwarding | `app/llm_client.go` | `ProxyAdminAPI()` | ✅ |
| AP-NF01 | Logging proxy con prefissi | `app/llm_client.go` | `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |
| AP-NF02 | Timeout proxy configurabile | `app/llm_client.go` | `ProxyChatLogAPI()`, `ProxyAdminAPI()` | ✅ |

## chat-ui

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| CU-01 | Classe ChatBot assegnata a window.chatBot | `statics/js/chat.js` | `ChatBot` class, `window.chatBot = new ChatBot()` | ✅ |
| CU-02 | Welcome screen stato iniziale | `statics/js/chat.js` | `ChatBot` constructor | ✅ |
| CU-03 | Transizione welcome a chat | `statics/js/chat.js` | `switchToChatMode()` | ✅ |
| CU-04 | Sender ID generazione unica | `statics/js/chat.js` | `ChatBot` constructor (this.senderId) | ✅ |
| CU-05 | Greeting dinamico per ora | `statics/js/chat.js` | `ChatBot` constructor (getTimeBasedGreeting) | ✅ |
| CU-06 | Quick actions da API predefined-questions | `statics/js/chat.js` | `loadPredefinedQuestions()` | ✅ |
| CU-07 | Quick actions click inserisce testo | `statics/js/chat.js` | `renderQuickActions()` (click handler) | ✅ |
| CU-08 | Quick actions Ctrl+Click invio diretto | `statics/js/chat.js` | `renderQuickActions()` (ctrlKey check) | ✅ |
| CU-09 | Streaming SSE con fallback sincrono | `statics/js/chat.js` | `sendMessage()`, `sendMessageStreaming()` | ✅ |
| CU-10 | Thinking message con pallini pulsanti | `statics/js/chat.js` | `sendMessageStreaming()` (thinkingDiv) | ✅ |
| CU-11 | Thinking message fade-out 0.3s | `statics/js/chat.js` | `handleSSEEvent()` (remove thinking) | ✅ |
| CU-12 | Download conversazione TXT | `statics/js/chat.js` | `downloadConversation()` | ✅ |
| CU-13 | Download escluso per fallback | `statics/js/chat.js` | `isFallbackMessage()` | ✅ |
| CU-14 | Liste collassabili oltre 10 elementi | `statics/js/chat.js` | `formatMessage()` (COLLAPSE_THRESHOLD) | ✅ |
| CU-15 | Guided learning buttons da fallback_intents | `statics/js/chat.js` | `createGuidedLearningContainer()` | ✅ |
| CU-16 | Guided learning auto-dismiss dopo 4s | `statics/js/chat.js` | `createGuidedLearningContainer()` (setTimeout) | ✅ |
| CU-17 | Question links [[text]] | `statics/js/chat.js` | `formatMessage()` (regex replace) | ✅ |
| CU-18 | Document download links [text](url) | `statics/js/chat.js` | `formatMessage()` (doc-download-link) | ✅ |
| CU-19 | Session reset (+ Nuova Chat) | `statics/js/chat.js` | `resetSession()` | ✅ |
| CU-20 | Suggestions chip cliccabili | `statics/js/chat.js` | `createSuggestionsContainer()` | ✅ |
| CU-21 | Logo Ctrl+Click naviga a debug | `statics/js/chat.js` | `ChatBot` constructor (logo click handler) | ✅ |
| CU-22 | Logo Shift+Click naviga a LangGraph | `statics/js/chat.js` | `ChatBot` constructor (logo click handler) | ✅ |
| CU-23 | Accessibilita' role=log aria-live | `template/index.html` | messages container attributes | ✅ |
| CU-24 | Scroll-to-bottom button visibile >100px | `statics/js/chat.js` | `scrollToBottom()`, scroll event listener | ✅ |
| CU-25 | Scroll-to-bottom nascosto <100px | `statics/js/chat.js` | scroll event listener (classList.remove) | ✅ |
| CU-26 | Format message HTML escape | `statics/js/chat.js` | `formatMessage()` (escapeHtml) | ✅ |
| CU-27 | Format message markdown headers | `statics/js/chat.js` | `formatMessage()` (section-header) | ✅ |
| CU-28 | Format message bold **text** | `statics/js/chat.js` | `formatMessage()` (strong replace) | ✅ |
| CU-29 | Format message numbered lists | `statics/js/chat.js` | `formatMessage()` (list-container) | ✅ |
| CU-30 | Format message fields Label: valore | `statics/js/chat.js` | `formatMessage()` (field-group) | ✅ |
| CU-31 | Typing indicator pallini animati | `statics/js/chat.js` | `showTypingIndicator()` | ✅ |
| CU-32 | Input auto-resize fino a 200px | `statics/js/chat.js` | `autoResizeTextarea()` | ✅ |
| CU-33 | Send button disabled se input vuoto | `statics/js/chat.js` | `ChatBot` constructor (input handler) | ✅ |
| CU-34 | Enter per inviare, Shift+Enter a capo | `statics/js/chat.js` | `ChatBot` constructor (keydown handler) | ✅ |
| CU-35 | Window variables injection nel template | `template/index.html` | script block (window.basePath, etc.) | ✅ |
| CU-36 | History link con query params | `template/index.html` | link cronologia (JS href build) | ✅ |
| CU-37 | SSE event handling status/reasoning/final | `statics/js/chat.js` | `handleSSEEvent()` | ✅ |
| CU-38 | Download nome file gias-{timestamp}.txt | `statics/js/chat.js` | `downloadConversation()` | ✅ |
| CU-39 | Payload ASL priorita' asl_name | `statics/js/chat.js` | `sendToServer()` (payload build) | ✅ |
| CU-40 | Guided learning disabilita bottoni | `statics/js/chat.js` | `createGuidedLearningContainer()` (disabled) | ✅ |
| CU-41 | Quick actions category icons SVG | `statics/js/chat.js` | `renderQuickActions()` (categoryIcons) | ✅ |
| CU-42 | EscapeHtml utility | `statics/js/chat.js` | `escapeHtml()` | ✅ |
| CU-NF01 | Smooth scroll | `statics/js/chat.js` | `scrollToBottom()` (behavior: smooth) | ✅ |
| CU-NF02 | Responsive layout <768px e <480px | `statics/css/style.css` | media queries 768px, 480px | ✅ |

## chat-network

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| CN-01 | AbortController timeout 75s | `statics/js/chat.js` | `sendToServer()` (AbortController) | ✅ |
| CN-02 | Retry 3 tentativi | `statics/js/chat.js` | `sendToServerWithRetry()` | ✅ |
| CN-03 | Exponential backoff 1s, 2s, max 5s | `statics/js/chat.js` | `sendToServerWithRetry()` | ✅ |
| CN-04 | No retry su timeout | `statics/js/chat.js` | `sendToServerWithRetry()` (AbortError check) | ✅ |
| CN-05 | Messaggio errore timeout client | `statics/js/chat.js` | `sendMessage()` (error handling) | ✅ |
| CN-06 | Messaggio errore server 5xx | `statics/js/chat.js` | `sendToServer()` (status check) | ✅ |
| CN-07 | Messaggio errore server 408 | `statics/js/chat.js` | `sendToServer()` (status check) | ✅ |
| CN-08 | Messaggio errore generico connessione | `statics/js/chat.js` | `sendMessage()` (catch block) | ✅ |
| CN-09 | Payload struttura JSON | `statics/js/chat.js` | `sendToServer()` (payload build) | ✅ |
| CN-10 | Status indicator retry tentativo N/3 | `statics/js/chat.js` | `sendToServerWithRetry()` (updateTypingIndicator) | ✅ |
| CN-11 | Endpoint chat sincrono POST /chat | `statics/js/chat.js` | `sendToServer()` | ✅ |
| CN-12 | Endpoint chat streaming POST /chat/stream | `statics/js/chat.js` | `sendMessageStreaming()` | ✅ |
| CN-NF01 | Timeout chain JS>Go>Backend | `statics/js/chat.js` | `sendToServer()` (75s timeout) | ✅ |

## theme-system

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| TS-01 | Due temi light e dark | `statics/css/style.css` | `body.dark-theme` selettore | ✅ |
| TS-02 | CSS variables toggle | `statics/css/style.css` | `body.dark-theme` (--bg-primary, etc.) | ✅ |
| TS-03 | LocalStorage persistenza tema | `statics/js/chat.js` | `toggleTheme()` (localStorage.setItem) | ✅ |
| TS-04 | Ripristino tema al caricamento | `statics/js/chat.js` | `initializeTheme()` | ✅ |
| TS-05 | Transizioni 0.3s ease | `statics/css/style.css` | transition rules | ✅ |
| TS-06 | Icona sole/luna toggle visibilita' | `statics/css/style.css` | `.sun-icon`, `.moon-icon` | ✅ |
| TS-07 | Header gradients per tema | `statics/css/style.css` | `.header`, `body.dark-theme .header` | ✅ |
| TS-08 | Tema consistente tra pagine | `statics/js/chat.js` | `initializeTheme()` (+history.js `initTheme()`) | ✅ |
| TS-09 | Admin/Analytics/Monitor dark-only | `template/analytics.html` | CSS inline (palette dark, +monitor.html, admin_rag.html) | ✅ |
| TS-10 | Dark theme ASL badge viola | `statics/css/style.css` | `body.dark-theme .asl-badge` | ✅ |
| TS-NF01 | No flash of unstyled content | `statics/js/chat.js` | `initializeTheme()` in constructor | ✅ |

## history-page

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| HP-01 | Codice fiscale obbligatorio | `statics/js/history.js` | `ChatHistory` constructor | ✅ |
| HP-02 | Caricamento conversazioni API | `statics/js/history.js` | `loadConversations()` | ✅ |
| HP-03 | Paginazione limit 50 | `statics/js/history.js` | `ChatHistory` constructor (this.limit) | ✅ |
| HP-04 | Load more button incrementa offset | `statics/js/history.js` | `loadMore()` | ✅ |
| HP-05 | Search debounce 300ms | `statics/js/history.js` | constructor (setTimeout 300) | ✅ |
| HP-06 | Filtro client-side case-insensitive | `statics/js/history.js` | `filterConversations()` | ✅ |
| HP-07 | Date relative (Oggi, Ieri, giorno, ecc.) | `statics/js/history.js` | `formatDate()` | ✅ |
| HP-08 | Caricamento messaggi conversazione | `statics/js/history.js` | `loadConversation()` | ✅ |
| HP-09 | Formattazione risposte escape+bold+br | `statics/js/history.js` | `renderMessages()` (escapeHtml, replace) | ✅ |
| HP-10 | Sidebar 300px desktop | `statics/css/style.css` | `.history-sidebar` | ✅ |
| HP-11 | Sidebar drawer mobile <768px | `statics/css/style.css` | media query `.history-sidebar` | ✅ |
| HP-12 | Chiusura sidebar mobile su selezione | `statics/js/history.js` | `loadConversation()` (sidebar close) | ✅ |
| HP-13 | Query params propagazione nei link | `template/history.html` | link navigation (queryParams) | ✅ |
| HP-14 | Escape HTML e JS nei dati dinamici | `statics/js/history.js` | `escapeHtml()`, `escapeJs()` | ✅ |
| HP-15 | Conversazione attiva highlight | `statics/js/history.js` | `renderList()` (active class) | ✅ |
| HP-NF01 | Tema condiviso da localStorage | `statics/js/history.js` | `initTheme()` | ✅ |

## debug-tools

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| DT-01 | Dual call Parse + Chat | `app/llm_client.go` | `HandleDebugChat()` | ✅ |
| DT-02 | Pannello intent classification | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (intent panel update) | ✅ |
| DT-03 | Pannello entities estratte | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (entities panel) | ✅ |
| DT-04 | Pannello agents eseguiti con badge | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (agents panel) | ✅ |
| DT-05 | Pannello conversation state | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (state panel) | ✅ |
| DT-06 | 19 intent descriptions italiane | `statics/js/debug_langgraph.js` | `intentDescriptions` object | ✅ |
| DT-07 | 19 tool-agent mappings con categorie | `statics/js/debug_langgraph.js` | `categoryColors`, `pathToAgent` objects | ✅ |
| DT-08 | Execution path priorita' | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (executionPath logic) | ✅ |
| DT-09 | Simulated path fallback | `app/llm_client.go` | `determineExecutionPath()` | ✅ |
| DT-10 | Responsive grid debug 2 colonne >1200px | `template/debug.html` | CSS grid layout (inline styles) | ✅ |
| DT-11 | Query params preservazione tra pagine | `template/debug.html` | nav links (queryParams, +debug_langgraph.html) | ✅ |
| DT-12 | Architecture badge framework+model | `template/debug.html` | header badge (framework + llmModel) | ✅ |
| DT-13 | Timeout 75s debug AbortController | `statics/js/debug_langgraph.js` | `sendToDebugServer()` (AbortController 75000) | ✅ |
| DT-14 | LangGraph SVG visualizer inline | `statics/js/debug_langgraph_visualizer.js` | `LangGraphDebugVisualizer` class | ✅ |
| DT-15 | Tab system LangGraph | `template/debug_langgraph.html` | tab elements (inline JS) | ✅ |
| DT-16 | Query history LangGraph | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` (query history) | ✅ |
| DT-17 | Sender ID debug stabile per sessione | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` constructor (senderId) | ✅ |
| DT-18 | Initial state loading da queryParams | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` constructor | ✅ |
| DT-19 | User context display nell'header | `template/debug.html` | header user info section | ✅ |
| DT-20 | Dark theme debug page | `template/debug.html` | CSS dark theme styles (inline) | ✅ |
| DT-NF01 | Tema persistente da localStorage | `statics/js/debug_langgraph.js` | `LangGraphDebugChatBot` constructor | ✅ |

## admin-analytics-monitor

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| AM-01 | Analytics 6 metriche summary | `template/analytics.html` | summary cards section (JS inline) | ✅ |
| AM-02 | Analytics auto-refresh 60s | `template/analytics.html` | setInterval 60000 (JS inline) | ✅ |
| AM-03 | Analytics chiamate dirette backend | `template/analytics.html` | fetch(backendUrl + ...) (JS inline) | ✅ |
| AM-04 | Analytics timeline bar chart CSS | `template/analytics.html` | timeline chart div (JS inline) | ✅ |
| AM-05 | Analytics period selector 1/7/30/90 giorni | `template/analytics.html` | period selector buttons (JS inline) | ✅ |
| AM-06 | Analytics top intent panel | `template/analytics.html` | top intents table (JS inline) | ✅ |
| AM-07 | Analytics top ASL panel | `template/analytics.html` | top ASL table (JS inline) | ✅ |
| AM-08 | Analytics recent messages con filtro ASL | `template/analytics.html` | recent messages section (JS inline) | ✅ |
| AM-09 | Monitor 10 problem types riconosciuti | `template/monitor.html` | problem type definitions (JS inline) | ✅ |
| AM-10 | Monitor 4 livelli severita' con colori | `template/monitor.html` | severity level definitions (JS inline) | ✅ |
| AM-11 | Monitor severity cards con conteggio | `template/monitor.html` | severity summary cards (JS inline) | ✅ |
| AM-12 | Monitor filtri periodo/ASL/severita' | `template/monitor.html` | filter controls (JS inline) | ✅ |
| AM-13 | Monitor auto-refresh 120s | `template/monitor.html` | setInterval 120000 (JS inline) | ✅ |
| AM-14 | Monitor problem cards con bordo colorato | `template/monitor.html` | problem card rendering (JS inline) | ✅ |
| AM-15 | Monitor raccomandazioni panel | `template/monitor.html` | recommendations section (JS inline) | ✅ |
| AM-16 | Monitor distribuzione tipi problema | `template/monitor.html` | type distribution panel (JS inline) | ✅ |
| AM-17 | Monitor tabella tutti i problemi max 600px | `template/monitor.html` | all problems table (JS inline) | ✅ |
| AM-18 | Monitor summary section gradiente | `template/monitor.html` | summary section (CSS gradient) | ✅ |
| AM-19 | Admin RAG dark-only | `template/admin_rag.html` | CSS inline (dark palette) | ✅ |
| AM-20 | Admin RAG CRUD domande | `template/admin_rag.html` | form + table (JS inline) | ✅ |
| AM-21 | Admin RAG lista PDF | `template/admin_rag.html` | documents list (JS inline) | ✅ |
| AM-22 | Admin RAG reindicizzazione | `template/admin_rag.html` | reindex button + status (JS inline) | ✅ |
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
| ST-02 | Whisper endpoint da env WHISPER_URL | `app/transcribe.go` | `TranscribeHandler()` | ✅ |
| ST-03 | Timeout 20s chiamata Whisper | `app/transcribe.go` | `callWhisper()` (http.Client 20s) | ✅ |
| ST-04 | Lingua default italiano "it" | `app/transcribe.go` | `TranscribeHandler()` | ✅ |
| ST-05 | File temporaneo webm con defer Remove | `app/transcribe.go` | `TranscribeHandler()` (os.CreateTemp) | ✅ |
| ST-06 | Profiling logging per fase | `app/transcribe.go` | `TranscribeHandler()` (PROFILE_*) | ✅ |
| ST-07 | Mic button pulsating red recording | `statics/css/style.css` | `.mic-button.recording` | ✅ |
| ST-08 | Toast notification trascrizione | `statics/js/chat.js` | transcription toast handler | ✅ |
| ST-NF01 | Multipart form upload file+language | `app/transcribe.go` | `callWhisper()` (multipart.Writer) | ✅ |
| ST-NF02 | Risposta trimmed | `app/transcribe.go` | `callWhisper()` (strings.TrimSpace) | ✅ |

## personnel-data

| ID | Descrizione | File | Funzione/Classe | Status |
|----|-------------|------|-----------------|--------|
| PD-01 | CSV loading in map[int]PersonaleRecord | `app/personale.go` | `LoadPersonaleData()` | ✅ |
| PD-02 | Cache basata su ModTime file | `app/personale.go` | `LoadPersonaleData()` | ✅ |
| PD-03 | Double-check lock con sync.RWMutex | `app/personale.go` | `LoadPersonaleData()` | ✅ |
| PD-04 | PersonaleRecord struct 8 campi | `app/personale.go` | `PersonaleRecord` struct | ✅ |
| PD-05 | UOS estrazione da terzo segmento -> | `app/personale.go` | `LoadPersonaleData()` (descParts[2]) | ✅ |
| PD-06 | Header row skip | `app/personale.go` | `LoadPersonaleData()` (records[1:]) | ✅ |
| PD-07 | Malformed record skip silenzioso | `app/personale.go` | `LoadPersonaleData()` (continue) | ✅ |
| PD-08 | GetPersonaleByUserID lookup | `app/personale.go` | `GetPersonaleByUserID()` | ✅ |
| PD-NF01 | Logging cache con prefisso PERSONALE_CACHE | `app/personale.go` | `LoadPersonaleData()` (log.Printf) | ✅ |
| PD-NF02 | Concorrenza sicura sync.RWMutex | `app/personale.go` | `personaleCache` struct | ✅ |
