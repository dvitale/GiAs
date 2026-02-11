# GChat - Interfaccia Web per Chatbot GIAS

Interfaccia web sviluppata in Go per comunicare con il backend LangGraph + LLM di GIAS.

## Struttura del Progetto

```
gchat/
├── app/                    # Codice sorgente Go
│   ├── main.go            # Server web principale
│   ├── config.go          # Gestione configurazione
│   └── llm_client.go      # Client API per backend LLM
├── bin/                   # Eseguibili compilati
├── config/                # File di configurazione
│   └── config.json        # Configurazione principale
├── log/                   # File di log
├── statics/               # File statici
│   ├── css/              # Fogli di stile
│   ├── js/               # JavaScript
│   └── img/              # Immagini
├── template/              # Template HTML
│   └── index.html        # Interfaccia chat
├── build.sh              # Script di compilazione
├── run.sh                # Script di avvio
├── stop.sh               # Script di arresto
├── status.sh             # Script di status
├── all.sh                # Script completo (build + restart)
└── go.mod                # Dipendenze Go
```

## Funzionalità

- **Interfaccia Web Moderna**: UI responsive con tema light/dark
- **Chat in Tempo Reale**: Comunicazione con il backend LangGraph
- **Debug Visualizer**: Visualizzatore del workflow LangGraph
- **Configurazione Flessibile**: Configurazione JSON per server e backend
- **Logging Completo**: Log strutturati per debugging
- **Script di Gestione**: Script per build, avvio, stop e deployment

## Requisiti

- Go 1.21 o superiore
- Backend GiAs-llm in esecuzione (default: http://localhost:5005)

## Installazione e Avvio

### 1. Build e avvio completo
```bash
./all.sh
```

### 2. Configurazione
Modifica `config/config.json` se necessario:
```json
{
  "server": {
    "port": "8080",
    "host": "localhost"
  },
  "llm_server": {
    "url": "http://localhost:5005",
    "timeout": 60
  },
  "log": {
    "level": "info",
    "file": "log/app.log"
  }
}
```

### 3. Avvio del server
```bash
./run.sh
```

L'applicazione sarà disponibile su: http://localhost:8080/gias/webchat/

## Script Disponibili

- `all.sh` - Build + stop + run (COMANDO PRINCIPALE)
- `build.sh` - Compila l'applicazione
- `run.sh` - Avvia il server
- `stop.sh` - Ferma il server
- `status.sh` - Verifica lo status

## API Endpoints

### GET /gias/webchat/
Interfaccia web principale

### POST /gias/webchat/chat
Endpoint per la comunicazione con il chatbot

### GET /gias/webchat/debug
Pagina debug standard

### GET /gias/webchat/debug/langgraph
LangGraph Workflow Visualizer

## Log

I log sono salvati in:
- `log/out.txt` - Output standard
- `log/err.txt` - Errori

## Personalizzazione

- **Stili**: Modifica `statics/css/style.css`
- **JavaScript**: Modifica `statics/js/chat.js`
- **Template**: Modifica `template/index.html`
- **Configurazione**: Modifica `config/config.json`
