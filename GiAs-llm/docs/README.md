# GiAs-llm

Sistema conversazionale basato su LangGraph per il monitoraggio veterinario della Regione Campania.

**Status**: ✅ Operativo e integrato con GChat
**Versione**: 1.3.0 - **LLM + Semantic Search**
**Data ultima modifica**: 2025-12-25

---

## 🎯 Overview

GiAs-llm sostituisce il backend Rasa con un'architettura moderna basata su:
- **LangGraph**: State machine per workflow conversazionali
- **LLM Router**: Classificazione intent con **LLaMA 3.1 via Ollama** (reale, non stub)
- **Tools**: 13 funzioni specializzate per query veterinarie
- **Dataset**: 323,153 record da CSV (piani, controlli, stabilimenti, personale)

### Differenze Rispetto a Rasa

| Feature | Rasa | GiAs-llm |
|---------|------|----------|
| Intent Classification | Rasa NLU | LLM-based Router |
| Workflow | Stories + Rules | LangGraph State Machine |
| Actions | Custom Action Server | LangChain @tool decorator |
| State Management | Tracker Slots | ConversationState TypedDict |
| Response Generation | Templates | LLM generativo + formatters |
| Plan Search | Keyword matching (58 keywords) | **Semantic search (Qdrant + embeddings)** |

---

## 📊 Dati Caricati

```
piani_monitoraggio.csv         →     730 record
Master list rev 11_filtered.csv →     538 record
vw_2025_eseguiti_filtered.csv  →  61,247 record
osa_mai_controllati...csv      → 154,406 record
OCSE_ISP_SEMP_2025...csv       → 101,343 record
vw_diff_programm...csv         →   3,002 record
personale_filtered.csv         →   1,880 record
────────────────────────────────────────────────
TOTALE                         → 323,146 record
```

### Qdrant Vector Database

```
Collection: piani_monitoraggio → 730 vectors (384 dims)
Storage: /opt/lang-env/GiAs-llm/qdrant_storage/ (3.3 MB)
Embedding model: paraphrase-multilingual-MiniLM-L12-v2
```

---

## 🚀 Quick Start

### Installazione

```bash
cd /opt/lang-env/GiAs-llm

# Setup virtuale environment (se necessario)
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt

# Indicizza piani per semantic search (IMPORTANTE!)
python3 tools/indexing/build_qdrant_index.py
```

### Avvio Server

```bash
# Start API server (porta 5005)
./start_server.sh

# Verifica status
curl http://localhost:5005/status

# Stop server
./stop_server.sh
```

**Log location**: `/opt/lang-env/GiAs-llm/logs/api-server.log`

---

## 💬 Uso Programmatico

### Esempio Base

```python
from orchestrator.graph import ConversationGraph

graph = ConversationGraph()

result = graph.run(
    message="quali attività ha il piano A1?",
    metadata={"asl": "NA1", "uoc": "Veterinaria"}
)

print(result["response"])
# Output: **Descrizione Piano A1** ...
```

### Con Risoluzione Automatica UOC

```python
# Metadata solo con user_id → UOC risolta automaticamente
result = graph.run(
    message="chi dovrei controllare per primo oggi?",
    metadata={
        "asl": "AVELLINO",
        "user_id": "42145"  # → Risolve UOC da personale.csv
    }
)

print(result["response"])
# Output: **Stabilimenti Prioritari da Controllare**
#         **ASL:** AVELLINO
#         **Struttura:** UNITA' OPERATIVA COMPLESSA...
```

---

## 🔌 API Endpoints

### 1. Webhook (Rasa-compatible)

**URL**: `POST /webhooks/rest/webhook`

```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "user123",
    "message": "di cosa tratta il piano A1?",
    "metadata": {"asl": "NA1", "user_id": "42145"}
  }'
```

**Response**:
```json
[
  {
    "text": "**Descrizione Piano A1**\n\n...",
    "recipient_id": "user123"
  }
]
```

### 2. Parse Intent (Debug)

**URL**: `POST /model/parse`

```bash
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "ciao"}'
```

**Response**:
```json
{
  "text": "ciao",
  "intent": {"name": "greet", "confidence": 0.95},
  "entities": [],
  "slots": {}
}
```

### 3. Conversation Tracker

**URL**: `GET /conversations/{sender_id}/tracker`

```bash
curl http://localhost:5005/conversations/user123/tracker
```

### 4. Health Check

**URL**: `GET /status`

```bash
curl http://localhost:5005/status
```

---

## 🎭 Intent Supportati

| Intent | Descrizione | Esempio Query | Semantic Search |
|--------|-------------|---------------|----------------|
| `greet` | Saluti iniziali | "ciao", "buongiorno" | - |
| `goodbye` | Saluti finali | "arrivederci", "grazie" | - |
| `ask_help` | Richiesta aiuto | "aiuto", "cosa puoi fare?" | - |
| `ask_piano_description` | Descrizione piano | "di cosa tratta il piano A1?" | - |
| `ask_piano_stabilimenti` | Stabilimenti per piano | "stabilimenti del piano B2" | - |
| `ask_piano_attivita` | Attività per piano | "attività del piano C3" | - |
| `ask_piano_generic` | Query generica piano | "dimmi del piano A1" | - |
| `search_piani_by_topic` | Ricerca per argomento | "piani su allevamenti bovini" | **✅ Qdrant** |
| `ask_priority_establishment` | Priorità programmazione | "chi devo controllare per primo?" | - |
| `ask_risk_based_priority` | Priorità rischio storico | "stabilimenti ad alto rischio" | - |
| `ask_suggest_controls` | Suggerimenti controlli | "suggerimenti mai controllati" | - |
| `ask_delayed_plans` | Piani in ritardo | "piani in ritardo UOC X" | - |
| `fallback` | Non classificabile | Qualsiasi altro input | - |

---

## 🧪 Testing

### Test Manuale

```bash
# Test rapido
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "ciao", "metadata": {}}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['text'])"
```

### Test Suite Completo

```bash
cd /opt/lang-env/GiAs-llm
python3 -m pytest tests/ -v
```

**Test coperti**:
- ✅ Classificazione intent (13 intent)
- ✅ Esecuzione tool (piano, priority, risk, search)
- ✅ Risoluzione UOC da user_id
- ✅ Formattazione risposte
- ✅ Gestione errori con messaggi user-friendly
- ✅ 10/10 domande predefinite GChat (con semantic search)
- ✅ Help con domande cliccabili

---

## 📁 Struttura Progetto

```
/opt/lang-env/GiAs-llm/
├── app/
│   ├── api.py                 # FastAPI server (Rasa-compatible endpoints)
│   └── main.py                # Entry point
├── orchestrator/
│   ├── router.py              # Intent classification (LLM Router)
│   └── graph.py               # LangGraph workflow (ConversationGraph)
├── tools/
│   ├── piano_tools.py         # Query piani di controllo
│   ├── priority_tools.py      # Analisi priorità e ritardi
│   ├── risk_tools.py          # Analisi rischio storico
│   ├── search_tools.py        # Ricerca semantica piani
│   └── indexing/
│       └── build_qdrant_index.py  # Script indicizzazione Qdrant
├── agents/
│   ├── data.py                # Data loading & get_uoc_from_user_id()
│   └── agents/
│       ├── data_agent.py      # DataRetriever, BusinessLogic, RiskAnalyzer
│       └── response_agent.py  # ResponseFormatter, SuggestionGenerator
├── llm/
│   └── client.py              # LLM stub (target: LLaMA 3.1 integration)
├── dataset/                   # CSV files (323K+ record)
│   ├── piani_monitoraggio.csv
│   ├── vw_2025_eseguiti_filtered.csv
│   ├── osa_mai_controllati_con_linea_852-3_filtered.csv
│   ├── personale_filtered.csv
│   └── ...
├── qdrant_storage/            # Vector database (3.3 MB)
│   └── piani_monitoraggio     # Indexed collection
├── logs/
│   └── api-server.log
├── tests/
│   ├── test_router.py
│   ├── test_graph.py
│   └── test_tools.py
├── start_server.sh            # Start FastAPI server
├── stop_server.sh             # Stop server
├── requirements.txt
├── README.md                  # Questo file
├── BUGFIX_REPORT.md           # Report risoluzione bug
├── INTEGRATION_GCHAT.md     # Guida integrazione con GChat
└── CLAUDE.md                  # Istruzioni per Claude Code
```

---

## 🔗 Integrazione GChat

**Path GChat**: `/opt/lang-env/gchat/`

### File Modificati

1. **Debug Page Template**:
   - `/opt/lang-env/gchat/template/debug_langgraph.html`
   - Architettura info: LangGraph + LLM Router
   - Tool badges con colori per categoria

2. **Debug JavaScript**:
   - `/opt/lang-env/gchat/statics/js/debug_langgraph.js`
   - Mapping intent → tool
   - Display UOC risolta automaticamente

### Configurazione Endpoint

Puntare a `http://localhost:5005` invece di `http://localhost:5055` (Rasa)

**Dettagli completi**: Vedi [INTEGRATION_GCHAT.md](./INTEGRATION_GCHAT.md)

---

## 🐛 Bug Fix Report

**Problemi risolti**:
1. ✅ Tutte le query restituivano fallback universale
2. ✅ UOC non presente in metadata GChat
3. ✅ Domande help non cliccabili
4. ✅ Errori mostrati come raw dict

**Cause e soluzioni**:
- ❌ API richiedeva `final_response`, graph restituiva `response` → Fixed
- ❌ StructuredTool decorator non gestito (`.func` missing) → Fixed
- ❌ Pattern matching LLM stub su prompt completo → Fixed su user_message
- ❌ UOC non presente → Risoluzione automatica da user_id con personale.csv
- ❌ Domande help con `"testo"` → Cambiate in `[testo]` per link cliccabili
- ❌ Errori senza `formatted_response` → Aggiunti messaggi user-friendly a tutti i tool

**Dettagli completi**: Vedi [BUGFIX_REPORT.md](./BUGFIX_REPORT.md)

---

## 🔧 Troubleshooting

### Server Non Risponde

```bash
# Verifica processo
ps aux | grep uvicorn

# Riavvia
./stop_server.sh && ./start_server.sh

# Check logs
tail -f logs/api-server.log
```

### UOC Non Risolta

```bash
# Verifica user_id in personale.csv
python3 -c "
import pandas as pd
df = pd.read_csv('dataset/personale_filtered.csv', sep='|')
print(df[df['user_id'] == 42145])
"
```

### Dataset Non Caricato

```bash
# Verifica presenza CSV
ls -lh dataset/*.csv

# Check permessi
chmod 644 dataset/*.csv

# Ricarica
python3 -c "from agents.data import load_data; load_data()"
```

---

## 📈 Roadmap

### ✅ Completato (v1.3.0)

- [x] Migrazione da Rasa a LangGraph
- [x] Estrazione business logic da Rasa actions
- [x] FastAPI server con endpoint Rasa-compatible
- [x] Risoluzione automatica UOC da user_id (personale.csv)
- [x] Integrazione con GChat debug page
- [x] Test suite completo (10/10 domande predefinite)
- [x] Help con domande cliccabili (sintassi `[testo]`)
- [x] Gestione errori formattata (messaggi user-friendly italiano)
- [x] **Integrazione LLaMA 3.1 reale** via Ollama (sostituito stub)
- [x] **Response generation con LLM** per risposte dinamiche e contestuali
- [x] **Semantic search con Qdrant** + sentence-transformers (730 piani indicizzati)

### 🚧 In Progress

- [ ] Prompt engineering avanzato (few-shot, chain-of-thought)
- [ ] Fallback graceful a stub quando Ollama non disponibile

### 📋 TODO

- [ ] Caching risultati semantic search (Redis)
- [ ] Semantic search anche per attività (oltre ai piani)
- [ ] Reranking results con cross-encoder
- [ ] Migrazione CSV → PostgreSQL
- [ ] Async tool execution
- [ ] Monitoring dashboard (Grafana)
- [ ] Rate limiting per API
- [ ] Multi-turn conversation context
- [ ] Logging strutturato (correlation IDs)

---

## 📝 Licenza

Uso interno Regione Campania - Sistema di monitoraggio veterinario

---

## 📚 Documentazione Aggiuntiva

- **[INSTALLATION.md](./INSTALLATION.md)**: 📦 **Guida completa installazione su server Debian** (Python 3.10, Ollama, GiAs-llm, GChat)
- **[PERFORMANCE_TUNING.md](./PERFORMANCE_TUNING.md)**: ⚡ **Ottimizzazione performance su server cloud** (6 GB RAM, 4 CPU - diagnosi e fix lentezza)
- **[SEMANTIC_SEARCH.md](./SEMANTIC_SEARCH.md)**: Guida completa semantic search (RAG, Qdrant, troubleshooting, future improvements)
- **[BUGFIX_REPORT.md](./BUGFIX_REPORT.md)**: Report dettagliato risoluzione bug critici
- **[INTEGRATION_GCHAT.md](./INTEGRATION_GCHAT.md)**: Guida integrazione con GChat (`/opt/lang-env/gchat/`)
- **[CLAUDE.md](./CLAUDE.md)**: Istruzioni per Claude Code (architettura, pattern, convenzioni)
- **[API_README.md](./API_README.md)**: Documentazione endpoint FastAPI
- **[DEBUG_PAGE_SUPPORT.md](./DEBUG_PAGE_SUPPORT.md)**: Compatibilità debug page GChat

---

## 🆘 Support

**Logs**: `/opt/lang-env/GiAs-llm/logs/api-server.log`

**Issues**: Verificare BUGFIX_REPORT.md e INTEGRATION_GCHAT.md prima di aprire nuovi issue

**Performance**: Vedere sezione "Performance" in INTEGRATION_GCHAT.md per metriche e ottimizzazioni
