# Piano: Evoluzione Agentica del Grafo LangGraph

## Contesto

L'LLM nel sistema attuale fa solo classificazione intent (1 call in `router.py`) e generazione risposta (~20% dei casi in `response_node.py`). Tutta la logica intermedia e' rule-based: 7 regole in `dialogue_manager.py`, mapping 1:1 intent→tool in `TOOL_REGISTRY`, soglie two-phase fisse in `two_phase.py`. Ogni sfumatura utente richiede modifiche a 4-5 file + INSERT DB.

**Obiettivo**: dare all'LLM il potere di scegliere tool e parametri autonomamente, senza abbandonare LangGraph ne' introdurre protocolli proprietari.

**Strategia**: evolvere il grafo esistente sostituendo i nodi `classify + dialogue_manager + 22 tool wrappers + response_generator` con un singolo **nodo ReAct** che usa `create_react_agent()` di LangGraph. L'infrastruttura (StateGraph, session, API, streaming, tools/*.py) resta invariata.

---

## Architettura Target

```
User Message
    |
    v
[fast_path_filter] -- saluti/conferme/gibberish (regex, <10ms, no LLM)
    |                  se match → risposta diretta → END
    v
[react_agent] -- LangGraph create_react_agent() con:
    |              - ChatModel wrapper attorno a LLMClient esistente
    |              - Tools da tools/*.py (gia' decorati @tool)
    |              - System prompt con identita' + regole + contesto utente
    |              - Max 5 iterazioni
    |              Loop interno:
    |                (1) LLM riceve messaggio + tools schema
    |                (2) LLM risponde con tool_calls → esegui → feedback → torna a (1)
    |                (3) LLM risponde con testo → fine
    v
[post_processor] -- follow-up suggestions, detail_context persistence,
    |                execution tracking, pseudo_query extraction
    v
END (stesso contratto ChatResponseV1)
```

### Cosa sostituisce

| Attuale | Nuovo | Motivo |
|---------|-------|--------|
| `_classify_node` (Router.classify, 6 layer) | L'LLM sceglie il tool direttamente | Classificazione implicita nella scelta tool |
| `_dialogue_manager_node` (7 regole) | System prompt guida l'LLM | Regole conversazionali nel prompt |
| 22 wrapper in `tool_nodes.py` | Tool LangChain nativi (gia' `@tool`) | Eliminazione boilerplate |
| `_response_generator_node` (2a call LLM) | L'LLM genera la risposta dopo aver visto i risultati tool | Una sola conversazione, non 2 call separate |

### Cosa resta invariato

- **`tools/*.py`**: logica di dominio intatta, gia' decorati con `@tool` via `_tool_compat.py`
- **`agents/`**: DataRetriever, ResponseFormatter, Qdrant singletons
- **`data_sources/`**: repository pattern (pandas/sql)
- **`llm/`**: LLMClient, tutti i provider, fallback_classifier
- **API contract**: `/api/v1/chat`, `/api/v1/chat/stream`, `ChatResponseV1`
- **`app/session_manager.py`**: struttura sessione (adattata, non riscritta)
- **LangGraph**: StateGraph, compile, invoke — stesso framework

---

## Fase 1: ChatModel Wrapper per LLMClient

**Problema**: `create_react_agent()` richiede un `BaseChatModel` LangChain con `bind_tools()`. Il nostro `LLMClient` e' un facade custom. Non vogliamo sostituirlo (perderemmo i 5 provider, GDPR check, fallback).

**Soluzione**: un thin wrapper che adatta `LLMClient` all'interfaccia `BaseChatModel`.

**Nuovo file**: `llm/langchain_adapter.py`

```python
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, ToolCall
from langchain_core.outputs import ChatResult, ChatGeneration

class GiAsLLM(BaseChatModel):
    """Adapter: espone LLMClient come BaseChatModel LangChain.
    
    Delega a LLMClient.query() per text, usa il protocollo nativo
    del provider sottostante per tool calling quando disponibile.
    """
    client: LLMClient  # il facade esistente
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Converte LangChain messages → formato provider
        # Se kwargs contiene "tools", usa il protocollo tool calling del provider
        # Altrimenti usa query() standard
        ...
    
    def bind_tools(self, tools, **kwargs):
        # Genera tools schema dal formato LangChain @tool
        # Ritorna self con tools bindati (pattern LangChain standard)
        ...
```

**Perche' un wrapper e non langchain-openai**: il wrapper preserva tutta l'infrastruttura esistente (5 provider, GDPR check, fallback stub, timeout, logging). Installare `langchain-openai` creerebbe un secondo path parallelo non integrato.

**Tool calling nel wrapper**: il metodo `_generate()` controlla se il provider supporta tool calling:
- `OpenAICompatProvider` / `OpenAIProvider`: aggiunge `tools` al request body (formato OpenAI nativo, gia' supportato dagli endpoint)
- `AnthropicProvider`: traduce tools in formato Anthropic (`input_schema`)
- `OllamaProvider`: passa `tools` nel body (supporto nativo Ollama >=0.4)
- `LlamaCppProvider`: fallback a "tools nel system prompt + JSON parsing" se il modello non supporta function calling

**File da modificare**:
- `llm/langchain_adapter.py` — **nuovo** (~150 righe)
- `llm/provider_base.py` — aggiungere `query_with_tools(messages, tools, ...) -> dict` e `supports_tool_calling() -> bool`
- `llm/providers.py` — implementare `query_with_tools` per ogni provider (o raise NotImplementedError per fallback)

**Verifica**: unit test con mock — `GiAsLLM.invoke()` restituisce `AIMessage`, `GiAsLLM.bind_tools()` ritorna modello con tools, tool calls vengono parsati correttamente.

---

## Fase 2: Tool Registration Nativa

**Problema attuale**: i tool in `tools/*.py` sono gia' decorati `@tool` LangChain, ma i wrapper in `tool_nodes.py` (1428 righe) aggiungono 3 cose: (a) estrazione slot/metadata dallo state, (b) iniezione UOS/ASL con fallback cascade, (c) two-phase check, (d) pseudo-query per debug.

**Soluzione**: tool wrapper leggeri che iniettano metadata, preservando il `@tool` nativo.

**Nuovo file**: `orchestrator/tool_registry.py` (~200 righe)

```python
from tools.piano_tools import get_piano_description, piano_tool
from tools.cu_statistics_tools import get_cu_statistics
from tools.risk_tools import get_risk_based_priority
# ... tutti i tool

def build_agent_tools(metadata: dict) -> list[BaseTool]:
    """Costruisce la lista tool per il ReAct agent, con metadata iniettato.
    
    Ogni tool riceve automaticamente asl, user_uos, etc. dal metadata
    dell'utente corrente, senza che l'LLM debba specificarli.
    """
    user_asl = metadata.get("asl")
    user_uos = _resolve_uos(metadata)  # cascade: metadata → user_id lookup → None
    
    @tool("statistiche_controlli")
    def cu_statistics(piano_code: str = None, anno: int = None, 
                      tipo_conteggio: str = "eseguiti") -> dict:
        """Conteggio controlli ufficiali eseguiti o programmati per piano, anno, macroarea."""
        return get_cu_statistics(
            piano_code=piano_code, anno=anno, asl=user_asl,
            user_uos=user_uos, tipo_conteggio=tipo_conteggio
        )
    
    # ... analogo per ogni tool
    return [cu_statistics, piano_description, ...]
```

**Vantaggi chiave**:
- I tool esposti all'LLM hanno **solo i parametri che l'LLM deve scegliere** (piano_code, anno, tipo_conteggio). ASL/UOS sono iniettati dalla closure — l'LLM non li vede nello schema, non li chiede all'utente, non li sbaglia.
- Le descrizioni tool sono in italiano (l'LLM opera in italiano).
- `build_agent_tools()` viene chiamato una volta per request con il metadata della sessione corrente.

**Two-phase**: diventa un tool esplicito `mostra_dettagli_completi(context_id)` — vedi Fase 3.

**Pseudo-query**: estratta nel post_processor dal tool output, non piu' nel wrapper.

**File coinvolti**:
- `orchestrator/tool_registry.py` — **nuovo** (~200 righe)
- `tools/*.py` — **nessuna modifica** (le funzioni sono gia' pronte)

---

## Fase 3: Nodo ReAct nel Grafo

**Nuovo file**: `orchestrator/react_node.py` (~250 righe)

Usa `create_react_agent()` di LangGraph (`langgraph.prebuilt`, gia' disponibile v1.0.5):

```python
from langgraph.prebuilt import create_react_agent

class ReactOrchestrator:
    def __init__(self, llm_client: LLMClient):
        self.llm_adapter = GiAsLLM(client=llm_client)
    
    def run(self, message: str, metadata: dict, session_context: dict) -> dict:
        # 1. Costruisci tools con metadata iniettato
        tools = build_agent_tools(metadata)
        
        # 2. Costruisci system prompt con contesto utente
        system = build_system_prompt(metadata, session_context)
        
        # 3. Crea agente ReAct (LangGraph gestisce il loop)
        agent = create_react_agent(
            model=self.llm_adapter,
            tools=tools,
            state_modifier=system,  # system prompt
        )
        
        # 4. Esegui con message history (dalla sessione)
        messages = self._build_messages(message, session_context)
        result = agent.invoke({"messages": messages})
        
        # 5. Estrai risposta + metadata per il post_processor
        return self._extract_result(result)
```

**Two-phase come tool**: l'agente vede i tool di dominio che gia' restituiscono `formatted_response` (testo completo). Per risultati lunghi, il tool restituisce un sommario + `context_id`. L'agente risponde con il sommario. Se l'utente chiede "mostra tutto", l'agente chiama `mostra_dettagli_completi(context_id)`:

```python
# In tool_registry.py
@tool("mostra_dettagli_completi")
def show_full_details(context_id: str) -> dict:
    """Mostra i dettagli completi di un risultato precedente."""
    return _detail_store.get(context_id, {"error": "Contesto non trovato"})
```

Il `_detail_store` e' un dict in-memory per sessione (o nel SessionManager), popolato dai tool quando troncano.

**Message history**: limitata a ultimi 3 turni (6 messaggi) per stare nel token budget. I turni piu' vecchi vengono riassunti in una riga nel system prompt. Il `SessionManager` viene esteso per persistere `messages[]` oltre ai campi strutturati attuali.

**File coinvolti**:
- `orchestrator/react_node.py` — **nuovo** (~250 righe)
- `orchestrator/react_prompts.py` — **nuovo** (~100 righe)
- `orchestrator/tool_registry.py` — esteso con `show_full_details`

---

## Fase 4: System Prompt Modulare

**Nuovo file**: `orchestrator/react_prompts.py`

Prompt costruito dinamicamente, non monolitico:

```python
def build_system_prompt(metadata: dict, session_context: dict) -> str:
    sections = [
        _IDENTITY,           # ~80 tok: chi sei, dominio veterinario
        _BEHAVIOR_RULES,     # ~150 tok: regole conversazionali
        _build_user_context(metadata),  # ~50 tok: ASL, UOC, UOS dell'utente
        _build_session_context(session_context),  # ~50 tok: ultimo intent, risultato precedente
    ]
    return "\n\n".join(sections)
```

**`_IDENTITY`**: identita' e dominio (ASL, GISA, veterinario campano).

**`_BEHAVIOR_RULES`** — sostituisce dialogue_manager.py:
- ASL/UOC/UOS dell'utente sono gia' noti (iniettati nei tool) — non chiederli mai
- Se manca un parametro obbligatorio (es. piano_code), chiedi in modo naturale in italiano
- Risultati lunghi: mostra sommario, offri dettagli (il tool tronca automaticamente)
- Mai inventare dati non presenti nei risultati tool
- Rispondi sempre in italiano con terminologia corretta
- Suggerisci 1-2 domande di follow-up pertinenti
- Se l'utente chiede "oppure" o alternative, proponi approcci diversi allo stesso problema
- Se l'utente raffina ("solo nel comune di X"), richiama il tool con il filtro aggiuntivo

**`_build_user_context`**: "L'utente opera nell'ASL {asl}, UOC {uoc}, UOS {uos}."

**`_build_session_context`**: "Nel turno precedente hai risposto riguardo a {last_response_context}." — per risoluzione anaforica, usando il campo gia' esistente nel SessionManager.

**Token budget totale prompt**: ~330 token (vs ~800 del piano originale).

**Few-shot**: **non inclusi nel system prompt**. I few-shot servivano per la classificazione intent nel router. Con il ReAct, l'LLM non classifica — sceglie direttamente il tool. Le descrizioni tool sono sufficienti.

---

## Fase 5: Integrazione nel Grafo Esistente

**Modifica**: `orchestrator/graph.py`

Il grafo viene evoluto, non riscritto. Si aggiunge un ramo condizionale all'entry point:

```python
def _build_graph(self) -> StateGraph:
    workflow = StateGraph(ConversationState)
    
    # Entry: fast-path filter
    workflow.add_node("fast_path", self._fast_path_node)
    
    # Ramo agent (nuovo)
    workflow.add_node("react_agent", self._react_agent_node)
    workflow.add_node("post_processor", self._post_processor_node)
    
    # Ramo graph legacy (preservato intatto)
    workflow.add_node("classify", self._classify_node)
    workflow.add_node("dialogue_manager", self._dialogue_manager_node)
    # ... tutti i nodi attuali ...
    
    # Entry point
    workflow.set_entry_point("fast_path")
    
    # fast_path → conditional
    workflow.add_conditional_edges("fast_path", self._mode_router, {
        "direct_response": END,        # saluti/conferme gestiti
        "react_agent": "react_agent",  # mode agent
        "classify": "classify",        # mode graph (legacy)
    })
    
    # Ramo agent: react_agent → post_processor → END
    workflow.add_edge("react_agent", "post_processor")
    workflow.add_edge("post_processor", END)
    
    # Ramo legacy: invariato
    workflow.add_edge("classify", "dialogue_manager")
    # ... tutte le edges attuali ...
```

**`_fast_path_node`**: estrae la logica di fast-path gia' presente nel router (saluti, conferme si/no dopo two-phase, gibberish). ~50 righe, regex puro.

**`_mode_router`**: legge `config.json → orchestration.mode` (`"agent"` | `"graph"`, default `"graph"`).

**`_react_agent_node`**: istanzia `ReactOrchestrator.run()`, mappa il risultato sul `ConversationState` esistente (popola `final_response`, `intent`, `slots`, `tool_output`, `suggestions`, `has_more_details`, `detail_context`).

**`_post_processor_node`**: estrae pseudo_query dal tool_output per la debug page, genera follow-up suggestions, persiste `detail_context` se two-phase attivo.

**Contratto invariato**: `ConversationGraph.run()` ritorna lo stesso dict di sempre. L'API in `api.py` non cambia.

**File da modificare**:
- `orchestrator/graph.py` — aggiungere nodi + conditional edge (~80 righe aggiunte)
- `configs/config.json` — aggiungere `"orchestration": {"mode": "graph"}` (default safe)
- `configs/config.py` — leggere il nuovo flag

---

## Fase 6: Observability e Shadow Mode

Prima del rollout, eseguire l'agente in **shadow mode** per confronto:

**Modifica** in `app/api.py`: se `orchestration.mode == "shadow"`, esegui **entrambi** (graph e agent) sullo stesso messaggio. Logga:

```python
# In chat_log, aggiungere colonna agent_response (nullable)
log_chat(
    ask=message, intent=intent, answer=graph_response,
    agent_answer=agent_response,  # nuovo campo shadow
    agent_intent=agent_intent,    # per confronto
    response_time_ms=graph_time, agent_response_time_ms=agent_time,
)
```

**Metriche da confrontare**:
- Accuratezza intent (agent vs graph sullo stesso messaggio)
- Latenza (ms)
- Token consumati per turno
- Tasso di fallback/errore
- Tasso two-phase (l'agente tronca quando dovrebbe?)

**Query di analisi**:
```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN intent = agent_intent THEN 1 ELSE 0 END) as intent_match,
    AVG(response_time_ms) as avg_graph_ms,
    AVG(agent_response_time_ms) as avg_agent_ms
FROM chat_log WHERE agent_answer IS NOT NULL;
```

---

## File Coinvolti — Riepilogo

| File | Azione | Fase |
|------|--------|------|
| `llm/langchain_adapter.py` | **Nuovo**: ChatModel wrapper | 1 |
| `llm/provider_base.py` | Modifica: `query_with_tools()`, `supports_tool_calling()` | 1 |
| `llm/providers.py` | Modifica: impl tool calling per provider | 1 |
| `orchestrator/tool_registry.py` | **Nuovo**: build_agent_tools con metadata injection | 2 |
| `orchestrator/react_node.py` | **Nuovo**: ReactOrchestrator con create_react_agent | 3 |
| `orchestrator/react_prompts.py` | **Nuovo**: system prompt modulare | 4 |
| `orchestrator/graph.py` | Modifica: fast_path + conditional mode routing | 5 |
| `configs/config.json` | Modifica: `orchestration.mode` | 5 |
| `configs/config.py` | Modifica: lettura flag | 5 |
| `app/api.py` | Modifica: shadow mode logging | 6 |

**File NON toccati**: `tools/*.py`, `agents/`, `data_sources/`, `app/session_manager.py` (minima estensione per messages[]), `orchestrator/dialogue_manager.py`, `orchestrator/router.py`, `orchestrator/tool_nodes.py`, `orchestrator/two_phase.py`, `orchestrator/response_node.py`.

---

## Cosa NON fa questo piano (deliberatamente)

- **Non depreca il grafo legacy**: resta come fallback permanente via flag. Zero rischio.
- **Non introduce dipendenze nuove**: usa LangGraph 1.0.5 e langchain-core 1.2.5 gia' installati. `create_react_agent` e' gia' disponibile. Nessun `langchain-openai` o SDK proprietario.
- **Non riscrive il session manager**: lo estende minimamente per messages[] (lista di 6 messaggi max, non una riscrittura).
- **Non tocca i tool di dominio**: le funzioni in `tools/*.py` restano identiche. Il `tool_registry.py` crea wrapper closure che iniettano metadata — il tool sottostante non sa di essere in un agente.
- **Non espone protocolli proprietari**: il formato OpenAI tools e' incapsulato dentro `GiAsLLM._generate()`. Se un domani il formato cambia, si modifica un solo file.

---

## Verifica End-to-End

1. **Fase 1**: `python -c "from llm.langchain_adapter import GiAsLLM; m = GiAsLLM(); print(m.invoke('ciao'))"` — verifica che il wrapper funzioni
2. **Fase 2**: `python -c "from orchestrator.tool_registry import build_agent_tools; tools = build_agent_tools({'asl':'NAPOLI'}); print([t.name for t in tools])"` — verifica lista tool
3. **Fase 3**: test manuale con curl (mode agent):
   ```bash
   curl -X POST http://localhost:5005/api/v1/chat \
     -H "Content-Type: application/json" \
     -d '{"sender":"test","message":"quanti controlli A9_A nel 2025?","metadata":{"asl":"BENEVENTO"}}'
   ```
   Verificare che l'LLM scelga `statistiche_controlli` autonomamente e presenti il risultato.
4. **Fase 5**: switch a mode `"graph"` in config.json, ripetere — verifica che il legacy funzioni identicamente
5. **Fase 6**: mode `"shadow"`, query di confronto su chat_log dopo 50+ messaggi reali
6. **Sempre**: `python -m pytest tests/unit/ -v` — i test esistenti devono passare (API contract invariato)

---

## Stima Costi e Latenza

| Metrica | Graph attuale | Agent (stima) |
|---------|--------------|---------------|
| LLM calls/turno | 2 (classify + response) | 1 (con tool calls inline) |
| Token/turno (prompt) | ~1500 | ~2500 (tools schema ~1500 + system ~330 + message ~500 + history ~200) |
| Token/turno (completion) | ~800 | ~600 (risposta diretta, no classify JSON) |
| Latenza tipica | 2-8s | 2-5s (1 roundtrip vs 2) |
| Costo/turno (Gemini Flash) | ~$0.0002 | ~$0.0003 |

L'aumento di token nel prompt e' compensato dalla riduzione a 1 sola call LLM (vs 2 separate). La latenza migliora perche' si elimina il roundtrip classify → dialogue_manager → response_generator.
