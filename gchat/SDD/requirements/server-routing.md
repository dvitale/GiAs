# Server Routing

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/main.go, app/config.go

## Requisiti Funzionali

### SR-01 Base Path per Reverse Proxy
- **Pattern EARS**: Il sistema DEVE registrare tutte le route sotto il base path `/gias/webchat` per compatibilita' con il reverse proxy.
- **Status**: IMPLEMENTATO

### SR-02 Pagina Principale GET
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/`, il sistema DEVE renderizzare il template `index.html` con i dati utente, messaggio di benvenuto, basePath e queryParams.
- **Status**: IMPLEMENTATO

### SR-03 Pagina Principale POST
- **Pattern EARS**: QUANDO un utente invia una richiesta POST a `/gias/webchat/`, il sistema DEVE renderizzare il template `index.html` con i parametri estratti dal body JSON o form (oltre a query string e sessione).
- **Status**: IMPLEMENTATO

### SR-04 Pagina Debug
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/debug`, il sistema DEVE renderizzare il template `debug.html` con dati utente, basePath, queryParams, llmModel e framework ottenuti dal backend.
- **Status**: IMPLEMENTATO

### SR-05 Pagina LangGraph Debugger
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/debug/langgraph`, il sistema DEVE renderizzare il template `debug_langgraph.html` con dati utente, basePath, queryParams, llmModel e framework.
- **Status**: IMPLEMENTATO

### SR-06 Pagina Analytics
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/analytics`, il sistema DEVE renderizzare il template `analytics.html` con dati utente, basePath, backendUrl e queryParams.
- **Status**: IMPLEMENTATO

### SR-07 Pagina Monitor
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/monitor`, il sistema DEVE renderizzare il template `monitor.html` con dati utente, basePath, backendUrl e queryParams.
- **Status**: IMPLEMENTATO

### SR-08 Pagina History
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/history`, il sistema DEVE renderizzare il template `history.html` con dati utente, basePath, backendUrl e queryParams.
- **Status**: IMPLEMENTATO

### SR-09 Pagina Admin RAG
- **Pattern EARS**: QUANDO un utente accede via GET a `/gias/webchat/admin/rag`, il sistema DEVE renderizzare il template `admin_rag.html` con title e basePath, senza richiedere autenticazione.
- **Status**: IMPLEMENTATO
- **Note**: Nessun caricamento dati utente per la pagina admin.

### SR-10 Servizio File Statici
- **Pattern EARS**: Il sistema DEVE servire i file statici dalla directory `./statics` sotto il path `/gias/webchat/static`.
- **Status**: IMPLEMENTATO

### SR-11 Template Function json
- **Pattern EARS**: Il sistema DEVE registrare una template function `json` che serializza un valore Go in JSON sicuro per l'inserimento nel template HTML, restituendo `null` se il valore e' nil o la serializzazione fallisce.
- **Status**: IMPLEMENTATO

### SR-12 Caricamento Template
- **Pattern EARS**: Il sistema DEVE caricare tutti i template HTML dalla directory `template/*` tramite `LoadHTMLGlob`.
- **Status**: IMPLEMENTATO

### SR-13 loadUserData da CSV
- **Pattern EARS**: QUANDO il parametro `user_id` e' presente, il sistema DEVE caricare i dati utente dal CSV tramite `GetPersonaleByUserID` e restituire un oggetto con user_id, namefirst (uppercase), namelast (uppercase), descrizione, asl, codice_fiscale e hierarchy.
- **Status**: IMPLEMENTATO

### SR-14 Priorita' asl_name su CSV
- **Pattern EARS**: QUANDO il parametro `asl_name` dalla query string e' non vuoto, il sistema DEVE utilizzarlo al posto del valore ASL proveniente dal CSV.
- **Status**: IMPLEMENTATO

### SR-15 buildHierarchyHTML con HTML Escape
- **Pattern EARS**: QUANDO il campo `Descrizione` contiene segmenti separati da `->`, il sistema DEVE generare una struttura HTML gerarchica `<li>...<ul><li>...</li></ul></li>` con escape HTML di ogni segmento per prevenire injection.
- **Status**: IMPLEMENTATO

### SR-16 Anno Dinamico dal Backend
- **Pattern EARS**: QUANDO si renderizza la pagina principale, il sistema DEVE ottenere l'anno corrente dal backend provando prima l'endpoint `/config` e poi `/status` come fallback, con timeout di 5 secondi.
- **Status**: IMPLEMENTATO

### SR-17 Fallback Anno Dinamico
- **Pattern EARS**: SE l'anno non puo' essere ottenuto dal backend, il sistema DEVE utilizzare il messaggio di welcome di default senza sostituzione dell'anno.
- **Status**: IMPLEMENTATO

### SR-18 Sostituzione Anno nel Welcome Message
- **Pattern EARS**: QUANDO l'anno e' ottenuto con successo, il sistema DEVE sostituire i placeholder `Anno 2025`, `Anno di riferimento: 2025` e `Priorita' 2025:` con l'anno corrente nel messaggio di benvenuto.
- **Status**: IMPLEMENTATO

### SR-19 parseQueryParams
- **Pattern EARS**: Il sistema DEVE estrarre i parametri `user_id`, `asl_id`, `asl_name`, `codice_fiscale` e `username` dalla query string della richiesta HTTP.
- **Status**: IMPLEMENTATO

### SR-20 Propagazione queryParams ai Template
- **Pattern EARS**: Il sistema DEVE passare i queryParams (asl_id, asl_name, user_id, codice_fiscale, username) a tutti i template delle 7 pagine per permettere la propagazione dei parametri tra le pagine.
- **Status**: IMPLEMENTATO

### SR-21 Porta Server Configurabile
- **Pattern EARS**: Il sistema DEVE leggere la porta dal config.json e utilizzarla per l'avvio del server Gin, con fallback al valore `8080` se non configurata.
- **Status**: IMPLEMENTATO

### SR-22 Logging Richieste Pagine
- **Pattern EARS**: QUANDO un utente accede a una pagina, il sistema DEVE loggare i parametri della richiesta (user_id, asl_id, asl_name, client_ip) con prefisso strutturato (INDEX_, DEBUG_, LANGGRAPH_DEBUG_, ANALYTICS_, MONITOR_, HISTORY_, ADMIN_RAG_).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### SR-NF01 Framework Web
- **Pattern EARS**: Il sistema DEVE utilizzare il framework Gin (gin-gonic/gin) per il routing HTTP.
- **Status**: IMPLEMENTATO

### SR-NF02 Timeout Recupero Anno
- **Pattern EARS**: Il sistema DEVE utilizzare un timeout di 5 secondi per le chiamate al backend per recuperare l'anno corrente.
- **Status**: IMPLEMENTATO
