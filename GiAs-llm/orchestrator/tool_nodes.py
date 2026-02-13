"""
Tool nodes per il grafo LangGraph.

Ogni funzione è un nodo del grafo che:
1. Estrae slot/metadata dallo state
2. Chiama la funzione tool corrispondente
3. Applica two-phase check se necessario
4. Setta state["tool_output"]
"""

import logging
from typing import Dict, Any

try:
    from tools.piano_tools import piano_tool, get_piano_statistics
    from tools.priority_tools import priority_tool, suggest_controls
    from tools.risk_tools import risk_tool, analyze_nc_by_category, get_establishments_with_sanctions
    from tools.search_tools import search_tool
    from tools.establishment_tools import get_establishment_history
    from tools.risk_analysis_tools import get_top_risk_activities
    from tools.predictor_tools import get_ml_risk_prediction
    from tools.proximity_tools import get_nearby_priority
    from agents.response_agent import ResponseFormatter
    from configs.config import RiskPredictorConfig
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.piano_tools import piano_tool, get_piano_statistics
    from tools.priority_tools import priority_tool, suggest_controls
    from tools.risk_tools import risk_tool, analyze_nc_by_category, get_establishments_with_sanctions
    from tools.search_tools import search_tool
    from tools.establishment_tools import get_establishment_history
    from tools.risk_analysis_tools import get_top_risk_activities
    from tools.predictor_tools import get_ml_risk_prediction
    from tools.proximity_tools import get_nearby_priority
    from agents.response_agent import ResponseFormatter
    from configs.config import RiskPredictorConfig

from .two_phase import apply_two_phase_check, TWO_PHASE_THRESHOLDS

logger = logging.getLogger(__name__)


def _unwrap_tool(tool_ref):
    """Unwrap LangChain @tool decorated function to get the raw callable."""
    return tool_ref.func if hasattr(tool_ref, 'func') else tool_ref


# =============================================================================
# SIMPLE TOOLS (no DB queries)
# =============================================================================

def greet_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    state["tool_output"] = {
        "type": "greet",
        "data": {
            "formatted_response": "Benvenuto nel supporto conversazionale per il sistema GISA della Regione Campania."
        }
    }
    return state


def goodbye_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    state["tool_output"] = {
        "type": "goodbye",
        "data": {
            "formatted_response": "Arrivederci! Buon lavoro."
        }
    }
    return state


def help_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    formatted_response = "**Come posso aiutarti?**\n\n"
    formatted_response += "Ecco cosa posso fare, con esempi di domande:\n\n"
    formatted_response += "**📋 Piani di Controllo**\n"
    formatted_response += "- [Di cosa tratta il piano A1?]\n"
    formatted_response += "- [Quali stabilimenti per piano A1?]\n"
    formatted_response += "- [Statistiche piano A1]\n"
    formatted_response += "\n**🔍 Ricerca Piani**\n"
    formatted_response += "- [Cerca piani sulla sicurezza alimentare]\n"
    formatted_response += "- [Piani sul benessere animale]\n"
    formatted_response += "\n**⏰ Ritardi**\n"
    formatted_response += "- [Piani in ritardo]\n"
    formatted_response += "- [Il piano A1 è in ritardo?]\n"
    formatted_response += "\n**⚠️ Priorità e Rischio**\n"
    formatted_response += "- [Stabilimenti prioritari]\n"
    formatted_response += "- [Stabilimenti a rischio]\n"
    formatted_response += "- [Stabilimenti mai controllati]\n"
    formatted_response += "- [Attività più rischiose]\n"
    formatted_response += "\n**📍 Ricerca per Prossimità**\n"
    formatted_response += "- [Stabilimenti vicino a Piazza Risorgimento, Benevento]\n"
    formatted_response += "- [Controlli nei dintorni di Via Roma 15, Napoli entro 3 km]\n"
    formatted_response += "\n**📜 Storico e Analisi**\n"
    formatted_response += "- [Storico controlli stabilimento]\n"
    formatted_response += "- [Analisi NC per categoria]\n"
    formatted_response += "\n**📋 Procedure Operative**\n"
    formatted_response += "- [Qual e' la procedura per ispezione semplice?]\n"
    formatted_response += "- [Come si esegue un controllo ufficiale?]\n"

    state["tool_output"] = {
        "type": "help",
        "data": {
            "formatted_response": formatted_response
        }
    }
    return state


def confirm_details_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    """Gestisce la conferma per visualizzare i dettagli (two-phase)."""
    detail_context = state.get("metadata", {}).get("detail_context", {})

    if detail_context:
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
        # Sessione scaduta o contesto perso: guida l'utente a ripetere la domanda
        state["tool_output"] = {
            "type": "confirm_details",
            "data": {
                "confirmed": False,
                "detail_context": None,
                "formatted_response": (
                    "La sessione è scaduta e non ho più il contesto della richiesta precedente.\n\n"
                    "Per favore, ripeti la domanda originale. Ecco alcuni esempi:\n"
                    "- [[Stabilimenti a rischio]]\n"
                    "- [[Stabilimenti prioritari]]\n"
                    "- [[Piani che trattano di sicurezza alimentare]]"
                )
            }
        }
    return state


def decline_details_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    """Gestisce il rifiuto dei dettagli (two-phase)."""
    state["tool_output"] = {
        "type": "decline_details",
        "data": {
            "confirmed": False,
            "formatted_response": "Va bene! Se hai altre domande, sono qui per aiutarti."
        }
    }
    return state


# =============================================================================
# PIANO TOOLS
# =============================================================================

def piano_description_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    piano_code = state["slots"].get("piano_code")
    result = piano_tool(action="description", piano_code=piano_code)
    state["tool_output"] = {"type": "piano_description", "data": result}
    return state


def piano_stabilimenti_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    if event_callback:
        event_callback({
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
        if unique_establishments > TWO_PHASE_THRESHOLDS.get("ask_piano_stabilimenti", 2):
            top_stab_data = result.get("top_stabilimenti", [])
            top_stab_df = pd.DataFrame(top_stab_data) if isinstance(top_stab_data, list) else top_stab_data
            summary_text = ResponseFormatter.format_stabilimenti_analysis_summary(
                piano_id=result.get("piano_code", piano_code),
                piano_desc=result.get("piano_description", ""),
                top_stabilimenti=top_stab_df,
                total_controls=result.get("total_controls", 0),
                unique_establishments=unique_establishments
            )
            result = apply_two_phase_check(
                state, "ask_piano_stabilimenti", result, unique_establishments, summary_text
            )

    state["tool_output"] = {"type": "piano_stabilimenti", "data": result}
    return state


def piano_statistics_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    asl = state["metadata"].get("asl")
    piano_code = state["slots"].get("piano_code")
    message = state.get("message", "").lower()

    if piano_code:
        result = piano_tool(action="stabilimenti", piano_code=piano_code)

        count_keywords = ["quanti", "quante", "numero di", "conta", "totale controlli"]
        is_count_query = any(kw in message for kw in count_keywords)

        if is_count_query and result.get("total_controls") is not None:
            from agents.data_agent import DataRetriever
            import pandas as pd

            total = result.get("total_controls", 0)
            piano_desc = result.get("piano_description", piano_code.upper())

            controlli_df = DataRetriever.get_controlli_by_piano(piano_code)

            data_primo = None
            data_ultimo = None
            if controlli_df is not None and not controlli_df.empty and 'data_inizio_controllo' in controlli_df.columns:
                controlli_df['data_inizio_controllo'] = pd.to_datetime(controlli_df['data_inizio_controllo'], errors='coerce')
                data_primo = controlli_df['data_inizio_controllo'].min()
                data_ultimo = controlli_df['data_inizio_controllo'].max()

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

            formatted = f"Per il piano **{piano_code.upper()}** sono stati inseriti:\n\n"
            formatted += f"📊 **Totale regionale:** {total:,} controlli\n"
            if asl and asl_count > 0:
                formatted += f"🏥 **{asl_name or asl}:** {asl_count:,} controlli\n"
            elif asl:
                formatted += f"🏥 **La tua ASL ({asl}):** nessun controllo registrato\n"

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

    stats_func = _unwrap_tool(get_piano_statistics)
    result = stats_func(asl=asl, top_n=10)
    state["tool_output"] = {"type": "piano_statistics", "data": result}
    return state


def search_piani_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    topic = state["slots"].get("topic")
    result = search_tool(query=topic)

    if isinstance(result, dict):
        total_found = result.get("total_found", 0)
        matches = result.get("matches", [])
        if total_found > TWO_PHASE_THRESHOLDS.get("search_piani_by_topic", 5):
            search_term = result.get("search_term", topic or "")
            summary_text = ResponseFormatter.format_search_results_summary(
                search_term=search_term,
                matches=matches
            )
            result = apply_two_phase_check(
                state, "search_piani_by_topic", result, total_found, summary_text
            )

    state["tool_output"] = {"type": "search_piani", "data": result}
    return state


# =============================================================================
# PRIORITY & RISK TOOLS
# =============================================================================

def priority_establishment_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    from agents.data import get_uoc_from_user_id

    if event_callback:
        event_callback({
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

    if isinstance(result, dict):
        total_found = result.get("total_found", 0)
        if total_found > TWO_PHASE_THRESHOLDS.get("ask_priority_establishment", 5):
            summary_text = ResponseFormatter.format_priority_establishments_summary(result)
            result = apply_two_phase_check(
                state, "ask_priority_establishment", result, total_found, summary_text
            )

    state["tool_output"] = {"type": "priority_establishment", "data": result}
    return state


def risk_predictor_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    """Nodo risk predictor configurabile (ML o statistico).

    Gestisce disambiguazione tra:
    - mai_controllati: stabilimenti mai controllati (default)
    - con_sanzioni: stabilimenti con più NC storiche
    """
    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "risk_predictor_tool",
            "message": "Analizzando rischio stabilimenti..."
        })

    asl = state["metadata"].get("asl")
    piano_code = state["slots"].get("piano_code")
    tipo_analisi = state["slots"].get("tipo_analisi_rischio")

    # Se tipo_analisi non specificato, chiedi disambiguazione
    if not tipo_analisi:
        disambiguation_response = (
            "**🎯 Stabilimenti a Rischio**\n\n"
            "Quale tipo di analisi preferisci?\n\n"
            "**1. Mai controllati** 🔍\n"
            "   Stabilimenti che non hanno mai ricevuto controlli,\n"
            "   ordinati per rischio dell'attività svolta\n\n"
            "**2. Con più sanzioni** ⚠️\n"
            "   Stabilimenti con più non conformità (NC) storiche\n"
            "   riportate nei controlli effettuati\n\n"
            "*Rispondi con 1, 2, oppure \"mai controllati\" / \"con sanzioni\"*"
        )
        state["tool_output"] = {
            "type": "disambiguation",
            "data": {
                "formatted_response": disambiguation_response,
                "pending_intent": "ask_risk_based_priority",
                "options": ["mai_controllati", "con_sanzioni"]
            }
        }
        state["pending_question"] = True
        state["needs_clarification"] = True
        return state

    # Tipo analisi: con_sanzioni
    if tipo_analisi == "con_sanzioni":
        if event_callback:
            event_callback({
                "type": "reasoning",
                "node": "risk_predictor_tool",
                "message": "Cercando stabilimenti con più sanzioni..."
            })

        sanctions_func = _unwrap_tool(get_establishments_with_sanctions)
        result = sanctions_func(asl=asl, limit=20)
        output_type = "sanctions_analysis"

        if isinstance(result, dict):
            total = result.get("total", 0)
            if total > TWO_PHASE_THRESHOLDS.get("ask_risk_based_priority", 5):
                summary_text = (
                    f"Ho trovato **{total} stabilimenti** con non conformità "
                    f"per l'ASL **{asl or 'Regione'}**.\n\n"
                    "Vuoi vedere i dettagli dei top 10?"
                )
                result = apply_two_phase_check(
                    state, "ask_risk_based_priority", result, total, summary_text
                )

        state["tool_output"] = {"type": output_type, "data": result}
        return state

    # Tipo analisi: mai_controllati (default)
    predictor_type = RiskPredictorConfig.get_predictor_type()

    if predictor_type == "ml":
        ml_func = _unwrap_tool(get_ml_risk_prediction)
        result = ml_func(asl=asl, piano_code=piano_code)
        output_type = "ml_risk_prediction"
    else:
        result = risk_tool(asl=asl, piano_code=piano_code)
        output_type = "statistical_risk_prediction"

    if isinstance(result, dict):
        result["predictor_type"] = predictor_type

        total_risky = result.get("total_risky", 0)
        if total_risky > TWO_PHASE_THRESHOLDS.get("ask_risk_based_priority", 5):
            mapped_result = {
                "user_asl": result.get("asl", "N/D"),
                "piano_code": result.get("piano_code"),
                "osa_total_count": result.get("total_never_controlled", 0),
                "osa_risky_count": total_risky,
                "activities_count": result.get("activities_at_risk", 0),
                "osa_rischiosi": result.get("risky_establishments", []),
            }
            summary_text = ResponseFormatter.format_risk_based_priority_summary(mapped_result)
            result = apply_two_phase_check(
                state, "ask_risk_based_priority", result, total_risky, summary_text
            )

    state["tool_output"] = {"type": output_type, "data": result}
    return state


def suggest_controls_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    asl = state["metadata"].get("asl")

    suggest_func = _unwrap_tool(suggest_controls)
    result = suggest_func(asl=asl, limit=20)

    if isinstance(result, dict):
        total_never_controlled = result.get("total_never_controlled", 0)
        if total_never_controlled > TWO_PHASE_THRESHOLDS.get("ask_suggest_controls", 5):
            import pandas as pd
            summary_text = ResponseFormatter.format_suggest_controls(
                asl=asl,
                filtered_count=total_never_controlled,
                sample_df=pd.DataFrame(result.get("suggested_establishments", [])[:5]),
                limit=5
            )
            result = apply_two_phase_check(
                state, "ask_suggest_controls", result, total_never_controlled, summary_text
            )

    state["tool_output"] = {"type": "suggest_controls", "data": result}
    return state


def delayed_plans_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    from agents.data import get_uoc_from_user_id

    asl = state["metadata"].get("asl")
    uoc = state["metadata"].get("uoc")

    if not uoc and state["metadata"].get("user_id"):
        uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

    result = priority_tool(asl=asl, uoc=uoc, action="delayed_plans")
    state["tool_output"] = {"type": "delayed_plans", "data": result}
    return state


def check_plan_delayed_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    from agents.data import get_uoc_from_user_id
    from tools.priority_tools import get_delayed_plans

    asl = state["metadata"].get("asl")
    uoc = state["metadata"].get("uoc")
    piano_code = state["slots"].get("piano_code")

    if not uoc and state["metadata"].get("user_id"):
        uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

    delayed_func = _unwrap_tool(get_delayed_plans)
    result = delayed_func(asl=asl, uoc=uoc, piano_code=piano_code)
    state["tool_output"] = {"type": "check_plan_delayed", "data": result}
    return state


def establishment_history_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    num_registrazione = state["slots"].get("num_registrazione")
    numero_riconoscimento = state["slots"].get("numero_riconoscimento")
    partita_iva = state["slots"].get("partita_iva")
    ragione_sociale = state["slots"].get("ragione_sociale")

    history_func = _unwrap_tool(get_establishment_history)
    result = history_func(
        num_registrazione=num_registrazione,
        numero_riconoscimento=numero_riconoscimento,
        partita_iva=partita_iva,
        ragione_sociale=ragione_sociale
    )

    if isinstance(result, dict):
        total_controls = result.get("total_controls", 0)
        if total_controls > TWO_PHASE_THRESHOLDS.get("ask_establishment_history", 5):
            summary_text = ResponseFormatter.format_establishment_history_summary(result)
            result = apply_two_phase_check(
                state, "ask_establishment_history", result, total_controls, summary_text
            )

    state["tool_output"] = {"type": "establishment_history", "data": result}
    return state


def top_risk_activities_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    limit = state["slots"].get("limit", 10)

    top_risk_func = _unwrap_tool(get_top_risk_activities)
    result = top_risk_func(limit=limit)

    state["tool_output"] = {"type": "top_risk_activities", "data": result}
    return state


def analyze_nc_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    categoria = state["slots"].get("categoria", "HACCP")
    asl = state["metadata"].get("asl")

    analyze_nc_func = _unwrap_tool(analyze_nc_by_category)
    result = analyze_nc_func(categoria=categoria, asl=asl)

    state["tool_output"] = {"type": "analyze_nc_by_category", "data": result}
    return state


def info_procedure_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    """RAG tool per informazioni su procedure operative documentate."""
    query = state.get("message", "")

    from tools.procedure_tools import get_procedure_info
    func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
    result = func(query=query)

    state["tool_output"] = {"type": "info_procedure", "data": result}
    return state


def nearby_priority_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    """Tool per ricerca stabilimenti per prossimità geografica."""
    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "nearby_priority_tool",
            "message": "Geocodificando indirizzo e cercando stabilimenti vicini..."
        })

    location = state["slots"].get("location")
    radius_km = state["slots"].get("radius_km", 5.0)
    asl = state["metadata"].get("asl")

    nearby_func = _unwrap_tool(get_nearby_priority)
    result = nearby_func(location=location, radius_km=radius_km, asl=asl)

    # Two-phase check se troppi risultati
    if isinstance(result, dict):
        total_found = result.get("total_found", 0)
        if total_found > TWO_PHASE_THRESHOLDS.get("ask_nearby_priority", 10):
            summary_text = ResponseFormatter.format_nearby_priority_summary(result)
            result = apply_two_phase_check(
                state, "ask_nearby_priority", result, total_found, summary_text
            )

    state["tool_output"] = {"type": "nearby_priority", "data": result}
    return state


# =============================================================================
# TOOL REGISTRY: mappa nome nodo → funzione
# =============================================================================

TOOL_REGISTRY = {
    "greet_tool": greet_tool,
    "goodbye_tool": goodbye_tool,
    "help_tool": help_tool,
    "piano_description_tool": piano_description_tool,
    "piano_stabilimenti_tool": piano_stabilimenti_tool,
    "piano_statistics_tool": piano_statistics_tool,
    "search_piani_tool": search_piani_tool,
    "priority_establishment_tool": priority_establishment_tool,
    "risk_predictor_tool": risk_predictor_tool,
    "suggest_controls_tool": suggest_controls_tool,
    "nearby_priority_tool": nearby_priority_tool,
    "delayed_plans_tool": delayed_plans_tool,
    "check_plan_delayed_tool": check_plan_delayed_tool,
    "establishment_history_tool": establishment_history_tool,
    "top_risk_activities_tool": top_risk_activities_tool,
    "analyze_nc_tool": analyze_nc_tool,
    "info_procedure_tool": info_procedure_tool,
    "confirm_details_tool": confirm_details_tool,
    "decline_details_tool": decline_details_tool,
}

# Mapping intent → nome nodo tool
INTENT_TO_TOOL = {
    "greet": "greet_tool",
    "goodbye": "goodbye_tool",
    "ask_help": "help_tool",
    "ask_piano_description": "piano_description_tool",
    "ask_piano_stabilimenti": "piano_stabilimenti_tool",
    "ask_piano_statistics": "piano_statistics_tool",
    "search_piani_by_topic": "search_piani_tool",
    "ask_priority_establishment": "priority_establishment_tool",
    "ask_risk_based_priority": "risk_predictor_tool",
    "ask_suggest_controls": "suggest_controls_tool",
    "ask_nearby_priority": "nearby_priority_tool",
    "ask_delayed_plans": "delayed_plans_tool",
    "check_if_plan_delayed": "check_plan_delayed_tool",
    "ask_establishment_history": "establishment_history_tool",
    "ask_top_risk_activities": "top_risk_activities_tool",
    "analyze_nc_by_category": "analyze_nc_tool",
    "info_procedure": "info_procedure_tool",
    "confirm_show_details": "confirm_details_tool",
    "decline_show_details": "decline_details_tool",
}
