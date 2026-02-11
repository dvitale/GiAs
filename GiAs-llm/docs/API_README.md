# FastAPI Wrapper per GiAs-llm

## Panoramica

Questo documento descrive l'implementazione del wrapper FastAPI per GiAs-llm, compatibile con il formato Rasa REST Channel utilizzato da GChat.

## Architettura

```
Client (GChat/curl)
        ↓
FastAPI (porta 5005)
        ↓
ConversationGraph (LangGraph)
        ↓
Router (LLM intent classification)
        ↓
Tools (piano, priority, risk, search)
        ↓
DataRetriever + BusinessLogic
        ↓
ResponseFormatter
        ↓
Risposta JSON compatibile Rasa
```

## Endpoints Implementati

### 1. Health Check
```bash
GET http://localhost:5005/
```

**Response**:
```json
{
    "status": "ok",
    "version": "1.0.0",
    "model_loaded": true
}
```

### 2. Status
```bash
GET http://localhost:5005/status
```

**Response**:
```json
{
    "status": "ok",
    "model_loaded": true,
    "data_loaded": {
        "piani": 730,
        "controlli": 61247,
        "osa_mai_controllati": 154406
    },
    "framework": "LangGraph",
    "llm": "LLaMA 3.1 (stub)"
}
```

### 3. Webhook (Rasa-compatible)
```bash
POST http://localhost:5005/webhooks/rest/webhook
Content-Type: application/json

{
    "sender": "user_id_123",
    "message": "quali attività ha il piano A1?",
    "metadata": {
        "asl": "NA1",
        "uoc": "Veterinaria",
        "user_id": "123",
        "username": "mario.rossi"
    }
}
```

**Response**:
```json
[
    {
        "text": "**Descrizione Piano A1**\n\n...",
        "recipient_id": "user_id_123"
    }
]
```

### 4. Parse NLU
```bash
POST http://localhost:5005/model/parse
Content-Type: application/json

{
    "sender": "user_id",
    "message": "quali attività ha il piano A1?",
    "metadata": {}
}
```

**Response**:
```json
{
    "text": "quali attività ha il piano A1?",
    "intent": {
        "name": "ask_piano_description",
        "confidence": 0.95
    },
    "entities": [
        {"entity": "piano_code", "value": "A1"}
    ],
    "slots": {"piano_code": "A1"},
    "needs_clarification": false
}
```

## Compatibilità con Rasa

### Formato Request
Identico a Rasa REST Channel:
- `sender`: ID utente univoco
- `message`: Testo messaggio
- `metadata`: Dati aggiuntivi (ASL, UOC, user_id, etc.)

### Formato Response
Array di oggetti con campi:
- `text`: Testo risposta
- `recipient_id`: Echo del sender

### Differenze
| Aspetto | Rasa | GiAs-llm |
|---------|------|----------|
| Intent Classification | Rasa NLU (ML) | LLM Router (prompt-based) |
| Dialogue Management | Rasa Core (stories) | LangGraph (state machine) |
| Response Generation | Template Rasa | LLM + formatted_response |
| Metadata | Via tracker | Via ConversationState |

## Avvio del Server

### Start
```bash
./start_server.sh
```

Output:
```
==========================================
   GiAs-llm API Server Startup
==========================================

📊 Verifica dataset...
   ✅ Dataset trovato: 7 file CSV

🚀 Avvio API server su porta 5005...
   ✅ API Server avviato (PID: 12345)

📋 Endpoints disponibili:
   - Webhook:    http://localhost:5005/webhooks/rest/webhook
   - Parse NLU:  http://localhost:5005/model/parse
   - Status:     http://localhost:5005/status
   - Health:     http://localhost:5005/
```

### Stop
```bash
./stop_server.sh
```

### Logs
```bash
tail -f logs/api-server.log
```

## Test

### Test Automatici
```bash
python test_api.py
```

### Test Manuali

**Saluto**:
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"ciao"}'
```

**Descrizione Piano**:
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"quali attività ha il piano A1?","metadata":{"asl":"NA1"}}'
```

**Ricerca Semantica**:
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"cerca piani sui bovini"}'
```

## Implementazione

### File Principali

**app/api.py**:
- FastAPI application
- Endpoints REST
- Integrazione ConversationGraph
- Logging

**llm/client.py**:
- Stub LLM client
- Mock classification (rule-based per testing)
- Mock response generation
- **TODO**: Implementare LLaMA 3.1 reale

**orchestrator/graph.py**:
- LangGraph workflow
- State management
- Tool routing
- Response generation

**tools/***:
- piano_tools.py: Descrizioni e attività piani
- search_tools.py: Ricerca semantica
- priority_tools.py: Priorità basate su programmazione
- risk_tools.py: Priorità basate su rischio

### Stato Attuale

✅ **Implementato**:
- FastAPI server configurato
- Endpoints Rasa-compatible
- Integrazione LangGraph
- Caricamento dataset reali (323K righe)
- Scripts start/stop
- Test suite

⚠️ **In Sviluppo**:
- LLM client stub (pattern-based classification)
- Response generation semplificata

❌ **Da Implementare**:
- LLaMA 3.1 API reale
- Hot-reload configurazione
- Caching risposte
- Rate limiting
- Authentication

## Troubleshooting

### Server non si avvia
```bash
# Verifica porta occupata
lsof -i:5005

# Kill processo
kill -9 $(lsof -ti:5005)

# Riavvia
./start_server.sh
```

### Risposte sempre fallback
- Verificare che i dataset siano caricati: `GET /status`
- Controllare i log: `tail -f logs/api-server.log`
- Testare classificazione: `POST /model/parse`

### Errori import moduli
```bash
# Verificare PYTHONPATH
python -c "import sys; print(sys.path)"

# Reinstallare dipendenze
pip install -r requirements.txt
```

## Integrazione con GChat

GChat (progetto Go) fa richieste a questo endpoint esattamente come faceva con Rasa:

1. User invia messaggio via browser
2. GChat costruisce RasaMessage con metadata (ASL, UOC, user_id)
3. POST a `/webhooks/rest/webhook`
4. GiAs-llm elabora e restituisce array di RasaResponse
5. GChat concatena i testi e mostra all'utente

**Nessuna modifica richiesta in GChat** - compatibilità 100%.

## Prossimi Passi

1. **Implementare LLM Client Reale**:
   ```python
   # llm/client.py
   import requests

   def query(self, prompt: str) -> str:
       response = requests.post(
           "http://localhost:11434/api/generate",
           json={"model": "llama3.1", "prompt": prompt}
       )
       return response.json()["response"]
   ```

2. **Ottimizzare Performance**:
   - Cache risposte frequenti
   - Pool connessioni database
   - Async data loading

3. **Deploy Produzione**:
   - Docker containerization
   - NGINX reverse proxy
   - SSL/TLS certificates
   - Monitoring (Prometheus/Grafana)

---

**Versione**: 1.0.0
**Data**: 2025-12-24
**Maintainer**: Sistema Veterinario GiAs-llm
