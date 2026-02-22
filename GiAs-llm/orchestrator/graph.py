"""
Grafo LangGraph per conversazione multi-turno con Dialogue Manager.

Architettura:
    classify → dialogue_manager → execute_tool → response_generator → END
                     │
                     └─→ ask_user → END (attende prossimo turno)

Il dialogue_manager decide se l'informazione è sufficiente per eseguire
un tool, oppure se chiedere disambiguazione/slot all'utente.
"""

from typing import TypedDict, Any, Dict, Literal, Optional, List
from langgraph.graph import StateGraph, END
import re
import time
import logging

try:
    from .router import Router
    from llm.client import LLMClient
    from .tool_nodes import TOOL_REGISTRY, INTENT_TO_TOOL
    from .response_node import response_generator_node
    from .two_phase import TWO_PHASE_THRESHOLDS, TWO_PHASE_SUFFIX, apply_two_phase_check
    from .dialogue_state import (
        DialogueState as DState, create_empty_state, from_session, to_session,
        merge_slots, is_state_valid,
    )
    from .dialogue_manager import evaluate as dm_evaluate, DialogueManagerResult
    from .workflow_validator import WorkflowStage
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from orchestrator.router import Router
    from llm.client import LLMClient
    from orchestrator.tool_nodes import TOOL_REGISTRY, INTENT_TO_TOOL
    from orchestrator.response_node import response_generator_node
    from orchestrator.two_phase import TWO_PHASE_THRESHOLDS, TWO_PHASE_SUFFIX, apply_two_phase_check
    from orchestrator.dialogue_state import (
        DialogueState as DState, create_empty_state, from_session, to_session,
        merge_slots, is_state_valid,
    )
    from orchestrator.dialogue_manager import evaluate as dm_evaluate, DialogueManagerResult
    from orchestrator.workflow_validator import WorkflowStage

logger = logging.getLogger(__name__)


class ConversationState(TypedDict, total=False):
    # Campi core
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

    # Classification confidence (P2)
    _classification_confidence: Optional[float]  # 0.0-1.0, dalla classificazione
    _intent_candidates: Optional[List[Dict[str, Any]]]  # candidati intent dal router

    # Dialogue State Tracking (nuovo)
    dialogue_state: Optional[Dict[str, Any]]
    dm_action: Optional[str]         # "execute", "ask_user", "fallback"
    dm_target_tool: Optional[str]    # nome nodo tool da eseguire
    dm_question: Optional[str]       # domanda per l'utente
    response_context: Optional[str]  # contesto risposta per risoluzione anaforica

    # Campi workflow legacy (mantenuti per backwards compatibility)
    workflow_stage: Optional[str]
    workflow_id: Optional[str]
    workflow_nonce: Optional[str]
    workflow_type: Optional[str]
    workflow_context: Optional[Dict[str, Any]]
    pending_question: Optional[Dict[str, Any]]
    available_options: Optional[List[Dict[str, Any]]]
    workflow_history: Optional[List[Dict[str, Any]]]
    accumulated_filters: Optional[Dict[str, Any]]

    # Suggestions per follow-up (dal response_node)
    suggestions: Optional[List[Dict[str, Any]]]

    # Fallback recovery (mantenuti)
    fallback_suggestions: Optional[List[Dict[str, Any]]]
    fallback_phase: Optional[int]
    fallback_count: Optional[int]
    fallback_selected_category: Optional[str]

    # Execution tracking per debug visualizer
    execution_path: Optional[List[str]]          # Sequenza nodi visitati
    node_timings: Optional[Dict[str, float]]     # {node_name: duration_ms}
    execution_start_ms: Optional[float]          # Timestamp inizio esecuzione


class ConversationGraph:
    # Re-export per backwards compat
    TWO_PHASE_THRESHOLDS = TWO_PHASE_THRESHOLDS
    TWO_PHASE_SUFFIX = TWO_PHASE_SUFFIX

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.router = Router(self.llm_client)
        self.graph = self._build_graph()
        self._event_callback = None
        self._fallback_engine = None

    @staticmethod
    def _apply_two_phase_check(state, intent, result, item_count, summary_text):
        """Backwards compat wrapper."""
        return apply_two_phase_check(state, intent, result, item_count, summary_text)

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ConversationState)

        # =====================================================================
        # Nodi principali del nuovo workflow
        # =====================================================================
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("dialogue_manager", self._dialogue_manager_node)
        workflow.add_node("ask_user", self._ask_user_node)
        workflow.add_node("fallback_tool", self._fallback_tool)
        workflow.add_node("response_generator", self._response_generator_node)

        # Tool nodes (registrati da tool_nodes.py)
        for name, func in TOOL_REGISTRY.items():
            # Wrappa per iniettare event_callback
            workflow.add_node(name, self._make_tool_wrapper(name, func))

        # =====================================================================
        # Edges
        # =====================================================================

        # Entry point
        workflow.set_entry_point("classify")

        # classify → dialogue_manager (sempre)
        workflow.add_edge("classify", "dialogue_manager")

        # dialogue_manager → conditional: ask_user, fallback_tool, o tool
        dm_routes = {
            "ask_user": "ask_user",
            "fallback": "fallback_tool",
        }
        for tool_name in TOOL_REGISTRY:
            dm_routes[tool_name] = tool_name

        workflow.add_conditional_edges(
            "dialogue_manager",
            self._dm_router,
            dm_routes,
        )

        # ask_user → END (risposta all'utente, attende prossimo turno)
        workflow.add_edge("ask_user", END)

        # fallback_tool → response_generator
        workflow.add_edge("fallback_tool", "response_generator")

        # Tutti i tool → response_generator
        for tool_name in TOOL_REGISTRY:
            workflow.add_edge(tool_name, "response_generator")

        # response_generator → END
        workflow.add_edge("response_generator", END)

        return workflow.compile()

    def _make_tool_wrapper(self, name, func):
        """Crea wrapper per tool node che inietta event_callback e traccia timing."""
        def wrapper(state):
            node_start = time.perf_counter()
            result = func(state, event_callback=self._event_callback)
            node_duration_ms = (time.perf_counter() - node_start) * 1000

            # Aggiorna execution tracking
            if result.get("execution_path") is not None:
                result["execution_path"].append(name)
            if result.get("node_timings") is not None:
                result["node_timings"][name] = round(node_duration_ms, 2)

            # Emit timing event per SSE
            if self._event_callback:
                self._event_callback({
                    "type": "node_timing",
                    "node": name,
                    "duration_ms": round(node_duration_ms, 2)
                })

            return result
        return wrapper

    # =========================================================================
    # CLASSIFY NODE
    # =========================================================================

    def _classify_node(self, state: ConversationState) -> ConversationState:
        """
        Nodo classificazione: Router ibrido 4 livelli.

        Produce intent_candidates (lista) per il dialogue_manager.
        Mantiene compatibilità con il router attuale (singolo intent) e
        lo espande ad output multi-candidato.
        """
        node_start = time.perf_counter()

        if self._event_callback:
            self._event_callback({
                "type": "status",
                "node": "router",
                "message": "Analizzando la richiesta..."
            })

        message = state.get("message", "")

        # Gestione selezione da menu disambiguazione intent
        ds_raw = state.get("dialogue_state")
        intent_candidates = ds_raw.get("intent_candidates") if ds_raw else None
        if intent_candidates and len(message.strip()) <= 3:
            try:
                choice = int(message.strip())
                if 1 <= choice <= len(intent_candidates):
                    selected = intent_candidates[choice - 1]
                    state["intent"] = selected["intent"]
                    state["slots"] = selected.get("slots", {})
                    state["needs_clarification"] = False
                    state["_classification_confidence"] = selected.get("confidence", 0.85)
                    state["_intent_candidates"] = [selected]
                    state["error"] = ""
                    # Clear intent_candidates dal dialogue_state
                    ds_raw["intent_candidates"] = None
                    state["dialogue_state"] = ds_raw
                    logger.info(f"[Classify] Disambiguazione: utente ha scelto {selected['intent']}")

                    # Tracking execution
                    node_duration_ms = (time.perf_counter() - node_start) * 1000
                    if state.get("execution_path") is not None:
                        state["execution_path"].append("classify")
                    if state.get("node_timings") is not None:
                        state["node_timings"]["classify"] = round(node_duration_ms, 2)
                    return state
            except ValueError:
                pass  # Non è un numero, prosegui con classificazione normale

        # Gestione selezione da fallback suggestions (legacy)
        if state.get("fallback_suggestions"):
            print(f"[DEBUG] Found {len(state['fallback_suggestions'])} fallback_suggestions, trying to parse: '{state['message']}'")
            selected = self._parse_user_selection(
                state["message"],
                state["fallback_suggestions"]
            )
            if selected:
                print(f"[DEBUG] Selection parsed successfully: type={selected.get('type')}, label={selected.get('label','?')}")
                if selected.get("type") == "intent":
                    state["intent"] = selected["intent"]
                    state["slots"] = {}
                    state["needs_clarification"] = bool(selected.get("requires_slots"))
                    state["error"] = ""
                    state["fallback_suggestions"] = None
                    state["fallback_count"] = 0
                    state["fallback_phase"] = 1
                    state["fallback_selected_category"] = None
                    return state
                elif selected.get("type") == "category":
                    state["fallback_selected_category"] = selected.get("category")
                    state["fallback_phase"] = 3
                    state["intent"] = "fallback"
                    state["slots"] = {}
                    state["needs_clarification"] = False
                    state["error"] = ""
                    return state

        # Classificazione standard
        metadata = state.get("metadata", {})
        workflow_context = state.get("workflow_context")

        # Passa dialogue_state al router per context-aware classification
        # (es. skip gibberish detection quando c'è un confirmed_intent con missing_slots)
        ds_for_router = state.get("dialogue_state")
        print(f"[Graph DEBUG] classify_node: ds_for_router={ds_for_router is not None}, confirmed_intent={ds_for_router.get('confirmed_intent') if ds_for_router else None}, missing_slots={ds_for_router.get('missing_slots') if ds_for_router else None}")
        if ds_for_router:
            metadata = {**metadata, "_dialogue_state": ds_for_router}

        if workflow_context:
            classification = self.router.classify_with_context(
                state["message"], metadata, workflow_context
            )
        else:
            classification = self.router.classify(
                state["message"], metadata
            )

        state["intent"] = classification.get("intent", "fallback")
        state["slots"] = classification.get("slots", {})
        state["needs_clarification"] = classification.get("needs_clarification", False)
        state["error"] = classification.get("error", "")
        # P2: Salva confidence reale dal router (heuristic o LLM)
        state["_classification_confidence"] = classification.get("confidence", 0.70)

        # Salva candidati per il dialogue_manager (multi-intent dal router)
        state["_intent_candidates"] = classification.get("_candidates", [
            {"intent": state["intent"], "confidence": state.get("_classification_confidence", 0.70), "slots": state.get("slots", {})}
        ])

        if self._event_callback and state["intent"]:
            self._event_callback({
                "type": "reasoning",
                "node": "router",
                "message": f"Intent rilevato: {state['intent']}"
            })

        # Slot carry-forward da sessione precedente (solo se stesso intent)
        if state["needs_clarification"]:
            session_last_intent = metadata.get("_session_last_intent")
            session_last_slots = metadata.get("_session_last_slots", {})
            # Carry-forward solo se l'intent corrente è lo stesso della sessione
            # (evita "memory bleed" quando l'utente cambia topic)
            if session_last_slots and session_last_intent == state["intent"]:
                merged = {**session_last_slots, **state["slots"]}
                state["slots"] = merged
                re_result = self.router._post_validate({
                    "intent": state["intent"],
                    "slots": merged,
                    "needs_clarification": state["needs_clarification"]
                })
                state["needs_clarification"] = re_result.get("needs_clarification", True)
                state["slots"] = re_result.get("slots", merged)

        # Tracking execution
        node_duration_ms = (time.perf_counter() - node_start) * 1000
        if state.get("execution_path") is not None:
            state["execution_path"].append("classify")
        if state.get("node_timings") is not None:
            state["node_timings"]["classify"] = round(node_duration_ms, 2)
        if self._event_callback:
            self._event_callback({
                "type": "node_timing",
                "node": "classify",
                "duration_ms": round(node_duration_ms, 2),
                "intent": state.get("intent", "unknown")
            })

        return state

    # =========================================================================
    # DIALOGUE MANAGER NODE
    # =========================================================================

    def _dialogue_manager_node(self, state: ConversationState) -> ConversationState:
        """
        Nodo Dialogue Manager: decide se eseguire, chiedere, o fallback.

        Usa il DialogueState accumulato + output del classify per decidere.
        """
        node_start = time.perf_counter()
        intent = state.get("intent", "fallback")
        slots = state.get("slots", {})
        message = state.get("message", "")
        needs_clarification = state.get("needs_clarification", False)

        # Carica o crea DialogueState
        ds_raw = state.get("dialogue_state")
        if ds_raw and is_state_valid(ds_raw):
            ds = ds_raw
        else:
            ds = create_empty_state()

        # Topic change detection: se l'intent corrente è diverso da quello confermato
        # nel DialogueState, resetta slots e confirmed_intent per evitare "memory bleed"
        metadata = state.get("metadata", {})
        session_last_intent = metadata.get("_session_last_intent")
        if session_last_intent and session_last_intent != intent and intent != "fallback":
            # L'utente ha cambiato argomento - reset DialogueState
            # NON resettare se intent è "fallback": potrebbe essere un messaggio
            # non riconosciuto (es. indirizzo puro) che è in realtà una risposta a slot mancante
            ds["slots"] = {}
            ds["confirmed_intent"] = None
            ds["confirmed_strategy"] = None
            ds["confirmed_strategy_id"] = None
            ds["missing_slots"] = []
            logger.info(f"[DM] Topic change detected ({session_last_intent} -> {intent}), reset DialogueState slots")

        # Costruisci lista candidati dal singolo intent del router
        # (il router attuale restituisce 1 intent — in futuro restituirà N)
        # P2: Usa confidence reale dal router con fallback a euristica
        classification_confidence = state.get("_classification_confidence")
        if classification_confidence is not None:
            confidence = classification_confidence
        else:
            # Fallback a euristica se router non ha fornito confidence
            confidence = 0.90 if not needs_clarification else 0.55
            if intent == "fallback":
                confidence = 0.30

        # Log per debug
        source = "router" if classification_confidence is not None else "hardcoded"
        logger.debug(f"[DM] Intent={intent}, confidence={confidence:.3f}, source={source}")

        # Usa candidati multipli dal router (se disponibili)
        candidates = state.get("_intent_candidates", [
            {"intent": intent, "confidence": confidence, "slots": slots}
        ])

        # Calcola raw_message_type
        from .dialogue_manager import _is_refinement, _is_oppure, _is_vague
        if _is_oppure(message):
            raw_type = "oppure"
        elif _is_refinement(message):
            raw_type = "refinement"
        elif _is_vague(message):
            raw_type = "vague_request"
        elif needs_clarification:
            raw_type = "continuation"
        else:
            raw_type = "specific_query"

        # Chiama il Dialogue Manager
        result: DialogueManagerResult = dm_evaluate(
            message=message,
            candidates=candidates,
            extracted_slots=slots,
            dialogue_state=ds,
            raw_message_type=raw_type,
        )

        # Aggiorna state dal risultato
        state["dialogue_state"] = result.updated_state
        state["dm_action"] = result.action

        if result.action == "execute":
            state["dm_target_tool"] = result.target_tool
            state["intent"] = result.intent or intent
            state["slots"] = result.slots or slots
            state["needs_clarification"] = False

        elif result.action == "ask_user":
            state["dm_question"] = result.question
            state["dm_target_tool"] = None

        elif result.action == "fallback":
            state["dm_target_tool"] = "fallback_tool"

        # Tracking execution
        node_duration_ms = (time.perf_counter() - node_start) * 1000
        if state.get("execution_path") is not None:
            state["execution_path"].append("dialogue_manager")
        if state.get("node_timings") is not None:
            state["node_timings"]["dialogue_manager"] = round(node_duration_ms, 2)
        if self._event_callback:
            self._event_callback({
                "type": "node_timing",
                "node": "dialogue_manager",
                "duration_ms": round(node_duration_ms, 2),
                "action": result.action,
                "target_tool": state.get("dm_target_tool")
            })

        return state

    def _dm_router(self, state: ConversationState) -> str:
        """Router condizionale post dialogue_manager."""
        action = state.get("dm_action", "fallback")

        if action == "ask_user":
            return "ask_user"

        if action == "execute":
            target = state.get("dm_target_tool")
            if target and target in TOOL_REGISTRY:
                return target
            # Fallback se tool non trovato
            return "fallback"

        return "fallback"

    # =========================================================================
    # ASK USER NODE
    # =========================================================================

    def _ask_user_node(self, state: ConversationState) -> ConversationState:
        """
        Nodo ask_user: genera domanda di chiarimento e termina il turno.

        La domanda viene salvata come final_response per essere restituita
        all'utente. Il DialogueState viene preservato per il turno successivo.
        """
        node_start = time.perf_counter()

        question = state.get("dm_question", "Non ho capito. Puoi riformulare?")
        state["final_response"] = question
        state["needs_clarification"] = True

        # Tracking execution
        node_duration_ms = (time.perf_counter() - node_start) * 1000
        if state.get("execution_path") is not None:
            state["execution_path"].append("ask_user")
        if state.get("node_timings") is not None:
            state["node_timings"]["ask_user"] = round(node_duration_ms, 2)
        if self._event_callback:
            self._event_callback({
                "type": "node_timing",
                "node": "ask_user",
                "duration_ms": round(node_duration_ms, 2)
            })

        return state

    # =========================================================================
    # FALLBACK TOOL (preservato dal vecchio grafo)
    # =========================================================================

    # Mapping slot → human-readable prompt
    SLOT_PROMPTS = {
        "piano_code": "Quale piano? (es. A1, B2, C3)",
        "topic": "Su quale argomento? (es. latte, bovini, benessere animale)",
        "num_registrazione": "Qual è il numero di registrazione dello stabilimento? (es. IT 123456)",
        "partita_iva": "Qual è la partita IVA dello stabilimento?",
        "ragione_sociale": "Qual è la ragione sociale dello stabilimento?",
        "categoria": "Quale categoria di non conformità? (es. HACCP, IGIENE, STRUTTURE)",
    }

    def _get_missing_slots(self, intent: str, slots: Dict[str, Any]) -> list:
        from orchestrator.router import Router
        required = Router.REQUIRED_SLOTS.get(intent, [])
        if intent == "ask_establishment_history":
            if any(slots.get(k) for k in required):
                return []
            return required
        return [r for r in required if not slots.get(r)]

    def _build_clarification_message(self, intent: str, missing_slots: list) -> str:
        if not missing_slots:
            return "Non ho capito la tua richiesta. Puoi riformularla?"

        # Caso speciale: ask_establishment_history richiede ALMENO UNO degli identificatori
        if intent == "ask_establishment_history":
            return (
                "Per trovare lo storico dello stabilimento, fornisci **uno** dei seguenti identificatori:\n\n"
                "- Numero di registrazione (es. IT 123456, UE IT 2287 M)\n"
                "- Partita IVA (es. 01234567890)\n"
                "- Ragione sociale (anche parziale, es. \"Rossi SRL\")"
            )

        intent_labels = {
            "ask_piano_description": "la descrizione di un piano",
            "ask_piano_stabilimenti": "gli stabilimenti di un piano",
            "check_if_plan_delayed": "il ritardo di un piano",
            "search_piani_by_topic": "la ricerca di piani per argomento",
            "analyze_nc_by_category": "l'analisi NC per categoria",
        }
        label = intent_labels.get(intent, "questa richiesta")
        prompts = [f"- {self.SLOT_PROMPTS.get(s, f'Specifica: {s}')}" for s in missing_slots]
        return f"Per completare {label}, ho bisogno di alcune informazioni:\n\n" + "\n".join(prompts)

    def _fallback_tool(self, state: ConversationState) -> ConversationState:
        """Fallback intelligente con approssimazioni successive."""
        node_start = time.perf_counter()

        # Helper per tracking
        def _track_fallback():
            node_duration_ms = (time.perf_counter() - node_start) * 1000
            if state.get("execution_path") is not None:
                state["execution_path"].append("fallback_tool")
            if state.get("node_timings") is not None:
                state["node_timings"]["fallback_tool"] = round(node_duration_ms, 2)
            if self._event_callback:
                self._event_callback({
                    "type": "node_timing",
                    "node": "fallback_tool",
                    "duration_ms": round(node_duration_ms, 2)
                })

        # Slot mancanti
        if state.get("needs_clarification"):
            intent = state.get("intent", "fallback")
            slots = state.get("slots", {})
            missing = self._get_missing_slots(intent, slots)
            if missing:
                clarification_msg = self._build_clarification_message(intent, missing)
                state["tool_output"] = {
                    "type": "fallback",
                    "data": {"formatted_response": clarification_msg}
                }
                state["error"] = ""
                _track_fallback()
                return state

        # Lazy init fallback engine
        if self._fallback_engine is None:
            from .fallback_recovery import FallbackRecoveryEngine
            try:
                from configs.config import AppConfig
                config = AppConfig.get_fallback_config()
            except:
                config = None
            self._fallback_engine = FallbackRecoveryEngine(self.llm_client, config)

        # Loop prevention
        fallback_count = (state.get("fallback_count") or 0) + 1
        if fallback_count > 3:
            help_text = self._get_help_text()
            state["tool_output"] = {
                "type": "fallback",
                "data": {"formatted_response": f"Sembra che ci siano difficoltà nel capire la tua richiesta. Ecco cosa posso fare per te:\n\n{help_text}"}
            }
            state["fallback_count"] = 0
            state["fallback_suggestions"] = None
            state["fallback_phase"] = 1
            state["fallback_selected_category"] = None
            state["error"] = ""
            _track_fallback()
            return state

        state["fallback_count"] = fallback_count

        phase = state.get("fallback_phase") or 1
        selected_category = state.get("fallback_selected_category")

        suggestions = self._fallback_engine.suggest_intents(
            state.get("message", ""),
            phase=phase,
            category=selected_category
        )

        state["fallback_suggestions"] = suggestions

        intro = f"**{selected_category}** - Scegli l'operazione:" if selected_category else None
        response = self._fallback_engine.format_suggestions_message(
            suggestions, phase=phase, intro_message=intro
        )

        state["tool_output"] = {"type": "fallback", "data": {"formatted_response": response}}
        state["error"] = ""
        _track_fallback()
        return state

    def _get_help_text(self) -> str:
        from .intent_metadata import CATEGORY_HIERARCHY, CATEGORY_EMOJI, get_intent_metadata
        lines = ["Ecco le operazioni disponibili, organizzate per categoria:\n"]
        for category, intent_ids in CATEGORY_HIERARCHY.items():
            if category == "Altro":
                continue
            emoji = CATEGORY_EMOJI.get(category, "📋")
            lines.append(f"\n{emoji} **{category}:**")
            for intent_id in intent_ids:
                metadata = get_intent_metadata(intent_id)
                if metadata:
                    lines.append(f"  • {metadata.label}: {metadata.description}")
        lines.append("\nScegli una categoria o descrivi la tua richiesta.")
        return "\n".join(lines)

    def _parse_user_selection(self, message, suggestions):
        # Lazy init fallback engine (stesso pattern di _fallback_tool)
        if self._fallback_engine is None:
            from .fallback_recovery import FallbackRecoveryEngine
            try:
                from configs.config import AppConfig
                config = AppConfig.get_fallback_config()
            except Exception:
                config = None
            self._fallback_engine = FallbackRecoveryEngine(self.llm_client, config)
        return self._fallback_engine.parse_user_selection(message, suggestions)

    # =========================================================================
    # RESPONSE GENERATOR NODE
    # =========================================================================

    def _response_generator_node(self, state: ConversationState) -> ConversationState:
        """Delega a response_node.py con tracking."""
        node_start = time.perf_counter()

        result = response_generator_node(state, self.llm_client, self._event_callback)

        # Propaga response_context nel dialogue_state per turni successivi
        response_context = result.get("response_context")
        if response_context:
            ds = result.get("dialogue_state") or {}
            ds["last_response_context"] = response_context
            result["dialogue_state"] = ds

        # Tracking execution
        node_duration_ms = (time.perf_counter() - node_start) * 1000
        if result.get("execution_path") is not None:
            result["execution_path"].append("response_generator")
        if result.get("node_timings") is not None:
            result["node_timings"]["response_generator"] = round(node_duration_ms, 2)
        if self._event_callback:
            self._event_callback({
                "type": "node_timing",
                "node": "response_generator",
                "duration_ms": round(node_duration_ms, 2)
            })

        return result

    # =========================================================================
    # RUN
    # =========================================================================

    def run(
        self,
        message: str,
        metadata: Dict[str, Any] = None,
        detail_context: Dict[str, Any] = None,
        workflow_context: Dict[str, Any] = None,
        event_callback=None,
        dialogue_state: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Esegue il grafo di conversazione.

        Args:
            message: Messaggio utente
            metadata: Metadata sessione
            detail_context: Contesto two-phase
            workflow_context: Workflow context legacy (backwards compat)
            event_callback: Callback SSE
            dialogue_state: DialogueState da turno precedente (nuovo)
        """
        effective_metadata = metadata or {}
        if detail_context:
            effective_metadata = {**effective_metadata, "detail_context": detail_context}

        self._event_callback = event_callback
        execution_start = time.perf_counter()

        try:
            initial_state: ConversationState = {
                "message": message,
                "metadata": effective_metadata,
                "intent": "",
                "slots": {},
                "tool_output": None,
                "final_response": "",
                "needs_clarification": False,
                "error": "",
                "has_more_details": False,
                "detail_context": {},
                # Nuovo: Dialogue State
                "dialogue_state": dialogue_state,
                "dm_action": None,
                "dm_target_tool": None,
                "dm_question": None,
                # Execution tracking per debug visualizer
                "execution_path": [],
                "node_timings": {},
                "execution_start_ms": execution_start * 1000,
                # Legacy workflow (backwards compat)
                "workflow_stage": workflow_context.get("workflow_stage") if workflow_context else None,
                "workflow_id": workflow_context.get("workflow_id") if workflow_context else None,
                "workflow_nonce": workflow_context.get("workflow_nonce") if workflow_context else None,
                "workflow_type": workflow_context.get("workflow_type") if workflow_context else None,
                "workflow_context": workflow_context or {},
                "pending_question": workflow_context.get("pending_question") if workflow_context else None,
                "available_options": workflow_context.get("available_options") if workflow_context else None,
                "workflow_history": workflow_context.get("workflow_history") if workflow_context else [],
                "accumulated_filters": workflow_context.get("accumulated_filters") if workflow_context else {},
                # Fallback recovery
                "fallback_suggestions": effective_metadata.get("_fallback_suggestions"),
                "fallback_phase": effective_metadata.get("_fallback_phase"),
                "fallback_count": effective_metadata.get("_fallback_count"),
                "fallback_selected_category": effective_metadata.get("_fallback_selected_category"),
            }

            final_state = self.graph.invoke(initial_state)

            # Calcola durata totale esecuzione
            total_execution_ms = round((time.perf_counter() - execution_start) * 1000, 2)

            return {
                "response": final_state.get("final_response", ""),
                "intent": final_state.get("intent", ""),
                "slots": final_state.get("slots", {}),
                "needs_clarification": final_state.get("needs_clarification", False),
                "error": final_state.get("error", ""),
                "has_more_details": final_state.get("has_more_details", False),
                "detail_context": final_state.get("detail_context", {}),
                # Suggestions e response_context dal response_node
                "suggestions": final_state.get("suggestions", []),
                "response_context": final_state.get("response_context"),
                # Nuovo: Dialogue State
                "dialogue_state": final_state.get("dialogue_state"),
                # Legacy workflow fields
                "workflow_stage": final_state.get("workflow_stage"),
                "workflow_id": final_state.get("workflow_id"),
                "workflow_nonce": final_state.get("workflow_nonce"),
                "workflow_type": final_state.get("workflow_type"),
                "workflow_context": final_state.get("workflow_context", {}),
                "pending_question": final_state.get("pending_question"),
                "available_options": final_state.get("available_options"),
                "workflow_history": final_state.get("workflow_history"),
                "accumulated_filters": final_state.get("accumulated_filters"),
                # Fallback recovery
                "fallback_suggestions": final_state.get("fallback_suggestions"),
                "fallback_phase": final_state.get("fallback_phase"),
                "fallback_count": final_state.get("fallback_count"),
                "fallback_selected_category": final_state.get("fallback_selected_category"),
                # Execution tracking per debug visualizer
                "execution_path": final_state.get("execution_path", []),
                "node_timings": final_state.get("node_timings", {}),
                "total_execution_ms": total_execution_ms,
            }
        finally:
            self._event_callback = None
