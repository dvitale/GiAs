# CLAUDE.md

## Overview

GISA-AI e' un assistente virtuale per gli utenfi GISA della Regione Campania. Risponde a domande su piani di monitoraggio, stabilimenti, controlli ufficiali, priorita' di ispezione e analisi del rischio, interrogando il suo database contenente estrazioni dati di GISA.

## Architettura

```
Browser --> gchat (Go, :8080) --> GiAs-llm (Python, :5005) --> LLM Provider
                                        |                         |
                                        v                         v
                                   PostgreSQL (GIAS)        Ollama / llama.cpp /
                                   Qdrant (vector search)   OpenAI / Anthropic /
                                                            OpenAI-compat (Mistral, Groq)
```

- **Backend** (`GiAs-llm/`): FastAPI + LangGraph + multi-model LLM. Dettagli in `GiAs-llm/CLAUDE.md`
- **Frontend** (`gchat/`): Go/Gin + HTML/CSS/JS vanilla. Dettagli in `gchat/CLAUDE.md`
- **Database**: PostgreSQL (gias_db) + Qdrant (vector search locale)

## Quick Start

```bash
cd GiAs-llm && scripts/server.sh start   
cd gchat && ./all.sh                      # Frontend (compila Go + riavvia)
```

## Convenzioni codice

- **Lingua**: codice in inglese, commenti/log/UI in italiano
- **Logging**: prefissi strutturati (CHAT_, LLM_, USER_, INDEX_, CHATLOG_PROXY_, HISTORY_, ANALYTICS_, MONITOR_)
- **Config**: JSON in `configs/config.json` (backend) e `config/config.json` (frontend)
- **Base path**: `/gias/webchat` per reverse proxy
- **Script shell**: non modificare gli .sh esistenti nella root di gchat
- **Regola test**: se un test fallisce per bug backend, correggere il backend, mai il test
- **Help domande**: le domande suggerite in `help_tool()` devono mappare a intent reali in `VALID_INTENTS`

## Metodologia SDD (Software Design Description)

Il progetto adotta una metodologia  SDD con requisiti in notazione EARS.

**Flusso**: `/req <descrizione>` → revisione → `/implement <ID>` → tag `# REQ: [ID]` nel codice → aggiorna `SDD/traceability.md`

| Comando | Scopo |
|---------|-------|
| `/req <descrizione>` | Analizza richiesta, propone requisiti EARS. **Non modifica file** — attende approvazione |
| `/implement <ID-001, ID-002>` | Implementa requisiti, aggiunge `# REQ: [ID]`, aggiorna status e traceability |

Ogni componente ha `SDD/requirements/` (file EARS) e `SDD/traceability.md`. ID progressivi per componente (LG-, IC-, TE-, API-, SR-, CU-, etc.). Status: DA IMPLEMENTARE → IMPLEMENTATO. Requisiti rimossi: marcare come RIMOSSO (non cancellare).

## Manutenzione documentazione

- **3 file CLAUDE.md**: root (questo), `GiAs-llm/CLAUDE.md` (backend), `gchat/CLAUDE.md` (frontend). Non crearne altri.
- **Singola fonte di verita'**: ogni info in UN solo file. Dettagli backend → `GiAs-llm/CLAUDE.md`. Dettagli frontend → `gchat/CLAUDE.md`. Info trasversali → qui.
- **Aggiornare contestualmente** al codice: nuovo intent → backend CLAUDE.md. Nuovo endpoint → CLAUDE.md del componente. Nuova convenzione → root.
- **Non duplicare** la lista intent, il flusso del grafo, il ConversationState, gli endpoint, o dettagli implementativi tra i file.
