# GiAs-llm API Endpoints

Documentazione completa degli endpoint REST esposti dal server GiAs-llm (FastAPI su porta 5005).

**Base URL**: `http://localhost:5005`

---

## Indice

1. [Health & Status](#health--status)
   - [GET /](#get---health-check)
   - [GET /status](#get-status)
   - [GET /config](#get-config)
2. [Chat Webhook](#chat-webhook)
   - [POST /webhooks/rest/webhook](#post-webhooksrestwebhook)
   - [POST /webhooks/rest/webhook/stream](#post-webhooksrestwebhookstream)
3. [NLU & Debug](#nlu--debug)
   - [POST /model/parse](#post-modelparse)
   - [GET /conversations/{id}/tracker](#get-conversationsidtracker)
4. [Analytics Chat Log](#analytics-chat-log)
   - [GET /api/chat-log/stats](#get-apichat-logstats)
   - [GET /api/chat-log/recent](#get-apichat-logrecent)
   - [GET /api/chat-log/by-asl](#get-apichat-logby-asl)
   - [GET /api/chat-log/by-intent](#get-apichat-logby-intent)
   - [GET /api/chat-log/errors](#get-apichat-logerrors)
   - [GET /api/chat-log/timeline](#get-apichat-logtimeline)
   - [GET /api/chat-log/quality](#get-apichat-logquality)

---

## Health & Status

### GET / (Health Check)

Verifica che il server sia attivo e funzionante. Compatibile con il formato Rasa.

**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "model_loaded": true
}
```

**Casi d'uso curl**:

```bash
# Verifica base che il server risponda
curl http://localhost:5005/

# Con output formattato
curl -s http://localhost:5005/ | jq

# Health check con timeout (utile per script di monitoraggio)
curl -s --max-time 5 http://localhost:5005/ && echo "OK" || echo "FAIL"
```

---

### GET /status

Restituisce informazioni dettagliate sullo stato del sistema: modello LLM, dati caricati, anno corrente.

**Response**:
```json
{
  "status": "ok",
  "model_loaded": true,
  "current_year": 2025,
  "data_loaded": {
    "piani": 150,
    "controlli": 12500,
    "osa_mai_controllati": 340
  },
  "framework": "LangGraph",
  "llm": "llama3.2:3b (real)"
}
```

**Casi d'uso curl**:

```bash
# Stato completo del sistema
curl -s http://localhost:5005/status | jq

# Verifica che i dati siano caricati
curl -s http://localhost:5005/status | jq '.data_loaded'

# Controlla quale modello LLM e' attivo
curl -s http://localhost:5005/status | jq -r '.llm'

# Script di monitoraggio: verifica piani caricati > 0
curl -s http://localhost:5005/status | jq -e '.data_loaded.piani > 0' > /dev/null && echo "Dati OK"
```

---

### GET /config

Restituisce informazioni di configurazione corrente.

**Response**:
```json
{
  "current_year": 2025,
  "data_source_type": "postgresql",
  "status": "ok"
}
```

**Casi d'uso curl**:

```bash
# Configurazione corrente
curl -s http://localhost:5005/config | jq

# Verifica anno configurato
curl -s http://localhost:5005/config | jq -r '.current_year'
```

---

## Chat Webhook

### POST /webhooks/rest/webhook

Endpoint principale per l'invio di messaggi chat. Compatibile con il protocollo Rasa REST channel.

**Request**:
```json
{
  "sender": "user123",
  "message": "quali piani sono in ritardo?",
  "metadata": {
    "asl": "AVELLINO",
    "uoc": "Veterinaria Area A",
    "user_id": "12345",
    "codice_fiscale": "RSSMRA80A01H501Z",
    "username": "mario.rossi"
  }
}
```

**Response** (array di oggetti):
```json
[
  {
    "text": "Ecco i piani in ritardo per l'ASL di Avellino:\n\n1. Piano A1 - Completamento 45%\n2. Piano B2 - Completamento 30%",
    "recipient_id": "user123"
  }
]
```

**Casi d'uso curl**:

```bash
# Domanda semplice con ASL
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test",
    "message": "piani in ritardo",
    "metadata": {"asl": "AVELLINO"}
  }'

# Domanda su piano specifico
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test",
    "message": "descrizione piano A1",
    "metadata": {"asl": "NAPOLI 1 CENTRO"}
  }'

# Richiesta aiuto
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "aiuto"}'

# Domanda su stabilimento specifico
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "user1",
    "message": "quali controlli ha lo stabilimento 12345?",
    "metadata": {"asl": "SALERNO", "user_id": "operatore1"}
  }'

# Analisi rischio
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test",
    "message": "quali sono gli stabilimenti a rischio alto?",
    "metadata": {"asl": "CASERTA"}
  }'

# Test con risposta formattata
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "quanti piani ci sono?", "metadata": {"asl": "BENEVENTO"}}' \
  | jq -r '.[0].text'

# Test sessione conversazionale (stesso sender mantiene contesto)
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "sessione1", "message": "piano A1", "metadata": {"asl": "AVELLINO"}}'

curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "sessione1", "message": "quali sono le attivita?"}'
```

---

### POST /webhooks/rest/webhook/stream

Endpoint webhook con streaming SSE (Server-Sent Events). Restituisce eventi progressivi durante l'elaborazione.

**Request**: Identico a `/webhooks/rest/webhook`

**Response**: Stream `text/event-stream` con eventi:
- `status`: Aggiornamenti sullo stato del nodo corrente
- `reasoning`: Messaggi di ragionamento del sistema
- `token`: Token streaming della risposta LLM
- `final`: Risposta finale completa
- `error`: Eventi di errore

**Casi d'uso curl**:

```bash
# Streaming base (mantiene connessione aperta)
curl -N -X POST http://localhost:5005/webhooks/rest/webhook/stream \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test",
    "message": "descrizione piano A1",
    "metadata": {"asl": "AVELLINO"}
  }'

# Streaming con output leggibile
curl -N -X POST http://localhost:5005/webhooks/rest/webhook/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"sender": "test", "message": "piani in ritardo", "metadata": {"asl": "NAPOLI 1 CENTRO"}}'

# Streaming con timeout
curl -N --max-time 120 -X POST http://localhost:5005/webhooks/rest/webhook/stream \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "aiuto"}'

# Cattura solo evento finale (utile per test)
curl -N -X POST http://localhost:5005/webhooks/rest/webhook/stream \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "quanti piani?", "metadata": {"asl": "SALERNO"}}' \
  2>/dev/null | grep "event: final" -A1 | tail -1 | sed 's/data: //' | jq
```

---

## NLU & Debug

### POST /model/parse

Endpoint per analisi NLU (Natural Language Understanding). Utile per debugging e testing del classificatore intent.

**Request**:
```json
{
  "text": "messaggio da analizzare",
  "metadata": {"asl": "AVELLINO"}
}
```

**Response**:
```json
{
  "text": "messaggio originale",
  "intent": {
    "name": "ask_piano_description",
    "confidence": 0.95
  },
  "entities": [
    {"entity": "piano", "value": "A1"}
  ],
  "metadata": {"asl": "AVELLINO"},
  "slots": {"piano": "A1"},
  "needs_clarification": false
}
```

**Casi d'uso curl**:

```bash
# Test classificazione intent
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "piani in ritardo"}' | jq

# Test estrazione slot (piano specifico)
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "descrizione del piano A1"}' | jq '.slots'

# Verifica intent riconosciuto
curl -s -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "stabilimenti mai controllati"}' | jq -r '.intent.name'

# Test batch di frasi (script)
for msg in "aiuto" "piani in ritardo" "analisi rischio" "stabilimento 123"; do
  echo "--- $msg ---"
  curl -s -X POST http://localhost:5005/model/parse \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$msg\"}" | jq '{intent: .intent.name, slots: .slots}'
done

# Test con metadata ASL
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{
    "text": "controlli ufficiali",
    "metadata": {"asl": "CASERTA", "uoc": "Area A"}
  }' | jq

# Verifica se serve clarification
curl -s -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "dammi informazioni"}' | jq '.needs_clarification'
```

---

### GET /conversations/{conversation_id}/tracker

Restituisce lo stato della conversazione. Stub per compatibilita' con Rasa (restituisce sempre stato vuoto).

**Response**:
```json
{
  "sender_id": "user123",
  "slots": {},
  "latest_message": {},
  "events": [],
  "paused": false,
  "followup_action": null,
  "active_loop": {}
}
```

**Casi d'uso curl**:

```bash
# Recupera tracker (stub)
curl http://localhost:5005/conversations/user123/tracker | jq

# Verifica esistenza conversazione
curl -s http://localhost:5005/conversations/sessione_test/tracker | jq '.sender_id'
```

---

## Analytics Chat Log

API per analisi e monitoraggio delle conversazioni registrate nel database.

### GET /api/chat-log/stats

Statistiche aggregate del chat_log.

**Query Parameters**:
- `days` (int, default: 7): Numero di giorni da considerare

**Response**:
```json
{
  "totale_messaggi": 1250,
  "totale_errori": 15,
  "tempo_medio_ms": 2340,
  "p95_ms": 5200,
  "sessioni_uniche": 89,
  "asl_attive": 7,
  "top_intents": [
    {"intent": "ask_piani_ritardo", "count": 234}
  ],
  "top_asl": [
    {"asl": "NAPOLI 1 CENTRO", "count": 456}
  ]
}
```

**Casi d'uso curl**:

```bash
# Statistiche ultimi 7 giorni (default)
curl -s http://localhost:5005/api/chat-log/stats | jq

# Statistiche ultimo giorno
curl -s "http://localhost:5005/api/chat-log/stats?days=1" | jq

# Statistiche ultimo mese
curl -s "http://localhost:5005/api/chat-log/stats?days=30" | jq

# Solo tempo medio risposta
curl -s http://localhost:5005/api/chat-log/stats | jq '.tempo_medio_ms'

# Top 5 intent piu' usati
curl -s http://localhost:5005/api/chat-log/stats | jq '.top_intents[:5]'

# Tasso errori (script)
curl -s http://localhost:5005/api/chat-log/stats | \
  jq '"Tasso errori: \(100 * .totale_errori / .totale_messaggi | round)%"'
```

---

### GET /api/chat-log/recent

Ultimi messaggi del chat_log con paginazione.

**Query Parameters**:
- `limit` (int, default: 50, max: 200): Numero di record
- `offset` (int, default: 0): Offset per paginazione
- `asl` (string, optional): Filtro per ASL

**Casi d'uso curl**:

```bash
# Ultimi 50 messaggi
curl -s http://localhost:5005/api/chat-log/recent | jq

# Ultimi 10 messaggi
curl -s "http://localhost:5005/api/chat-log/recent?limit=10" | jq '.records'

# Messaggi di una specifica ASL
curl -s "http://localhost:5005/api/chat-log/recent?asl=AVELLINO&limit=20" | jq

# Paginazione: pagina 2
curl -s "http://localhost:5005/api/chat-log/recent?limit=50&offset=50" | jq

# Solo domande e intent
curl -s "http://localhost:5005/api/chat-log/recent?limit=10" | \
  jq '.records[] | {ask, intent}'

# Messaggi con errori
curl -s "http://localhost:5005/api/chat-log/recent?limit=100" | \
  jq '[.records[] | select(.error != null)]'

# Export CSV-like
curl -s "http://localhost:5005/api/chat-log/recent?limit=100" | \
  jq -r '.records[] | [.timestamp, .asl, .intent, .ask] | @tsv'
```

---

### GET /api/chat-log/by-asl

Statistiche raggruppate per ASL.

**Query Parameters**:
- `days` (int, default: 30): Numero di giorni da considerare

**Casi d'uso curl**:

```bash
# Statistiche per ASL ultimo mese
curl -s http://localhost:5005/api/chat-log/by-asl | jq

# Statistiche ultima settimana
curl -s "http://localhost:5005/api/chat-log/by-asl?days=7" | jq

# ASL ordinate per numero messaggi
curl -s http://localhost:5005/api/chat-log/by-asl | jq '.data | sort_by(-.totale)'

# ASL con piu' errori
curl -s http://localhost:5005/api/chat-log/by-asl | \
  jq '.data | sort_by(-.tasso_errore_pct) | .[0:3]'

# Tempo medio per ASL
curl -s http://localhost:5005/api/chat-log/by-asl | \
  jq '.data[] | {asl, tempo_medio_ms}'

# Report testuale
curl -s http://localhost:5005/api/chat-log/by-asl | \
  jq -r '.data[] | "\(.asl): \(.totale) msg, \(.errori) errori (\(.tasso_errore_pct)%)"'
```

---

### GET /api/chat-log/by-intent

Statistiche raggruppate per intent.

**Query Parameters**:
- `days` (int, default: 30): Numero di giorni da considerare

**Casi d'uso curl**:

```bash
# Statistiche per intent ultimo mese
curl -s http://localhost:5005/api/chat-log/by-intent | jq

# Statistiche ultima settimana
curl -s "http://localhost:5005/api/chat-log/by-intent?days=7" | jq

# Top 10 intent piu' usati
curl -s http://localhost:5005/api/chat-log/by-intent | \
  jq '.data | sort_by(-.totale) | .[0:10]'

# Intent con piu' errori
curl -s http://localhost:5005/api/chat-log/by-intent | \
  jq '[.data[] | select(.errori > 0)] | sort_by(-.errori)'

# Intent con tempo risposta P95 > 5 secondi
curl -s http://localhost:5005/api/chat-log/by-intent | \
  jq '[.data[] | select(.p95_ms > 5000)]'

# Distribuzione intent (per grafici)
curl -s http://localhost:5005/api/chat-log/by-intent | \
  jq '.data | map({name: .intent, value: .totale})'
```

---

### GET /api/chat-log/errors

Lista errori recenti con classificazione per tipo.

**Query Parameters**:
- `limit` (int, default: 50, max: 200): Numero di record
- `days` (int, default: 7): Numero di giorni da considerare

**Casi d'uso curl**:

```bash
# Errori ultimi 7 giorni
curl -s http://localhost:5005/api/chat-log/errors | jq

# Errori ultime 24 ore
curl -s "http://localhost:5005/api/chat-log/errors?days=1" | jq

# Solo tipi di errore (distribuzione)
curl -s http://localhost:5005/api/chat-log/errors | jq '.error_types'

# Errori di timeout
curl -s http://localhost:5005/api/chat-log/errors | \
  jq '[.records[] | select(.error | test("timeout"; "i"))]'

# Errori LLM/Ollama
curl -s http://localhost:5005/api/chat-log/errors | \
  jq '[.records[] | select(.error | test("llm|ollama"; "i"))]'

# Ultimi 5 errori con dettaglio
curl -s "http://localhost:5005/api/chat-log/errors?limit=5" | \
  jq '.records[] | {timestamp, asl, ask, error}'

# Conteggio errori per ASL
curl -s http://localhost:5005/api/chat-log/errors | \
  jq '.records | group_by(.asl) | map({asl: .[0].asl, count: length}) | sort_by(-.count)'
```

---

### GET /api/chat-log/timeline

Timeline messaggi per grafici temporali.

**Query Parameters**:
- `days` (int, default: 7): Numero di giorni
- `granularity` (string, default: "hour"): `hour` o `day`

**Casi d'uso curl**:

```bash
# Timeline oraria ultima settimana
curl -s http://localhost:5005/api/chat-log/timeline | jq

# Timeline giornaliera ultimo mese
curl -s "http://localhost:5005/api/chat-log/timeline?days=30&granularity=day" | jq

# Solo conteggi (per grafici)
curl -s http://localhost:5005/api/chat-log/timeline | \
  jq '.data | map({t: .timestamp, n: .count})'

# Ore con piu' traffico
curl -s http://localhost:5005/api/chat-log/timeline | \
  jq '.data | sort_by(-.count) | .[0:5]'

# Media messaggi/ora
curl -s http://localhost:5005/api/chat-log/timeline | \
  jq '.data | map(.count) | add / length | round'

# Ore con errori
curl -s http://localhost:5005/api/chat-log/timeline | \
  jq '[.data[] | select(.errors > 0)]'

# Export per grafici (formato CSV)
curl -s "http://localhost:5005/api/chat-log/timeline?granularity=day" | \
  jq -r '.data[] | [.timestamp, .count, .errors, .avg_time_ms] | @csv'
```

---

### GET /api/chat-log/quality

Analisi qualita' conversazioni. Rileva problemi come fallback loop, domande ripetute, risposte brevi.

**Query Parameters**:
- `days` (int, default: 7): Numero di giorni da analizzare
- `asl` (string, optional): Filtro per ASL specifica
- `min_severity` (string, optional): Severita' minima: `low`, `medium`, `high`, `critical`

**Casi d'uso curl**:

```bash
# Analisi qualita' ultima settimana
curl -s http://localhost:5005/api/chat-log/quality | jq

# Analisi ultimi 3 giorni
curl -s "http://localhost:5005/api/chat-log/quality?days=3" | jq

# Analisi per ASL specifica
curl -s "http://localhost:5005/api/chat-log/quality?asl=AVELLINO" | jq

# Solo problemi critici
curl -s "http://localhost:5005/api/chat-log/quality?min_severity=critical" | jq

# Problemi high e critical
curl -s "http://localhost:5005/api/chat-log/quality?min_severity=high" | jq

# Conteggio problemi per severita'
curl -s http://localhost:5005/api/chat-log/quality | \
  jq '.issues | group_by(.severity) | map({severity: .[0].severity, count: length})'

# Sessioni problematiche
curl -s http://localhost:5005/api/chat-log/quality | \
  jq '.issues | map(.session_id) | unique'
```

---

## Note

### Headers richiesti

Per tutti gli endpoint POST:
```
Content-Type: application/json
```

Per endpoint streaming:
```
Accept: text/event-stream
```

### Timeout consigliati

| Endpoint | Timeout consigliato |
|----------|---------------------|
| `/` (health) | 5 secondi |
| `/status` | 10 secondi |
| `/webhooks/rest/webhook` | 60 secondi |
| `/webhooks/rest/webhook/stream` | 120 secondi |
| `/model/parse` | 30 secondi |
| `/api/chat-log/*` | 30 secondi |

### Codici di errore

| Codice | Significato |
|--------|-------------|
| 200 | OK |
| 400 | Bad Request (parametri non validi) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (database non disponibile) |

### Esempio script di monitoraggio

```bash
#!/bin/bash
# health_check.sh - Verifica stato GiAs-llm

BASE_URL="http://localhost:5005"

echo "=== GiAs-llm Health Check ==="

# Health base
if curl -s --max-time 5 "$BASE_URL/" | jq -e '.status == "ok"' > /dev/null; then
    echo "[OK] Server attivo"
else
    echo "[FAIL] Server non risponde"
    exit 1
fi

# Status dettagliato
STATUS=$(curl -s "$BASE_URL/status")
echo "[INFO] LLM: $(echo $STATUS | jq -r '.llm')"
echo "[INFO] Piani caricati: $(echo $STATUS | jq -r '.data_loaded.piani')"
echo "[INFO] Controlli caricati: $(echo $STATUS | jq -r '.data_loaded.controlli')"

# Test chat
RESPONSE=$(curl -s -X POST "$BASE_URL/webhooks/rest/webhook" \
    -H "Content-Type: application/json" \
    -d '{"sender": "healthcheck", "message": "aiuto"}')

if echo "$RESPONSE" | jq -e '.[0].text' > /dev/null 2>&1; then
    echo "[OK] Chat funzionante"
else
    echo "[WARN] Chat potrebbe avere problemi"
fi

# Errori recenti
ERRORS=$(curl -s "$BASE_URL/api/chat-log/errors?days=1" | jq '.total_errors')
echo "[INFO] Errori ultime 24h: $ERRORS"

echo "=== Fine Check ==="
```

---

*Documento generato automaticamente - GiAs-llm v1.0*
