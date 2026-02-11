from typing import TypedDict, Any, Dict, Literal, Optional, List
from langgraph.graph import StateGraph, END
import re
import time

try:
    from .router import Router
    from llm.client import LLMClient
    from configs.config import RiskPredictorConfig
    from tools.piano_tools import piano_tool, get_piano_statistics
    from tools.priority_tools import priority_tool, suggest_controls
    from tools.risk_tools import risk_tool, analyze_nc_by_category
    from tools.search_tools import search_tool
    from tools.establishment_tools import get_establishment_history
    from tools.risk_analysis_tools import get_top_risk_activities
    from tools.predictor_tools import get_ml_risk_prediction
    from agents.response_agent import ResponseFormatter
    from .workflow_validator import WorkflowStage
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from orchestrator.router import Router
    from llm.client import LLMClient
    from configs.config import RiskPredictorConfig
    from tools.piano_tools import piano_tool, get_piano_statistics
    from tools.priority_tools import priority_tool, suggest_controls
    from tools.risk_tools import risk_tool, analyze_nc_by_category
    from tools.search_tools import search_tool
    from tools.establishment_tools import get_establishment_history
    from tools.risk_analysis_tools import get_top_risk_activities
    from tools.predictor_tools import get_ml_risk_prediction
    from agents.response_agent import ResponseFormatter
    from orchestrator.workflow_validator import WorkflowStage


class ConversationState(TypedDict, total=False):
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

    # NUOVI campi opzionali per workflow conversazionali (default: None/empty)
    workflow_stage: Optional[str]                      # Stato workflow corrente (WorkflowStage enum)
    workflow_id: Optional[str]                         # ID workflow attivo (timestamp-based)
    workflow_nonce: Optional[str]                      # Token crittografico freshness
    workflow_type: Optional[str]                       # Tipo workflow (es: "ask_suggest_controls")
    workflow_context: Optional[Dict[str, Any]]         # Contesto workflow specifico (whitelist)
    pending_question: Optional[Dict[str, Any]]         # Domanda in sospeso (con nonce)
    available_options: Optional[List[Dict[str, Any]]]  # Opzioni presentate
    workflow_history: Optional[List[Dict[str, Any]]]   # Storia scelte utente
    accumulated_filters: Optional[Dict[str, Any]]      # Filtri accumulati (validati)

    # NUOVI campi per fallback recovery intelligente
    fallback_suggestions: Optional[List[Dict[str, Any]]]  # Suggerimenti mostrati all'utente
    fallback_phase: Optional[int]                          # Fase corrente (1=keyword, 2=LLM, 3=menu)
    fallback_count: Optional[int]                          # Contatore fallback consecutivi
    fallback_selected_category: Optional[str]              # Categoria selezionata (menu livello 2)


class ConversationGraph:
    TWO_PHASE_THRESHOLDS = {
        "ask_establishment_history": 3,
        "ask_risk_based_priority": 3,
        "ask_priority_establishment": 3,
        "ask_suggest_controls": 3,
        "search_piani_by_topic": 3,
        "ask_piano_stabilimenti": 3,
    }
    TWO_PHASE_SUFFIX = "\n\n---\n**Vuoi vedere tutti i dettagli?** (rispondi *sì* o *no*)"

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.router = Router(self.llm_client)
        self.graph = self._build_graph()
        # Attributo temporaneo per event callback (non serializzato)
        self._event_callback = None
        # Engine fallback recovery (lazy init)
        self._fallback_engine = None

    @staticmethod
    def _apply_two_phase_check(state, intent, result, item_count, summary_text):
        """
        Applica il controllo two-phase: se item_count > threshold,
        salva la risposta completa in detail_context e sostituisce
        formatted_response con il sommario + suffix.
        """
        threshold = ConversationGraph.TWO_PHASE_THRESHOLDS.get(intent, 5)
        if item_count > threshold and isinstance(result, dict) and "formatted_response" in result:
            state["has_more_details"] = True
            state["detail_context"] = {
                "formatted_response": result["formatted_response"],
                "intent": intent,
                "item_count": item_count
            }
            result["formatted_response"] = summary_text + ConversationGraph.TWO_PHASE_SUFFIX
        return result

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ConversationState)

        # Nodi esistenti
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("greet_tool", self._greet_tool)
        workflow.add_node("goodbye_tool", self._goodbye_tool)
        workflow.add_node("help_tool", self._help_tool)
        workflow.add_node("piano_description_tool", self._piano_description_tool)
        workflow.add_node("piano_stabilimenti_tool", self._piano_stabilimenti_tool)
        workflow.add_node("piano_generic_tool", self._piano_generic_tool)
        workflow.add_node("piano_statistics_tool", self._piano_statistics_tool)
        workflow.add_node("search_piani_tool", self._search_piani_tool)
        workflow.add_node("priority_establishment_tool", self._priority_establishment_tool)
        # Risk predictor configurabile (ML o statistico)
        workflow.add_node("risk_predictor_tool", self._risk_predictor_tool)
        workflow.add_node("suggest_controls_tool", self._suggest_controls_tool)
        workflow.add_node("delayed_plans_tool", self._delayed_plans_tool)
        workflow.add_node("check_plan_delayed_tool", self._check_plan_delayed_tool)
        workflow.add_node("establishment_history_tool", self._establishment_history_tool)
        workflow.add_node("top_risk_activities_tool", self._top_risk_activities_tool)
        workflow.add_node("analyze_nc_tool", self._analyze_nc_tool)
        workflow.add_node("confirm_details_tool", self._confirm_details_tool)
        workflow.add_node("decline_details_tool", self._decline_details_tool)
        workflow.add_node("fallback_tool", self._fallback_tool)
        workflow.add_node("response_generator", self._response_generator_node)

        # NUOVI nodi orchestration workflow
        workflow.add_node("present_strategies", self._present_strategies_node)
        workflow.add_node("handle_strategy_choice", self._handle_strategy_choice_node)
        workflow.add_node("collect_params", self._collect_params_node)
        workflow.add_node("handle_oppure", self._handle_oppure_node)
        workflow.add_node("refine_query", self._refine_query_node)

        workflow.set_entry_point("classify")

        # Routing potenziato con workflow-aware router
        workflow.add_conditional_edges(
            "classify",
            self._workflow_router,  # NUOVO router
            {
                # Workflow routes (intent speciali)
                "__present_strategies__": "present_strategies",
                "__choose_strategy__": "handle_strategy_choice",
                "__provide_param__": "collect_params",
                "__oppure__": "handle_oppure",
                "__refine__": "refine_query",
                # Existing routes
                "greet": "greet_tool",
                "goodbye": "goodbye_tool",
                "ask_help": "help_tool",
                "ask_piano_description": "piano_description_tool",
                "ask_piano_stabilimenti": "piano_stabilimenti_tool",
                "ask_piano_generic": "piano_generic_tool",
                "ask_piano_statistics": "piano_statistics_tool",
                "search_piani_by_topic": "search_piani_tool",
                "ask_priority_establishment": "priority_establishment_tool",
                "ask_risk_based_priority": "risk_predictor_tool",  # Configurable: ML or statistical predictor
                "ask_suggest_controls": "suggest_controls_tool",
                "ask_delayed_plans": "delayed_plans_tool",
                "check_if_plan_delayed": "check_plan_delayed_tool",
                "ask_establishment_history": "establishment_history_tool",
                "ask_top_risk_activities": "top_risk_activities_tool",
                "analyze_nc_by_category": "analyze_nc_tool",
                "confirm_show_details": "confirm_details_tool",
                "decline_show_details": "decline_details_tool",
                "fallback": "fallback_tool",
            }
        )

        # Response generator per tutti i nodi esistenti
        for tool_node in [
            "greet_tool", "goodbye_tool", "help_tool",
            "piano_description_tool", "piano_stabilimenti_tool",
            "piano_generic_tool", "piano_statistics_tool", "search_piani_tool", "priority_establishment_tool",
            "risk_predictor_tool", "suggest_controls_tool", "delayed_plans_tool",
            "check_plan_delayed_tool", "establishment_history_tool", "top_risk_activities_tool", "analyze_nc_tool",
            "confirm_details_tool", "decline_details_tool", "fallback_tool"
        ]:
            workflow.add_edge(tool_node, "response_generator")

        # Response generator per nuovi nodi workflow
        workflow.add_edge("present_strategies", "response_generator")
        workflow.add_edge("handle_strategy_choice", "response_generator")
        workflow.add_edge("collect_params", "response_generator")
        workflow.add_edge("handle_oppure", "response_generator")
        workflow.add_edge("refine_query", "response_generator")

        workflow.add_edge("response_generator", END)

        return workflow.compile()

    def _classify_node(self, state: ConversationState) -> ConversationState:
        # Emit event: start classification
        if self._event_callback:
            self._event_callback({
                "type": "status",
                "node": "router",
                "message": "Analizzando la richiesta..."
            })

        # NUOVO: Gestione selezione da fallback suggestions
        if state.get("fallback_suggestions"):
            selected = self._parse_user_selection(
                state["message"],
                state["fallback_suggestions"]
            )

            if selected:
                # Selezione valida
                if selected.get("type") == "intent":
                    # Intent selezionato
                    state["intent"] = selected["intent"]
                    state["slots"] = {}
                    state["needs_clarification"] = bool(selected.get("requires_slots"))
                    state["error"] = ""

                    # Reset fallback state
                    state["fallback_suggestions"] = None
                    state["fallback_count"] = 0
                    state["fallback_phase"] = 1
                    state["fallback_selected_category"] = None

                    # Emit event
                    if self._event_callback:
                        self._event_callback({
                            "type": "reasoning",
                            "node": "router",
                            "message": f"Intent selezionato: {state['intent']}"
                        })

                    return state

                elif selected.get("type") == "category":
                    # Categoria selezionata - mostra menu livello 2
                    category = selected.get("category")
                    state["fallback_selected_category"] = category
                    state["fallback_phase"] = 3  # Force category menu
                    state["intent"] = "fallback"  # Richiama fallback con category
                    state["slots"] = {}
                    state["needs_clarification"] = False
                    state["error"] = ""
                    return state

            # Selezione non valida - riclassifica messaggio
            # (continua con classificazione normale)
            pass

        # UPDATED: Usa classify_with_context se workflow attivo
        workflow_context = state.get("workflow_context")

        if workflow_context:
            classification = self.router.classify_with_context(
                state["message"],
                state.get("metadata", {}),
                workflow_context
            )
        else:
            classification = self.router.classify(
                state["message"],
                state.get("metadata", {})
            )

        state["intent"] = classification.get("intent", "fallback")
        state["slots"] = classification.get("slots", {})
        state["needs_clarification"] = classification.get("needs_clarification", False)
        state["error"] = classification.get("error", "")

        # Emit event: classification complete
        if self._event_callback and state["intent"]:
            self._event_callback({
                "type": "reasoning",
                "node": "router",
                "message": f"Intent rilevato: {state['intent']}"
            })

        # Slot carry-forward: if needs_clarification and session has slots from previous turn,
        # carry them forward and re-check if clarification is still needed
        if state["needs_clarification"]:
            metadata = state.get("metadata", {})
            session_last_slots = metadata.get("_session_last_slots", {})
            if session_last_slots:
                # Merge: current slots take priority over session slots
                merged_slots = {**session_last_slots, **state["slots"]}
                state["slots"] = merged_slots

                # Re-validate with merged slots
                re_result = self.router._post_validate({
                    "intent": state["intent"],
                    "slots": merged_slots,
                    "needs_clarification": state["needs_clarification"]
                })
                state["needs_clarification"] = re_result.get("needs_clarification", True)
                state["slots"] = re_result.get("slots", merged_slots)

        return state

    def _route_by_intent(self, state: ConversationState) -> str:
        # If clarification is needed, route to fallback for targeted message
        if state.get("needs_clarification", False):
            return "fallback"
        return state.get("intent", "fallback")

    def _workflow_router(self, state: ConversationState) -> str:
        """
        Router workflow-aware che decide dove instradare basandosi su:
        - Intent classificato
        - Workflow attivo
        - Stage corrente

        Args:
            state: Conversation state

        Returns:
            Nome nodo target
        """
        intent = state.get("intent", "fallback")
        workflow_stage = state.get("workflow_stage")
        workflow_type = state.get("workflow_type")
        needs_clarification = state.get("needs_clarification", False)

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
        from .workflow_strategies import CONVERSATIONAL_INTENTS

        if intent in CONVERSATIONAL_INTENTS and workflow_stage is None:
            # Controlla se richiesta è ambigua (necessita strategie)
            if self._needs_strategy_presentation(state):
                return "__present_strategies__"

        # Altrimenti routing standard per intent
        if needs_clarification:
            return "fallback"

        return intent

    def _greet_tool(self, state: ConversationState) -> ConversationState:
        state["tool_output"] = {
            "type": "greet",
            "data": "Benvenuto nel supporto conversazionale per il sistema GISA della Regione Campania."
        }
        return state

    def _goodbye_tool(self, state: ConversationState) -> ConversationState:
        state["tool_output"] = {
            "type": "goodbye",
            "data": "Arrivederci! Buon lavoro."
        }
        return state

    def _help_tool(self, state: ConversationState) -> ConversationState:
        capabilities = [
            "Consultare descrizioni dei piani di controllo",
            "Analizzare stabilimenti controllati per piano",
            "Identificare priorità di controllo",
            "Cercare piani per argomento",
            "Visualizzare piani in ritardo",
            "🆕 Analizzare non conformità per categoria",
            "🆕 Prevedere rischi NC per tipologia attività",
            "🆕 Visualizzare trend NC temporali"
        ]

        formatted_response = "**Come posso aiutarti?**\n\n"
        formatted_response += "Posso assisterti con le seguenti funzionalità:\n\n"
        for i, cap in enumerate(capabilities, 1):
            formatted_response += f"{i}. {cap}\n"
        formatted_response += "\n**Esempi di domande:**\n"
        formatted_response += "- [Di cosa tratta il piano A1?]\n"
        formatted_response += "- [Chi devo controllare per primo?]\n"
        formatted_response += "- [Stabilimenti ad alto rischio per il piano A1]\n"
        formatted_response += "- [Quali sono i miei piani in ritardo?]\n"
        formatted_response += "\n**🆕 Nuove funzionalità - Analisi Non Conformità:**\n"
        formatted_response += "- [Problemi HACCP nella mia ASL]\n"
        formatted_response += "- [Trend igiene alimenti ultimo anno]\n"
        formatted_response += "- [Stabilimenti a rischio NC strutture]\n"
        formatted_response += "- [Predici categorie NC per ristoranti]\n"

        state["tool_output"] = {
            "type": "help",
            "data": {
                "capabilities": capabilities,
                "formatted_response": formatted_response
            }
        }
        return state

    def _piano_description_tool(self, state: ConversationState) -> ConversationState:
        piano_code = state["slots"].get("piano_code")
        result = piano_tool(action="description", piano_code=piano_code)
        state["tool_output"] = {"type": "piano_description", "data": result}
        return state

    def _piano_stabilimenti_tool(self, state: ConversationState) -> ConversationState:
        # Emit event: start piano stabilimenti tool
        if self._event_callback:
            self._event_callback({
                "type": "reasoning",
                "node": "piano_stabilimenti_tool",
                "message": "Consultando il database dei piani..."
            })

        piano_code = state["slots"].get("piano_code")
        result = piano_tool(action="stabilimenti", piano_code=piano_code)

        # Two-phase check
        if isinstance(result, dict) and "formatted_response" in result:
            import pandas as pd
            unique_establishments = result.get("unique_establishments", 0)
            if unique_establishments > self.TWO_PHASE_THRESHOLDS.get("ask_piano_stabilimenti", 2):
                top_stab_data = result.get("top_stabilimenti", [])
                top_stab_df = pd.DataFrame(top_stab_data) if isinstance(top_stab_data, list) else top_stab_data
                summary_text = ResponseFormatter.format_stabilimenti_analysis_summary(
                    piano_id=result.get("piano_code", piano_code),
                    piano_desc=result.get("piano_description", ""),
                    top_stabilimenti=top_stab_df,
                    total_controls=result.get("total_controls", 0),
                    unique_establishments=unique_establishments
                )
                result = self._apply_two_phase_check(
                    state, "ask_piano_stabilimenti", result, unique_establishments, summary_text
                )

        state["tool_output"] = {"type": "piano_stabilimenti", "data": result}
        return state

    def _piano_generic_tool(self, state: ConversationState) -> ConversationState:
        piano_code = state["slots"].get("piano_code")
        result = piano_tool(action="generic", piano_code=piano_code)
        state["tool_output"] = {"type": "piano_generic", "data": result}
        return state

    def _piano_statistics_tool(self, state: ConversationState) -> ConversationState:
        asl = state["metadata"].get("asl")
        piano_code = state["slots"].get("piano_code")
        message = state.get("message", "").lower()

        # Se è specificato un piano_code, restituisci le statistiche per quel piano specifico
        if piano_code:
            result = piano_tool(action="stabilimenti", piano_code=piano_code)

            # Se la domanda è di tipo "quanti" (count), restituisci solo il conteggio
            count_keywords = ["quanti", "quante", "numero di", "conta", "totale controlli"]
            is_count_query = any(kw in message for kw in count_keywords)

            if is_count_query and result.get("total_controls") is not None:
                from agents.data_agent import DataRetriever
                import pandas as pd

                total = result.get("total_controls", 0)
                piano_desc = result.get("piano_description", piano_code.upper())

                # Recupera i controlli per calcolare date e filtro ASL
                controlli_df = DataRetriever.get_controlli_by_piano(piano_code)

                # Calcola intervallo date
                data_primo = None
                data_ultimo = None
                if controlli_df is not None and not controlli_df.empty and 'data_inizio_controllo' in controlli_df.columns:
                    controlli_df['data_inizio_controllo'] = pd.to_datetime(controlli_df['data_inizio_controllo'], errors='coerce')
                    data_primo = controlli_df['data_inizio_controllo'].min()
                    data_ultimo = controlli_df['data_inizio_controllo'].max()

                # Calcola controlli per ASL dell'utente
                asl_count = 0
                asl_name = None
                if asl and controlli_df is not None and not controlli_df.empty:
                    asl_upper = asl.upper()
                    asl_filtered = controlli_df[
                        controlli_df['descrizione_asl'].fillna('').str.upper().str.contains(asl_upper, na=False)
                    ]
                    asl_count = len(asl_filtered)
                    if not asl_filtered.empty:
                        asl_name = asl_filtered['descrizione_asl'].iloc[0]

                # Formatta risposta
                formatted = f"Per il piano **{piano_code.upper()}** sono stati inseriti:\n\n"
                formatted += f"📊 **Totale regionale:** {total:,} controlli\n"
                if asl and asl_count > 0:
                    formatted += f"🏥 **{asl_name or asl}:** {asl_count:,} controlli\n"
                elif asl:
                    formatted += f"🏥 **La tua ASL ({asl}):** nessun controllo registrato\n"

                # Aggiungi intervallo temporale
                if data_primo is not None and data_ultimo is not None:
                    formatted += f"\n📅 **Periodo:** dal {data_primo.strftime('%d/%m/%Y')} al {data_ultimo.strftime('%d/%m/%Y')}\n"

                formatted += f"\n📋 *{piano_desc}*"

                result = {
                    "piano_code": piano_code.upper(),
                    "total_controls": total,
                    "asl_controls": asl_count,
                    "asl": asl_name or asl,
                    "data_primo_controllo": data_primo.isoformat() if data_primo else None,
                    "data_ultimo_controllo": data_ultimo.isoformat() if data_ultimo else None,
                    "formatted_response": formatted
                }

            state["tool_output"] = {"type": "piano_statistics", "data": result}
            return state

        # Altrimenti restituisci statistiche aggregate
        stats_func = get_piano_statistics.func if hasattr(get_piano_statistics, 'func') else get_piano_statistics
        result = stats_func(asl=asl, top_n=10)

        state["tool_output"] = {"type": "piano_statistics", "data": result}
        return state

    def _search_piani_tool(self, state: ConversationState) -> ConversationState:
        topic = state["slots"].get("topic")
        result = search_tool(query=topic)

        # Two-phase check
        if isinstance(result, dict):
            total_found = result.get("total_found", 0)
            matches = result.get("matches", [])
            if total_found > self.TWO_PHASE_THRESHOLDS.get("search_piani_by_topic", 5):
                search_term = result.get("search_term", topic or "")
                summary_text = ResponseFormatter.format_search_results_summary(
                    search_term=search_term,
                    matches=matches
                )
                result = self._apply_two_phase_check(
                    state, "search_piani_by_topic", result, total_found, summary_text
                )

        state["tool_output"] = {"type": "search_piani", "data": result}
        return state

    def _priority_establishment_tool(self, state: ConversationState) -> ConversationState:
        from agents.data import get_uoc_from_user_id

        # Emit event: start priority tool
        if self._event_callback:
            self._event_callback({
                "type": "reasoning",
                "node": "priority_establishment_tool",
                "message": "Calcolando priorità controlli..."
            })

        asl = state["metadata"].get("asl")
        uoc = state["metadata"].get("uoc")

        if not uoc and state["metadata"].get("user_id"):
            uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

        piano_code = state["slots"].get("piano_code")
        result = priority_tool(asl=asl, uoc=uoc, piano_code=piano_code)

        # Two-phase check
        if isinstance(result, dict):
            total_found = result.get("total_found", 0)
            if total_found > self.TWO_PHASE_THRESHOLDS.get("ask_priority_establishment", 5):
                summary_text = ResponseFormatter.format_priority_establishments_summary(result)
                result = self._apply_two_phase_check(
                    state, "ask_priority_establishment", result, total_found, summary_text
                )

        state["tool_output"] = {"type": "priority_establishment", "data": result}
        return state

    def _risk_predictor_tool(self, state: ConversationState) -> ConversationState:
        """
        Nodo LangGraph per predizione rischio - configurabile.

        Seleziona automaticamente tra:
        - ML predictor: modello addestrato su dati storici NC
        - Statistical predictor: rule-based (Risk Score = P(NC) × Impatto × 100)

        Configurazione via:
        - Variabile ambiente: GIAS_RISK_PREDICTOR=ml|statistical
        - config.json: risk_predictor.type
        """
        # Emit event: start risk predictor
        if self._event_callback:
            self._event_callback({
                "type": "reasoning",
                "node": "risk_predictor_tool",
                "message": "Analizzando rischio stabilimenti..."
            })

        asl = state["metadata"].get("asl")
        piano_code = state["slots"].get("piano_code")

        predictor_type = RiskPredictorConfig.get_predictor_type()

        if predictor_type == "ml":
            # Predittore ML
            ml_func = get_ml_risk_prediction.func if hasattr(get_ml_risk_prediction, 'func') else get_ml_risk_prediction
            result = ml_func(asl=asl, piano_code=piano_code)
            output_type = "ml_risk_prediction"
        else:
            # Predittore statistico (rule-based)
            result = risk_tool(asl=asl, piano_code=piano_code)
            output_type = "statistical_risk_prediction"

        # Aggiungi info sul predittore usato
        if isinstance(result, dict):
            result["predictor_type"] = predictor_type

            # Two-phase check
            total_risky = result.get("total_risky", 0)
            if total_risky > self.TWO_PHASE_THRESHOLDS.get("ask_risk_based_priority", 5):
                mapped_result = {
                    "user_asl": result.get("asl", "N/D"),
                    "piano_code": result.get("piano_code"),
                    "osa_total_count": result.get("total_never_controlled", 0),
                    "osa_risky_count": total_risky,
                    "activities_count": result.get("activities_at_risk", 0),
                    "osa_rischiosi": result.get("risky_establishments", []),
                }
                summary_text = ResponseFormatter.format_risk_based_priority_summary(mapped_result)
                result = self._apply_two_phase_check(
                    state, "ask_risk_based_priority", result, total_risky, summary_text
                )

        state["tool_output"] = {"type": output_type, "data": result}
        return state

    def _suggest_controls_tool(self, state: ConversationState) -> ConversationState:
        asl = state["metadata"].get("asl")

        # Chiama suggest_controls direttamente con limit=20 per avere dati sufficienti per fase 2
        suggest_func = suggest_controls.func if hasattr(suggest_controls, 'func') else suggest_controls
        result = suggest_func(asl=asl, limit=20)

        # Two-phase check
        if isinstance(result, dict):
            total_never_controlled = result.get("total_never_controlled", 0)
            if total_never_controlled > self.TWO_PHASE_THRESHOLDS.get("ask_suggest_controls", 5):
                # Fase 1: mostra solo i primi 5
                summary_text = ResponseFormatter.format_suggest_controls(
                    asl=asl,
                    filtered_count=total_never_controlled,
                    sample_df=__import__('pandas').DataFrame(result.get("suggested_establishments", [])[:5]),
                    limit=5
                )
                result = self._apply_two_phase_check(
                    state, "ask_suggest_controls", result, total_never_controlled, summary_text
                )

        state["tool_output"] = {"type": "suggest_controls", "data": result}
        return state

    def _delayed_plans_tool(self, state: ConversationState) -> ConversationState:
        from agents.data import get_uoc_from_user_id

        asl = state["metadata"].get("asl")
        uoc = state["metadata"].get("uoc")

        if not uoc and state["metadata"].get("user_id"):
            uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

        result = priority_tool(asl=asl, uoc=uoc, action="delayed_plans")
        state["tool_output"] = {"type": "delayed_plans", "data": result}
        return state

    def _check_plan_delayed_tool(self, state: ConversationState) -> ConversationState:
        from agents.data import get_uoc_from_user_id
        from tools.priority_tools import get_delayed_plans

        asl = state["metadata"].get("asl")
        uoc = state["metadata"].get("uoc")
        piano_code = state["slots"].get("piano_code")

        if not uoc and state["metadata"].get("user_id"):
            uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

        delayed_func = get_delayed_plans.func if hasattr(get_delayed_plans, 'func') else get_delayed_plans
        result = delayed_func(asl=asl, uoc=uoc, piano_code=piano_code)
        state["tool_output"] = {"type": "check_plan_delayed", "data": result}
        return state

    def _establishment_history_tool(self, state: ConversationState) -> ConversationState:
        num_registrazione = state["slots"].get("num_registrazione")
        partita_iva = state["slots"].get("partita_iva")
        ragione_sociale = state["slots"].get("ragione_sociale")

        history_func = get_establishment_history.func if hasattr(get_establishment_history, 'func') else get_establishment_history
        result = history_func(
            num_registrazione=num_registrazione,
            partita_iva=partita_iva,
            ragione_sociale=ragione_sociale
        )

        # Two-phase check
        if isinstance(result, dict):
            total_controls = result.get("total_controls", 0)
            if total_controls > self.TWO_PHASE_THRESHOLDS.get("ask_establishment_history", 5):
                summary_text = ResponseFormatter.format_establishment_history_summary(result)
                result = self._apply_two_phase_check(
                    state, "ask_establishment_history", result, total_controls, summary_text
                )

        state["tool_output"] = {"type": "establishment_history", "data": result}
        return state

    def _top_risk_activities_tool(self, state: ConversationState) -> ConversationState:
        limit = state["slots"].get("limit", 10)  # Default a 10

        # Usa la funzione del tool
        top_risk_func = get_top_risk_activities.func if hasattr(get_top_risk_activities, 'func') else get_top_risk_activities
        result = top_risk_func(limit=limit)

        state["tool_output"] = {"type": "top_risk_activities", "data": result}
        return state

    def _analyze_nc_tool(self, state: ConversationState) -> ConversationState:
        categoria = state["slots"].get("categoria", "HACCP")
        asl = state["metadata"].get("asl")

        # Usa la funzione del tool
        analyze_nc_func = analyze_nc_by_category.func if hasattr(analyze_nc_by_category, 'func') else analyze_nc_by_category
        result = analyze_nc_func(categoria=categoria, asl=asl)

        state["tool_output"] = {"type": "analyze_nc_by_category", "data": result}
        return state

    def _confirm_details_tool(self, state: ConversationState) -> ConversationState:
        """
        Gestisce la conferma dell'utente per visualizzare i dettagli.
        Usa il detail_context memorizzato nella sessione precedente.
        """
        detail_context = state.get("metadata", {}).get("detail_context", {})

        if detail_context:
            # L'utente ha confermato, mostra i dettagli dal contesto salvato
            state["tool_output"] = {
                "type": "confirm_details",
                "data": {
                    "confirmed": True,
                    "detail_context": detail_context,
                    "formatted_response": detail_context.get("formatted_response",
                        "Ecco i dettagli richiesti.")
                }
            }
        else:
            # Nessun contesto disponibile (sessione scaduta o errore)
            state["tool_output"] = {
                "type": "confirm_details",
                "data": {
                    "confirmed": True,
                    "detail_context": None,
                    "formatted_response": "Non ho dettagli da mostrare al momento. Fai una domanda sui piani di controllo e potrò fornirti i dettagli."
                }
            }
        return state

    def _decline_details_tool(self, state: ConversationState) -> ConversationState:
        """
        Gestisce il rifiuto dell'utente di visualizzare i dettagli.
        """
        state["tool_output"] = {
            "type": "decline_details",
            "data": {
                "confirmed": False,
                "formatted_response": "Va bene! Se hai altre domande, sono qui per aiutarti."
            }
        }
        return state

    # Mapping slot → human-readable prompt for clarification
    SLOT_PROMPTS = {
        "piano_code": "Quale piano? (es. A1, B2, C3)",
        "topic": "Su quale argomento? (es. latte, bovini, benessere animale)",
        "num_registrazione": "Qual è il numero di registrazione dello stabilimento? (es. IT 123456)",
        "partita_iva": "Qual è la partita IVA dello stabilimento?",
        "ragione_sociale": "Qual è la ragione sociale dello stabilimento?",
        "categoria": "Quale categoria di non conformità? (es. HACCP, IGIENE, STRUTTURE)",
    }

    def _get_missing_slots(self, intent: str, slots: Dict[str, Any]) -> list:
        """Return list of missing required slots for the given intent."""
        from orchestrator.router import Router
        required = Router.REQUIRED_SLOTS.get(intent, [])
        if intent == "ask_establishment_history":
            # At least one identifier needed
            has_any = any(slots.get(k) for k in required)
            if has_any:
                return []
            return required  # All missing, suggest them
        return [r for r in required if not slots.get(r)]

    def _build_clarification_message(self, intent: str, missing_slots: list) -> str:
        """Build a targeted clarification message for the missing slots."""
        if not missing_slots:
            return "Non ho capito la tua richiesta. Puoi riformularla?"

        intent_labels = {
            "ask_piano_description": "la descrizione di un piano",
            "ask_piano_stabilimenti": "gli stabilimenti di un piano",
            "ask_piano_generic": "informazioni su un piano",
            "check_if_plan_delayed": "il ritardo di un piano",
            "search_piani_by_topic": "la ricerca di piani per argomento",
            "ask_establishment_history": "lo storico di uno stabilimento",
            "analyze_nc_by_category": "l'analisi NC per categoria",
        }

        label = intent_labels.get(intent, "questa richiesta")
        prompts = []
        for slot in missing_slots:
            prompt_text = self.SLOT_PROMPTS.get(slot, f"Specifica: {slot}")
            prompts.append(f"- {prompt_text}")

        msg = f"Per completare {label}, ho bisogno di alcune informazioni:\n\n"
        msg += "\n".join(prompts)
        return msg

    def _fallback_tool(self, state: ConversationState) -> ConversationState:
        """
        Fallback intelligente con approssimazioni successive.

        Flusso:
        1. Se needs_clarification → messaggio slot mancanti (esistente)
        2. Controlla loop prevention (max 3 fallback consecutivi)
        3. Genera suggerimenti (keyword + LLM + menu categorizzato)
        4. Costruisce messaggio formattato con suggerimenti
        """
        # Comportamento esistente per needs_clarification (slot mancanti)
        if state.get("needs_clarification"):
            intent = state.get("intent", "fallback")
            slots = state.get("slots", {})
            missing = self._get_missing_slots(intent, slots)
            if missing:
                clarification_msg = self._build_clarification_message(intent, missing)
                state["tool_output"] = {
                    "type": "fallback",
                    "data": clarification_msg
                }
                state["error"] = ""  # Clear error
                return state

        # NUOVO: Fallback intelligente con suggerimenti
        # Lazy init fallback engine
        if self._fallback_engine is None:
            from .fallback_recovery import FallbackRecoveryEngine
            # Load config if available
            try:
                from configs.config import AppConfig
                config = AppConfig.get_fallback_config()
            except:
                config = None
            self._fallback_engine = FallbackRecoveryEngine(self.llm_client, config)

        # Loop prevention (max 3 fallback consecutivi)
        fallback_count = (state.get("fallback_count") or 0) + 1
        if fallback_count > 3:
            # Escalation: mostra help completo
            help_text = self._get_help_text()
            state["tool_output"] = {
                "type": "fallback",
                "data": f"Sembra che ci siano difficoltà nel capire la tua richiesta. Ecco cosa posso fare per te:\n\n{help_text}"
            }
            state["fallback_count"] = 0  # Reset
            state["fallback_suggestions"] = None
            state["fallback_phase"] = 1
            state["fallback_selected_category"] = None
            state["error"] = ""  # Clear error
            return state

        state["fallback_count"] = fallback_count

        # Determina fase e categoria
        phase = state.get("fallback_phase") or 1
        selected_category = state.get("fallback_selected_category")

        # Genera suggerimenti
        user_message = state.get("message", "")
        suggestions = self._fallback_engine.suggest_intents(
            user_message,
            phase=phase,
            category=selected_category
        )

        # Salva suggerimenti nello stato
        state["fallback_suggestions"] = suggestions

        # Costruisci messaggio formattato
        if selected_category:
            intro = f"**{selected_category}** - Scegli l'operazione:"
        else:
            intro = None

        response = self._fallback_engine.format_suggestions_message(
            suggestions,
            phase=phase,
            intro_message=intro
        )

        state["tool_output"] = {
            "type": "fallback",
            "data": response
        }

        # CRITICAL: Clear error quando fallback gestito correttamente
        # Altrimenti l'API interpreta l'errore come critico e non mostra i suggerimenti
        state["error"] = ""

        return state

    def _get_help_text(self) -> str:
        """Genera testo di aiuto completo"""
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

    def _parse_user_selection(
        self,
        message: str,
        suggestions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse selezione utente da numero o testo.

        Args:
            message: Messaggio utente
            suggestions: Lista suggerimenti mostrati

        Returns:
            Suggerimento selezionato o None
        """
        if not self._fallback_engine:
            return None

        return self._fallback_engine.parse_user_selection(message, suggestions)

    def _response_generator_node(self, state: ConversationState) -> ConversationState:
        # Emit event: start response generation
        if self._event_callback:
            self._event_callback({
                "type": "status",
                "node": "response_generator",
                "message": "Generando risposta..."
            })

        tool_output = state.get("tool_output") or {}
        intent = state.get("intent", "fallback")
        tool_type = tool_output.get("type", "") if isinstance(tool_output, dict) else ""

        # Intent con risposte dirette (non richiedono LLM per formattare)
        # Include anche casi dove tool_type è "fallback" (es. needs_clarification)
        if intent in ["greet", "goodbye", "fallback", "confirm_show_details", "decline_show_details"] or tool_type == "fallback":
            data = tool_output.get("data", {})
            if isinstance(data, dict) and "formatted_response" in data:
                state["final_response"] = data["formatted_response"]
            else:
                state["final_response"] = str(data)
            return state

        data = tool_output.get("data", {})
        if isinstance(data, dict) and "formatted_response" in data:
            response = data["formatted_response"]
            response = self._clean_excessive_newlines(response)
            state["final_response"] = response
            return state

        messages = self._build_response_messages(intent, tool_output, state.get("message", ""))

        try:
            response = self.llm_client.query(messages=messages)
            response = self._clean_excessive_newlines(response) if response else "Errore nella generazione della risposta."
            state["final_response"] = response.strip()
        except Exception as e:
            state["final_response"] = f"Errore: {str(e)}"

        return state

    def _clean_excessive_newlines(self, text: str) -> str:
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'\n\n\n+', '\n\n', text)
        return text.strip()

    RESPONSE_SYSTEM_PROMPT = """Sei un assistente esperto nel monitoraggio veterinario della Regione Campania.

**TASK:**
Genera una risposta chiara, professionale e utile in italiano che:

1. **Spiega i risultati** in modo comprensibile:
   - Sintetizza le informazioni principali
   - Evidenzia numeri e metriche chiave
   - Usa formattazione markdown (bold, liste) per chiarezza

2. **Motiva le priorità** (se presenti):
   - Spiega PERCHÉ certi stabilimenti/piani sono prioritari
   - Evidenzia i criteri utilizzati (rischio storico, ritardi, correlazioni)
   - Dai contesto operativo pratico

3. **Fornisci valore aggiunto**:
   - Interpreta i dati in chiave operativa
   - Suggerisci 1-2 domande di follow-up pertinenti
   - NON aggiungere informazioni sui punteggi che non sono presenti nei dati forniti

**IMPORTANTE - Formula Risk Score:**
Se menzioni punteggi di rischio, usa SOLO questa formula:
- Risk Score = P(NC) × Impatto × 100
- P(NC) = (NC totali) / (controlli totali)
- Impatto = (NC gravi) / (controlli totali)
- NON usare mai formule come "NC grave = 3 punti" che sono ERRATE

4. **Linee guida per la risposta**:
   - Interpreta i dati nel contesto veterinario regionale
   - Suggerisci azioni concrete basate sui risultati
   - Se ci sono anomalie o punti critici, evidenziali

5. **Proponi 1-2 domande successive** che l'utente potrebbe trovare utili:
   - Basate sui risultati attuali
   - Che approfondiscano l'analisi
   - Che guidino verso azioni operative

**REGOLE:**
- Tono formale ma accessibile, adatto a operatori ASL
- NON inventare dati non presenti
- Se i risultati sono vuoti o in errore, spiegalo chiaramente
- Usa terminologia tecnica corretta (ASL, UOC, OSA, NC, piani di controllo)
- Formatta usando markdown per migliore leggibilità

**OUTPUT:**
Rispondi SOLO con il testo della risposta finale, strutturato e professionale.
NO prefissi tipo "Ecco la risposta:" o "Sulla base dei dati:".
Inizia direttamente con il contenuto."""

    RESPONSE_USER_TEMPLATE = """**CONTESTO:**
L'utente ha richiesto: {context_description}

**DOMANDA ORIGINALE:**
"{user_message}"

**TIPO DI ANALISI:**
{intent}

**RISULTATI OTTENUTI:**
{data}"""

    def _build_response_messages(self, intent: str, tool_output: Dict[str, Any], user_message: str = "") -> list:
        """Build system + user messages for LLM response generation."""
        data = tool_output.get("data", {})

        formatted_response = data.get("formatted_response", "") if isinstance(data, dict) else ""

        intent_descriptions = {
            "ask_piano_description": "descrizione di un piano di controllo veterinario",
            "ask_piano_stabilimenti": "analisi degli stabilimenti controllati per un piano",
            "ask_piano_statistics": "statistiche aggregate sui piani di controllo eseguiti",
            "search_piani_by_topic": "ricerca di piani per argomento",
            "ask_priority_establishment": "stabilimenti prioritari da controllare secondo programmazione",
            "ask_risk_based_priority": "stabilimenti prioritari basati sul rischio storico",
            "ask_suggest_controls": "suggerimenti per controlli di stabilimenti mai ispezionati",
            "ask_delayed_plans": "analisi dei piani in ritardo",
            "check_if_plan_delayed": "verifica se un piano specifico è in ritardo",
            "ask_establishment_history": "storico controlli e NC per stabilimento",
            "ask_top_risk_activities": "top attività con risk score più elevato",
            "analyze_nc_by_category": "analisi non conformità per categoria specifica",
            "ask_help": "informazioni sulle funzionalità disponibili"
        }

        context_description = intent_descriptions.get(intent, "analisi di dati veterinari")
        data_str = formatted_response if formatted_response else str(data)

        user_content = self.RESPONSE_USER_TEMPLATE.format(
            context_description=context_description,
            user_message=user_message,
            intent=intent,
            data=data_str
        )

        return [
            {"role": "system", "content": self.RESPONSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

    # =========================================================================
    # WORKFLOW ORCHESTRATION NODES (Fase 3: Workflow Nodes)
    # =========================================================================

    def _set_pending_question(
        self,
        state: ConversationState,
        question_type: str,
        question_text: str,
        **kwargs
    ) -> None:
        """
        Helper standardizzato per impostare pending_question con nonce.
        FIXES: Standardizza pending_question e needs_clarification insieme.

        Args:
            state: Conversation state
            question_type: Tipo domanda (strategy_choice, param_collection, etc.)
            question_text: Testo domanda
            **kwargs: Parametri aggiuntivi (strategy_id, param_name, etc.)
        """
        from .workflow_validator import WorkflowValidator

        workflow_nonce = state.get("workflow_nonce")
        if not workflow_nonce:
            workflow_nonce = WorkflowValidator.create_workflow_nonce()
            state["workflow_nonce"] = workflow_nonce

        state["pending_question"] = {
            "type": question_type,
            "question": question_text,
            "workflow_nonce": workflow_nonce,
            **kwargs
        }
        state["needs_clarification"] = True  # Sincronizza sempre

    def _needs_strategy_presentation(self, state: ConversationState) -> bool:
        """
        Determina se la richiesta è abbastanza ambigua da richiedere
        presentazione di strategie alternative.

        Args:
            state: Conversation state

        Returns:
            True se serve presentazione strategie
        """
        intent = state.get("intent")
        message = state.get("message", "").lower()
        slots = state.get("slots", {})

        from .workflow_strategies import get_strategy_config
        strategy_config = get_strategy_config(intent)

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

    def _track_metric(self, metric_name: str, properties: Dict[str, Any]) -> None:
        """
        Helper per telemetria workflow.
        TELEMETRY: Track workflow events per monitorare usage patterns.

        Args:
            metric_name: Nome metrica
            properties: Proprietà metrica
        """
        # TODO: Integrazione con sistema monitoring (Prometheus/Datadog)
        # Per ora: log strutturato
        import logging
        logger = logging.getLogger("workflow_telemetry")
        logger.info(f"[TELEMETRY] {metric_name}", extra=properties)

    def _present_strategies_node(self, state: ConversationState) -> ConversationState:
        """
        Presenta strategie alternative all'utente con security validation.
        TELEMETRY: Track strategy presentation frequency.

        Args:
            state: Conversation state

        Returns:
            Updated state con opzioni e pending_question
        """
        import time
        intent = state.get("intent")
        from .workflow_strategies import get_strategy_config
        from .workflow_validator import WorkflowValidator

        strategy_config = get_strategy_config(intent)
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

        # Genera workflow_id e nonce
        workflow_id = f"{intent}_{int(time.time())}"
        workflow_nonce = WorkflowValidator.create_workflow_nonce()

        # Aggiorna state workflow
        state["workflow_stage"] = WorkflowStage.CHOOSING.value
        state["workflow_id"] = workflow_id
        state["workflow_nonce"] = workflow_nonce
        state["workflow_type"] = intent
        state["workflow_context"] = {
            "available_strategies": strategies,
            "current_strategy_index": 0,
            "selected_strategy": None  # Sarà popolato dopo scelta
        }
        state["available_options"] = options
        state["workflow_history"] = []

        # Usa helper standardizzato per pending_question
        self._set_pending_question(
            state,
            question_type="strategy_choice",
            question_text=initial_question
        )

        # Costruisci risposta con numerazione chiara per UX
        response_parts = [initial_question, ""]  # Linea vuota per separazione
        for i, opt in enumerate(options, 1):
            response_parts.append(f"{i}. **{opt['label']}**: {opt['description']}")
        response_parts.append("\n*Rispondi con il numero (1, 2, 3) o il nome della strategia.*")

        state["final_response"] = "\n".join(response_parts)

        # TELEMETRY
        self._track_metric("workflow_strategy_presentation", {"intent": intent, "num_strategies": len(strategies)})

        return state

    def _handle_strategy_choice_node(self, state: ConversationState) -> ConversationState:
        """
        Gestisce la scelta dell'utente tra strategie.
        FIXED: Persiste selected_strategy in workflow_context.

        Args:
            state: Conversation state

        Returns:
            Updated state
        """
        import time
        choice_id = state.get("slots", {}).get("strategy_choice")
        workflow_ctx = state.get("workflow_context", {})
        strategies = workflow_ctx.get("available_strategies", [])

        # Trova strategia scelta
        selected = next((s for s in strategies if s["id"] == choice_id), None)

        if not selected:
            state["final_response"] = (
                "Non ho capito la tua scelta. "
                "Rispondi con il numero (1, 2, 3) o il nome della strategia."
            )
            self._set_pending_question(
                state,
                question_type="strategy_choice",
                question_text=state["final_response"]
            )
            return state

        # FIXED: Persiste selected_strategy in workflow_context
        workflow_ctx["selected_strategy"] = selected
        state["workflow_context"] = workflow_ctx

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
            state["workflow_stage"] = WorkflowStage.COLLECTING.value

            # Controlla quali parametri mancano
            slots = state.get("slots", {})
            missing_params = [p for p in required_params if p not in slots]

            if missing_params:
                # Chiedi primo parametro mancante
                param_name = missing_params[0]
                question = self._get_param_question(selected, param_name)

                # Usa helper standardizzato
                self._set_pending_question(
                    state,
                    question_type="param_collection",
                    question_text=question,
                    param_name=param_name
                )
                state["final_response"] = question
                return state

        # Tutti i parametri presenti: esegui tool
        state["workflow_stage"] = WorkflowStage.EXECUTING.value
        state["intent"] = selected["intent_mapping"]

        # Esegui tool corrispondente
        tool_output = self._execute_strategy_tool(selected, state)
        state["tool_output"] = tool_output

        return state

    def _collect_params_node(self, state: ConversationState) -> ConversationState:
        """
        Raccoglie parametri progressivamente dall'utente.

        Args:
            state: Conversation state

        Returns:
            Updated state
        """
        workflow_ctx = state.get("workflow_context", {})
        selected = workflow_ctx.get("selected_strategy")

        if not selected:
            # Fallback se selected_strategy mancante (non dovrebbe accadere)
            state["error"] = "Workflow context corrupted"
            state["final_response"] = "Si è verificato un errore. Riprova dall'inizio."
            return state

        required_params = selected.get("requires_params", [])
        slots = state.get("slots", {})

        # Controlla parametri ancora mancanti
        missing_params = [p for p in required_params if p not in slots]

        if missing_params:
            # Chiedi prossimo parametro
            param_name = missing_params[0]
            question = self._get_param_question(selected, param_name)

            # Usa helper standardizzato
            self._set_pending_question(
                state,
                question_type="param_collection",
                question_text=question,
                param_name=param_name
            )
            state["final_response"] = question
            return state

        # Tutti parametri raccolti: esegui
        state["workflow_stage"] = WorkflowStage.EXECUTING.value
        state["intent"] = selected["intent_mapping"]

        tool_output = self._execute_strategy_tool(selected, state)
        state["tool_output"] = tool_output

        return state

    def _handle_oppure_node(self, state: ConversationState) -> ConversationState:
        """
        Gestisce richiesta 'oppure?' per mostrare strategia successiva.
        FIXED: Gestione esplicita oppure_confirmation con strategy_id.
        TELEMETRY: Track oppure usage frequency.

        Args:
            state: Conversation state

        Returns:
            Updated state
        """
        workflow_ctx = state.get("workflow_context", {})
        strategies = workflow_ctx.get("available_strategies", [])
        current_idx = workflow_ctx.get("current_strategy_index", 0)

        if not strategies:
            state["final_response"] = "Non ci sono altre alternative disponibili."
            return state

        # Passa alla prossima strategia
        next_idx = (current_idx + 1) % len(strategies)
        next_strategy = strategies[next_idx]

        workflow_ctx["current_strategy_index"] = next_idx
        state["workflow_context"] = workflow_ctx

        # Presenta prossima strategia
        state["final_response"] = (
            f"**Alternativa {next_idx + 1}**: {next_strategy['label']}\n\n"
            f"{next_strategy['description']}\n\n"
            f"Vuoi procedere con questa strategia? (rispondi *sì* o *no*)"
        )

        # FIXED: Usa helper standardizzato con strategy_id
        self._set_pending_question(
            state,
            question_type="oppure_confirmation",
            question_text=state["final_response"],
            strategy_id=next_strategy["id"]
        )

        # TELEMETRY
        self._track_metric("workflow_oppure_request", {"workflow_type": state.get("workflow_type")})

        return state

    def _refine_query_node(self, state: ConversationState) -> ConversationState:
        """
        Applica filtri di raffinamento alla query precedente.
        FIXED: Usa allowlist per tool execution invece di getattr.
        TELEMETRY: Track refinement usage.

        Args:
            state: Conversation state

        Returns:
            Updated state
        """
        from .workflow_validator import WorkflowValidator

        workflow_ctx = state.get("workflow_context", {})
        previous_query = workflow_ctx.get("last_query", {})

        if not previous_query:
            state["final_response"] = "Non c'è una ricerca precedente da raffinare."
            return state

        # Merge filtri esistenti con nuovi (validati)
        existing_filters = state.get("accumulated_filters", {})
        new_filters = state.get("slots", {})
        merged_filters = {**existing_filters, **new_filters}

        # Valida filtri merged
        validated_filters = WorkflowValidator.validate_filters(merged_filters)

        state["accumulated_filters"] = validated_filters
        state["workflow_stage"] = WorkflowStage.REFINING.value

        # Ri-esegui tool con filtri aggiuntivi
        intent = previous_query.get("intent")
        slots = {**previous_query.get("slots", {}), **validated_filters}

        state["intent"] = intent
        state["slots"] = slots

        # FIXED: Usa allowlist esplicita per tool execution
        tool_allowlist = {
            "ask_suggest_controls": self._suggest_controls_tool,
            "ask_priority_establishment": self._priority_establishment_tool,
            "ask_risk_based_priority": self._risk_predictor_tool,
            "ask_delayed_plans": self._delayed_plans_tool,
            "ask_establishment_history": self._establishment_history_tool,
            "search_piani_by_topic": self._search_piani_tool,
        }

        tool_method = tool_allowlist.get(intent)
        if tool_method:
            result_state = tool_method(state)
            state["tool_output"] = result_state.get("tool_output")
        else:
            state["error"] = f"Refinement not supported for intent: {intent}"
            state["final_response"] = "Impossibile raffinare questa ricerca."

        # Salva query per futuri raffinamenti
        workflow_ctx["last_query"] = {
            "intent": intent,
            "slots": slots
        }
        state["workflow_context"] = workflow_ctx

        # TELEMETRY
        self._track_metric("workflow_refinement", {
            "intent": intent,
            "filters_applied": list(validated_filters.keys())
        })

        # Mostra filtri applicati all'utente (migliora UX)
        filter_description = ", ".join([f"{k}: {v}" for k, v in validated_filters.items()])
        state["final_response"] = f"Ricerca raffinata con filtri: {filter_description}\n\n" + state.get("final_response", "")

        return state

    def _get_param_question(self, strategy: Dict, param_name: str) -> str:
        """
        Genera domanda per raccogliere parametro specifico.

        Args:
            strategy: Strategia selezionata
            param_name: Nome parametro

        Returns:
            Testo domanda
        """
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
        """
        Esegue il tool corrispondente alla strategia.
        FIXED: Usa allowlist esplicita per tool execution.
        SECURITY: Valida intent_mapping contro STRATEGY_TO_INTENT_MAP.

        Args:
            strategy: Strategia da eseguire
            state: Conversation state

        Returns:
            Tool output
        """
        from .workflow_strategies import STRATEGY_TO_INTENT_MAP

        strategy_id = strategy.get("id")
        intent_mapping = strategy.get("intent_mapping")

        # CRITICAL: Valida strategy_id contro allowlist
        expected_intent = STRATEGY_TO_INTENT_MAP.get(strategy_id)
        if not expected_intent or expected_intent != intent_mapping:
            return {"error": "Invalid strategy mapping"}

        # Allowlist esplicita per tool execution
        tool_allowlist = {
            "ask_delayed_plans": self._delayed_plans_tool,
            "ask_top_risk_activities": self._top_risk_activities_tool,
            "ask_risk_based_priority": self._risk_predictor_tool,
            "ask_suggest_controls": self._suggest_controls_tool,
            "ask_priority_establishment": self._priority_establishment_tool,
        }

        tool_method = tool_allowlist.get(intent_mapping)
        if tool_method:
            result_state = tool_method(state)
            return result_state.get("tool_output")

        return {"error": "Tool not found in allowlist"}

    def run(
        self,
        message: str,
        metadata: Dict[str, Any] = None,
        detail_context: Dict[str, Any] = None,
        workflow_context: Dict[str, Any] = None,  # NUOVO parametro
        event_callback = None
    ) -> Dict[str, Any]:
        """
        Execute conversation graph with workflow context.

        Args:
            message: User message
            metadata: Session metadata
            detail_context: Detail context for 2-phase flow
            workflow_context: Validated workflow context (NUOVO)
            event_callback: Event callback

        Returns:
            Result dict con response, intent, slots, workflow fields
        """
        # Merge detail_context into metadata if provided (for 2-phase flow)
        effective_metadata = metadata or {}
        if detail_context:
            effective_metadata = {**effective_metadata, "detail_context": detail_context}

        # Imposta event_callback come attributo di istanza (non serializzato in state)
        self._event_callback = event_callback

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
                # Workflow fields (opzionali)
                "workflow_stage": workflow_context.get("workflow_stage") if workflow_context else None,
                "workflow_id": workflow_context.get("workflow_id") if workflow_context else None,
                "workflow_nonce": workflow_context.get("workflow_nonce") if workflow_context else None,
                "workflow_type": workflow_context.get("workflow_type") if workflow_context else None,
                "workflow_context": workflow_context or {},
                "pending_question": workflow_context.get("pending_question") if workflow_context else None,
                "available_options": workflow_context.get("available_options") if workflow_context else None,
                "workflow_history": workflow_context.get("workflow_history") if workflow_context else [],
                "accumulated_filters": workflow_context.get("accumulated_filters") if workflow_context else {},
                # NUOVO: Fallback recovery fields (opzionali)
                "fallback_suggestions": effective_metadata.get("_fallback_suggestions"),
                "fallback_phase": effective_metadata.get("_fallback_phase"),
                "fallback_count": effective_metadata.get("_fallback_count"),
                "fallback_selected_category": effective_metadata.get("_fallback_selected_category"),
            }

            final_state = self.graph.invoke(initial_state)

            return {
                "response": final_state["final_response"],
                "intent": final_state["intent"],
                "slots": final_state["slots"],
                "needs_clarification": final_state["needs_clarification"],
                "error": final_state.get("error", ""),
                "has_more_details": final_state.get("has_more_details", False),
                "detail_context": final_state.get("detail_context", {}),
                # NUOVO: Workflow fields nel result
                "workflow_stage": final_state.get("workflow_stage"),
                "workflow_id": final_state.get("workflow_id"),
                "workflow_nonce": final_state.get("workflow_nonce"),
                "workflow_type": final_state.get("workflow_type"),
                "workflow_context": final_state.get("workflow_context", {}),
                "pending_question": final_state.get("pending_question"),
                "available_options": final_state.get("available_options"),
                "workflow_history": final_state.get("workflow_history"),
                "accumulated_filters": final_state.get("accumulated_filters"),
                # NUOVO: Fallback recovery fields nel result
                "fallback_suggestions": final_state.get("fallback_suggestions"),
                "fallback_phase": final_state.get("fallback_phase"),
                "fallback_count": final_state.get("fallback_count"),
                "fallback_selected_category": final_state.get("fallback_selected_category"),
            }
        finally:
            # Pulisce il callback dopo l'esecuzione
            self._event_callback = None
