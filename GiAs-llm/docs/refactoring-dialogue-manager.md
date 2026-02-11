# Refactoring GISA-AI: Workflow + GUI

---

# Parte I — Refactoring LangGraph Workflow: Dialogue State Tracking

## 1. Analisi del sistema attuale

### Architettura runtime

Il workflow LangGraph è definito in `orchestrator/graph.py` (~1661 righe) come un grafo piatto a 3 stadi:

```
classify → tool_node/workflow_node → response_generator → END
```

Ogni turno è **single-pass**: il messaggio entra, viene classificato, esegue un nodo, genera risposta, esce. Non esiste un ciclo interno al grafo.

### File coinvolti a runtime

| File | Righe | Ruolo |
|------|-------|-------|
| `app/api.py` | ~935 | Entry point FastAPI, sessioni, webhook |
| `orchestrator/graph.py` | ~1661 | Grafo LangGraph, tutti i nodi, stato |
| `orchestrator/router.py` | ~1070 | Router ibrido 4 livelli |
| `orchestrator/fallback_recovery.py` | ~547 | Recovery 3 fasi |
| `orchestrator/workflow_strategies.py` | ~307 | Strategie multi-turno (2 su 6) |
| `orchestrator/workflow_validator.py` | ~278 | Validazione sicurezza workflow |
| `orchestrator/intent_cache.py` | ~216 | Cache intent MD5+TTL |
| `orchestrator/intent_metadata.py` | ~383 | Registry 19 intent |
| `agents/response_agent.py` | ~1256 | Formattazione risposte |
| `agents/data.py` | — | Caricamento dati in memoria |

**Nota**: i file `agents/data_agent.py`, `risk_agent.py`, `search_agent.py`, `piano_agent.py`, `priority_agent.py` **non sono importati** da nessun modulo runtime. Solo `response_agent.py` e `data.py` sono usati.

### Flusso dati attuale

```
User message
  │
  ▼
api.py webhook
  ├── Carica _session_store[sender]
  ├── Valida workflow_context (WorkflowValidator)
  ├── Inietta sessione in metadata (_session_last_intent, _session_last_slots, _session_summary)
  │
  ▼
ConversationGraph.run(message, metadata, detail_context, workflow_context)
  │
  ▼
[classify] node
  ├── Check selezione da fallback_suggestions
  ├── classify_with_context() OPPURE classify()
  │     ├── Layer 1: Heuristics (~25 regex)
  │     ├── Layer 2: Pre-parse slot (regex)
  │     ├── Layer 3: Cache (MD5, TTL 1h)
  │     └── Layer 4: LLM (Ollama)
  ├── Post-validation (required slots)
  └── Slot carry-forward (se needs_clarification)
  │
  ▼
[_workflow_router] conditional edge
  ├── 5 intent workflow: __present_strategies__, __choose_strategy__, __provide_param__, __oppure__, __refine__
  └── 19 intent standard → tool node corrispondente
  │
  ▼
[tool_node] o [workflow_node]
  ├── Esegui tool function
  ├── Applica two-phase check (sommario + "Vuoi vedere i dettagli?")
  └── Setta tool_output
  │
  ▼
[response_generator]
  ├── Intent diretti (greet, fallback): restituisce formatted_response
  └── Dati complessi: LLM genera risposta naturale
  │
  ▼
END → api.py aggiorna _session_store → RasaResponse
```

---

## 2. Problemi identificati

### 2.1 Nessuna memoria conversazionale strutturata

Lo stato tra turni è un dizionario flat in `_session_store` con solo `last_intent`, `last_slots` e un `conversation_summary` testuale. Non esiste un modello di **dialogue state** che tracci:
- L'obiettivo dell'utente (goal)
- Quali slot sono stati raccolti e quali mancano
- La storia delle disambiguazioni già fatte

### 2.2 Il Router classifica ma non disambigua

Il Router a 4 livelli mappa un messaggio → 1 intent in un singolo colpo. `classify_with_context()` gestisce solo workflow già avviati. Non c'è meccanismo per:
- Riconoscere un intent **parziale/vago** e formulare una domanda mirata
- Accumulare informazioni da più turni prima di scegliere l'intent definitivo

### 2.3 Il grafo è lineare, non ciclico

Tutti gli edge vanno verso `response_generator → END`. Non c'è modo per un nodo di dire "ho bisogno di più informazione, torna a chiedere all'utente". Il workflow multi-turno funziona solo perché `api.py` ricostruisce lo stato ad ogni turno tramite `workflow_context`, ma è fragile.

### 2.4 Slot carry-forward limitato

Il carry-forward (`_classify_node` riga ~280) opera solo quando `needs_clarification=True`. Un raffinamento come "rifai nel comune di X" richiede che `workflow_context` sia ancora valido (TTL 5 min) e che il router lo riconosca come `__refine__`.

### 2.5 Workflow strategies troppo rigide

`workflow_strategies.py` definisce strategie solo per 2 intent su 6. La configurazione è statica: domande, opzioni e parametri sono hardcoded.

### 2.6 graph.py monolitico

~1661 righe contengono: stato, grafo, 22 nodi, two-phase logic, workflow, response generator, run(). Candidato principale per decomposizione.

---

## 3. Dialogo target

Il refactoring deve supportare conversazioni come la seguente:

| Turno | Utente | Sistema | Stato DST |
|-------|--------|---------|-----------|
| 0 | "Vorrei sapere come organizzarmi la giornata" | "Intendi dire come organizzare i controlli da eseguire?" | goal="organizzare giornata", candidates=[suggest_controls(0.6), priority(0.55), delayed(0.4)] |
| 1 | "sì, vorrei indicazioni sulle priorità dei controlli" | "preferisci partire dalla programmazione o dall'analisi del rischio?" | goal confermato, intent_area=priorità/controlli |
| 2 | "dal rischio" | "posso partire dalle NC rilevate e mostrarti le attività più rischiose" | confirmed_strategy=risk_nc |
| 3 | "oppure?" | "posso estrarre dagli stabilimenti mai controllati quelli con attività a maggior rischio" | mostra alternative stessa area |
| 4 | "ok, mostrami i primi 100" | "[risultati]" | slots.limit=100, execute |
| 5 | "puoi rifare la ricerca solo nel comune di ...?" | "[risultati filtrati]" | filters.comune=X, re-execute |

### Cosa manca oggi per supportarlo

| Turno | Comportamento attuale | Problema |
|-------|----------------------|----------|
| 0 | Fallback o intent errato (confidence bassa) | Nessuna disambiguazione strutturata |
| 1 | Classification da zero, perde contesto turno 0 | Solo `last_intent` + `conversation_summary` disponibili |
| 2 | Funziona solo se workflow_context è stato creato al turno 1 | Fragile, dipende da path specifico |
| 3 | Funziona tramite `__oppure__` se workflow attivo | OK ma legato a workflow_context |
| 4 | Richiede parsing numerico + workflow attivo | OK se workflow_context non scaduto |
| 5 | Solo se workflow_context non scaduto e refine riconosciuto | TTL 5 min, fragile |

---

## 4. Proposta di refactoring

### 4.1 Principio: Dialogue State Tracking (DST) con ciclo inter-turno

Trasformare il grafo da lineare a ciclico (tra turni), introducendo un nodo **dialogue manager**:

```
                    ┌─────────────────────────────┐
                    │                             ▼
classify ──► dialogue_manager ──► info sufficiente? ──NO──► ask_user ──► END
                    │                                        (salva DialogueState)
                    │ SÌ
                    ▼
              execute_tool ──► response_generator ──► END
```

Il ciclo non è intra-request ma **inter-turno**: `ask_user` genera la domanda e termina. Al turno successivo, `classify` riceve il messaggio con il `DialogueState` salvato, e il `dialogue_manager` riprende da dove aveva lasciato.

### 4.2 DialogueState strutturato

Nuovo modulo `orchestrator/dialogue_state.py`:

```python
from typing import TypedDict, Optional, List, Dict, Any

class IntentCandidate(TypedDict):
    intent: str
    confidence: float
    slots: Dict[str, Any]

class ClarificationRecord(TypedDict):
    turn: int
    question: str
    answer: str
    resolved: str  # cosa ha risolto: "intent", "strategy", "slot:nome_slot"

class DialogueState(TypedDict):
    # Obiettivo conversazionale
    goal: Optional[str]                    # descrizione alto livello
    intent_candidates: List[IntentCandidate]  # candidati con confidence

    # Stato confermato
    confirmed_intent: Optional[str]
    confirmed_strategy: Optional[str]

    # Slot e filtri accumulati
    slots: Dict[str, Any]                 # slot raccolti nei turni
    missing_slots: List[str]              # slot ancora necessari
    filters: Dict[str, Any]              # filtri accumulati (comune, limit, ecc.)

    # Storia dialogo
    clarification_history: List[ClarificationRecord]
    turn_count: int

    # Per refinement
    last_tool_result: Optional[Any]
    last_tool_intent: Optional[str]
    last_tool_strategy: Optional[str]
```

Questo stato viene serializzato in `_session_store` e passato tra turni, sostituendo i campi sparsi attuali (`last_intent`, `last_slots`, `conversation_summary`, `workflow_context`).

### 4.3 Nodo dialogue_manager

Nuovo modulo `orchestrator/dialogue_manager.py`.

Logica decisionale **rule-based** (niente LLM aggiuntivo, per velocità):

```
REGOLA 1 — Intent chiaro, slot completi
  SE intent_candidates ha 1 candidato con confidence > 0.8
     E tutti i required_slots sono presenti:
     → confirmed_intent = candidato
     → vai a execute_tool

REGOLA 2 — Intent chiaro, slot mancanti
  SE intent_candidates ha 1 candidato con confidence > 0.8
     MA mancano slot obbligatori:
     → chiedi lo slot mancante (domanda specifica generata dal template)

REGOLA 3 — Intent ambiguo
  SE intent_candidates ha 2+ candidati con confidence simile (delta < 0.2):
     → formula domanda di disambiguazione tra i candidati top
     → usa intent_metadata per generare opzioni leggibili

REGOLA 4 — Nessun candidato valido
  SE nessun candidato ha confidence > 0.5:
     → chiedi riformulazione con suggerimenti basati sui candidati
     → (equivale al fallback attuale ma integrato nel DST)

REGOLA 5 — Refinement
  SE c'è last_tool_result E il messaggio contiene filtri nuovi:
     → aggiungi filtri a DialogueState.filters
     → re-esegui last_tool_intent con parametri aggiornati

REGOLA 6 — Strategia necessaria
  SE confirmed_intent ha strategie disponibili (da WORKFLOW_STRATEGIES)
     E confirmed_strategy è None:
     → presenta strategie come opzioni
     → salva in pending

REGOLA 7 — "Oppure?"
  SE messaggio è variante di "oppure/alternative/altro modo"
     E c'è confirmed_strategy:
     → mostra strategie alternative non ancora proposte
```

### 4.4 Modifiche al Router

Il Router resta come classificatore di primo livello ma cambia il suo output:

**Prima** (attuale):
```python
return {
    "intent": "ask_suggest_controls",
    "confidence": 0.85,
    "slots": {"limit": 10},
    "needs_clarification": False
}
```

**Dopo**:
```python
return {
    "candidates": [
        {"intent": "ask_suggest_controls", "confidence": 0.72, "slots": {}},
        {"intent": "ask_priority_establishment", "confidence": 0.65, "slots": {}},
        {"intent": "ask_delayed_plans", "confidence": 0.40, "slots": {}}
    ],
    "extracted_slots": {"limit": 10},
    "raw_message_type": "vague_request"  # vague_request | specific_query | continuation | refinement | selection
}
```

Il campo `raw_message_type` aiuta il dialogue_manager a capire **come** trattare il messaggio senza dover ri-analizzare il testo. Il LLM Layer 4 del router viene modificato per restituire i top-3 candidati invece del singolo migliore.

### 4.5 Accumulo filtri cross-turno

`DialogueState.filters` accumula filtri da tutti i turni. Quando l'utente dice "nel comune di X" al turno 5:

1. Il Router classifica come `raw_message_type = "refinement"`
2. Il dialogue_manager vede `last_tool_result` presente
3. Estrae `comune=X` dal messaggio (regex già presenti in `workflow_strategies.py`)
4. Aggiunge a `filters`, merge con slot esistenti
5. Re-esegue `last_tool_intent` + `last_tool_strategy` con parametri aggiornati

Questo sostituisce il nodo `refine_query` attuale.

### 4.6 Decomposizione di graph.py

| Nuovo file | Contenuto | Provenienza |
|------------|-----------|-------------|
| `orchestrator/graph.py` | Solo definizione grafo, routing, run() | Scheletro attuale (~200 righe) |
| `orchestrator/dialogue_state.py` | `DialogueState`, serializzazione, merge | Nuovo |
| `orchestrator/dialogue_manager.py` | Nodo DST, regole decisione | Nuovo |
| `orchestrator/tool_nodes.py` | Tutti i metodi `_*_tool()` | Estratti da graph.py (~800 righe) |
| `orchestrator/response_node.py` | `_response_generator_node()` + prompt | Estratto da graph.py (~100 righe) |
| `orchestrator/two_phase.py` | Logica two-phase check | Estratta da graph.py (~50 righe) |

### 4.7 Nuovo grafo LangGraph

```python
def _build_graph(self) -> StateGraph:
    workflow = StateGraph(ConversationState)

    # Nodi principali
    workflow.add_node("classify", self._classify_node)
    workflow.add_node("dialogue_manager", self._dialogue_manager_node)
    workflow.add_node("ask_user", self._ask_user_node)

    # Tool nodes (registrati da tool_nodes.py)
    for name, func in TOOL_REGISTRY.items():
        workflow.add_node(name, func)

    workflow.add_node("response_generator", self._response_generator_node)

    # Entry
    workflow.set_entry_point("classify")

    # classify → dialogue_manager (sempre)
    workflow.add_edge("classify", "dialogue_manager")

    # dialogue_manager → ask_user O tool_node (conditional)
    workflow.add_conditional_edges(
        "dialogue_manager",
        self._dm_router,
        {
            "ask_user": "ask_user",
            **{name: name for name in TOOL_REGISTRY},
        }
    )

    # ask_user → END (risposta all'utente, attende prossimo turno)
    workflow.add_edge("ask_user", END)

    # tool_nodes → response_generator → END
    for name in TOOL_REGISTRY:
        workflow.add_edge(name, "response_generator")
    workflow.add_edge("response_generator", END)

    return workflow.compile()
```

Differenze chiave rispetto all'attuale:
- **`classify` va sempre a `dialogue_manager`**, non direttamente ai tool
- **`dialogue_manager` decide** se servono chiarimenti (`ask_user`) o se eseguire (`tool_node`)
- **`ask_user` → END`**: la domanda esce, il prossimo turno riparte da `classify` con il `DialogueState` aggiornato
- Il routing dei tool è nel `dialogue_manager`, non nel `classify`

### 4.8 Pulizia codice morto

File da rimuovere o archiviare (non usati a runtime):

- `agents/data_agent.py`
- `agents/risk_agent.py`
- `agents/search_agent.py`
- `agents/piano_agent.py`
- `agents/priority_agent.py`

---

## 5. Piano di migrazione incrementale

La migrazione può avvenire in fasi, mantenendo il sistema funzionante ad ogni step.

### Fase 1: Decomposizione graph.py (nessun cambio funzionale)

1. Estrarre tool nodes in `orchestrator/tool_nodes.py`
2. Estrarre response generator in `orchestrator/response_node.py`
3. Estrarre two-phase in `orchestrator/two_phase.py`
4. Verificare che tutti i test passino

### Fase 2: DialogueState + serializzazione

1. Creare `orchestrator/dialogue_state.py`
2. In `api.py`, convertire la gestione sessione: popolare `DialogueState` dai campi attuali
3. Passare `DialogueState` nel metadata
4. Backwards-compatible: i campi vecchi restano come fallback

### Fase 3: Router multi-candidato

1. Modificare `router.classify()` per restituire lista candidati
2. Aggiungere `raw_message_type` all'output
3. In `_classify_node`, adattare per consumare il nuovo formato
4. Il dialogue_manager non esiste ancora: usare il candidato top come prima (comportamento identico)

### Fase 4: Dialogue Manager (cambio funzionale)

1. Creare `orchestrator/dialogue_manager.py` con le 7 regole
2. Inserire nel grafo tra `classify` e i tool
3. Aggiungere nodo `ask_user`
4. Testare con il dialogo target

### Fase 5: Eliminazione codice legacy

1. Rimuovere nodi workflow vecchi (`present_strategies`, `handle_strategy_choice`, `collect_params`, `handle_oppure`, `refine_query`)
2. Rimuovere `workflow_context` da `api.py`
3. Rimuovere intent speciali `__present_strategies__`, `__choose_strategy__`, ecc.
4. Rimuovere file agenti non usati

---

## 6. Rischi e trade-off

| Aspetto | Pro | Contro |
|---------|-----|--------|
| Rule-based dialogue_manager | Veloce, prevedibile, nessuna latenza LLM aggiuntiva | Richiede regole per ogni combinazione, meno flessibile |
| Multi-candidato dal Router | Disambiguazione più intelligente | Prompt LLM più complesso, output più grande da parsare |
| DialogueState persistente | Conversazioni articolate, refinement robusto | Più stato da gestire, serializzazione, TTL |
| Decomposizione graph.py | Manutenibilità, testabilità | Refactoring import, possibili regressioni |
| Migrazione incrementale | Nessun downtime, rollback facile per fase | Più tempo totale, codice bridge temporaneo |

### Latenza

Nessun impatto: il ciclo DST è inter-turno (tra request HTTP separate). Il dialogue_manager è rule-based e aggiunge ~1ms per turno.

### Compatibilità

Il protocollo Rasa (sender/message/metadata → [{text}]) non cambia. Il frontend non richiede modifiche.

---

# Parte II — Review GUI gchat: Visualizzazione Messaggi

## 7. Contesto del problema

L'applicazione è una chat assistente per veterinari ASL. Il pattern di utilizzo è fortemente **asimmetrico**: le domande dell'utente sono brevi (5-20 parole), mentre le risposte del sistema sono molto lunghe — elenchi di stabilimenti, piani di monitoraggio, analisi di rischio — che possono contenere decine o centinaia di item strutturati.

Questo crea uno squilibrio visivo: una riga di domanda seguita da una "muraglia di testo" che occupa diversi schermi di scroll.

## 8. Architettura UI attuale

### File coinvolti

| File | Ruolo |
|------|-------|
| `gchat/template/index.html` | Template Gin, struttura pagina |
| `gchat/statics/js/chat.js` | Classe `ChatBot`: rendering messaggi, formatting, scroll, SSE |
| `gchat/statics/css/style.css` | Layout, messaggi, tema light/dark, responsive |
| `gchat/statics/css/new-formatting.css` | Formattazione contenuto: liste, campi, sezioni, rischio |

### Struttura DOM dei messaggi

```html
<!-- Domanda utente -->
<div class="message user-message">
  <div class="message-content">testo breve</div>
  <div class="message-time">14:32</div>
</div>

<!-- Risposta bot -->
<div class="message bot-message">
  <div class="message-content">
    <!-- Blocchi: section-header, list-container, field-group, text-content, ecc. -->
  </div>
  <div class="message-time">14:33</div>
  <div class="download-btn-container">...</div>
  <div class="suggestions-container">...</div>
</div>
```

### Rendering dei messaggi (`formatMessage`)

Il metodo `formatMessage` in `chat.js` usa un parser custom a blocchi (non markdown standard):
- Identifica tipi di riga: `list-item`, `bullet-item`, `markdown-header`, `header`, `field`, `subheader`, `text`
- Converte in HTML con classi CSS specifiche per dominio (`.list-item-compact`, `.establishment-header`, `.risk-score`, ecc.)
- Gestisce campi veterinari specifici: Comune, Indirizzo, Punteggio rischio, NC storiche, Controlli

**Non supporta**: tabelle markdown, code block, link/URL auto-detect.

### Stili chiave

| Elemento | Light | Dark |
|----------|-------|------|
| Messaggio utente | `background: #f4f4f4`, `max-width: 70%`, pill shape | `background: #3a3a3a` |
| Messaggio bot | `background: transparent`, `max-width: 100%`, nessun bordo | `color: #ececec` |
| Section header | Gradiente blu `#007acc→#005293`, testo bianco, pill | Gradiente `#1d4ed8→#1e40af` |
| List item | `background: rgba(245,245,247,0.8)`, pill, numero blu | `background: rgba(55,65,81,0.8)` |
| Font base | `13px`, `line-height: 1.45` | Identico |
| Dettagli item | `0.85em` (~11px), label grigio, valore nero | Label `#9ca3af`, valore `#e5e7eb` |

## 9. Problemi identificati

### 9.1 Assenza di collapsing/troncamento per risposte lunghe

Le risposte con 50-100+ item vengono renderizzate per intero in un singolo `.message-content`. Non esiste:
- Troncamento con "Mostra altro"
- Sezioni collassabili
- Paginazione interna al messaggio

**Impatto**: l'utente deve scrollare per diversi schermi per raggiungere la fine della risposta o i suggerimenti. La domanda breve che ha originato la risposta scompare dal viewport.

### 9.2 Font troppo piccoli per contenuto denso

- Base messaggi: `13px`
- Dettagli item (Comune, Indirizzo, Rischio): `0.85em` = ~11px
- Label campi: `11px` (in `style.css`)
- Timestamp: `10px`

Su schermi desktop standard e soprattutto su dispositivi usati in contesti operativi (uffici ASL), 11px è al limite della leggibilità. Il contrasto label grigio (`#666`) su sfondo chiaro (`rgba(245,245,247)`) è insufficiente.

### 9.3 Nessuna separazione visiva domanda/risposta

I messaggi bot hanno `background: transparent` e nessun bordo — sono testo libero nella pagina. Quando la risposta è molto lunga, non c'è modo di distinguere visivamente dove finisce un turno di conversazione e inizia il successivo. L'unico separatore è `margin-top: 8px` su `.user-message + .bot-message`.

### 9.4 Scroll istantaneo senza "torna giù"

`scrollToBottom()` fa un salto istantaneo (`scrollTop = scrollHeight`). Se l'utente sta rileggendo una risposta precedente e arriva un nuovo messaggio, perde la posizione. Non c'è:
- Smooth scrolling
- Pulsante "Nuovi messaggi ↓"
- Rilevamento della posizione di scroll dell'utente

### 9.5 Streaming non progressivo

I token SSE vengono ricevuti ma scartati (`chat.js`). L'utente vede solo l'animazione "thinking" e poi la risposta completa appare di colpo. Per risposte lunghe, l'attesa senza feedback è problematica.

### 9.6 Suggerimenti poco visibili

I suggerimenti di follow-up (`.suggestions-container`) appaiono **dopo** la risposta completa. Se la risposta è lunga, l'utente deve scrollare fino in fondo per vederli. Usano stili inline invece di classi CSS, rendendo fragile il supporto dark theme (compensato con `!important`).

### 9.7 Due sistemi di stile in conflitto

`style.css` e `new-formatting.css` definiscono entrambi `.section-header`:
- `style.css`: sfondo `#f7f7f7`, border-left marrone `#d4a574`
- `new-formatting.css`: gradiente blu `#007acc→#005293`, pill shape

Il secondo vince per cascade, ma il codice morto in `style.css` crea confusione e rischio di regressioni.

### 9.8 Nessun breakpoint intermedio

Solo due breakpoint: `max-width: 768px` (mobile) e `min-width: 1600px` (wide). Tablet e laptop 1024-1366px non hanno regole specifiche. L'area chat è fissa a `max-width: 900px` centrata, lasciando ampi margini vuoti su schermi 1200-1500px.

### 9.9 Nessuna accessibilità

- Nessun `role="log"` sulla chat area
- Nessun `aria-live="polite"` per nuovi messaggi
- Nessun `aria-label` sui pulsanti (download, tema, invio)
- Focus non gestito dopo invio messaggio

## 10. Proposte di miglioramento

### 10.1 Collapsing progressivo per risposte lunghe

Per risposte con più di N item (configurabile, default 10), mostrare i primi N con un pulsante "Mostra tutti i K risultati ▼":

```
┌─ Sezione header ─────────────────────────────┐
│ Item 1 — Stabilimento X, Comune Y            │
│ Item 2 — ...                                  │
│ ...                                           │
│ Item 10 — ...                                 │
├───────────────────────────────────────────────┤
│         ▼ Mostra tutti i 87 risultati         │
└───────────────────────────────────────────────┘
```

Implementazione nel metodo `formatMessage` o come post-processing del DOM:

```javascript
// Dopo il rendering, wrappa i list-item oltre il threshold
const items = messageEl.querySelectorAll('.list-item-compact');
if (items.length > COLLAPSE_THRESHOLD) {
    const wrapper = document.createElement('div');
    wrapper.className = 'collapsed-section';
    items.forEach((item, i) => {
        if (i >= COLLAPSE_THRESHOLD) {
            item.style.display = 'none';
            item.classList.add('collapsible-item');
        }
    });
    // Aggiungi pulsante toggle
    const toggle = document.createElement('button');
    toggle.className = 'expand-toggle';
    toggle.textContent = `▼ Mostra tutti i ${items.length} risultati`;
    toggle.onclick = () => { /* toggle display */ };
}
```

Questo è **complementare** al two-phase attuale (sommario + "Vuoi i dettagli?"). Il two-phase gestisce il caso "troppi risultati" lato backend; il collapsing gestisce la visualizzazione di quelli mostrati.

### 10.2 Aumentare i font e il contrasto

| Elemento | Attuale | Proposto |
|----------|---------|----------|
| Base messaggi | 13px / 1.45 | **14px** / 1.5 |
| Detail lines | 0.85em (11px) | **0.9em** (12.6px) |
| Field labels | 11px, `#666` | **12px**, `#555` |
| Field values | 11px | **12px** |
| Timestamp | 10px | **11px** |
| Mobile base | 0.8rem (12.8px) | **0.85rem** (13.6px) |

Per il contrasto, usare `#555` invece di `#666` per le label su sfondo chiaro (ratio WCAG AA: 4.5:1 minimo).

### 10.3 Card per i messaggi bot con separazione visiva turni

Wrappare ogni coppia domanda-risposta in un contenitore visuale, oppure aggiungere un bordo/sfondo sottile ai messaggi bot:

```css
.bot-message .message-content {
    background: #fafbfc;            /* sfondo appena percettibile */
    border: 1px solid #e8eaed;     /* bordo sottile */
    border-radius: 12px;
    padding: 16px;
    max-width: 100%;
}

body.dark-theme .bot-message .message-content {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
}
```

In alternativa, un separatore di turno:

```css
.bot-message + .user-message {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
}
```

### 10.4 Pulsante "Scroll to bottom" e smooth scrolling

```javascript
// Rileva se l'utente ha scrollato verso l'alto
chatMessages.addEventListener('scroll', () => {
    const isNearBottom = chatMessages.scrollHeight - chatMessages.scrollTop
                         - chatMessages.clientHeight < 100;
    scrollToBottomBtn.style.display = isNearBottom ? 'none' : 'flex';
});

// Smooth scroll
scrollToBottom() {
    this.chatMessages.scrollTo({
        top: this.chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}
```

Pulsante fisso in basso a destra nell'area chat, con badge "N nuovi messaggi" se ci sono messaggi non letti sotto il fold.

### 10.5 Rendering progressivo dei token SSE

Attualmente i token SSE vengono ricevuti ma ignorati. Abilitare il rendering progressivo:

1. Alla ricezione del primo token, sostituire il "thinking" message con un `.message-content` vuoto
2. Ad ogni token, appendere il testo e ri-parsare i blocchi visibili
3. Alla fine, fare il formatting completo

Per evitare il costo del re-parsing continuo, appendere i token come testo raw e fare il formatting solo alla fine (approccio ibrido):

```javascript
// Durante streaming: mostra testo grezzo con cursore lampeggiante
thinkingEl.innerHTML = rawText + '<span class="cursor">▊</span>';

// Al final event: sostituisci con formatMessage()
messageEl.innerHTML = this.formatMessage(fullText);
```

Questo dà feedback immediato senza il costo del parsing ad ogni token.

### 10.6 Suggerimenti sticky in fondo all'area visibile

Spostare i suggerimenti fuori dal messaggio e posizionarli come barra fissa sopra l'input:

```
┌─────────────────────────────────────────────┐
│ [area messaggi scrollabile]                 │
│                                             │
├─────────────────────────────────────────────┤
│ 💡 Puoi anche: [Filtra per comune] [Top 20] │  ← suggestions bar
├─────────────────────────────────────────────┤
│ 📝 Domande predefinite                       │
├─────────────────────────────────────────────┤
│ [input] [Invia]                             │
└─────────────────────────────────────────────┘
```

I suggerimenti rimangono visibili senza scrollare e si aggiornano ad ogni risposta.

### 10.7 Consolidare gli stili e rimuovere codice morto

1. Rimuovere da `style.css` le regole `.section-header`, `.list-item`, `.list-number`, `.field-label`, `.field-value` che sono sovrascritte da `new-formatting.css`
2. Spostare gli stili inline dei suggerimenti (`createSuggestionsContainer`) in classi CSS in `new-formatting.css`
3. Unificare l'accento colore: light usa `#d4a574` (marrone) in alcuni punti e `#007acc` (blu) in altri. Scegliere uno schema coerente.

### 10.8 Breakpoint intermedio per tablet/laptop

```css
@media (min-width: 769px) and (max-width: 1200px) {
    .chat-messages {
        max-width: 95%;     /* usa più spazio su schermi medi */
        padding: 12px 16px;
    }

    .user-message .message-content {
        max-width: 75%;
    }
}
```

### 10.9 Accessibilità base

```html
<div class="chat-messages" role="log" aria-live="polite" aria-label="Conversazione">
```

```html
<button id="sendButton" aria-label="Invia messaggio">Invia</button>
<button class="theme-toggle" aria-label="Cambia tema">...</button>
<button class="download-btn" aria-label="Scarica conversazione">...</button>
```

Gestire il focus dopo invio: riportare il focus sull'input dopo l'aggiunta del messaggio bot.

## 11. Riepilogo priorità interventi GUI

| # | Intervento | Impatto UX | Complessità |
|---|-----------|------------|-------------|
| 1 | Collapsing risposte lunghe (10.1) | Alto | Media |
| 2 | Aumentare font e contrasto (10.2) | Alto | Bassa |
| 3 | Card/separatori tra turni (10.3) | Medio | Bassa |
| 4 | Scroll to bottom + smooth (10.4) | Medio | Bassa |
| 5 | Suggerimenti sticky (10.6) | Medio | Media |
| 6 | Rendering token SSE (10.5) | Medio | Alta |
| 7 | Consolidare stili (10.7) | Basso (manutenibilità) | Bassa |
| 8 | Breakpoint tablet (10.8) | Basso | Bassa |
| 9 | Accessibilità (10.9) | Basso (compliance) | Bassa |

---

# Parte III — Procedure operative: Rollback e Conferma

## 12. Stato attuale dell'implementazione

### File nuovi creati (Parte I — Backend)

| File | Descrizione |
|------|-------------|
| `orchestrator/dialogue_state.py` | DialogueState TypedDict, serializzazione, conversione legacy |
| `orchestrator/dialogue_manager.py` | Decision engine rule-based con 7 regole |
| `orchestrator/tool_nodes.py` | 18 tool node functions + TOOL_REGISTRY + INTENT_TO_TOOL |
| `orchestrator/response_node.py` | Response generator node + prompt LLM |
| `orchestrator/two_phase.py` | Logica two-phase (sommario + dettagli) |

### File modificati

| File | Modifiche |
|------|-----------|
| `orchestrator/graph.py` | Riscritto da ~1661 a ~580 righe. Nuovo grafo con nodo dialogue_manager |
| `app/api.py` | 4 modifiche: passaggio/storage dialogue_state nella sessione |
| `gchat/statics/css/style.css` | Font 14px, card bot, separatori turno, breakpoint tablet, dark theme |
| `gchat/statics/css/new-formatting.css` | Contrasto migliorato, scroll-to-bottom, collapsible, suggestions bar |
| `gchat/statics/js/chat.js` | Smooth scroll, scroll-to-bottom button, collapsing liste, accessibilità |

### File NON modificati (preservati intatti)

`orchestrator/router.py`, `orchestrator/workflow_strategies.py`, `orchestrator/workflow_validator.py`, `orchestrator/fallback_recovery.py`, `orchestrator/intent_metadata.py`, `orchestrator/intent_cache.py`, `agents/response_agent.py`, tutti gli altri agenti e tool.

---

## 13. Scenario 1 — Rollback al sistema legacy

Se i test o l'uso in produzione evidenziano regressioni, seguire questa procedura per tornare al sistema precedente.

### 13.1 Rollback Backend

#### Passo 1: Ripristinare graph.py

Il file `graph.py` originale è disponibile nella cronologia git. Ripristinarlo:

```bash
cd /opt/lang-env/GiAs-llm
git checkout HEAD~1 -- orchestrator/graph.py
```

Se non è disponibile in git, il file originale (~1661 righe) aveva questa struttura:
- Classe `GIASGraph` con metodo `_build_graph()` che creava un grafo lineare `classify → tool → response → END`
- Tutti i tool node inline nella classe
- Response generator inline
- Two-phase inline

#### Passo 2: Ripristinare api.py

Rimuovere le 4 modifiche fatte ad `api.py`:

1. **Rimuovere** la riga che estrae `dialogue_state_from_session`:
   ```python
   # RIMUOVERE:
   dialogue_state_from_session = sender_session.get("dialogue_state") if session_valid else None
   ```

2. **Rimuovere** il parametro `dialogue_state=` dalla chiamata a `graph.run()`:
   ```python
   # PRIMA (nuovo):
   result = _conversation_graph.run(..., dialogue_state=dialogue_state_from_session)
   # DOPO (legacy):
   result = _conversation_graph.run(...)
   ```

3. **Rimuovere** `"dialogue_state": result.get("dialogue_state")` dalle 3 righe di salvataggio sessione (rami `has_more_details`, `confirm/decline`, `else`).

#### Passo 3: I nuovi file possono restare

I file `dialogue_state.py`, `dialogue_manager.py`, `tool_nodes.py`, `response_node.py`, `two_phase.py` non sono importati da nessun altro modulo se `graph.py` è il vecchio. Possono restare nella directory senza effetti (dead code) o essere rimossi per pulizia:

```bash
rm orchestrator/dialogue_state.py
rm orchestrator/dialogue_manager.py
rm orchestrator/tool_nodes.py
rm orchestrator/response_node.py
rm orchestrator/two_phase.py
```

#### Passo 4: Riavviare il backend

```bash
scripts/server.sh restart
```

### 13.2 Rollback Frontend

Le modifiche CSS e JS sono indipendenti dal backend e possono essere rollbackate separatamente o mantenute (sono miglioramenti puri di UX).

Per rollback completo:

```bash
cd /opt/lang-env/gchat
git checkout HEAD~1 -- statics/css/style.css statics/css/new-formatting.css statics/js/chat.js
./all.sh
```

### 13.3 Verifica rollback

```bash
# Backend health
curl http://localhost:5005/

# Test funzionale
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"rollback-test","message":"piani in ritardo","metadata":{"asl":"AVELLINO"}}'
```

---

## 14. Scenario 2 — Conferma nuovo sistema ed eliminazione legacy

Se il nuovo sistema funziona correttamente dopo test adeguati, procedere con la pulizia del codice legacy.

### 14.1 Prerequisiti

Prima di procedere, verificare:

- [ ] Backend avviato con il nuovo `graph.py` senza errori
- [ ] Almeno 5 intent diversi testati con risposta corretta
- [ ] Multi-turno testato: disambiguazione intent, slot mancanti, "oppure?", refinement
- [ ] Fallback recovery funzionante (messaggio non riconosciuto → menu categorie)
- [ ] Two-phase funzionante (risposta lunga → sommario → "vuoi dettagli?")
- [ ] Frontend: collapsing, scroll-to-bottom, card, separatori visibili e funzionanti
- [ ] Dark theme verificato

### 14.2 Eliminazione nodi workflow legacy da graph.py

Nel nuovo `graph.py` sono già stati rimossi i vecchi nodi workflow. Verificare che non ci siano riferimenti residui a:

- `present_strategies` (nodo)
- `handle_strategy_choice` (nodo)
- `collect_params` (nodo)
- `handle_oppure` (nodo)
- `refine_query` (nodo)
- `_present_strategies_node`, `_handle_strategy_choice_node`, ecc. (metodi)

```bash
cd /opt/lang-env/GiAs-llm
grep -rn "present_strategies\|handle_strategy_choice\|collect_params\|handle_oppure\|refine_query" orchestrator/graph.py
# Deve restituire 0 risultati
```

### 14.3 Rimuovere intent speciali dal Router

In `orchestrator/router.py`, rimuovere gli intent speciali usati solo dal vecchio workflow:

```python
# RIMUOVERE da VALID_INTENTS (se presenti):
"__present_strategies__"
"__choose_strategy__"
"__collect_params__"
"__oppure__"
"__refine__"
```

Verificare in `INTENT_PATTERNS` e nelle heuristic rules che non ci siano pattern per questi intent.

### 14.4 Rimuovere workflow_context legacy da api.py

Dopo aver verificato che `dialogue_state` funziona correttamente per almeno una settimana, rimuovere i campi legacy dalla sessione:

In `app/api.py`, nei punti dove si salva la sessione, rimuovere:
- `"last_intent"`
- `"last_slots"`
- `"conversation_summary"` (la stringa formattata legacy)
- `"workflow_context"` (l'intero dict legacy)

Mantenere solo `"dialogue_state"` e `"timestamp"`.

In `orchestrator/dialogue_state.py`, la funzione `from_session()` ha un ramo di conversione legacy. Dopo la rimozione completa, semplificarla rimuovendo il fallback ai campi vecchi.

### 14.5 Rimuovere file agenti non usati a runtime

Questi file contengono classi agente che non sono mai invocate dal grafo attuale (né vecchio né nuovo):

```bash
rm agents/data_agent.py
rm agents/risk_agent.py
rm agents/search_agent.py
rm agents/piano_agent.py
rm agents/priority_agent.py
```

**Attenzione**: prima di rimuovere, verificare con:

```bash
grep -rn "data_agent\|DataAgent" orchestrator/ app/ tools/ --include="*.py"
grep -rn "risk_agent\|RiskAgent" orchestrator/ app/ tools/ --include="*.py"
grep -rn "search_agent\|SearchAgent" orchestrator/ app/ tools/ --include="*.py"
grep -rn "piano_agent\|PianoAgent" orchestrator/ app/ tools/ --include="*.py"
grep -rn "priority_agent\|PriorityAgent" orchestrator/ app/ tools/ --include="*.py"
```

Se ci sono import, rimuoverli prima.

### 14.6 Pulizia CSS

In `gchat/statics/css/style.css`, rimuovere le regole sovrascritte da `new-formatting.css`:

- `.section-header` (versione con sfondo `#f7f7f7` e border-left marrone)
- `.list-item`, `.list-number` (se presenti, sovrascritti da `.list-item-compact`)
- `.field-label`, `.field-value` (versione vecchia, sovrascritti)

Verificare che la rimozione non alteri il rendering confrontando visivamente prima e dopo.

### 14.7 Consolidare l'accento colore

Scegliere uno schema colore unico:
- **Blu** (`#007acc` / `#005293`): attualmente usato in `new-formatting.css` per headers, numeri, link
- **Marrone** (`#d4a574`): residuo in `style.css` per alcuni bordi

Raccomandazione: mantenere **blu** come colore primario, rimuovere tutti i riferimenti a `#d4a574`.

### 14.8 Ordine operazioni consigliato

1. Verificare prerequisiti (14.1)
2. Rimuovere intent speciali dal Router (14.3) — basso rischio
3. Rimuovere file agenti non usati (14.5) — nessun impatto runtime
4. Pulizia CSS (14.6, 14.7) — impatto solo visivo, facilmente verificabile
5. Rimuovere workflow_context legacy da api.py (14.4) — **solo dopo 1 settimana di uso stabile**
6. Semplificare `from_session()` in dialogue_state.py — ultima operazione

Ad ogni passo, riavviare e verificare:

```bash
# Backend
scripts/server.sh restart && sleep 3 && curl http://localhost:5005/

# Frontend
cd /opt/lang-env/gchat && ./all.sh

# Test funzionale
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"cleanup-test","message":"stabilimenti a rischio alto","metadata":{"asl":"AVELLINO"}}'
```
