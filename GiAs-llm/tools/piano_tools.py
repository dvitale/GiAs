from typing import Dict, Any, Optional

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(name):
        def decorator(func):
            return func
        return decorator

try:
    from agents.data_agent import DataRetriever, BusinessLogic
    from agents.response_agent import ResponseFormatter
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever, BusinessLogic
    from agents.response_agent import ResponseFormatter


@tool("piano_description")
def get_piano_description(piano_code: str) -> Dict[str, Any]:
    """
    Recupera la descrizione completa di un piano di controllo.

    Args:
        piano_code: Codice del piano (es. "A1", "B2")

    Returns:
        Dict con descrizione piano o messaggio di errore
    """
    if not piano_code:
        return {
            "error": "Piano code non specificato",
            "formatted_response": "Devi specificare un codice piano valido (es. A1, B2, C3)."
        }

    piano_rows = DataRetriever.get_piano_by_id(piano_code)

    if piano_rows is None or piano_rows.empty:
        return {
            "error": f"Piano {piano_code} non trovato",
            "formatted_response": f"Il piano **{piano_code}** non è presente nel database dei piani di monitoraggio. Verifica il codice e riprova."
        }

    unique_descriptions = BusinessLogic.extract_unique_piano_descriptions(piano_rows)
    total_variants = len(piano_rows)

    response = ResponseFormatter.format_piano_description(
        piano_id=piano_code,
        unique_descriptions=unique_descriptions,
        total_variants=total_variants
    )

    return {
        "piano_code": piano_code,
        "formatted_response": response,
        "total_variants": total_variants,
        "raw_data": unique_descriptions
    }


@tool("piano_attivita")
def get_piano_attivita(piano_code: str) -> Dict[str, Any]:
    """
    Recupera gli stabilimenti controllati per un piano specifico.

    Args:
        piano_code: Codice del piano (es. "A1", "B2")

    Returns:
        Dict con analisi stabilimenti o messaggio di errore
    """
    if not piano_code:
        return {
            "error": "Piano code non specificato",
            "formatted_response": "Devi specificare un codice piano valido (es. A1, B2, C3)."
        }

    controlli_df = DataRetriever.get_controlli_by_piano(piano_code)

    if controlli_df is None or controlli_df.empty:
        return {
            "error": f"Nessun controllo trovato per il piano {piano_code}",
            "piano_code": piano_code,
            "formatted_response": f"Non ci sono controlli eseguiti nel 2025 per il piano **{piano_code}**. Questo potrebbe significare che:\n\n- Il piano non ha ancora avuto controlli eseguiti\n- Il codice piano non corrisponde esattamente a quelli nei dati\n\nProva a cercare piani simili o chiedi informazioni sui piani disponibili."
        }

    top_stabilimenti = BusinessLogic.aggregate_stabilimenti_by_piano(controlli_df, top_n=10)

    if top_stabilimenti.empty:
        return {
            "error": f"Nessuno stabilimento trovato per il piano {piano_code}",
            "piano_code": piano_code,
            "formatted_response": f"Non ci sono stabilimenti associati al piano **{piano_code}** nei controlli del 2025."
        }

    piano_desc = controlli_df['descrizione_piano'].iloc[0]
    total_controls = controlli_df.shape[0]
    unique_establishments = len(controlli_df.groupby(['macroarea_cu', 'aggregazione_cu']).size())

    response = ResponseFormatter.format_stabilimenti_analysis(
        piano_id=piano_code,
        piano_desc=piano_desc,
        top_stabilimenti=top_stabilimenti,
        total_controls=total_controls,
        unique_establishments=unique_establishments
    )

    top_stabilimenti_dict = top_stabilimenti.to_dict(orient='records')

    return {
        "piano_code": piano_code,
        "piano_description": piano_desc,
        "total_controls": total_controls,
        "unique_establishments": unique_establishments,
        "top_stabilimenti": top_stabilimenti_dict,
        "formatted_response": response
    }


@tool("piano_correlation")
def get_piano_correlation(piano_code: str) -> Dict[str, Any]:
    """
    Trova la correlazione statistica tra piano e attività dai controlli 2025.

    Args:
        piano_code: Codice del piano (es. "A1", "B2")

    Returns:
        Dict con attività correlate o messaggio di errore
    """
    if not piano_code:
        return {
            "error": "Piano code non specificato",
            "formatted_response": "Devi specificare un codice piano valido (es. A1, B2, C3)."
        }

    related_activities = BusinessLogic.correlate_piano_attivita(piano_code)

    if related_activities.empty:
        return {
            "error": f"Nessuna attività correlata trovata per il piano {piano_code}",
            "piano_code": piano_code,
            "formatted_response": f"Non ho trovato attività correlate al piano **{piano_code}** nei controlli del 2025."
        }

    activities_list = related_activities.to_dict(orient='records')

    return {
        "piano_code": piano_code,
        "activities": activities_list,
        "total_activities": len(activities_list)
    }


@tool("compare_piani")
def compare_piani(piano1_code: str, piano2_code: str) -> Dict[str, Any]:
    """
    Confronta due piani di controllo.

    Args:
        piano1_code: Codice del primo piano
        piano2_code: Codice del secondo piano

    Returns:
        Dict con confronto metriche o messaggio di errore
    """
    if not piano1_code or not piano2_code:
        return {
            "error": "Entrambi i codici piano devono essere specificati",
            "formatted_response": "Per confrontare due piani, devi specificare entrambi i codici (es. A1 e A2)."
        }

    metrics = BusinessLogic.compare_plans_metrics(piano1_code, piano2_code)

    response = ResponseFormatter.format_comparison(piano1_code, piano2_code, metrics)

    return {
        "piano1_code": piano1_code,
        "piano2_code": piano2_code,
        "metrics": metrics,
        "formatted_response": response
    }


@tool("piano_statistics")
def get_piano_statistics(asl: Optional[str] = None, top_n: int = 10) -> Dict[str, Any]:
    """
    Recupera statistiche aggregate sui piani di controllo eseguiti.

    Args:
        asl: Codice o nome ASL per filtrare (es. "AVELLINO", "NA1") (opzionale)
        top_n: Numero di piani da includere nelle statistiche (default: 10)

    Returns:
        Dict con statistiche piani o messaggio di errore
    """
    try:
        stats_df = BusinessLogic.get_piano_statistics(asl=asl, top_n=top_n)

        if stats_df.empty:
            error_msg = f"Non sono disponibili statistiche sui controlli"
            if asl:
                error_msg += f" per l'ASL **{asl}**"
            error_msg += "."

            return {
                "error": "No statistics available",
                "asl": asl,
                "formatted_response": error_msg
            }

        response = ResponseFormatter.format_piano_statistics(stats_df, asl=asl)

        stats_dict = stats_df.to_dict(orient='records')

        return {
            "asl": asl,
            "top_n": top_n,
            "total_plans": len(stats_df),
            "total_controls": int(stats_df['num_controlli'].sum()),
            "statistics": stats_dict,
            "formatted_response": response
        }

    except Exception as e:
        return {
            "error": f"Errore nel calcolo delle statistiche: {str(e)}",
            "formatted_response": f"Si è verificato un errore durante il calcolo delle statistiche: {str(e)}"
        }


def piano_tool(action: str, piano_code: Optional[str] = None, piano2_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Router per funzionalità piano.

    Args:
        action: Tipo di azione ("description", "attivita", "correlation", "compare", "generic")
        piano_code: Codice del piano principale
        piano2_code: Codice del secondo piano (solo per compare)

    Returns:
        Dict con risultati o messaggio di errore
    """

    try:
        get_desc_func = get_piano_description.func if hasattr(get_piano_description, 'func') else get_piano_description
        get_att_func = get_piano_attivita.func if hasattr(get_piano_attivita, 'func') else get_piano_attivita
        get_corr_func = get_piano_correlation.func if hasattr(get_piano_correlation, 'func') else get_piano_correlation
        compare_func = compare_piani.func if hasattr(compare_piani, 'func') else compare_piani

        if action == "description":
            return get_desc_func(piano_code)
        elif action in ("stabilimenti", "generic"):
            return get_att_func(piano_code)
        elif action == "correlation":
            return get_corr_func(piano_code)
        elif action == "compare":
            return compare_func(piano_code, piano2_code)
        else:
            return {
                "error": f"Azione non riconosciuta: {action}",
                "formatted_response": f"L'azione '{action}' non è supportata. Azioni valide: description, stabilimenti, generic, correlation, compare."
            }
    except Exception as e:
        return {
            "error": f"Errore in piano_tool: {str(e)}",
            "formatted_response": f"Si è verificato un errore durante l'elaborazione della richiesta: {str(e)}"
        }
