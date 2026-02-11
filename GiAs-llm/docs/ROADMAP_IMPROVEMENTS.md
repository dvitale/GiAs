# GiAs-llm: Roadmap Miglioramenti
**Data**: 2025-12-25
**Versione Corrente**: 1.1.0

---

## 🚀 Suggerimenti Migliorativi per Evoluzione Progetto

### **1. ARCHITETTURA & SCALABILITÀ**

#### A. Database Migration (Priorità: ALTA)
**Problema attuale**: 323K record caricati da CSV in RAM a ogni avvio
```python
# Impatto: ~2-3s startup time, RAM sprecata
piani_df = pd.read_csv(...)  # Caricati ad ogni restart
```

**Soluzione**: Migrazione a PostgreSQL
- **Benefici**:
  - Startup istantaneo (no caricamento CSV)
  - Query indicizzate (10-100x più veloci su join complessi)
  - Gestione concorrenza nativa
  - Backup incrementali
- **Implementazione**:
  ```sql
  -- Schema PostgreSQL
  CREATE TABLE piani (alias VARCHAR PRIMARY KEY, descrizione TEXT, ...);
  CREATE TABLE controlli (id SERIAL, piano_alias VARCHAR REFERENCES piani, ...);
  CREATE INDEX idx_controlli_piano ON controlli(piano_alias);
  CREATE INDEX idx_osa_asl ON osa_mai_controllati(asl);
  ```
- **Migration path**: Mantenere CSV come fallback durante transizione

#### B. Caching Layer (Priorità: ALTA)
**Problema**: Query ripetute ricalcolate ogni volta
```python
# Esempio: "piani in ritardo" eseguito 10 volte/giorno → 10 scansioni complete
diff_prog_eseg_df[diff_prog_eseg_df['programmati'] > diff_prog_eseg_df['eseguiti']]
```

**Soluzione**: Redis per caching multi-livello
- **Cache L1 (10s TTL)**: Aggregazioni pesanti (piani ritardo, rischio attività)
- **Cache L2 (1h TTL)**: Piano descriptions (immutabili)
- **Cache L3 (24h TTL)**: Statistiche storiche NC regionali
```python
@lru_cache(maxsize=128, ttl=600)  # 10 min
def get_delayed_plans(asl: str, uoc: str):
    # Query pesante cachata
```

#### C. Async Tool Execution (Priorità: MEDIA)
**Ottimizzazione**: LangGraph supporta async, ma i tool sono sincroni
```python
# Attuale (seriale):
result1 = piano_tool(...)  # 200ms
result2 = priority_tool(...)  # 150ms
# TOTALE: 350ms

# Target (parallelo):
results = await asyncio.gather(
    piano_tool_async(...),
    priority_tool_async(...)
)
# TOTALE: 200ms (↓43%)
```

---

### **2. LLM INTEGRATION (Attualmente Stub)**

#### A. Sostituire LLM Stub con LLaMA 3.1 Reale
**File**: `llm/client.py` (attualmente pattern matching hard-coded)

**Opzioni deployment**:

**1. Ollama (CONSIGLIATO per sviluppo)**:
```python
import ollama

class LLMClient:
    def query(self, prompt: str) -> str:
        response = ollama.chat(
            model='llama3.1:8b',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3  # Bassa per classificazione
        )
        return response['message']['content']
```
- **Pro**: Setup locale immediato, no costi API
- **Contro**: Richiede GPU (o CPU lento)

**2. vLLM (CONSIGLIATO per produzione)**:
```bash
# Server vLLM
vllm serve meta-llama/Llama-3.1-8B-Instruct --host 0.0.0.0 --port 8000

# Client Python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")
```
- **Pro**: 10-20x throughput vs Ollama, batching automatico
- **Contro**: Setup più complesso

**3. OpenAI-compatible API (Alternative)**:
- Together.ai, Replicate, Groq
- **Pro**: Zero setup hardware
- **Contro**: Costi, latenza rete, privacy

#### B. Prompt Engineering Avanzato
**Migliorare classificazione intent**:
```python
# Attuale: Prompt generico → 85% accuracy
# Target: Few-shot examples → 95%+ accuracy

CLASSIFICATION_PROMPT_V2 = """
**ESEMPI**:
USER: "quali attività ha il piano A1?"
INTENT: ask_piano_attivita
SLOTS: {"piano_code": "A1"}

USER: "stabilimenti mai controllati ad alto rischio"
INTENT: ask_risk_based_priority
SLOTS: {}

USER: "{message}"
INTENT: ?
SLOTS: ?
"""
```

**Chain-of-Thought per risposte complesse**:
```python
# Per query ambigue, forzare ragionamento esplicito
prompt = f"""
Domanda: {user_message}
Dati: {tool_output}

PASSO 1: Quali metriche sono rilevanti?
PASSO 2: Cosa indicano questi numeri?
PASSO 3: Qual è la raccomandazione operativa?

Risposta finale:
"""
```

---

### **3. MIGLIORAMENTI FUNZIONALI**

#### A. Conversazioni Multi-Turn con Memoria
**Problema attuale**: Ogni messaggio è stateless
```python
# User: "dimmi dei piani in ritardo"
# Bot: [lista 10 piani]
# User: "mostrami il primo"  ← ❌ Non capisce "primo"
```

**Soluzione**: LangGraph Checkpointer
```python
from langgraph.checkpoint.sqlite import SqliteSaver

workflow = StateGraph(ConversationState)
memory = SqliteSaver.from_conn_string("conversations.db")
graph = workflow.compile(checkpointer=memory)

# Ora supporta context:
result = graph.run(
    message="mostrami il primo",
    config={"configurable": {"thread_id": "user123"}}
)
```

#### B. Suggerimenti Dinamici Personalizzati
**Attuale**: Suggerimenti generici fissi
**Target**: Basati su contesto ASL/UOC
```python
# Esempio: ASL con molti piani in ritardo
suggestions = [
    "Vuoi vedere i piani più critici per la tua ASL?",
    "Ti mostro gli stabilimenti mai controllati ad alto rischio?"
]

# ASL con pochi ritardi
suggestions = [
    "Ottimo lavoro! Vuoi esplorare correlazioni piano-attività?",
    "Ti interessa l'analisi predittiva per il prossimo trimestre?"
]
```

#### C. Export & Reporting
**Feature richiesta**: Download dati per analisi offline
```python
@tool("export_analysis")
def export_analysis_tool(format: str = "excel"):
    """Esporta analisi completa ASL in Excel/PDF"""
    # Genera workbook con sheets:
    # - Piani in ritardo
    # - Stabilimenti ad alto rischio
    # - Statistiche NC trimestrali
    # - Timeline controlli eseguiti
    return {"file_url": "/downloads/report_ASL_NA1.xlsx"}
```

---

### **4. MONITORING & OBSERVABILITY**

#### A. Structured Logging
**Attuale**: Log testuali difficili da parsare
```python
# logs/api-server.log
INFO:__main__:[Webhook] Ricevuto messaggio da test: ciao
```

**Target**: JSON structured logs
```python
import structlog

logger = structlog.get_logger()
logger.info(
    "webhook_request",
    sender="user123",
    message="ciao",
    intent="greet",
    response_time_ms=245,
    asl="AVELLINO"
)
# Output JSON parsabile da Grafana/ELK
```

#### B. Metrics Dashboard
**Implementare**: Prometheus + Grafana
```python
from prometheus_client import Counter, Histogram

intent_counter = Counter('gias_intent_total', 'Intent classificati', ['intent'])
response_time = Histogram('gias_response_seconds', 'Response time')

@response_time.time()
def handle_message(...):
    intent = classify(...)
    intent_counter.labels(intent=intent).inc()
```

**Dashboard metrics utili**:
- Intent distribution (quali funzioni più usate)
- Response time p50/p95/p99
- Error rate per tool
- Cache hit ratio
- Query ASL più attive

#### C. Error Tracking
**Integrare Sentry**:
```python
import sentry_sdk

sentry_sdk.init(dsn="...", traces_sample_rate=0.1)

try:
    result = tool.invoke(...)
except Exception as e:
    sentry_sdk.capture_exception(e)
    # Alert automatici su Slack/email
```

---

### **5. SICUREZZA & COMPLIANCE**

#### A. Rate Limiting
**Protezione DoS**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/webhooks/rest/webhook")
@limiter.limit("60/minute")  # Max 60 richieste/minuto per IP
async def webhook(...):
    ...
```

#### B. Input Sanitization
**Prevenire injection in query CSV/DB**:
```python
def sanitize_piano_code(code: str) -> str:
    # Allow only: A-F, 0-9, underscore
    if not re.match(r'^[A-F]\d{1,2}(_[A-Z0-9]+)?$', code):
        raise ValueError(f"Piano code non valido: {code}")
    return code.upper()
```

#### C. Audit Log
**Tracciabilità operazioni sensibili**:
```python
# Chi ha chiesto cosa, quando
audit_log.append({
    "timestamp": now(),
    "user_id": "42145",
    "asl": "AVELLINO",
    "action": "query_risk_based_priority",
    "result_count": 20
})
```

---

### **6. TESTING & QA**

#### A. Integration Tests con Dati Reali
**Attuale**: Test su dati mock
**Target**: Test su snapshot CSV reali
```python
@pytest.fixture(scope="session")
def real_dataset():
    """Carica snapshot CSV produzione per test"""
    return load_data(path="tests/fixtures/dataset_snapshot_202512/")

def test_delayed_plans_real_data(real_dataset):
    result = priority_tool(asl="AVELLINO", action="delayed_plans")
    assert len(result["data"]) > 0
    assert all("piano" in item for item in result["data"])
```

#### B. Load Testing
**Verificare performance sotto carico**:
```bash
# Locust script
locust -f tests/load_test.py --host http://localhost:5005 --users 50 --spawn-rate 10

# Simulazione: 50 utenti concorrenti, 10 nuovi/sec
# Target: p95 < 500ms, 0% error rate
```

#### C. Regression Tests su Intent Classification
**Prevenire degradazione accuracy LLM**:
```python
# tests/test_intent_regression.py
GOLDEN_DATASET = [
    ("di cosa tratta il piano A1?", "ask_piano_description", {"piano_code": "A1"}),
    ("piani in ritardo", "ask_delayed_plans", {}),
    # ... 100+ esempi annotati
]

def test_intent_accuracy():
    correct = 0
    for message, expected_intent, expected_slots in GOLDEN_DATASET:
        result = router.classify(message)
        if result["intent"] == expected_intent:
            correct += 1

    accuracy = correct / len(GOLDEN_DATASET)
    assert accuracy >= 0.95, f"Accuracy dropped to {accuracy:.2%}"
```

---

### **7. UX IMPROVEMENTS**

#### A. Risposte Progressive (Streaming)
**Per query lunghe, mostrare progressivamente**:
```python
# Invece di aspettare 3s per risposta completa:
async def stream_response():
    yield "**Analisi in corso...**\n\n"
    data = fetch_establishments()  # 2s
    yield f"Trovati {len(data)} stabilimenti\n\n"
    formatted = format_response(data)  # 1s
    yield formatted

# Frontend mostra chunks in real-time
```

#### B. Grafici & Visualizzazioni
**Arricchire risposte testuali con chart**:
```python
@tool("delayed_plans_chart")
def delayed_plans_with_chart(asl: str):
    data = get_delayed_plans(asl)

    # Genera chart URL (Chart.js, Plotly, etc.)
    chart_url = generate_bar_chart(
        labels=[p["piano"] for p in data],
        values=[p["ritardo_percentuale"] for p in data]
    )

    return {
        "formatted_response": "...",
        "chart_url": chart_url,  # Frontend renderizza
        "data": data
    }
```

#### C. Notifiche Proattive
**Alert automatici su Slack/email**:
```python
# Cronjob giornaliero
if len(get_delayed_plans(asl)) > threshold:
    send_slack_notification(
        channel="#gias-alerts",
        message=f"⚠️ ASL {asl}: {len(delayed)} piani critici in ritardo"
    )
```

---

### **8. PRIORITIZZAZIONE SUGGERIMENTI**

| Priorità | Intervento | Impatto | Effort | ROI |
|----------|-----------|---------|--------|-----|
| 🔴 **ALTA** | PostgreSQL migration | ⭐⭐⭐⭐⭐ | 3-4gg | Alto |
| 🔴 **ALTA** | LLaMA 3.1 integration (Ollama) | ⭐⭐⭐⭐⭐ | 1-2gg | Alto |
| 🔴 **ALTA** | Redis caching layer | ⭐⭐⭐⭐ | 2gg | Alto |
| 🟡 **MEDIA** | Multi-turn conversations | ⭐⭐⭐⭐ | 2-3gg | Medio |
| 🟡 **MEDIA** | Prometheus + Grafana | ⭐⭐⭐ | 2gg | Medio |
| 🟡 **MEDIA** | Async tool execution | ⭐⭐⭐ | 1gg | Medio |
| 🟢 **BASSA** | Export Excel/PDF | ⭐⭐ | 1gg | Basso |
| 🟢 **BASSA** | Grafici visualizzazioni | ⭐⭐ | 2gg | Basso |
| 🟢 **BASSA** | Notifiche proattive | ⭐ | 1gg | Basso |

---

### **9. QUICK WINS (Implementabili Subito)**

#### 1. Aggiungere `@lru_cache` a funzioni pure (15 min)
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_piano_description(piano_code: str):
    # Immutabile, perfetto per cache
```

#### 2. Logging structured con JSON (30 min)
```python
import json
logger.info(json.dumps({"event": "webhook", "intent": intent, "asl": asl}))
```

#### 3. Healthcheck avanzato (15 min)
```python
@app.get("/health")
def health():
    return {
        "status": "ok",
        "dataset_loaded": len(piani_df) > 0,
        "llm_available": llm_client.ping(),
        "uptime_seconds": time.time() - start_time
    }
```

---

## 📋 Prossimi Passi Consigliati

### Fase 1: Foundation (Settimana 1-2)
1. ✅ Implementare LLaMA 3.1 con Ollama (Punto 2.A)
2. Aggiungere healthcheck avanzato (Quick Win 3)
3. Structured logging JSON (Quick Win 2)

### Fase 2: Performance (Settimana 3-4)
4. Redis caching per query frequenti (Punto 1.B)
5. LRU cache su funzioni pure (Quick Win 1)
6. Async tool execution (Punto 1.C)

### Fase 3: Scalability (Mese 2)
7. Migrazione PostgreSQL (Punto 1.A)
8. Prometheus + Grafana monitoring (Punto 4.B)
9. Rate limiting (Punto 5.A)

### Fase 4: Advanced Features (Mese 3+)
10. Multi-turn conversations (Punto 3.A)
11. Export & reporting (Punto 3.C)
12. Visualizzazioni grafiche (Punto 7.B)

---

**Ultimo aggiornamento**: 2025-12-25
**Stato**: Pronto per implementazione Fase 1
