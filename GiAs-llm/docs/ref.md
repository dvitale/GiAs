# Piano di Refactoring: Workflow Conversazionale Multi-Turno per GiAs-llm

## 1. Obiettivo

Refactorizzare il workflow LangGraph per supportare conversazioni multi-turno articolate, permettendo al sistema di:
- Chiedere chiarimenti proattivamente quando la richiesta è ambigua
- Presentare opzioni alternative ("preferisci X o Y?")
- Supportare raffinamento progressivo dei risultati ("rifare la ricerca solo nel comune di...")
- Gestire richieste di alternative ("oppure?")
- Mantenere contesto conversazionale attraverso più turni

## 2. Scope del Refactoring

### Intent Conversazionali (6 intent)
Rendere multi-turno i seguenti intent che supportano filtri:

1. **ask_suggest_controls** - Suggerimenti controlli con strategie alternative
2. **ask_priority_establishment** - Stabilimenti prioritari (pianificazione vs rischio)
3. **ask_risk_based_priority** - Stabilimenti a rischio con filtri
4. **ask_delayed_plans** - Piani in ritardo con filtri
5. **ask_establishment_history** - Storico stabilimento
6. **search_piani_by_topic** - Ricerca piani con raffinamento

### Intent Single-Turn (13 intent)
Rimangono invariati come workflow lineare:
- greet, goodbye, ask_help
- ask_piano_description, ask_piano_stabilimenti, ask_piano_generic, ask_piano_statistics
- check_if_plan_delayed, ask_top_risk_activities, analyze_nc_by_category
- confirm_show_details, decline_show_details, fallback

## 3. Architettura Proposta

### 3.1 Estensione ConversationState

Aggiungere campi opzionali al TypedDict esistente (orchestrator/graph.py):

```python
class WorkflowStage(str, Enum):
    INITIAL = "initial"           # Classificazione intent iniziale
    CLARIFYING = "clarifying"     # Sistema chiede chiarimenti
    CHOOSING = "choosing"         # Utente sceglie tra opzioni
    COLLECTING = "collecting"     # Raccolta parametri progressiva
    EXECUTING = "executing"       # Esecuzione tool
    REFINING = "refining"         # Raffinamento query
    COMPLETED = "completed"       # Workflow completato

class ConversationState(TypedDict):
    # Campi esistenti (invariati)
    message: str
    metadata: Dict[str, Any]
    intent: str
    slots: Dict[str, Any]
    tool_output: Any
    final_response: str
    needs_clarification: bool
    error: str
    has_more_details: bool
    detail_context: Dict[str, Any]

    # NUOVI campi opzionali (default: None/empty)
    workflow_stage: Optional[WorkflowStage]           # Stato workflow corrente
    workflow_id: Optional[str]                        # ID workflow attivo
    workflow_type: Optional[str]                      # Tipo workflow (es: "suggest_controls")
    workflow_context: Optional[Dict[str, Any]]        # Contesto workflow specifico
    pending_question: Optional[Dict[str, Any]]        # Domanda in sospeso dal sistema
    available_options: Optional[List[Dict[str, Any]]] # Opzioni presentate
    workflow_history: Optional[List[Dict[str, Any]]]  # Storia scelte utente
    accumulated_filters: Optional[Dict[str, Any]]     # Filtri accumulati (raffinamento)
```

**Backward Compatibility**: Tutti i nuovi campi sono `Optional` con default `None` - gli intent single-turn non li useranno.

### 3.2 Workflow Strategies (Nuovo File)

Creare `orchestrator/workflow_strategies.py` con configurazione data-driven:

```python
WORKFLOW_STRATEGIES = {
    "suggest_controls": {
        "strategies": [
            {
                "id": "strategy_planning",
                "label": "dalla pianificazione",
                "description": "Analizza piani in ritardo della tua UOC",
                "intent_mapping": "ask_delayed_plans",
                "requires_params": ["limit"],
                "question": "vuoi che ti mostri i top 10 piani in maggior ritardo della tua struttura organizzativa?"
            },
            {
                "id": "strategy_risk_nc",
                "label": "dall'analisi del rischio - non conformità",
                "description": "Identifica attività statisticamente più rischiose basandosi su NC storiche",
                "intent_mapping": "ask_top_risk_activities",
                "requires_params": ["limit"]
            },
            {
                "id": "strategy_risk_mai_controllati",
                "label": "dall'analisi del rischio - mai controllati",
                "description": "Estrae stabilimenti mai controllati che esercitano attività a maggior rischio",
                "intent_mapping": "ask_risk_based_priority",
                "requires_params": ["limit"]
            }
        ],
        "initial_question": "preferisci partire dalla pianificazione o dall'analisi del rischio?",
        "supported_filters": ["comune", "asl", "tipo_attivita", "limit"]
    },

    "ask_priority_establishment": {
        "strategies": [
            {
                "id": "priority_delayed",
                "label": "piani in ritardo",
                "description": "Priorità basata su ritardi nella programmazione",
                "intent_mapping": "priority_tool",
                "requires_params": []
            },
            {
                "id": "priority_risk",
                "label": "rischio storico",
                "description": "Priorità basata su analisi rischio NC",
                "intent_mapping": "risk_tool",
                "requires_params": []
            }
        ],
        "initial_question": "vuoi basare la priorità sui ritardi o sul rischio storico?",
        "supported_filters": ["comune", "asl", "tipo_attivita", "limit"]
    },

    "ask_risk_based_priority": {
        "strategies": [],  # Intent diretto, solo raffinamento
        "supported_filters": ["comune", "asl", "tipo_attivita", "limit", "piano_code"]
    },

    "ask_delayed_plans": {
        "strategies": [],
        "supported_filters": ["asl", "uoc", "limit", "piano_code"]
    },

    "ask_establishment_history": {
        "strategies": [],
        "supported_filters": ["asl", "limit", "data_inizio", "data_fine"]
    },

    "search_piani_by_topic": {
        "strategies": [],
        "supported_filters": ["limit", "categoria"]
    }
}

# Filtri supportati con pattern regex per estrazione
FILTER_PATTERNS = {
    "comune": r"(?:nel\s+comune\s+(?:di\s+)?|a\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    "asl": r"(?:ASL\s+|asl\s+)([A-Z]{2}[0-9])",
    "limit": r"(?:primi?\s+|top\s+)?(\d+)",
    "tipo_attivita": {
        "macroarea": r"macroarea\s+([^\s,]+)",
        "aggregazione": r"aggregazione\s+([^\s,]+)",
        "attivita": r"attivit[àa]\s+([^\s,]+)"
    }
}
```

### 3.3 Router Potenziato (orchestrator/router.py)

Aggiungere metodi alla classe `Router` esistente:

```python
class Router:
    # Metodi esistenti invariati...

    def classify_with_context(
        self,
        message: str,
        metadata: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classificazione context-aware che considera workflow attivo.
        """
        # 1. Se workflow attivo, controlla se è risposta a pending_question
        if workflow_context and workflow_context.get("pending_question"):
            return self._classify_response_to_question(message, workflow_context)

        # 2. Controlla se è richiesta "oppure?" per alternative
        if workflow_context and self._is_oppure_request(message):
            return self._handle_oppure_request(workflow_context)

        # 3. Controlla se è raffinamento query
        if workflow_context and self._is_refinement_request(message):
            filters = self._extract_refinement_filters(message)
            return {
                "intent": "__refine__",  # Intent speciale
                "slots": filters,
                "needs_clarification": False,
                "is_refinement": True
            }

        # 4. Altrimenti usa classificazione standard
        return self.classify(message, metadata)

    def _classify_response_to_question(
        self,
        message: str,
        workflow_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classifica risposta a domanda del sistema.
        """
        pending = workflow_context.get("pending_question", {})
        question_type = pending.get("type")

        if question_type == "strategy_choice":
            # Estrai scelta utente tra le opzioni disponibili
            available_opts = workflow_context.get("available_options", [])
            choice = self._match_user_choice(message, available_opts)
            return {
                "intent": "__choose_strategy__",
                "slots": {"strategy_choice": choice},
                "needs_clarification": choice is None
            }

        elif question_type == "param_collection":
            # Estrai parametro richiesto
            param_name = pending.get("param_name")
            value = self._extract_param_value(message, param_name)
            return {
                "intent": "__provide_param__",
                "slots": {param_name: value},
                "needs_clarification": value is None
            }

        return {"intent": "fallback", "slots": {}, "needs_clarification": False}

    def _is_oppure_request(self, message: str) -> bool:
        """Riconosce richieste di alternative."""
        oppure_patterns = [
            r"^\s*oppure\s*\??$",
            r"^\s*alternative?\??$",
            r"^\s*altro\??$",
            r"^\s*cos[\'']?altro\??$"
        ]
        return any(re.match(p, message.lower()) for p in oppure_patterns)

    def _is_refinement_request(self, message: str) -> bool:
        """Riconosce richieste di raffinamento."""
        refinement_patterns = [
            r"rifare\s+(?:la\s+)?ricerca",
            r"rifai\s+(?:la\s+)?ricerca",
            r"stessa\s+ricerca",
            r"solo\s+(?:nel|in|per|con)",
            r"filtra\s+per",
            r"limita\s+a"
        ]
        return any(re.search(p, message.lower()) for p in refinement_patterns)

    def _extract_refinement_filters(self, message: str) -> Dict[str, Any]:
        """Estrae filtri da richiesta raffinamento."""
        from .workflow_strategies import FILTER_PATTERNS

        filters = {}
        for filter_name, pattern in FILTER_PATTERNS.items():
            if isinstance(pattern, dict):
                # Filtro composito (tipo_attivita)
                for subkey, subpattern in pattern.items():
                    match = re.search(subpattern, message, re.IGNORECASE)
                    if match:
                        if filter_name not in filters:
                            filters[filter_name] = {}
                        filters[filter_name][subkey] = match.group(1)
            else:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    filters[filter_name] = match.group(1)

        return filters
```

### 3.4 Nuovi Nodi Orchestration (orchestrator/graph.py)

Aggiungere 5 nuovi nodi al grafo per gestire workflow conversazionali:

```python
def _build_graph(self) -> StateGraph:
    workflow = StateGraph(ConversationState)

    # Nodi esistenti (invariati)
    workflow.add_node("classify", self._classify_node)
    workflow.add_node("greet_tool", self._greet_tool)
    # ... altri 17 nodi esistenti ...

    # NUOVI nodi orchestration
    workflow.add_node("present_strategies", self._present_strategies_node)
    workflow.add_node("handle_strategy_choice", self._handle_strategy_choice_node)
    workflow.add_node("collect_params", self._collect_params_node)
    workflow.add_node("handle_oppure", self._handle_oppure_node)
    workflow.add_node("refine_query", self._refine_query_node)

    # Routing potenziato
    workflow.add_conditional_edges(
        "classify",
        self._workflow_router,  # NUOVO router
        {
            "__present_strategies__": "present_strategies",
            "__choose_strategy__": "handle_strategy_choice",
            "__provide_param__": "collect_params",
            "__oppure__": "handle_oppure",
            "__refine__": "refine_query",
            # Existing routes...
            "greet": "greet_tool",
            "fallback": "fallback_tool",
            # ... altri 16 intent esistenti ...
        }
    )

    # Response generator per tutti i nodi
    workflow.add_edge("present_strategies", "response_generator")
    workflow.add_edge("handle_strategy_choice", "response_generator")
    workflow.add_edge("collect_params", "response_generator")
    workflow.add_edge("handle_oppure", "response_generator")
    workflow.add_edge("refine_query", "response_generator")

    workflow.set_entry_point("classify")
    return workflow.compile()

def _workflow_router(self, state: ConversationState) -> str:
    """
    Router workflow-aware che decide dove instradare basandosi su:
    - Intent classificato
    - Workflow attivo
    - Stage corrente
    """
    intent = state.get("intent", "fallback")
    workflow_stage = state.get("workflow_stage")
    workflow_type = state.get("workflow_type")

    # Intent speciali workflow
    if intent == "__present_strategies__":
        return "__present_strategies__"
    if intent == "__choose_strategy__":
        return "__choose_strategy__"
    if intent == "__provide_param__":
        return "__provide_param__"
    if intent == "__oppure__":
        return "__oppure__"
    if intent == "__refine__":
        return "__refine__"

    # Intent conversazionali: controlla se iniziare workflow
    if intent in CONVERSATIONAL_INTENTS and workflow_stage is None:
        # Controlla se richiesta è ambigua (necessita strategie)
        if self._needs_strategy_presentation(state):
            return "__present_strategies__"

    # Altrimenti routing standard per intent
    if state.get("needs_clarification"):
        return "fallback"
    return intent

def _needs_strategy_presentation(self, state: ConversationState) -> bool:
    """
    Determina se la richiesta è abbastanza ambigua da richiedere
    presentazione di strategie alternative.
    """
    intent = state.get("intent")
    message = state.get("message", "").lower()
    slots = state.get("slots", {})

    from .workflow_strategies import WORKFLOW_STRATEGIES
    strategy_config = WORKFLOW_STRATEGIES.get(intent, {})

    # Se non ha strategie multiple, non serve presentazione
    if not strategy_config.get("strategies"):
        return False

    # Pattern che indicano richiesta generica
    generic_patterns = [
        r"quali\s+controlli",
        r"indicazioni\s+su\s+controlli",
        r"cosa\s+devo\s+controllare",
        r"chi\s+devo\s+controllare",
        r"priorit[àa]",
        r"suggerimenti"
    ]

    is_generic = any(re.search(p, message) for p in generic_patterns)
    has_specific_slots = any(
        slot in slots for slot in ["piano_code", "comune", "asl", "num_registrazione"]
    )

    return is_generic and not has_specific_slots

def _present_strategies_node(self, state: ConversationState) -> ConversationState:
    """
    Presenta strategie alternative all'utente.
    """
    intent = state.get("intent")
    from .workflow_strategies import WORKFLOW_STRATEGIES

    strategy_config = WORKFLOW_STRATEGIES.get(intent, {})
    strategies = strategy_config.get("strategies", [])
    initial_question = strategy_config.get("initial_question", "")

    # Prepara opzioni per l'utente
    options = [
        {
            "id": s["id"],
            "label": s["label"],
            "description": s.get("description", "")
        }
        for s in strategies
    ]

    # Aggiorna state workflow
    state["workflow_stage"] = WorkflowStage.CHOOSING
    state["workflow_id"] = f"{intent}_{int(time.time())}"
    state["workflow_type"] = intent
    state["workflow_context"] = {
        "available_strategies": strategies,
        "current_strategy_index": 0
    }
    state["pending_question"] = {
        "type": "strategy_choice",
        "question": initial_question
    }
    state["available_options"] = options
    state["workflow_history"] = []

    # Costruisci risposta
    response_parts = [initial_question]
    for i, opt in enumerate(options, 1):
        response_parts.append(f"{i}. **{opt['label']}**: {opt['description']}")

    state["final_response"] = "\n".join(response_parts)

    return state

def _handle_strategy_choice_node(self, state: ConversationState) -> ConversationState:
    """
    Gestisce la scelta dell'utente tra strategie.
    """
    choice_id = state.get("slots", {}).get("strategy_choice")
    workflow_ctx = state.get("workflow_context", {})
    strategies = workflow_ctx.get("available_strategies", [])

    # Trova strategia scelta
    selected = next((s for s in strategies if s["id"] == choice_id), None)

    if not selected:
        state["needs_clarification"] = True
        state["final_response"] = "Non ho capito la tua scelta. Puoi ripetere?"
        return state

    # Aggiorna workflow history
    history = state.get("workflow_history", [])
    history.append({
        "action": "strategy_choice",
        "choice": choice_id,
        "timestamp": int(time.time())
    })
    state["workflow_history"] = history

    # Controlla se strategia richiede parametri
    required_params = selected.get("requires_params", [])

    if required_params:
        # Vai in COLLECTING stage
        state["workflow_stage"] = WorkflowStage.COLLECTING

        # Controlla quali parametri mancano
        slots = state.get("slots", {})
        missing_params = [p for p in required_params if p not in slots]

        if missing_params:
            # Chiedi primo parametro mancante
            param_name = missing_params[0]
            question = self._get_param_question(selected, param_name)

            state["pending_question"] = {
                "type": "param_collection",
                "param_name": param_name,
                "question": question
            }
            state["final_response"] = question
            return state

    # Tutti i parametri presenti: esegui tool
    state["workflow_stage"] = WorkflowStage.EXECUTING
    state["intent"] = selected["intent_mapping"]

    # Esegui tool corrispondente
    tool_output = self._execute_strategy_tool(selected, state)
    state["tool_output"] = tool_output

    return state

def _collect_params_node(self, state: ConversationState) -> ConversationState:
    """
    Raccoglie parametri progressivamente dall'utente.
    """
    workflow_ctx = state.get("workflow_context", {})
    selected = workflow_ctx.get("selected_strategy")

    required_params = selected.get("requires_params", [])
    slots = state.get("slots", {})

    # Controlla parametri ancora mancanti
    missing_params = [p for p in required_params if p not in slots]

    if missing_params:
        # Chiedi prossimo parametro
        param_name = missing_params[0]
        question = self._get_param_question(selected, param_name)

        state["pending_question"] = {
            "type": "param_collection",
            "param_name": param_name,
            "question": question
        }
        state["final_response"] = question
        return state

    # Tutti parametri raccolti: esegui
    state["workflow_stage"] = WorkflowStage.EXECUTING
    state["intent"] = selected["intent_mapping"]

    tool_output = self._execute_strategy_tool(selected, state)
    state["tool_output"] = tool_output

    return state

def _handle_oppure_node(self, state: ConversationState) -> ConversationState:
    """
    Gestisce richiesta 'oppure?' per mostrare strategia successiva.
    """
    workflow_ctx = state.get("workflow_context", {})
    strategies = workflow_ctx.get("available_strategies", [])
    current_idx = workflow_ctx.get("current_strategy_index", 0)

    # Passa alla prossima strategia
    next_idx = (current_idx + 1) % len(strategies)
    next_strategy = strategies[next_idx]

    workflow_ctx["current_strategy_index"] = next_idx
    state["workflow_context"] = workflow_ctx

    # Presenta prossima strategia
    state["final_response"] = (
        f"**Alternativa**: {next_strategy['label']}\n\n"
        f"{next_strategy['description']}\n\n"
        f"Vuoi procedere con questa strategia?"
    )

    state["pending_question"] = {
        "type": "oppure_confirmation",
        "strategy": next_strategy
    }

    return state

def _refine_query_node(self, state: ConversationState) -> ConversationState:
    """
    Applica filtri di raffinamento alla query precedente.
    """
    workflow_ctx = state.get("workflow_context", {})
    previous_query = workflow_ctx.get("last_query", {})

    # Merge filtri esistenti con nuovi
    existing_filters = state.get("accumulated_filters", {})
    new_filters = state.get("slots", {})
    merged_filters = {**existing_filters, **new_filters}

    state["accumulated_filters"] = merged_filters
    state["workflow_stage"] = WorkflowStage.REFINING

    # Ri-esegui tool con filtri aggiuntivi
    intent = previous_query.get("intent")
    slots = {**previous_query.get("slots", {}), **merged_filters}

    state["intent"] = intent
    state["slots"] = slots

    # Esegui tool
    tool_node_name = f"{intent}_tool"
    tool_method = getattr(self, f"_{tool_node_name}", None)

    if tool_method:
        tool_output = tool_method(state)
        state["tool_output"] = tool_output.get("tool_output")

    # Salva query per futuri raffinamenti
    workflow_ctx["last_query"] = {
        "intent": intent,
        "slots": slots
    }
    state["workflow_context"] = workflow_ctx

    return state

def _get_param_question(self, strategy: Dict, param_name: str) -> str:
    """Genera domanda per raccogliere parametro specifico."""
    questions = {
        "limit": strategy.get("question", "quanti risultati vuoi vedere?"),
        "comune": "in quale comune vuoi cercare?",
        "asl": "per quale ASL?",
        "piano_code": "per quale piano?"
    }
    return questions.get(param_name, f"specifica il valore per {param_name}")

def _execute_strategy_tool(
    self,
    strategy: Dict,
    state: ConversationState
) -> Dict[str, Any]:
    """Esegue il tool corrispondente alla strategia."""
    intent_mapping = strategy.get("intent_mapping")

    # Map intent to tool
    tool_map = {
        "ask_delayed_plans": self._delayed_plans_tool,
        "ask_top_risk_activities": self._top_risk_activities_tool,
        "ask_risk_based_priority": self._risk_predictor_tool,
    }

    tool_method = tool_map.get(intent_mapping)
    if tool_method:
        result_state = tool_method(state)
        return result_state.get("tool_output")

    return {"error": "Tool not found"}
```

### 3.5 Gestione Sessione Potenziata (app/api.py)

Estendere il session store per includere workflow context:

```python
# Dopo ogni risposta, salva workflow context in sessione
if result.get("workflow_id"):
    _session_store[message.sender] = {
        "detail_context": result.get("detail_context", {}),
        "workflow_context": {
            "workflow_id": result.get("workflow_id"),
            "workflow_type": result.get("workflow_type"),
            "workflow_stage": result.get("workflow_stage"),
            "pending_question": result.get("pending_question"),
            "available_options": result.get("available_options"),
            "workflow_history": result.get("workflow_history"),
            "accumulated_filters": result.get("accumulated_filters"),
        },
        "timestamp": time.time(),
        "last_intent": result.get("intent"),
        "last_slots": result.get("slots", {}),
    }

# Prima di ogni richiesta, recupera workflow context
sender_session = _session_store.get(message.sender, {})
workflow_context = sender_session.get("workflow_context")

# Passa workflow_context a ConversationGraph.run()
result = _conversation_graph.run(
    message=message.message,
    metadata=enhanced_metadata,
    detail_context=detail_context,
    workflow_context=workflow_context  # NUOVO parametro
)
```

Modificare firma `ConversationGraph.run()`:

```python
def run(
    self,
    message: str,
    metadata: Dict[str, Any] = None,
    detail_context: Dict[str, Any] = None,
    workflow_context: Dict[str, Any] = None,  # NUOVO
    event_callback = None
) -> Dict[str, Any]:
    """Execute conversation graph with workflow context."""
    state = {
        "message": message,
        "metadata": metadata or {},
        "intent": "",
        "slots": {},
        "tool_output": None,
        "final_response": "",
        "needs_clarification": False,
        "error": "",
        "has_more_details": False,
        "detail_context": detail_context or {},
        # Workflow fields
        "workflow_stage": workflow_context.get("workflow_stage") if workflow_context else None,
        "workflow_id": workflow_context.get("workflow_id") if workflow_context else None,
        "workflow_type": workflow_context.get("workflow_type") if workflow_context else None,
        "workflow_context": workflow_context or {},
        "pending_question": workflow_context.get("pending_question") if workflow_context else None,
        "available_options": workflow_context.get("available_options") if workflow_context else None,
        "workflow_history": workflow_context.get("workflow_history") if workflow_context else [],
        "accumulated_filters": workflow_context.get("accumulated_filters") if workflow_context else {},
    }

    # Usa Router.classify_with_context invece di classify
    # (resto della logica invariato)
```

## 4. Esempi di Flow Conversazionali

### Esempio 1: suggest_controls con scelta strategia

```
Turno 1:
U: "vorrei avere indicazioni su quali controlli eseguire"
→ classify: intent=ask_suggest_controls, workflow_stage=None
→ _needs_strategy_presentation() → True (richiesta generica)
→ present_strategies_node:
   - workflow_stage = CHOOSING
   - pending_question = {type: "strategy_choice"}
S: "preferisci partire dalla pianificazione o dall'analisi del rischio?
   1. **dalla pianificazione**: Analizza piani in ritardo della tua UOC
   2. **dall'analisi del rischio - non conformità**: Identifica attività statisticamente più rischiose
   3. **dall'analisi del rischio - mai controllati**: Estrae stabilimenti mai controllati ad alto rischio"

Turno 2:
U: "dalla pianificazione"
→ classify_with_context: _classify_response_to_question()
   → intent=__choose_strategy__, slots={strategy_choice: "strategy_planning"}
→ handle_strategy_choice_node:
   - selected strategy: intent_mapping=ask_delayed_plans, requires_params=["limit"]
   - pending_question = {type: "param_collection", param_name: "limit"}
S: "vuoi che ti mostri i top 10 piani in maggior ritardo della tua struttura organizzativa?"

Turno 3:
U: "mostrami i primi 20 piani in maggior ritardo"
→ classify_with_context: _classify_response_to_question()
   → intent=__provide_param__, slots={limit: 20}
→ collect_params_node:
   - All params collected
   - workflow_stage = EXECUTING
   - Execute: delayed_plans_tool(limit=20)
S: "📋 Piani in ritardo (Top 20):
   1. Piano A1 - Ritardo: 45 controlli...
   ..."
```

### Esempio 2: Raffinamento progressivo con "oppure?"

```
Turno 1:
U: "vorrei avere indicazioni su quali controlli eseguire"
S: [presenta 3 strategie]

Turno 2:
U: "dal rischio"
S: "posso partire dalle non conformità rilevate negli ultimi anni e mostrarti le attività statisticamente più rischiose. Vuoi procedere?"

Turno 3:
U: "oppure?"
→ _is_oppure_request() → True
→ handle_oppure_node:
   - current_strategy_index: 1 → 2
   - next_strategy: strategy_risk_mai_controllati
S: "**Alternativa**: dall'analisi del rischio - mai controllati

   Posso estrarre dall'elenco degli stabilimenti mai controllati quelli che esercitano le stesse attività considerate a maggior rischio. Vuoi procedere?"

Turno 4:
U: "ok, mostrami i primi 100"
→ classify_with_context: risposta positiva + limite
   → intent=__provide_param__, slots={limit: 100}
→ Execute: risk_predictor_tool(limit=100)
S: "📊 Stabilimenti mai controllati ad alto rischio (100):
   1. IT 2287 M - Comune: Napoli - Rischio: 78.5
   ..."

Turno 5:
U: "puoi rifare la ricerca individuando i primi 100 solo nel comune di Napoli?"
→ _is_refinement_request() → True
→ _extract_refinement_filters() → {comune: "Napoli", limit: 100}
→ refine_query_node:
   - accumulated_filters = {comune: "Napoli", limit: 100}
   - Re-execute: risk_predictor_tool(limit=100, comune="Napoli")
S: "📊 Stabilimenti mai controllati ad alto rischio nel comune di Napoli (100):
   1. IT 2287 M - Comune: Napoli - Rischio: 78.5
   ..."
```

## 5. File da Modificare

### 5.1 File Nuovi

1. **orchestrator/workflow_strategies.py** (nuovo)
   - Configurazione data-driven workflow
   - Pattern filtri
   - ~300 righe

### 5.2 File da Modificare

1. **orchestrator/graph.py**
   - Estendere `ConversationState` (linee 33-43)
   - Aggiungere 5 nuovi nodi (linee 82-100)
   - Modificare `_build_graph()` per routing workflow (linea 82)
   - Aggiungere `_workflow_router()` (nuovo metodo)
   - Implementare 5 nuovi nodi (5 metodi ~400 righe totali)
   - Modificare `run()` per accettare `workflow_context` (linea 391)
   - ~500 righe aggiunte

2. **orchestrator/router.py**
   - Aggiungere `classify_with_context()` (nuovo metodo ~50 righe)
   - Aggiungere metodi helper:
     - `_classify_response_to_question()` (~60 righe)
     - `_is_oppure_request()` (~10 righe)
     - `_is_refinement_request()` (~10 righe)
     - `_extract_refinement_filters()` (~30 righe)
     - `_match_user_choice()` (~40 righe)
     - `_extract_param_value()` (~30 righe)
   - ~230 righe aggiunte

3. **app/api.py**
   - Estendere `_session_store` structure (linee 36-41)
   - Modificare session save logic (linee 312-320)
   - Modificare session load logic (linee 284-303)
   - Passare `workflow_context` a `ConversationGraph.run()` (linea 306)
   - ~50 righe modificate

### 5.3 File Invariati

- `tools/*.py` - Tutti i tool rimangono invariati
- `agents/data_agent.py` - Logica dati invariata
- `agents/response_agent.py` - Formattazione invariata
- `llm/client.py` - LLM client invariato
- Frontend `gchat/` - Zero modifiche necessarie

## 6. Backward Compatibility

### 6.1 Zero Breaking Changes

**Intent single-turn (13 intent)**:
- Non usano campi workflow
- Comportamento identico a prima
- Nessuna modifica necessaria

**API endpoints**:
- `/webhooks/rest/webhook` - formato response invariato
- `/webhooks/rest/webhook/stream` - SSE format invariato
- Tutti i campi nuovi in response sono opzionali

**Session store**:
- Struttura estesa con backward compatibility
- Sessioni esistenti continuano a funzionare
- Campi workflow solo se workflow attivo

**ConversationState**:
- Tutti i campi nuovi sono `Optional`
- Default values: `None` o `{}`
- TypedDict con `total=False` per nuovi campi

### 6.2 Feature Flag (Opzionale)

Per rollout graduale, aggiungere flag in `config.json`:

```json
{
  "conversational_intents": {
    "enabled": true,
    "intents": [
      "ask_suggest_controls",
      "ask_priority_establishment",
      "ask_risk_based_priority",
      "ask_delayed_plans",
      "ask_establishment_history",
      "search_piani_by_topic"
    ]
  }
}
```

Se `enabled=false`, tutti gli intent funzionano come single-turn.

## 7. Strategie di Test

### 7.1 Test Unitari (tests/)

1. **test_workflow_strategies.py** (nuovo)
   - Test configurazione workflow
   - Validazione strategie
   - Test pattern filtri

2. **test_router_workflow.py** (nuovo)
   - Test `classify_with_context()`
   - Test riconoscimento "oppure"
   - Test estrazione filtri raffinamento
   - Test classificazione risposte

3. **test_graph_workflow.py** (nuovo)
   - Test nodi orchestration
   - Test flow multi-turno completo
   - Test session persistence

### 7.2 Test Integrazione

1. **Dialogo completo suggest_controls**
   - Presentazione strategie
   - Scelta utente
   - Raccolta parametri
   - Esecuzione tool
   - Raffinamento

2. **Dialogo con "oppure?"**
   - Navigazione tra strategie
   - Conferma scelta

3. **Raffinamento progressivo**
   - Query iniziale
   - Applicazione filtri multipli
   - Accumulated filters

### 7.3 Test Backward Compatibility

1. Test tutti i 13 intent single-turn
2. Test two-phase system esistente
3. Test API response format
4. Test gchat integration

## 8. Metriche di Successo

### 8.1 Funzionali

- ✅ Workflow completion rate: >80% per i 6 intent conversazionali
- ✅ Intent conversazionali supportano almeno 3 strategie alternative
- ✅ Raffinamento supporta tutti i 4 filtri configurati (comune, ASL, tipo_attività, limit)
- ✅ Riconoscimento "oppure?" accuracy: >90%
- ✅ Backward compatibility: 100% test esistenti passano

### 8.2 Performance

- ✅ Latency P95: <200ms overhead per turno conversazionale
- ✅ Session TTL: 5 minuti (invariato)
- ✅ Memory overhead: <50MB per 100 sessioni attive
- ✅ No degradazione performance intent single-turn

### 8.3 User Experience

- ✅ Average turni per workflow: 2-4
- ✅ Clarification success rate: >85%
- ✅ Refinement usage: >10% delle query conversazionali
- ✅ Fallback rate: <5% per workflow attivi

## 9. Piano di Implementazione

### Fase 1: Foundation (Week 1-2)
- [ ] Creare `workflow_strategies.py` con configurazione
- [ ] Estendere `ConversationState` con campi workflow
- [ ] Implementare `FILTER_PATTERNS` e helper estrazione
- [ ] Test unitari per workflow_strategies

### Fase 2: Router Enhancement (Week 2-3)
- [ ] Implementare `classify_with_context()`
- [ ] Aggiungere metodi helper Router:
  - `_classify_response_to_question()`
  - `_is_oppure_request()`
  - `_is_refinement_request()`
  - `_extract_refinement_filters()`
- [ ] Test unitari per Router potenziato

### Fase 3: Workflow Nodes (Week 3-4)
- [ ] Implementare `present_strategies_node`
- [ ] Implementare `handle_strategy_choice_node`
- [ ] Implementare `collect_params_node`
- [ ] Implementare `handle_oppure_node`
- [ ] Implementare `refine_query_node`
- [ ] Aggiungere `_workflow_router()`
- [ ] Test unitari per ogni nodo

### Fase 4: Graph Integration (Week 4-5)
- [ ] Modificare `_build_graph()` per includere nuovi nodi
- [ ] Aggiungere conditional edges per workflow routing
- [ ] Modificare `run()` per accettare `workflow_context`
- [ ] Test integrazione grafo completo

### Fase 5: Session Management (Week 5-6)
- [ ] Estendere `_session_store` structure in api.py
- [ ] Modificare session save/load logic
- [ ] Implementare workflow context persistence
- [ ] Test session TTL e cleanup

### Fase 6: Testing Completo (Week 6-7)
- [ ] Test dialoghi completi (3 scenari principali)
- [ ] Test backward compatibility (tutti i 13 intent single-turn)
- [ ] Test performance (latency, memory)
- [ ] Test gchat integration

### Fase 7: Documentation & Deployment (Week 7-8)
- [ ] Aggiornare docs/INTENT_OPERATIONS.md
- [ ] Aggiornare docs/CLAUDE.md
- [ ] Creare guida workflow strategies
- [ ] Deploy su staging environment
- [ ] User acceptance testing

### Fase 8: Rollout (Week 8)
- [ ] Feature flag enabled per 10% utenti
- [ ] Monitoring metriche
- [ ] Gradual rollout a 50%, poi 100%
- [ ] Post-deployment monitoring

## 10. Rischi e Mitigazioni

### Rischio 1: Complessità Workflow
**Mitigazione**: Workflow strategies come configurazione data-driven, facile da debuggare e modificare senza toccare codice.

### Rischio 2: Session Bloat
**Mitigazione**: TTL 5 minuti invariato, garbage collection automatico, workflow_context limitato a dati essenziali.

### Rischio 3: User Confusion
**Mitigazione**: Domande chiare con opzioni numerate, sempre permettere fallback a single-turn con query diretta.

### Rischio 4: Performance Degradation
**Mitigazione**: Intent single-turn non toccati, workflow router lightweight, caching Router invariato.

### Rischio 5: Backward Compatibility Break
**Mitigazione**: Feature flag, tutti i campi nuovi opzionali, test completi su intent esistenti, zero modifiche a gchat.

## 11. File Critici da Verificare Post-Implementazione

1. **orchestrator/graph.py:33-43** - ConversationState esteso
2. **orchestrator/graph.py:82-150** - _build_graph() con nuovi nodi
3. **orchestrator/router.py:730+** - Metodi workflow-aware
4. **orchestrator/workflow_strategies.py** - Configurazione completa
5. **app/api.py:284-320** - Session management esteso
6. **tests/test_graph_workflow.py** - Test copertura workflow

## 12. Checklist Finale Pre-Deployment

- [ ] Tutti i test unitari passano (pytest tests/)
- [ ] Test integrazione completi (3 dialoghi principali)
- [ ] Performance benchmark (latency <200ms overhead)
- [ ] Backward compatibility verificata (100% test esistenti)
- [ ] gchat integration testata
- [ ] Documentation aggiornata
- [ ] Logs strutturati per debugging workflow
- [ ] Monitoring dashboard configurato
- [ ] Rollback plan documentato
- [ ] User acceptance testing completato

---

## Note Finali

Questo refactoring introduce un sistema di workflow conversazionali **pragmatico e incrementale**:
- **Scope limitato**: Solo 6 intent conversazionali, 13 intent rimangono single-turn
- **Zero breaking changes**: Tutti i campi nuovi opzionali, backward compatibility garantita
- **Data-driven**: Workflow strategies configurabili senza modifiche codice
- **Performance-aware**: Intent single-turn non impattati, overhead minimo per workflow
- **User-friendly**: Domande chiare, opzioni numerate, sempre possibile fallback a query diretta

Il sistema supporta tutti i dialoghi target richiesti mantenendo semplicità e affidabilità del sistema esistente.
