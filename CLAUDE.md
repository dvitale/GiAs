# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

GISA-AI e' un assistente virtuale per i servizi veterinari delle ASL della Regione Campania. Risponde a domande su piani di monitoraggio, stabilimenti, controlli ufficiali, priorita' di ispezione e analisi del rischio, interrogando il database GIAS (Gestione Integrata Attivita' Sanitarie).

## Architettura

```
Browser --> gchat (Go, :8080) --> GiAs-llm (Python, :5005) --> Ollama (:11434)
                                        |                         |
                                        v                         v
                                   PostgreSQL (GIAS)        llama3.2:3b
                                   Qdrant (vector search)
```

### Backend - GiAs-llm/
- **Framework**: FastAPI + Uvicorn
- **Orchestrazione**: LangGraph (workflow ad agenti)
- **LLM**: Ollama (default llama3.2:3b) oppure llama.cpp
- **ML**: PyTorch, XGBoost (modello rischio v4)
- **Embeddings**: sentence-transformers
- **Database**: PostgreSQL (psycopg2), Qdrant (ricerca semantica)
- **Data processing**: Pandas, NumPy
- **Dettagli**: vedere `GiAs-llm/docs/CLAUDE.md`

### Frontend - gchat/
- **Server**: Go 1.21+ con Gin framework
- **UI**: HTML/CSS/JS vanilla (tema light/dark, responsive)
- **Comunicazione**: POST JSON verso backend, compatibile protocollo Rasa
- **Dettagli**: vedere `gchat/CLAUDE.md`

### Database
- **PostgreSQL** (host: GIAS, db: gias_db) - tabelle: piani_monitoraggio, masterlist, cu_eseguiti, osa_mai_controllati, ocse_isp_semp, personale
- **Qdrant** - storage vettoriale locale per ricerca semantica

## Comandi

### Avvio completo

```bash
# 1. Backend (richiede Ollama attivo su :11434)
cd GiAs-llm && scripts/server.sh start

# 2. Frontend
cd gchat && ./all.sh    # compila Go + riavvia server
```

### Gestione backend (GiAs-llm)

```bash
scripts/server.sh start|stop|restart|status|logs|test
GIAS_LLM_MODEL=velvet scripts/server.sh start   # modello custom
```

### Gestione frontend (gchat)

```bash
./all.sh        # build + stop + run (COMANDO PRINCIPALE)
./build.sh      # solo compilazione
./run.sh        # solo avvio (nohup)
./stop.sh       # stop
./status.sh     # health check
```

### Test

```bash
# Test backend
cd GiAs-llm && scripts/server.sh test

# Singolo test
cd GiAs-llm && python -m pytest tests/test_graph.py -v
cd GiAs-llm && python -m pytest tests/test_graph.py::TestGIASGraph::test_help_tool -v

# Test API manuale
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"piani in ritardo","metadata":{"asl":"AVELLINO"}}'
```

### Endpoint principali

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `localhost:5005/` | GET | Health check backend |
| `localhost:5005/webhooks/rest/webhook` | POST | Chat principale |
| `localhost:5005/status` | GET | Stato + dati caricati |
| `localhost:5005/model/parse` | POST | Parsing NLU |
| `localhost:8080/gias/webchat/` | GET | UI chat |
| `localhost:8080/gias/webchat/chat` | POST | Invio messaggio |

## Convenzioni codice

- **Lingua**: codice in inglese, commenti/log/UI in italiano
- **Logging**: prefissi strutturati (CHAT_, BACKEND_, USER_, INDEX_)
- **Pattern backend**: Factory (data sources), Singleton (graph + dati globali), lazy loading
- **Sessioni**: TTL 5 minuti, state in memoria (dict in api.py)
- **Config**: JSON in `configs/config.json` (backend) e `config/config.json` (frontend)
- **Base path**: `/gias/webchat` per reverse proxy
- **Script shell**: non modificare gli .sh esistenti nella root di gchat
- **Regola test**: se un test fallisce per bug backend, correggere il backend, mai il test
- **Help domande**: le domande suggerite in `help_tool()` devono mappare a intent reali in `VALID_INTENTS`. Mai suggerire domande a cui il sistema non sa rispondere.

## Note per sviluppo

- **`./all.sh`** e' il comando per compilare e riavviare gchat. Usare sempre questo.
- **Ollama obbligatorio**: il backend richiede Ollama su localhost:11434 con il modello precaricato.
- **Dati precaricati**: al primo avvio il backend carica tutti i dati da PostgreSQL/CSV in memoria. Il primo request puo' essere lento.
- **Protocollo Rasa**: l'API webhook mantiene compatibilita' con il formato Rasa (`sender`, `message`, `metadata`) anche se il backend usa LangGraph.
- **Metadata utente**: passati via query string URL -> template JS -> POST body -> backend state. Il campo `asl` (nome) ha priorita' su `asl_id`.
- **Config duplicata**: backend e frontend hanno ciascuno il proprio `config.json` con impostazioni indipendenti.
- **Timeout chain**: JS (75s) > Go (60s) > Backend streaming (120s). Il client deve avere timeout maggiore del server.
- **Health check**: il frontend verifica la disponibilita' del backend prima di ogni richiesta chat.
- **Refactoring docs**: il piano di refactoring completo (architettura, migrazione, rollback) e' in `GiAs-llm/docs/refactoring-dialogue-manager.md`.

## Mappa documentazione CLAUDE.md

Ogni componente ha il proprio CLAUDE.md con i dettagli specifici. Questo file (root) contiene solo le informazioni trasversali e operative. **Non duplicare qui contenuti dei sotto-documenti.**

| File | Perimetro | Contenuti principali |
|------|-----------|----------------------|
| `CLAUDE.md` (questo file) | Progetto intero | Overview, comandi, convenzioni, note operative |
| `GiAs-llm/docs/CLAUDE.md` | Backend Python | Architettura 3-layer, LangGraph, intent, tool, hybrid search, risk predictor, file tree |
| `gchat/CLAUDE.md` | Frontend Go | Struttura Go/Gin, comunicazione con backend, UI/UX, debug API, timeout |

## Regole di manutenzione documentazione

Per evitare disallineamenti tra i CLAUDE.md, seguire queste regole:

### Principio di singola fonte di verita'

Ogni informazione deve essere documentata in UN SOLO file CLAUDE.md:
- **Dettagli architetturali backend** (intent, tool, flusso grafo, ConversationState) → solo in `GiAs-llm/docs/CLAUDE.md`
- **Dettagli frontend** (strutture Go, JS, CSS, debug curl) → solo in `gchat/CLAUDE.md`
- **Informazioni trasversali** (comandi avvio, endpoint, convenzioni, config paths) → solo in questo file root

### Quando aggiornare

Aggiornare il CLAUDE.md pertinente CONTESTUALMENTE alla modifica del codice:

| Modifica al codice | CLAUDE.md da aggiornare |
|---------------------|-------------------------|
| Nuovo intent in `VALID_INTENTS` | `GiAs-llm/docs/CLAUDE.md` (lista intent + count) |
| Nuovo tool in `TOOL_REGISTRY` | `GiAs-llm/docs/CLAUDE.md` (file tree + common patterns) |
| Nuovo file in `orchestrator/` | `GiAs-llm/docs/CLAUDE.md` (file tree) |
| Modifica struttura gchat | `gchat/CLAUDE.md` |
| Nuovo endpoint API | Root `CLAUDE.md` (tabella endpoint) |
| Nuova convenzione di progetto | Root `CLAUDE.md` (sezione convenzioni) |
| Modifica comandi avvio/test | Root `CLAUDE.md` (sezione comandi) |

### Sincronizzazione tabella intents nel database

**REGOLA OBBLIGATORIA**: Ogni modifica agli intent (`VALID_INTENTS` in `orchestrator/router.py`) deve essere seguita dall'aggiornamento della tabella `intents` nel database PostgreSQL (`gias_db`).

La tabella `intents` e' la fonte di verita' per la documentazione strutturata degli intent e contiene:
- `intent`: nome intent (deve corrispondere a `VALID_INTENTS`)
- `section_number`: numero sezione per ordinamento
- `title`: titolo descrittivo in italiano
- `example_question`: domanda di esempio
- `tool`: tool o funzione invocata
- `graph_node`: nodo del grafo LangGraph
- `data_retriever`: metodo DataRetriever usato
- `business_logic`: metodo BusinessLogic usato
- `two_phase_threshold`: soglia per risposta two-phase (o null)
- `required_slots`: slot richiesti (JSON array)
- `query_equivalent`: query SQL equivalente
- `notes`: note aggiuntive

**Procedura di sincronizzazione**:
1. Dopo aver aggiunto/modificato un intent in `VALID_INTENTS`
2. Eseguire INSERT/UPDATE sulla tabella `intents` con tutti i campi rilevanti
3. Verificare che il conteggio intent nel DB corrisponda a `len(VALID_INTENTS)`

**Comando di verifica**:
```sql
SELECT COUNT(*) FROM intents;  -- Deve essere uguale a len(VALID_INTENTS)
```

### Checklist per aggiornamento

Prima di considerare completata una modifica che tocca architettura, intent, tool o struttura file:

1. Verificare che il CLAUDE.md pertinente rifletta la modifica
2. Verificare che NON si stia duplicando l'informazione in un altro CLAUDE.md
3. Se si aggiunge un intent: aggiornare `VALID_INTENTS` count, lista intent, `REQUIRED_SLOTS` se applicabile
4. Se si aggiunge un file: aggiornare il file tree nel CLAUDE.md del componente

### Cosa NON fare

- **Non duplicare** la lista intent, il flusso del grafo o il ConversationState nel root CLAUDE.md
- **Non creare** nuovi CLAUDE.md per sotto-componenti (mantenere la struttura a 3 file)
- **Non documentare** dettagli implementativi effimeri (numeri di riga, conteggi record) che cambiano frequentemente
