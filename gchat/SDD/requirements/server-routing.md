# Server Routing

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/main.go, app/config.go

## Requisiti Funzionali

### SR-01 Base Path per Reverse Proxy
- **Pattern EARS**: Il sistema DEVE registrare tutte le route sotto il base path `/gias/webchat` per compatibilita' con il reverse proxy.
- **Status**: IMPLEMENTATO

### SR-02 Route pagine HTML con template data injection
- **Pattern EARS**: Il sistema DEVE servire le seguenti pagine con i rispettivi dati iniettati nel template: (1) GET/POST `/gias/webchat/` renderizza `index.html` con dati utente, messaggio di benvenuto, basePath e queryParams, (2) GET `/gias/webchat/debug` renderizza `debug.html` con dati utente, basePath, queryParams, llmModel e framework, (3) GET `/gias/webchat/debug/langgraph` renderizza `debug_langgraph.html` con gli stessi dati del debug, (4) GET `/gias/webchat/analytics` renderizza `analytics.html` con dati utente, basePath, backendUrl e queryParams, (5) GET `/gias/webchat/monitor` renderizza `monitor.html` con dati utente, basePath, backendUrl e queryParams, (6) GET `/gias/webchat/history` renderizza `history.html` con dati utente, basePath, backendUrl e queryParams, (7) GET `/gias/webchat/admin/rag` renderizza `admin_rag.html` con title e basePath senza autenticazione.
- **Status**: IMPLEMENTATO
- **Accorpa**: SR-02, SR-03, SR-04, SR-05, SR-06, SR-07, SR-08, SR-09

### SR-10 Servizio File Statici
- **Pattern EARS**: Il sistema DEVE servire i file statici dalla directory `./statics` sotto il path `/gias/webchat/static`.
- **Status**: IMPLEMENTATO

### SR-11 Template Function json
- **Pattern EARS**: Il sistema DEVE registrare una template function `json` che serializza un valore Go in JSON sicuro per l'inserimento nel template HTML, restituendo `null` se il valore e' nil o la serializzazione fallisce.
- **Status**: IMPLEMENTATO

### SR-12 Caricamento Template
- **Pattern EARS**: Il sistema DEVE caricare tutti i template HTML dalla directory `template/*` tramite `LoadHTMLGlob`.
- **Status**: IMPLEMENTATO

### SR-13 Gestione dati utente e hierarchy HTML
- **Pattern EARS**: QUANDO il parametro `user_id` e' presente, il sistema DEVE caricare i dati utente dal CSV tramite `GetPersonaleByUserID` e restituire un oggetto con user_id, namefirst (uppercase), namelast (uppercase), descrizione, asl, codice_fiscale e hierarchy. QUANDO il parametro `asl_name` dalla query string e' non vuoto, DEVE utilizzarlo al posto del valore ASL dal CSV. QUANDO il campo `Descrizione` contiene segmenti separati da `->`, DEVE generare una struttura HTML gerarchica `<li>...<ul><li>...</li></ul></li>` con escape HTML per prevenire injection.
- **Status**: IMPLEMENTATO
- **Accorpa**: SR-13, SR-14, SR-15

### SR-16 Anno dinamico dal backend
- **Pattern EARS**: QUANDO si renderizza la pagina principale, il sistema DEVE ottenere l'anno corrente dal backend provando prima l'endpoint `/config` e poi `/status` come fallback, con timeout di 5 secondi. SE l'anno non puo' essere ottenuto, DEVE utilizzare il messaggio di welcome di default senza sostituzione. QUANDO l'anno e' ottenuto con successo, DEVE sostituire i placeholder `Anno 2025`, `Anno di riferimento: 2025` e `Priorita' 2025:` con l'anno corrente nel messaggio di benvenuto.
- **Status**: IMPLEMENTATO
- **Accorpa**: SR-16, SR-17, SR-18

### SR-19 Query params estrazione e propagazione
- **Pattern EARS**: Il sistema DEVE estrarre i parametri `user_id`, `asl_id`, `asl_name`, `codice_fiscale` e `username` dalla query string della richiesta HTTP e passarli a tutti i template delle 7 pagine per permettere la propagazione dei parametri tra le pagine.
- **Status**: IMPLEMENTATO
- **Accorpa**: SR-19, SR-20

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
