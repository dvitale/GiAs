# GiAs-llm: Architettura LLM + Agents
**Presentazione Tecnica**

---

## 🎯 Executive Summary

**GiAs-llm** è un sistema conversazionale basato su **LangGraph** e **LLM** per il monitoraggio veterinario della Regione Campania. Sostituisce l'architettura Rasa con un approccio moderno basato su agenti specializzati e Large Language Models.

**Versione**: 1.1.0
**Data**: 2025-12-25
**Dataset**: 323,146 record da CSV
**Endpoint**: `http://localhost:5005` (Rasa-compatible)

---

## 📐 Architettura Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     GChat Frontend                          │
│                  (Web UI - Port 8080)                       │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP POST
                     │ /webhooks/rest/webhook
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Server (5005)                      │
│                    app/api.py                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              LangGraph Orchestrator                         │
│              orchestrator/graph.py                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ConversationGraph (State Machine)                   │   │
│  │                                                      │   │
│  │  1. classify_node    → Router (LLM)                  │   │
│  │  2. route_by_intent  → Conditional routing           │   │
│  │  3. tool_node        → Execute specialized tool      │   │
│  │  4. response_gen     → LLM response generation       │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴──────────────┬─────────────┬──────────┐
        ↓                           ↓             ↓          ↓
┌───────────────┐  ┌─────────────────────┐  ┌──────────┐  ┌──────────┐
│ LLM Router    │  │   Tool Layer        │  │  Agents  │  │   Data   │
│ (Intent)      │  │   @tool decorated   │  │  Layer   │  │  Layer   │
└───────────────┘  └─────────────────────┘  └──────────┘  └──────────┘
```

---

## 🧠 Layer 1: LLM Router - Intent Classification

### Componente: `orchestrator/router.py`

**Ruolo**: Classificare l'intento dell'utente usando un Large Language Model.

### Architettura

```python
class Router:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.VALID_INTENTS = [
            "greet", "goodbye", "ask_help",
            "ask_piano_description", "ask_piano_stabilimenti",
            "ask_piano_attivita", "ask_piano_generic",
            "search_piani_by_topic",
            "ask_priority_establishment", "ask_risk_based_priority",
            "ask_suggest_controls", "ask_delayed_plans",
            "fallback"
        ]
```

### Prompt Engineering per Classification

```python
CLASSIFICATION_PROMPT = """
**TASK**: Classifica il messaggio utente in uno degli intent disponibili.

**MESSAGGIO UTENTE**: "{message}"

**METADATA**:
- ASL: {asl}
- UOC: {uoc}
- User ID: {user_id}

**INTENT DISPONIBILI**:
1. greet: Saluti (es. "ciao", "buongiorno")
2. goodbye: Saluti finali (es. "arrivederci")
3. ask_help: Richieste aiuto (es. "cosa puoi fare?")
4. ask_piano_description: Descrizione piano (es. "di cosa tratta A1?")
5. ask_piano_stabilimenti: Stabilimenti per piano
6. ask_piano_attivita: Attività per piano
7. ask_piano_generic: Query generica su piano
8. search_piani_by_topic: Ricerca piani per argomento
9. ask_priority_establishment: Priorità programmazione
10. ask_risk_based_priority: Priorità basata su rischio storico
11. ask_suggest_controls: Suggerimenti controlli
12. ask_delayed_plans: Piani in ritardo
13. fallback: Non classificabile

**OUTPUT**: JSON
{
  "intent": "intent_name",
  "slots": {"piano_code": "A1", ...},
  "needs_clarification": false
}
"""
```

### Slot Extraction

Il Router estrae automaticamente **slot** dal messaggio:

| Slot | Descrizione | Esempio |
|------|-------------|---------|
| `piano_code` | Codice piano (A1, B2, C3_F) | "Di cosa tratta il piano **A22**?" |
| `topic` | Argomento ricerca | "Piani su **allevamenti bovini**" |
| `asl` | Azienda Sanitaria Locale | Da metadata |
| `uoc` | Unità Operativa Complessa | Da metadata o risolto da user_id |

### LLM Client Interface

```python
class LLMClient:
    def query(self, prompt: str) -> str:
        """
        Interfaccia LLM.

        Attualmente: Stub rule-based
        Target: LLaMA 3.1 8B via Ollama/vLLM

        Produzione:
            response = requests.post("http://localhost:11434/api/generate",
                json={"model": "llama3.1", "prompt": prompt})
            return response.json()["response"]
        """
```

---

## 🔧 Layer 2: Tool Layer - Specialized Functions

### Architettura Tool

Tutti i tool sono decorati con `@tool` di LangChain:

```python
from langchain_core.tools import tool

@tool("piano_description")
def get_piano_description(piano_code: str) -> Dict[str, Any]:
    """
    Recupera descrizione completa di un piano.

    Args:
        piano_code: Codice piano (es. "A1")

    Returns:
        {
            "piano_code": "A1",
            "formatted_response": "Il piano A1 riguarda...",
            "total_variants": 15,
            "raw_data": [...]
        }
    """
```

### 4 Categorie di Tool

#### 1. **Piano Tools** (`tools/piano_tools.py`)

Query su piani di controllo:

| Tool | Descrizione | Input |
|------|-------------|-------|
| `get_piano_description` | Descrizione piano | `piano_code` |
| `get_piano_attivita` | Stabilimenti controllati | `piano_code` |
| `get_piano_correlation` | Correlazione piano-attività | `piano_code` |
| `compare_piani` | Confronto metriche | `piano1_code`, `piano2_code` |

**Esempio Output**:
```json
{
  "piano_code": "A1",
  "formatted_response": "**Piano A1**: Controllo carni bovine fresche...",
  "total_controls": 2547,
  "unique_establishments": 134,
  "top_stabilimenti": [...]
}
```

#### 2. **Priority Tools** (`tools/priority_tools.py`)

Analisi priorità e ritardi:

| Tool | Descrizione | Input |
|------|-------------|-------|
| `get_priority_establishment` | Stabilimenti prioritari (programmazione) | `asl`, `uoc`, `piano_code` |
| `get_delayed_plans` | Piani in ritardo | `asl`, `uoc` |
| `suggest_controls` | Mai controllati ad alto rischio | `asl` |

**Business Logic**:
```python
# Logica priorità basata su ritardi programmazione
delayed_plans = diff_prog_eseg_df[
    (diff_prog_eseg_df['descrizione_uoc'] == uoc) &
    (diff_prog_eseg_df['diff'] < 0)  # Ritardo = eseguiti < programmati
]

# Correlazione statistica piano → attività
correlations = controlli_df.groupby(['descrizione_piano', 'attivita_cu']).size()

# Filtra stabilimenti mai controllati correlati
priority_establishments = osa_mai_controllati_df[
    osa_mai_controllati_df['attivita'].isin(correlated_activities)
]
```

#### 3. **Risk Tools** (`tools/risk_tools.py`)

Analisi rischio storico:

| Tool | Descrizione | Input |
|------|-------------|-------|
| `get_risk_based_priority` | Stabilimenti ad alto rischio NC | `asl`, `piano_code` |

**Risk Scoring**:
```python
# Punteggio rischio = NC_gravi × 3 + NC_non_gravi × 1
risk_score = (
    ocse_df['numero_nc_gravi'] * 3 +
    ocse_df['numero_nc_non_gravi'] * 1
)

# Aggregazione per attività (macroarea_sottoposta_a_controllo)
risk_by_activity = ocse_df.groupby('macroarea_sottoposta_a_controllo').agg({
    'numero_nc_gravi': 'sum',
    'numero_nc_non_gravi': 'sum',
    'punteggio_rischio': 'sum'
}).sort_values('punteggio_rischio', ascending=False)
```

#### 4. **Search Tools** (`tools/search_tools.py`)

Ricerca semantica piani:

| Tool | Descrizione | Input |
|------|-------------|-------|
| `search_piani_by_topic` | Ricerca piani per argomento | `query` |

**Implementazione**:
```python
# Ricerca fuzzy su descrizioni piani
from fuzzywuzzy import fuzz

matches = piani_df[
    piani_df['descrizione'].apply(
        lambda x: fuzz.partial_ratio(query.lower(), x.lower()) > 60
    )
]
```

---

## 🤖 Layer 3: Agent Layer - Business Logic

### Architettura 3-Layer Separation

```
┌────────────────────────────────────────────────────────┐
│  agents/agents/data_agent.py                          │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │  DataRetriever                                   │ │
│  │  - get_piano_by_id()                            │ │
│  │  - get_controlli_by_piano()                     │ │
│  │  - get_osa_by_asl()                             │ │
│  └──────────────────────────────────────────────────┘ │
│                         ↓                              │
│  ┌──────────────────────────────────────────────────┐ │
│  │  BusinessLogic                                   │ │
│  │  - correlate_piano_attivita()                   │ │
│  │  - aggregate_stabilimenti_by_piano()            │ │
│  │  - compare_plans_metrics()                      │ │
│  └──────────────────────────────────────────────────┘ │
│                         ↓                              │
│  ┌──────────────────────────────────────────────────┐ │
│  │  RiskAnalyzer                                    │ │
│  │  - calculate_risk_score()                       │ │
│  │  - rank_establishments_by_risk()                │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────┐
│  agents/agents/response_agent.py                      │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │  ResponseFormatter                               │ │
│  │  - format_piano_description()                   │ │
│  │  - format_stabilimenti_analysis()               │ │
│  │  - format_priority_list()                       │ │
│  └──────────────────────────────────────────────────┘ │
│                         ↓                              │
│  ┌──────────────────────────────────────────────────┐ │
│  │  SuggestionGenerator                             │ │
│  │  - generate_followup_questions()                │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Principi Architetturali

**1. Separation of Concerns**
- **DataRetriever**: Solo accesso dati, no logica
- **BusinessLogic**: Aggregazioni, correlazioni, statistiche
- **RiskAnalyzer**: Scoring rischio, ranking
- **ResponseFormatter**: Dati strutturati → Testo italiano formattato

**2. No Side Effects**
- Tool functions sono pure: stesso input → stesso output
- No stato condiviso tra chiamate
- No modifica globale di variabili

**3. Template-based Responses**
```python
class ResponseFormatter:
    @staticmethod
    def format_piano_description(piano_id: str,
                                  unique_descriptions: List[Dict],
                                  total_variants: int) -> str:
        """
        Formatta descrizione piano in markdown.

        Returns:
            **Piano {piano_id}**: {sezione}

            {descrizione principale}

            **Varianti**: {total_variants}
            - Variante 1: ...
            - Variante 2: ...
        """
```

---

## 🌊 LangGraph State Machine

### ConversationState TypedDict

```python
class ConversationState(TypedDict):
    message: str              # Input utente
    metadata: Dict[str, Any]  # {asl, uoc, user_id, codice_fiscale}
    intent: str               # Classificato da Router
    slots: Dict[str, Any]     # Entità estratte (piano_code, topic)
    tool_output: Any          # Risultato esecuzione tool
    final_response: str       # Risposta finale generata
    needs_clarification: bool # Se serve chiarimento
    error: str                # Messaggi errore
```

### Graph Workflow

```python
workflow = StateGraph(ConversationState)

# Nodes
workflow.add_node("classify", self._classify_node)
workflow.add_node("piano_description_tool", self._piano_description_tool)
workflow.add_node("priority_establishment_tool", self._priority_establishment_tool)
# ... altri tool nodes
workflow.add_node("response_generator", self._response_generator_node)

# Entry point
workflow.set_entry_point("classify")

# Conditional routing
workflow.add_conditional_edges(
    "classify",
    self._route_by_intent,  # Router function
    {
        "ask_piano_description": "piano_description_tool",
        "ask_priority_establishment": "priority_establishment_tool",
        # ... mappings
    }
)

# All tools → response generator
for tool_node in [all_tool_nodes]:
    workflow.add_edge(tool_node, "response_generator")

workflow.add_edge("response_generator", END)
```

### Execution Flow Example

**User Query**: "Di cosa tratta il piano A1?"

```
1. classify_node:
   ├─ LLM Router analizza messaggio
   ├─ Estrae slot: {"piano_code": "A1"}
   └─ Classifica: intent = "ask_piano_description"

2. route_by_intent:
   └─ Conditional edge → "piano_description_tool"

3. piano_description_tool:
   ├─ Chiama piano_tool(action="description", piano_code="A1")
   │  ├─ DataRetriever.get_piano_by_id("A1")
   │  ├─ BusinessLogic.extract_unique_piano_descriptions()
   │  └─ ResponseFormatter.format_piano_description()
   └─ Salva in state["tool_output"]

4. response_generator_node:
   ├─ Recupera tool_output["formatted_response"]
   ├─ Opzionale: LLM arricchisce risposta
   └─ Salva in state["final_response"]

5. END → Ritorna stato finale
```

---

## 🎨 Response Generation Strategy

### Due Modalità

#### 1. **Template-based** (Attuale)
```python
def _response_generator_node(self, state: ConversationState):
    data = state["tool_output"]["data"]

    # Se tool ha già formatted_response, usalo direttamente
    if isinstance(data, dict) and "formatted_response" in data:
        state["final_response"] = data["formatted_response"]
        return state
```

**Pro**: Deterministico, veloce, no latenza LLM
**Contro**: Risposte rigide, no adattamento contestuale

#### 2. **LLM-generated** (Target)
```python
def _build_response_prompt(self, intent: str, tool_output: Dict) -> str:
    return f"""
    Sei un assistente veterinario esperto.

    **CONTESTO**: {intent_descriptions[intent]}
    **DOMANDA**: {user_message}
    **DATI**: {tool_output}

    **TASK**:
    1. Spiega i risultati in modo comprensibile
    2. Motiva le priorità (PERCHÉ questi stabilimenti?)
    3. Suggerisci azioni operative concrete
    4. Proponi 1-2 domande di follow-up

    **OUTPUT**: Risposta professionale in italiano, markdown.
    """
```

**Pro**: Risposte contestuali, adattive, personalizzate
**Contro**: Latenza LLM, costi computazionali

---

## 📊 Data Layer

### Dataset Caricati (323,146 record)

```python
# agents/data.py
piani_df = pd.read_csv("piani_monitoraggio.csv")              # 730
attivita_df = pd.read_csv("Master list rev 11_filtered.csv") # 538
controlli_df = pd.read_csv("vw_2025_eseguiti_filtered.csv")  # 61,247
osa_mai_controllati_df = pd.read_csv("osa_mai_controllati_con_linea_852-3_filtered.csv")  # 154,406
ocse_df = pd.read_csv("OCSE_ISP_SEMP_2025_filtered_v2.csv")  # 101,343
diff_prog_eseg_df = pd.read_csv("vw_diff_programmmati_eseguiti.csv")  # 3,002
personale_df = pd.read_csv("personale_filtered.csv")         # 1,880
```

### Schema Dati Chiave

**piani_df**:
- `alias`: Codice piano (A1, B2, C3_F)
- `alias_indicatore`: Codice indicatore
- `sezione`: Categoria piano
- `descrizione`: Testo descrittivo
- `descrizione-2`: Dettagli aggiuntivi

**controlli_df** (Controlli eseguiti 2025):
- `descrizione_piano`: Nome piano
- `macroarea_cu`: Nome stabilimento
- `aggregazione_cu`: Tipo attività
- `attivita_cu`: Linea attività specifica

**osa_mai_controllati_df** (Stabilimenti mai controllati):
- `asl`: Codice ASL
- `comune`, `indirizzo`: Localizzazione
- `macroarea`: Nome stabilimento
- `aggregazione`: Tipo attività
- `num_riconoscimento`: ID univoco

**ocse_df** (Non conformità storiche):
- `macroarea_sottoposta_a_controllo`: Tipo attività
- `numero_nc_gravi`: NC gravi
- `numero_nc_non_gravi`: NC non gravi

**personale_df** (Risoluzione UOC):
- `user_id`: ID utente
- `descrizione_uoc`: Nome UOC completo
- `asl`: Codice ASL

### UOC Resolution Pattern

```python
def get_uoc_from_user_id(user_id: str) -> str:
    """
    Risolve automaticamente UOC da user_id.

    Problema: GChat invia solo user_id, non UOC
    Soluzione: Lookup in personale_df

    Example:
        user_id="42145" →
        "UNITA' OPERATIVA COMPLESSA SERVIZIO IGIENE
         DEGLI ALIMENTI E DELLA NUTRIZIONE"
    """
    user_row = personale_df[personale_df['user_id'] == int(user_id)]
    return user_row.iloc[0]['descrizione_uoc']
```

---

## 🔄 Migration from Rasa

### Before (Rasa)

```
┌─────────────────────────────────────┐
│  Rasa NLU (Intent + Entity)        │
│  - domain.yml                       │
│  - nlu.yml (training examples)      │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  Rasa Core (Stories + Rules)       │
│  - stories.yml                      │
│  - rules.yml                        │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  Custom Action Server (Python)     │
│  - actions/actions.py               │
│  - Dispatcher, Tracker, SlotSet     │
└─────────────────────────────────────┘
```

**Problemi**:
- Intent classification limitato (no LLM)
- Stories fragili (esplodono con complessità)
- Action Server monolitico
- Difficile testing e manutenzione

### After (LangGraph + LLM)

```
┌─────────────────────────────────────┐
│  LLM Router (Few-shot prompting)   │
│  - Prompt-based classification      │
│  - Slot extraction automatica       │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  LangGraph State Machine           │
│  - Conditional routing              │
│  - Type-safe state (TypedDict)      │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  Specialized Tools (@tool)         │
│  - Pure functions                   │
│  - Testable, composable             │
└─────────────────────────────────────┘
```

**Vantaggi**:
- Intent classification LLM-based (più robusto)
- State machine esplicita (no stories)
- Tool modulari e testabili
- Facile integrazione con LLM diversi

---

## 🚀 Deployment Architecture

### Production Stack

```
┌──────────────────────────────────────────────────────────┐
│  Nginx Reverse Proxy (Port 80/443)                      │
│  - SSL termination                                       │
│  - Load balancing                                        │
└──────────────┬────────────────────────────────────────┬──┘
               │                                        │
       ┌───────┴────────┐                    ┌─────────┴────────┐
       │  GChat (8080)  │                    │  GiAs-llm (5005) │
       │  Go server     │                    │  FastAPI + Uvicorn│
       └────────────────┘                    └─────────┬─────────┘
                                                       │
                                             ┌─────────┴─────────┐
                                             │  LLaMA 3.1 (11434)│
                                             │  Ollama / vLLM    │
                                             └───────────────────┘
```

### Scalability Options

**Horizontal Scaling**:
```bash
# Multiple FastAPI workers
uvicorn app.api:app --workers 4 --port 5005
```

**LLM Serving**:
- **Ollama**: Simple, good for dev/test
- **vLLM**: Production, GPU optimization, batch inference
- **OpenAI-compatible API**: Cloud (GPT-4, Claude)

**Caching Layer**:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_piano_description_cached(piano_code: str):
    return get_piano_description(piano_code)
```

---

## 📈 Performance Metrics

### Latency Breakdown

| Componente | Latency (ms) | Note |
|------------|--------------|------|
| API Routing | 5-10 | FastAPI overhead |
| LLM Classification | 200-500 | Ollama local (stub: 1ms) |
| Tool Execution | 50-200 | Pandas aggregations |
| Response Generation | 300-800 | LLM (stub: template-based 1ms) |
| **Total** | **600-1500ms** | Target < 2s |

### Throughput

- **Stub (current)**: ~200 req/s (single worker)
- **LLM (target)**: ~10-50 req/s (depends on GPU)
- **Recommendation**: Async tool execution + batching

---

## 🔬 Testing Strategy

### Unit Tests

```python
# tests/test_router.py
def test_intent_classification():
    router = Router(LLMClient())
    result = router.classify("di cosa tratta il piano A1?")
    assert result["intent"] == "ask_piano_description"
    assert result["slots"]["piano_code"] == "A1"
```

### Integration Tests

```python
# tests/test_graph.py
def test_full_conversation_flow():
    graph = ConversationGraph()
    result = graph.run(
        message="stabilimenti ad alto rischio per A1",
        metadata={"asl": "AVELLINO", "user_id": "42145"}
    )
    assert "risk_based_priority" in result["intent"]
    assert len(result["response"]) > 100
```

### End-to-End Tests

```bash
# Predefined questions from GChat config
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -d '{"sender": "test", "message": "Cosa posso chiederti?", "metadata": {}}'

# Expected: Help response with clickable questions
# Actual: ✅ 8/8 predefined questions passed
```

---

## 🎯 Key Takeaways

### Architectural Strengths

1. **LLM-first Design**: Intent classification robusto, adattabile
2. **Modularity**: Tool layer separato, facilmente estensibile
3. **Type Safety**: TypedDict per state, riduce bug runtime
4. **Data-driven**: 323K records, business logic separata da presentation
5. **Rasa-compatible**: Drop-in replacement, no cambio frontend

### Innovation Points

1. **Automatic UOC Resolution**: user_id → UOC lookup (1880 utenti)
2. **Risk Scoring**: NC storiche → punteggio rischio attività
3. **Statistical Correlation**: Piano → Attività mapping automatico
4. **Clickable Help**: Markdown `[testo]` → frontend interattivo
5. **Formatted Errors**: No raw dict, messaggi user-friendly italiano

### Technical Debt

1. **LLM Stub**: Sostituire con LLaMA 3.1 reale
2. **Template Responses**: Migrare a LLM-generated
3. **CSV Data**: Migrare a PostgreSQL per performance
4. **Sync Tools**: Implementare async execution
5. **No Multi-turn**: Aggiungere conversation history tracking

---

## 📚 References

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **LangChain Tools**: https://python.langchain.com/docs/modules/tools/
- **Ollama**: https://ollama.ai/
- **vLLM**: https://vllm.readthedocs.io/
- **FastAPI**: https://fastapi.tiangolo.com/

---

## 🔗 Documentation Links

- **[README.md](./README.md)**: Guida completa utente
- **[BUGFIX_REPORT.md](./BUGFIX_REPORT.md)**: Bug risolti e soluzioni
- **[INTEGRATION_GCHAT.md](./INTEGRATION_GCHAT.md)**: Integrazione frontend
- **[CLAUDE.md](./CLAUDE.md)**: Istruzioni sviluppo
- **[CHANGELOG.md](./CHANGELOG.md)**: Versioning e modifiche

---

**Presentato da**: GiAs-llm Development Team
**Contatto**: Sistema interno Regione Campania - Monitoraggio Veterinario
**Versione Documento**: 1.0 (2025-12-25)
