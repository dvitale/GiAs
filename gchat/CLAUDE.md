# GChat - Interfaccia Web per Chatbot GIAS

Programma Golang che fornisce un'interfaccia web per il chatbot GIAS (sistema integrato LangGraph + LLM).

## ⚠️ Regole di Sviluppo

- **Test vs Backend**: Quando un test evidenzia un problema del backend, correggi SEMPRE il backend — mai il test. Non modificare domande predefinite, test o input per aggirare un bug: individua e risolvi la causa nel codice backend.

## 🎨 Novità UI/UX (Dicembre 2024)

### Toggle Tema Light/Dark
- **Switch tema** in alto a destra nell'header
- **Tema Light**: palette giallo oro/ambra (#f59e0b, #fef3c7, #fde68a)
- **Tema Dark**: palette slate/indaco (#1e293b, #4f46e5, #0f172a)
- **Persistenza**: preferenza salvata in localStorage
- **Transizioni smooth**: 0.3s su tutti i cambi colore
- **Icone animate**: sole ☀️ (light) / luna 🌙 (dark)

### Download Conversazioni
- **Pulsante download** automatico sotto ogni risposta bot valida
- **Formato**: file `.txt` con struttura:
  ```
  Conversazione Chatbot GIAS
  Data: [timestamp]

  DOMANDA: [testo domanda]
  RISPOSTA: [testo pulito senza HTML]
  ```
- **Nome file**: `gias-conversazione-[timestamp].txt`
- **Esclusioni**: messaggi di errore/fallback non mostrano il pulsante
- **Icona SVG**: download icon con testo "Scarica"

### Design Modernizzato
- **Bordi arrotondati**: 16px su container principale
- **Shadow sofisticati**: rgba con trasparenze per profondità
- **Palette coerente**: tutti gli elementi UI seguono la palette oro (light) o slate (dark)
- **Responsive**: ottimizzato per mobile e desktop

## Struttura del Progetto

- **app/**: Sorgenti Go dell'applicazione
  - `main.go`: Entry point, routing HTTP (Gin), gestione template e parametri query
  - `llm_client.go`: Client HTTP per comunicazione con backend LLM + `ProxyChatLogAPI` (proxy CORS)
  - `config.go`: Gestione configurazione JSON
  - `personale.go`: Caricamento dati CSV del personale
  - `session.go`: Session middleware cookie-based (gin-contrib/sessions), `SessionMiddleware()`, `MergeSessionParams()`
  - `transcribe.go`: Trascrizione audio (speech-to-text)
  - `config_test.go`: Test configurazione

- **statics/**: Asset statici (CSS, JavaScript, immagini)
  - `css/style.css`: Stili UI con supporto tema light/dark, palette oro, responsive, stili history page
  - `js/chat.js`: Logica chat, gestione tema, download conversazioni, retry logic
  - `js/history.js`: Logica pagina cronologia chat (caricamento conversazioni, ricerca, paginazione)
  - `js/debug_langgraph.js`: Debug panel LangGraph
  - `js/debug_langgraph_visualizer.js`: Renderer grafo LangGraph
  - `img/`: Immagini (logo GIAS, logo Regione)

- **template/**: Template HTML con supporto Go template engine
  - `index.html`: Interfaccia chatbot principale
  - `history.html`: Pagina cronologia chat (layout sidebar + area messaggi)
  - `debug.html`: Debug mode (visualizzazione intent/entity/slot)
  - `debug_langgraph.html`: LangGraph workflow visualizer
  - `analytics.html`: Dashboard analytics chat
  - `monitor.html`: Monitor qualita' conversazioni

- **config/**: File di configurazione
  - `config.json`: Configurazione server, LLM backend, logging, UI

- **data/**: Dati CSV
  - `personale.csv`: Dati utenti (ASL, nome, cognome, codice fiscale, user_id)

- **log/**: Directory per file di log dell'applicazione

- **bin/**: Eseguibili compilati

- **Script .sh**: Non modificare - utilizzati per build, run, deploy, stop, restart, status

## Dipendenze Go

- **gin-gonic/gin v1.9.1**: Framework web HTTP
- **gin-contrib/sessions**: Session management cookie-based (TTL 5 min)
- Go 1.21+

## Interfaccia Go ↔ Backend Chatbot

### 1. Endpoint Backend Utilizzato

**Chat V1**: `POST {BACKEND_URL}/api/v1/chat`
**Chat Streaming V1 (SSE)**: `POST {BACKEND_URL}/api/v1/chat/stream`
**Parse NLU V1**: `POST {BACKEND_URL}/api/v1/parse`

Configurazione in `config/config.json`:
```json
{
  "llm_server": {
    "url": "http://localhost:5005",
    "timeout": 60
  }
}
```

- `url`: URL base del backend LLM
- `timeout`: Timeout HTTP in secondi

### 2. Strutture Dati per Comunicazione con Backend

#### Request a Backend (app/llm_client.go)
```go
type NativeUserMetadata struct {
    ASL           string `json:"asl,omitempty"`
    ASLID         string `json:"asl_id,omitempty"`
    UserID        string `json:"user_id,omitempty"`
    CodiceFiscale string `json:"codice_fiscale,omitempty"`
    Username      string `json:"username,omitempty"`
    UOC           string `json:"uoc,omitempty"`
}

type NativeChatMessage struct {
    Sender   string              `json:"sender"`
    Message  string              `json:"message"`
    Metadata *NativeUserMetadata `json:"metadata,omitempty"`
}
```

- **sender**: Identificatore sessione utente (default: "user")
- **message**: Testo messaggio utente
- **metadata**: Contesto utente tipizzato (ASL, user_id, codice_fiscale, username, asl_id, uoc)

#### Response da Backend (app/llm_client.go)
```go
type NativeChatResponse struct {
    Result ChatResultV1 `json:"result"`
    Sender string       `json:"sender"`
}

type ChatResultV1 struct {
    Text               string                 `json:"text"`
    Intent             string                 `json:"intent"`
    Slots              map[string]interface{} `json:"slots"`
    Suggestions        []Suggestion           `json:"suggestions"`
    Execution          *ExecutionInfo         `json:"execution,omitempty"`
    NeedsClarification bool                   `json:"needs_clarification"`
    HasMoreDetails     bool                   `json:"has_more_details"`
    Error              string                 `json:"error,omitempty"`
}
```

Il backend restituisce un singolo oggetto `NativeChatResponse` con `result` contenente tutti i campi del grafo (text, intent, slots, suggestions, execution info, etc.).

### 3. Flusso di Comunicazione

#### A. Health Check (app/llm_client.go)
```
CheckLLMServerHealth() → GET {BACKEND_URL}
```
- Verifica disponibilita' backend prima di ogni richiesta
- Cache health status: 30s (successo), 5s (fallimento)
- Log dettagliato: `LLM_HEALTH_CHECK`, `LLM_HEALTH_ERROR`, `LLM_HEALTH_OK`, `LLM_HEALTH_CACHE`

#### B. Invio Messaggio (app/llm_client.go)
```
SendToLLMV1(message, sender, llmServerURL, timeout, context) → NativeChatResponse
```

**Processo**:
1. Costruisce `NativeChatMessage` con messaggio, sender e metadata tipizzato
2. Serializza JSON
3. POST a `{LLM_URL}/api/v1/chat`
4. Timeout HTTP configurabile
5. Parsing response JSON in `NativeChatResponse`
6. Logging completo di ogni fase

**Logging** (prefissi):
- `BACKEND_REQUEST`: Parametri richiesta
- `BACKEND_CONTEXT`: Metadata contesto
- `BACKEND_SEND`: Payload JSON inviato
- `BACKEND_RESPONSE`: Status HTTP e durata
- `BACKEND_RAW_RESPONSE`: Corpo response
- `BACKEND_SUCCESS`: Conferma con conteggio risposte
- `BACKEND_RESPONSE_ITEM`: Dettaglio singola risposta
- `BACKEND_ERROR`: Errori in qualsiasi fase

### 4. Endpoint API Web

#### POST /chat (app/llm_client.go:131-215)
Handler principale per messaggi chat.

**Request Body**:
```go
type ChatRequest struct {
    Message       string `json:"message"`
    Sender        string `json:"sender"`
    ASL           string `json:"asl,omitempty"`
    ASLID         string `json:"asl_id,omitempty"`
    UserID        string `json:"user_id,omitempty"`
    CodiceFiscale string `json:"codice_fiscale,omitempty"`
    Username      string `json:"username,omitempty"`
    UOC           string `json:"uoc,omitempty"`   // Unita' Operativa Complessa (auto da personale.csv)
}
```

**Response**:
```go
type ChatResponse struct {
    Message     string                   `json:"message"`
    Status      string                   `json:"status"`
    Error       string                   `json:"error,omitempty"`
    FullData    interface{}              `json:"full_data,omitempty"`    // Dati strutturati completi
    DataType    string                   `json:"data_type,omitempty"`    // Tipo dati (table, list, etc.)
    Suggestions []map[string]interface{} `json:"suggestions,omitempty"`  // Suggerimenti follow-up
}
```

**Flusso**:
1. Parse JSON request
2. Costruisce mappa `context` da parametri utente (ASL prioritaria su ASLID)
3. Health check backend
4. Invio a backend con contesto
5. Concatena multiple risposte in singolo testo
6. Restituisce JSON con stato e messaggio

**Gestione Errori**:
- 400 Bad Request: JSON malformato
- 503 Service Unavailable: Backend non disponibile
- 500 Internal Server Error: Errore comunicazione backend
- 200 OK: Successo (anche se risposta vuota)

#### GET /api/predefined-questions (app/llm_client.go:217-226)
Restituisce domande predefinite da `config.json`.

#### GET / (app/main.go:19-72)
Pagina principale con template HTML.

**Query Parameters**:
- `user_id`: Carica dati utente da CSV
- `asl_id`, `asl_name`: Identifica ASL
- `codice_fiscale`, `username`: Dati utente aggiuntivi

Dati passati a JavaScript via template per invio con richieste chat.

### 5. Gestione Contesto Utente

**Session Management** (`app/session.go`):
- Cookie-based sessions via `gin-contrib/sessions`
- TTL: 5 minuti (`SessionTTL`)
- `SessionMiddleware()`: salva parametri query/POST nella sessione
- `MergeSessionParams()`: merge con priorita' POST body > Query string > Session cookie
- Cookie path: `/gias/webchat`, HttpOnly, SameSite=Lax

**Metadata inviata a backend** (app/llm_client.go):
```go
context := map[string]interface{}{
    "asl":            req.ASL,           // Nome ASL (prioritario)
    "asl_id":         req.ASLID,         // ID ASL (fallback)
    "user_id":        req.UserID,
    "codice_fiscale": req.CodiceFiscale,
    "username":       req.Username,
    "uoc":            uoc,               // Unita' Operativa (auto da personale.csv)
}
```

Il backend utilizza questi metadati per:
- Personalizzazione risposte
- Slot filling automatico
- Routing conversazionale contestuale
- Accesso a dati specifici ASL/utente

### 5b. Proxy CORS per API Chat-Log

**Funzione**: `ProxyChatLogAPI()` in `app/llm_client.go`

Le API `/api/chat-log/*` del backend Python non sono raggiungibili direttamente dal browser (CORS cross-origin `:8080` → `:5005`). Il server Go fa da proxy:

```
Browser (:8080) → Go /gias/webchat/api/chat-log/* → Python :5005/api/chat-log/*
```

Route registrate in `main.go`:
- `GET /gias/webchat/api/chat-log/user-conversations` → proxy
- `GET /gias/webchat/api/chat-log/conversation/:sessionId` → proxy

Usate da `history.js` per caricare la cronologia chat.

### 6. Caricamento Dati Utente

**CSV Structure** (`data/personale.csv`):
```
ASL,DescrizioneAreaStrutturaComplessa,Descrizione,NameFirst,NameLast,CodiceFiscale,UserID
```

**Funzioni**:
- `LoadPersonaleData()`: Carica CSV in mappa `map[int]PersonaleRecord`
- `GetPersonaleByUserID(userID)`: Recupero dati utente per user_id

Dati caricati al rendering pagina se `user_id` presente in query string.

### 7. Configurazione

**config/config.json**:
```json
{
  "server": { "port": "8080", "host": "localhost" },
  "llm_server": {
    "url": "http://localhost:5005",
    "timeout": 60
  },
  "log": { "level": "info", "file": "log/app.log" },
  "predefined_questions": [
    {
      "id": "d1",
      "text": "Che domande posso fare",
      "question": "Cosa posso chiederti?",
      "category": "help"
    },
    {
      "id": "d2",
      "text": "Stabilimenti piano A22 - Approccio Statistico",
      "question": "stabilimenti del piano A22",
      "category": "piani"
    },
    {
      "id": "d3",
      "text": "Attività Piano A32 - Approccio Semantico",
      "question": "Quali attività sono semanticamente collegate al piano B2?",
      "category": "piani"
    },
    {
      "id": "d4",
      "text": "Quali controlli dovrei fare, basandomi sul rischio storico?",
      "question": "Sulla base del rischio storico chi dovrei controllare per primo?",
      "category": "priorita"
    },
    {
      "id": "d5",
      "text": "Quale stabilimento dovrei controllare per primo secondo la programmazione?",
      "question": "quale stabilimento dovrei controllare per primo secondo la programmazione?",
      "category": "priorita"
    },
    {
      "id": "d6",
      "text": "Di cosa tratta il piano A11_F?",
      "question": "di cosa tratta il piano A11_F?",
      "category": "piani"
    },
    {
      "id": "d7",
      "text": "Quali piani riguardano allevamenti?",
      "question": "quali sono i piani che riguardano allevamenti?",
      "category": "piani"
    }
  ],
  "ui": { "welcome_message": "..." }
}
```

Fallback a configurazione default se file mancante o malformato.

### 8. Logging

Logging strutturato con prefissi:
- **CHAT_**: Eventi handler chat HTTP
- **CHAT_STREAM_**: Eventi streaming SSE
- **LLM_**: Comunicazione con backend LLM
- **LLM_STREAM_**: Streaming SSE con backend
- **LLM_HEALTH_**: Health check backend (con cache)
- **USER_**: Caricamento dati utente
- **INDEX_**: Richieste pagina principale
- **HISTORY_**: Richieste pagina cronologia
- **ANALYTICS_**: Richieste dashboard analytics
- **MONITOR_**: Richieste monitor qualita'
- **LANGGRAPH_DEBUG_**: Richieste debugger LangGraph
- **CHATLOG_PROXY_**: Proxy API chat-log verso backend
- **PREDEFINED_QUESTIONS_**: Richieste domande
- **DEBUG_CHAT_**: Handler debug chat

Include: IP client, session ID, durata operazioni, parametri richiesta/response.

## Sequenza Completa delle Chiamate

Quando viene invocato `http://localhost:8080/gias/webchat/?asl_id=202&user_id=6448&codice_fiscale=ZZIBRD65R11A783K&asl_name=BENEVENTO`:

### 1. **Browser → Go Server** (GET `/gias/webchat/`)
Parametri mergiati da Session + Query + POST (priorita': POST > Query > Session):
```go
userIDStr, aslID, aslName, codiceFiscale, username := MergeSessionParams(c)
// Risultato: asl_id="202", user_id="6448", codice_fiscale="ZZIBRD65R11A783K", asl_name="BENEVENTO"
```

### 2. **Go Server → Caricamento Dati Utente**
Se `user_id` presente, carica dati da `data/personale.csv`

### 3. **Go Server → Template Rendering**
Parametri iniettati in JavaScript (`template/index.html:72-84`):
```javascript
window.queryParams = {
    asl_id: "202",
    asl_name: "BENEVENTO",
    user_id: "6448",
    codice_fiscale: "ZZIBRD65R11A783K",
    username: null
};
```

### 4. **Browser → JavaScript Client**
Quando utente invia messaggio, costruisce payload (`statics/js/chat.js:125-161`):
```javascript
const payload = {
    message: "quale stabilimento controllare",
    sender: "user",
    asl: "BENEVENTO",           // da queryParams.asl_name (priorità)
    asl_id: "202",
    user_id: "6448",
    codice_fiscale: "ZZIBRD65R11A783K"
};
```

### 5. **JavaScript → Go Server** (POST `/gias/webchat/chat`)
Body JSON inviato all'handler `app/llm_client.go:131-215`

### 6. **Go Server → Health Check LLM**
`GET http://localhost:5005/` (`app/llm_client.go:106-129`)

### 7. **Go Server → Costruzione Context Metadata**
```go
context := map[string]interface{}{
    "asl": "BENEVENTO",              // priorità a asl_name
    "asl_id": "202",
    "user_id": "6448",
    "codice_fiscale": "ZZIBRD65R11A783K",
    "username": ""
}
```

### 8. **Go Server → Backend API**
`POST http://localhost:5005/api/v1/chat`:
```json
{
  "sender": "user",
  "message": "quale stabilimento controllare",
  "metadata": {
    "asl": "BENEVENTO",
    "asl_id": "202",
    "user_id": "6448",
    "codice_fiscale": "ZZIBRD65R11A783K"
  }
}
```

### 9. **Backend → LangGraph Workflow**
Il backend LangGraph utilizza automaticamente i metadati nello state:
```python
# ConversationState viene popolato dai metadati
state = ConversationState(
    asl="BENEVENTO",
    asl_id="202",
    user_id="6448",
    codice_fiscale="ZZIBRD65R11A783K"
)

# Tool nodes accedono ai dati tramite state
Async def analyze_plans(state: ConversationState) -> Dict:
    asl = state.asl  # "BENEVENTO"
    # Tool execution logic...
```

### 10-12. **Response Chain**
Backend → Go Server → JavaScript → DOM Update

## Flusso Dati Query String → Metadata Backend

```
Query String URL / POST body
    ↓
Go Server (session.go) - MergeSessionParams (POST > Query > Session cookie)
    ↓
Template HTML (index.html) - injection in window.queryParams
    ↓
JavaScript (chat.js) - read queryParams, add to POST body (+ UOC auto)
    ↓
Go Handler /chat (llm_client.go) - extract from JSON, build metadata map, lookup UOC da personale.csv
    ↓
Backend API webhook - receive metadata field (asl, asl_id, user_id, codice_fiscale, username, uoc)
    ↓
LangGraph State - auto-populate state from metadata
    ↓
Tool Nodes - read state values from ConversationState
```

## Note Implementative

- Client HTTP con timeout configurabile per prevenire hang
- Health check preventivo prima di ogni messaggio
- Gestione errori dettagliata con logging completo
- Concatenazione automatica risposte multiple backend
- Supporto metadata opzionali per contesto conversazionale
- Fallback graceful per configurazione mancante
- Session ID via header `X-Session-ID` per tracking
- **IMPORTANTE**: Metadata passati via campo `metadata` dell'API webhook, NON come parte del messaggio testuale
- **ARCHITETTURA**: Sistema basato su LangGraph + LLM con API V1 nativa

## Funzionalità JavaScript (statics/js/chat.js)

### Gestione Tema (Theme Toggle)
```javascript
// Inizializzazione tema da localStorage
initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
    }
}

// Toggle tema light/dark
toggleTheme() {
    document.body.classList.toggle('dark-theme');
    const isDark = document.body.classList.contains('dark-theme');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}
```

**Persistenza**: La preferenza utente viene salvata in `localStorage` e ripristinata al caricamento pagina.

### Download Conversazioni
```javascript
// Creazione pulsante download per ogni messaggio bot
createDownloadButton(question, answer) {
    // SVG icon + label "Scarica"
    // Event listener per download
}

// Download file .txt
downloadConversation(question, answer) {
    const timestamp = new Date().toLocaleString('it-IT');
    const cleanAnswer = this.stripHtmlTags(answer);

    const content = `Conversazione Chatbot GIAS
Data: ${timestamp}

DOMANDA:
${question}

RISPOSTA:
${cleanAnswer}`;

    // Blob + download automatico
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    // Nome file: gias-conversazione-[timestamp].txt
}
```

**Esclusione messaggi fallback**:
```javascript
isFallbackMessage(message) {
    const fallbackKeywords = [
        'non ho capito', 'mi dispiace', 'non riesco',
        'si è verificato un errore', 'riprova più tardi',
        'controlla la tua connessione'
    ];
    return fallbackKeywords.some(keyword =>
        message.toLowerCase().includes(keyword)
    );
}
```

### Retry Logic con Exponential Backoff
```javascript
async sendToServerWithRetry(message, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await this.sendToServer(message);
        } catch (error) {
            if (attempt < maxRetries) {
                // Exponential backoff: 1s, 2s, 4s (max 5s)
                const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
                this.updateTypingIndicator(`Riconnessione in corso... (${attempt}/${maxRetries})`);
                await this.sleep(delay);
            }
        }
    }
}
```

### Formattazione Messaggi Avanzata
Il metodo `formatMessage()` gestisce:
- **Escape HTML**: conversione caratteri speciali
- **Emoji preservation**: mantiene emoji Unicode comuni
- **Headers markdown**: `**Header:**` → `<div class="section-header">`
- **Bold text**: `**text**` → `<strong>`
- **Numbered lists**: auto-formattazione con styling
- **Sub-fields**: parsing campi strutturati (Aggregazione, Attività, ecc.)
- **Similarità badges**: highlight percentuali
- **Line breaks**: conversione `\n` → `<br>` intelligente

## Stili CSS Tema Light vs Dark

### Light Theme (Default)
**Palette Oro/Ambra**:
- Background: `linear-gradient(135deg, #fef3c7, #fde68a)`
- Header: `linear-gradient(135deg, #f59e0b, #d97706)`
- Container: `#ffffff` con border `#fcd34d`
- Messaggi bot: `#ffffff` con border oro
- Messaggi user: `#f59e0b`
- Accenti: `#fef3c7`, `#fed7aa`

### Dark Theme
**Palette Slate/Indaco**:
- Background: `linear-gradient(135deg, #1e293b, #0f172a)`
- Header: `linear-gradient(135deg, #4f46e5, #3730a3)`
- Container: `#1e293b` con border `#334155`
- Messaggi bot: `#1e293b` con border slate
- Messaggi user: `#4f46e5`
- Accenti: `#334155`, `#1e3a8a`

**Transizioni**: Tutti gli elementi hanno `transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease` per cambio tema fluido.

## 🔧 Debug API GIAS con Curl

### Sistema di Logging Debug Automatico

Il sistema genera automaticamente comandi curl per testare manualmente le API GIAS durante lo sviluppo e il troubleshooting. Ogni chiamata API viene loggata in `log/gias_api_debug.log` con i comandi curl corrispondenti.

### File di Log Debug

**Posizione**: `log/gias_api_debug.log`

**Formato Log**:
```
=== GIAS API DEBUG SESSION - 2024-12-20 15:30:45 ===
Endpoint: CHAT_V1
Request Data:
{
  "url": "http://localhost:5005/api/v1/chat",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "User-Agent": "GChat/1.0",
    "X-Source": "gchat-debug"
  },
  "payload": {
    "sender": "user",
    "message": "stabilimenti piano A22",
    "metadata": {
      "asl": "BENEVENTO",
      "asl_id": "202",
      "user_id": "6448",
      "codice_fiscale": "ZZIBRD65R11A783K"
    }
  },
  "timeout": 30,
  "timestamp": "2024-12-20 15:30:45"
}

CURL TEST COMMAND:
curl -X POST 'http://localhost:5005/api/v1/chat' -H 'Content-Type: application/json' -H 'User-Agent: GChat/1.0' -H 'X-Source: gchat-debug' -d '{"sender":"user","message":"stabilimenti piano A22","metadata":{"asl":"BENEVENTO","asl_id":"202","user_id":"6448","codice_fiscale":"ZZIBRD65R11A783K"}}'
=== END DEBUG SESSION ===
```

### Endpoint API Supportati

#### 1. **Chat V1** (`/api/v1/chat`)
```bash
curl -X POST 'http://localhost:5005/api/v1/chat' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: GChat/1.0' \
  -H 'X-Source: gchat-debug' \
  -d '{
    "sender": "user",
    "message": "stabilimenti piano A22",
    "metadata": {
      "asl": "BENEVENTO",
      "asl_id": "202",
      "user_id": "6448",
      "codice_fiscale": "ZZIBRD65R11A783K"
    }
  }'
```

#### 2. **Endpoint Parse V1** (`/api/v1/parse`)
Per test di analisi NLU:
```bash
curl -X POST 'http://localhost:5005/api/v1/parse' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: GChat/1.0' \
  -H 'X-Source: gchat-debug-parse' \
  -d '{
    "text": "stabilimenti piano A22",
    "metadata": {
      "asl": "BENEVENTO",
      "user_id": "6448"
    }
  }'
```

#### 3. **Streaming V1** (`/api/v1/chat/stream`)
Per test streaming SSE:
```bash
curl -N -X POST 'http://localhost:5005/api/v1/chat/stream' \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{
    "sender": "user",
    "message": "piani in ritardo",
    "metadata": {"asl": "BENEVENTO"}
  }'
```

### Modalità Debug Integrata

#### Accesso Debug Mode

**URL Debug**: `POST /gias/webchat/debug`

Utilizza l'endpoint debug per ottenere informazioni dettagliate:
```javascript
// Richiesta debug con dati estesi
{
  "message": "stabilimenti piano A22",
  "sender": "debug_user",
  "asl": "BENEVENTO",
  "asl_id": "202",
  "user_id": "6448",
  "codice_fiscale": "ZZIBRD65R11A783K"
}
```

**Response Debug**:
```json
{
  "message": "Risposta del chatbot...",
  "status": "success",
  "intent": {
    "name": "query_piano",
    "confidence": 0.95
  },
  "entities": [
    {
      "entity": "piano_code",
      "value": "A22",
      "start": 13,
      "end": 16
    }
  ],
  "slots": {
    "piano_code": "A22",
    "asl": "BENEVENTO"
  },
  "metadata": {
    "asl": "BENEVENTO",
    "user_id": "6448"
  },
  "confidence": 0.95,
  "executed_actions": [
    "action_search_piano",
    "action_format_results"
  ]
}
```

### Utilizzo Pratico

#### 1. **Test Isolato API**
Copia il comando curl dal log e eseguilo direttamente:
```bash
# Dal log gias_api_debug.log
curl -X POST 'http://localhost:5005/api/v1/chat' -H 'Content-Type: application/json' -H 'User-Agent: GChat/1.0' -H 'X-Source: gchat-debug' -d '{"sender":"user","message":"stabilimenti piano A22","metadata":{"asl":"BENEVENTO","asl_id":"202","user_id":"6448"}}'
```

#### 2. **Test con Variazioni**
Modifica parametri per test specifici:
```bash
# Test con ASL diversa
curl -X POST 'http://localhost:5005/api/v1/chat' \
  -H 'Content-Type: application/json' \
  -d '{"sender":"user","message":"stabilimenti piano A22","metadata":{"asl":"NAPOLI","asl_id":"203"}}'

# Test senza metadati
curl -X POST 'http://localhost:5005/api/v1/chat' \
  -H 'Content-Type: application/json' \
  -d '{"sender":"user","message":"stabilimenti piano A22"}'
```

#### 3. **Monitoring Continuo Log**
```bash
# Tail del file di debug
tail -f log/gias_api_debug.log

# Grep specifico endpoint
grep -A 20 "=== GIAS API DEBUG SESSION" log/gias_api_debug.log | grep -A 15 "WEBHOOK"

# Solo comandi curl
grep "curl -X" log/gias_api_debug.log
```

#### 4. **Test Batch**
```bash
# Salva comandi curl in script
grep "curl -X" log/gias_api_debug.log > test_api.sh
chmod +x test_api.sh

# Esegui test in sequenza
./test_api.sh
```

### Headers Debug Personalizzati

Il sistema aggiunge header specifici per identificare richieste debug:

- **Chat V1**: `X-Source: gchat-debug`
- **Parse V1**: `X-Source: gchat-debug-parse`
- **User-Agent**: `GChat/1.0`

### Best Practices

1. **Verifica Backend Attivo**:
   ```bash
   curl -X GET 'http://localhost:5005/'
   # Deve rispondere 200 OK
   ```

2. **Test Incrementale**:
   ```bash
   # 1. Test health check
   curl -X GET 'http://localhost:5005/'

   # 2. Test parse semplice
   curl -X POST 'http://localhost:5005/api/v1/parse' \
     -H 'Content-Type: application/json' \
     -d '{"text": "ciao"}'

   # 3. Test chat completo
   curl -X POST 'http://localhost:5005/api/v1/chat' \
     -H 'Content-Type: application/json' \
     -d '{"sender":"test","message":"ciao"}'
   ```

3. **Debug Errori**:
   ```bash
   # Verbose output per debug
   curl -v -X POST 'http://localhost:5005/api/v1/chat' \
     -H 'Content-Type: application/json' \
     -d '{"sender":"user","message":"test"}'

   # Con timeout
   curl --max-time 10 -X POST 'http://localhost:5005/api/v1/chat' \
     -H 'Content-Type: application/json' \
     -d '{"sender":"user","message":"test"}'
   ```

### Funzioni Debug nel Codice

Le funzioni principali che generano i log curl sono:

- **`generateCurlCommand()`**: Genera comando curl da URL, payload e headers
- **`logCurlCommand()`**: Scrive comando e metadati nel file di log debug
- **Integrazione in `SendToLLMV1()`**: Auto-logging di ogni richiesta chat V1
- **Integrazione in `ParseMessage()`**: Auto-logging richieste parse V1

Questo sistema facilita significativamente il troubleshooting e il test isolato delle API GIAS durante lo sviluppo.

## ⏱️ Gestione Timeout

### Problemi di Timeout Risolti

La configurazione timeout è stata ottimizzata per gestire le richieste LLM lunghe che possono richiedere elaborazione intensiva:

**Prima (Problematico)**:
- **Server Go**: 30 secondi
- **Client JavaScript**: nessun timeout (indefinito)
- **Risultato**: Messaggi "Mi dispiace, non riesco a connettermi al server. Controlla la tua connessione."

**Dopo (Ottimizzato)**:
- **Server Go**: 60 secondi (`config.json: llm_server.timeout`)
- **Client JavaScript**: 75 secondi (con AbortController)
- **Gestione errori specifica** per tipo di timeout

### Configurazione Timeout

#### File di Configurazione
```json
// config/config.json
{
  "llm_server": {
    "url": "http://localhost:5005",
    "timeout": 60
  }
}
```

**Parametri LLM Server**:
- `url`: URL base del backend LLM
- `timeout`: Timeout in secondi per le richieste HTTP

#### Client JavaScript
```javascript
// statics/js/chat.js - sendToServer()
const controller = new AbortController();
const timeoutMs = 75000; // 75 seconds - maggiore del server Go
const timeoutId = setTimeout(() => {
    controller.abort();
}, timeoutMs);
```

### Messaggi di Errore Migliorati

Il sistema ora distingue diversi tipi di errori con messaggi specifici:

#### 1. **Timeout Client JavaScript (>75s)**
```
⏱️ La richiesta ha impiegato troppo tempo. Il sistema LLM potrebbe essere sovraccarico. Riprova tra qualche minuto.
```

#### 2. **Error Server LLM (5xx)**
```
🔧 Il server LLM non è disponibile al momento. Riprova più tardi o contatta l'amministratore.
```

#### 3. **Timeout Server Go (408)**
```
⏳ Il server ha impiegato troppo tempo a elaborare la richiesta. Riprova con una domanda più semplice.
```

#### 4. **Errori di Connessione Generici**
```
Mi dispiace, non riesco a connettermi al server dopo diversi tentativi. Verifica la tua connessione e riprova.
```

### Logica Retry Ottimizzata

- **Timeout errors NON vengono ritentati** (inutile)
- **Server errors vengono ritentati** (3 tentativi max)
- **Exponential backoff**: 1s, 2s, 4s (max 5s)
- **Abort immediato** su timeout per non bloccare l'UI

### Debug Timeout

#### Verifica Timeout Configurazione
```bash
# 1. Controlla config
grep -A 3 "llm_server" config/config.json

# 2. Test diretto LLM
curl -X GET 'http://localhost:5005/' --max-time 10

# 3. Monitoring log timeout
tail -f log/app.log | grep -i timeout
```

#### Test Timeout da Browser Console
```javascript
// Test timeout client
console.time('fetch-test');
fetch('/gias/webchat/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: 'test long query', sender: 'test' }),
    signal: AbortSignal.timeout(10000) // 10s test timeout
}).then(() => console.timeEnd('fetch-test'))
  .catch(e => {
    console.timeEnd('fetch-test');
    console.log('Timeout test:', e.name, e.message);
  });
```

#### Simulazione Carico LLM
```bash
# Test multiple requests per verificare timeout sotto carico
for i in {1..5}; do
  curl -X POST 'http://localhost:5005/api/v1/chat' \
    -H 'Content-Type: application/json' \
    -d '{"sender":"stress_test_'$i'","message":"analizza tutti i piani di controllo della campania"}' &
done
```

### Best Practices Timeout

1. **Configurazione Progressive**: Client > Server Go > LLM backend
2. **Messaggi Specifici**: Distingui timeout da errori di connessione
3. **No Retry su Timeout**: Evita loop inutili
4. **Monitoring**: Log tutti i timeout per ottimizzazione
5. **Test Load**: Verifica comportamento sotto carico

### Performance Tuning

Per richieste LLM molto complesse, considera:

```json
// Aumenta timeout per queries complesse
{
  "llm_server": {
    "timeout": 120  // 2 minuti per analisi pesanti
  }
}
```

```javascript
// Client JavaScript corrispondente
const timeoutMs = 150000; // 2.5 minuti
```

Il sistema ora gestisce correttamente le richieste LLM lunghe senza falsi errori di connessione.

## Regole di manutenzione

Questo file e' la **fonte di verita' unica** per i dettagli del frontend gchat. Vedere le regole complete in `../CLAUDE.md` (sezione "Regole di manutenzione documentazione").

Quando modifichi gchat, aggiorna questo file se tocchi:
- File Go in `app/` → aggiornare sezione "Struttura del Progetto"
- Strutture dati request/response → aggiornare sezione "Strutture Dati"
- Configurazione timeout → aggiornare sezione "Gestione Timeout"
- Funzionalita' JavaScript → aggiornare sezione "Funzionalita' JavaScript"
- Endpoint API → aggiornare sezione "Endpoint API Supportati" e la tabella in `../CLAUDE.md`
- Template HTML → aggiornare sezione "Struttura del Progetto" (template/)
- Route proxy → aggiornare sezione "Proxy CORS per API Chat-Log"
- Session/parametri → aggiornare sezione "Gestione Contesto Utente"
