# Integrazione GiAs-llm con GChat

**Path GChat**: `/opt/lang-env/gchat/`
**API Endpoint**: `http://localhost:5005`

---

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                    GChat (Frontend)                        │
│                   /opt/lang-env/gchat/                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Debug Page: debug_langgraph.html                  │    │
│  │  JavaScript: debug_langgraph.js                    │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           │ HTTP POST/GET                    │
│                           ▼                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ REST API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              GiAs-llm FastAPI Server                         │
│              /opt/lang-env/GiAs-llm/                        │
│                    Port: 5005                                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  app/api.py - FastAPI Endpoints                    │    │
│  │   - POST /webhooks/rest/webhook                    │    │
│  │   - POST /model/parse                              │    │
│  │   - GET  /conversations/{id}/tracker               │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  orchestrator/graph.py - LangGraph Workflow        │    │
│  │   ConversationGraph                                │    │
│  │    ├─ classify_node                                │    │
│  │    ├─ route_by_intent                              │    │
│  │    ├─ tool_nodes (13 tools)                        │    │
│  │    └─ response_generator_node                      │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  tools/ - @tool decorated functions                │    │
│  │   ├─ piano_tools.py                                │    │
│  │   ├─ priority_tools.py                             │    │
│  │   ├─ risk_tools.py                                 │    │
│  │   └─ search_tools.py                               │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  agents/data.py - Data Access Layer                │    │
│  │   ├─ 323K+ CSV records loaded                      │    │
│  │   ├─ get_uoc_from_user_id()                        │    │
│  │   └─ DataRetriever, BusinessLogic, RiskAnalyzer    │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Endpoints API

### 1. Webhook Conversazionale

**URL**: `POST /webhooks/rest/webhook`

**Compatibilità**: Rasa REST Channel

**Request**:
```json
{
  "sender": "user_12345",
  "message": "chi dovrei controllare per primo oggi?",
  "metadata": {
    "asl": "AVELLINO",
    "asl_id": "201",
    "user_id": "42145",
    "codice_fiscale": "MNTWTR87S03F839J",
    "username": "mario.rossi"
  }
}
```

**Response**:
```json
[
  {
    "text": "**Stabilimenti Prioritari da Controllare**\n**ASL:** AVELLINO\n...",
    "recipient_id": "user_12345"
  }
]
```

**Metadata Supportati**:
- `asl` (string): Codice ASL (es. "AVELLINO", "NA1", "SA1")
- `asl_id` (string): ID numerico ASL
- `user_id` (string): ID utente → **risolve automaticamente UOC**
- `uoc` (string, optional): Nome UOC esplicito (fallback se presente)
- `codice_fiscale` (string): CF utente
- `username` (string): Username

**Note Importanti**:
- Se `uoc` non è presente nei metadata, il sistema lo risolve automaticamente da `user_id` usando `personale_filtered.csv` (1880 record)
- User ID `"42145"` viene mappato a `"UNITA' OPERATIVA COMPLESSA SERVIZIO IGIENE DEGLI ALIMENTI E DELLA NUTRIZIONE"`

---

### 2. Parse Intent (Debug)

**URL**: `POST /model/parse`

**Request**:
```json
{
  "text": "di cosa tratta il piano A1?",
  "metadata": {
    "asl": "NA1"
  }
}
```

**Response**:
```json
{
  "text": "di cosa tratta il piano A1?",
  "intent": {
    "name": "ask_piano_description",
    "confidence": 0.95
  },
  "entities": [
    {
      "entity": "piano_code",
      "value": "A1"
    }
  ],
  "slots": {
    "piano_code": "A1"
  }
}
```

**Intents Supportati**:
1. `greet` - Saluti iniziali
2. `goodbye` - Saluti finali
3. `ask_help` - Richiesta aiuto
4. `ask_piano_description` - Descrizione piano
5. `ask_piano_stabilimenti` - Stabilimenti per piano
6. `ask_piano_attivita` - Attività per piano
7. `ask_piano_generic` - Query generica su piano
8. `search_piani_by_topic` - Ricerca piani per argomento
9. `ask_priority_establishment` - Priorità controlli programmazione
10. `ask_risk_based_priority` - Priorità basate su rischio storico
11. `ask_suggest_controls` - Suggerimenti controlli mai eseguiti
12. `ask_delayed_plans` - Piani in ritardo per struttura
13. `fallback` - Non classificabile

---

### 3. Tracker Conversazione (Debug)

**URL**: `GET /conversations/{sender_id}/tracker`

**Response**:
```json
{
  "sender_id": "user_12345",
  "slots": {
    "piano_code": "A1",
    "asl": "AVELLINO"
  },
  "latest_message": {
    "text": "di cosa tratta il piano A1?",
    "intent": "ask_piano_description"
  },
  "metadata": {
    "asl": "AVELLINO",
    "user_id": "42145"
  }
}
```

---

### 4. Status / Health Check

**URL**: `GET /status` o `GET /`

**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "model_loaded": true
}
```

---

## File GChat Modificati

### 1. Debug Page Template

**Path**: `/opt/lang-env/gchat/template/debug_langgraph.html`

**Modifiche principali**:
- Header badge: `LangGraph + LLM` (era: "Rasa")
- Architecture info panel:
  - **Router**: LLM-based Intent Classification
  - **Tools**: Piano, Priority, Risk, Search
  - **State**: ConversationState (TypedDict)
- Sezioni aggiornate:
  - "Intent Classification" (era: "Rasa NLU Intent")
  - "Tools Eseguiti" (era: "Actions Eseguite")
  - "Conversation State" (era: "Tracker Slots")

**Tool Badge Colors**:
- 🔵 `piano` tools → Blue (#3b82f6)
- 🟢 `search` tools → Green (#10b981)
- 🟠 `priority` tools → Orange (#f59e0b)
- 🔴 `risk` tools → Red (#ef4444)

---

### 2. Debug JavaScript

**Path**: `/opt/lang-env/gchat/statics/js/debug_langgraph.js`

**Classe**: `LangGraphDebugChatBot`

**Mapping Intent → Tool**:
```javascript
const intentToTool = {
  'greet': { name: 'greet_tool', category: 'system' },
  'ask_piano_description': { name: 'piano_description_tool', category: 'piano' },
  'ask_piano_stabilimenti': { name: 'piano_stabilimenti_tool', category: 'piano' },
  'ask_piano_attivita': { name: 'piano_attivita_tool', category: 'piano' },
  'ask_piano_generic': { name: 'piano_generic_tool', category: 'piano' },
  'search_piani_by_topic': { name: 'search_piani_tool', category: 'search' },
  'ask_priority_establishment': { name: 'priority_establishment_tool', category: 'priority' },
  'ask_risk_based_priority': { name: 'risk_based_priority_tool', category: 'risk' },
  'ask_suggest_controls': { name: 'suggest_controls_tool', category: 'priority' },
  'ask_delayed_plans': { name: 'delayed_plans_tool', category: 'priority' },
  'goodbye': { name: 'goodbye_tool', category: 'system' },
  'ask_help': { name: 'help_tool', category: 'system' },
  'fallback': { name: 'fallback_tool', category: 'system' }
};
```

**Funzioni principali**:
- `updateToolsDisplay(response)` - Visualizza tool eseguito con badge colorato
- `updateStateDisplay(response)` - Distingue metadata (context) vs slots (extracted)
- `sendMessage()` - POST a `/webhooks/rest/webhook` con metadata da form

---

## Deployment GChat

### Opzione 1: URL Separato (Raccomandato)

Creare nuovo percorso dedicato:
```
http://yourdomain.com/debug-langgraph
```

**Vantaggi**:
- Nessuna modifica a deployment Rasa esistente
- A/B testing facile
- Rollback immediato se necessario

**Setup**:
1. Configurare reverse proxy (nginx/Apache) per `/debug-langgraph`
2. Servire `debug_langgraph.html` invece di `debug.html`
3. Aggiornare riferimenti JavaScript a `debug_langgraph.js`

---

### Opzione 2: Sostituire Debug Page Esistente

**ATTENZIONE**: Richiede backup e disattivazione temporanea Rasa

**Step**:
```bash
# 1. Backup file originali
cp /opt/lang-env/gchat/template/debug.html /opt/lang-env/gchat/template/debug.html.backup
cp /opt/lang-env/gchat/statics/js/debug.js /opt/lang-env/gchat/statics/js/debug.js.backup

# 2. Sostituire con versione LangGraph
cp /opt/lang-env/gchat/template/debug_langgraph.html /opt/lang-env/gchat/template/debug.html
cp /opt/lang-env/gchat/statics/js/debug_langgraph.js /opt/lang-env/gchat/statics/js/debug.js

# 3. Riavviare web server
sudo systemctl restart nginx  # o apache2
```

---

## Configurazione Endpoint

### File di Configurazione GChat

Se GChat usa un file di config (es. `config.js`, `settings.py`), aggiornare endpoint:

```javascript
// config.js
const ENDPOINTS = {
  rasa: 'http://localhost:5055',       // Vecchio Rasa (deprecato)
  langgraph: 'http://localhost:5005',  // Nuovo GiAs-llm
};

// Usare langgraph come default
const API_ENDPOINT = ENDPOINTS.langgraph;
```

**O** in Python (se GChat è Flask/Django):
```python
# settings.py
CHATBOT_ENDPOINT = os.getenv('CHATBOT_ENDPOINT', 'http://localhost:5005')
```

---

## Test Integrazione

### 1. Test Manuale da Debug Page

**URL Debug**: `http://localhost/debug-langgraph` (o percorso configurato)

**Test Cases**:
1. **Saluto**:
   - Input: `"ciao"`
   - Expected: `"Benvenuto nel sistema di monitoraggio veterinario della Regione Campania."`

2. **Query Piano**:
   - Input: `"di cosa tratta il piano A1?"`
   - Expected: Descrizione completa Piano A1 (2935 caratteri)
   - Verifica: Badge "piano_description_tool" blu

3. **Priority con User ID**:
   - Input: `"chi dovrei controllare per primo oggi?"`
   - Metadata: `{"asl": "AVELLINO", "user_id": "42145"}`
   - Expected: Lista stabilimenti prioritari con UOC risolta automaticamente
   - Verifica: Badge "priority_establishment_tool" arancione

4. **Risk Analysis**:
   - Input: `"stabilimenti ad alto rischio"`
   - Expected: Analisi rischio storico basato su NC
   - Verifica: Badge "risk_based_priority_tool" rosso

---

### 2. Test Automatizzato

**Script**: `/opt/lang-env/GiAs-llm/test_rasaweb_integration.py`

```python
#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:5005"

def test_webhook_integration():
    """Simula richiesta da GChat debug page"""

    # Simula form metadata da GChat
    metadata = {
        "asl": "AVELLINO",
        "asl_id": "201",
        "user_id": "42145",
        "codice_fiscale": "TESTCF123",
        "username": "test.user"
    }

    payload = {
        "sender": "debug_user_test",
        "message": "chi dovrei controllare per primo oggi?",
        "metadata": metadata
    }

    response = requests.post(f"{BASE_URL}/webhooks/rest/webhook", json=payload)

    assert response.status_code == 200, f"Status code: {response.status_code}"

    result = response.json()
    assert len(result) == 1, "Deve restituire esattamente 1 messaggio"

    text = result[0]['text']
    assert len(text) > 100, f"Risposta troppo corta: {len(text)} caratteri"
    assert "AVELLINO" in text, "Risposta deve contenere ASL"
    assert "Stabilimenti" in text or "UOC" in text, "Risposta deve contenere dati priorità"

    print("✅ Test integrazione GChat PASSATO")
    print(f"   - Status: {response.status_code}")
    print(f"   - Response length: {len(text)} caratteri")
    print(f"   - Preview: {text[:200]}...")

if __name__ == "__main__":
    test_webhook_integration()
```

**Esecuzione**:
```bash
python3 /opt/lang-env/GiAs-llm/test_rasaweb_integration.py
```

---

## Monitoring e Troubleshooting

### Log Locations

**API Server Logs**:
```bash
tail -f /opt/lang-env/GiAs-llm/logs/api-server.log
```

**Pattern tipici**:
```
INFO:__main__:[Webhook] Ricevuto messaggio da debug_user_1766596665548: chi dovrei controllare per primo oggi?
INFO:__main__:[Webhook] Metadata: {'asl': 'AVELLINO', 'user_id': '42145', ...}
INFO:__main__:[Webhook] Risposta generata (2733 caratteri)
[Data] Caricati: piani=730, attivita=538, controlli=61247, osa=118729, ocse=101343, diff_prog_eseg=3002, personale=1880
```

---

### Problemi Comuni

#### 1. **Connection Refused**

**Sintomo**: `ECONNREFUSED localhost:5005`

**Causa**: API server non avviato

**Soluzione**:
```bash
cd /opt/lang-env/GiAs-llm
./start_server.sh

# Verifica
curl http://localhost:5005/status
```

---

#### 2. **UOC Non Risolta**

**Sintomo**: Errore `"UOC non specificata"` anche con `user_id` presente

**Debug**:
```bash
# Verifica personale.csv caricato
grep "personale=" /opt/lang-env/GiAs-llm/logs/api-server.log
# Expected: personale=1880

# Verifica user_id esiste
python3 << EOF
import pandas as pd
df = pd.read_csv('/opt/lang-env/GiAs-llm/dataset/personale_filtered.csv', sep='|')
print(df[df['user_id'] == 42145])
EOF
```

**Soluzione**: Aggiungere utente a `personale_filtered.csv` o passare `uoc` esplicitamente in metadata

---

#### 3. **Intent Sempre Fallback**

**Sintomo**: Tutte le query → `"Non ho capito la tua richiesta. Puoi riformularla?"`

**Debug**:
```bash
# Test parse endpoint
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "ciao"}'

# Expected: {"intent": {"name": "greet", ...}}
```

**Causa possibile**: Stub LLM pattern matching non aggiornato

**Soluzione**: Verificare `/opt/lang-env/GiAs-llm/llm/client.py:_mock_classification()`

---

#### 4. **Risposta Vuota o Troppo Breve**

**Sintomo**: Response `{"text": "", "recipient_id": "..."}`

**Debug**:
```bash
# Verifica dataset caricati
curl http://localhost:5005/status

# Controlla log per errori caricamento CSV
grep "Errore caricamento" /opt/lang-env/GiAs-llm/logs/api-server.log
```

**Soluzione**: Verificare presenza file CSV in `/opt/lang-env/GiAs-llm/dataset/`

---

## Sicurezza

### 1. Firewall Rules

**Produzione**: Bloccare porta 5005 dall'esterno
```bash
# Permettere solo localhost
sudo ufw allow from 127.0.0.1 to any port 5005
```

**Reverse Proxy**: Esporre solo tramite nginx/Apache con autenticazione

---

### 2. Validazione Input

Il sistema valida automaticamente:
- ✅ Lunghezza messaggi (max: illimitato, gestito da Pydantic)
- ✅ Formato metadata (Dict[str, Any])
- ✅ Sender ID presente (required)

**Non validato**:
- ❌ SQL Injection (N/A - usa solo Pandas CSV, no DB)
- ❌ XSS (responsabilità frontend GChat)

---

### 3. Rate Limiting

**Consigliato**: Implementare rate limiting in nginx per prevenire DoS

```nginx
# /etc/nginx/conf.d/ratelimit.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location /api/langgraph/ {
    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass http://localhost:5005;
}
```

---

## Performance

### Metriche Attuali

| Metrica | Valore | Note |
|---------|--------|------|
| Cold start | ~3s | Caricamento 323K CSV |
| Warm request | ~50-200ms | Intent + tool execution |
| Response size | 25-3000 chars | Dipende da query |
| Memory footprint | ~500MB | Pandas DataFrames in RAM |
| Concurrent users | ~50-100 | Limiti uvicorn default |

---

### Ottimizzazioni Possibili

1. **Caching**:
   ```python
   # Cachare risultati frequenti
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def get_piano_description(piano_code: str):
       # ...
   ```

2. **Lazy Loading CSV**:
   Caricare solo quando tool viene chiamato (tradeoff: latenza primo request)

3. **Database Migration**:
   Migrare CSV → PostgreSQL per query più veloci su dataset grandi

4. **Async Tools**:
   ```python
   async def piano_tool_async(piano_code: str):
       # Esecuzione non-blocking
   ```

---

## Riferimenti

- **GiAs-llm Repo**: `/opt/lang-env/GiAs-llm/`
- **GChat Repo**: `/opt/lang-env/gchat/`
- **API Docs**: `http://localhost:5005/docs` (FastAPI auto-generated)
- **Bug Report**: `/opt/lang-env/GiAs-llm/BUGFIX_REPORT.md`
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
