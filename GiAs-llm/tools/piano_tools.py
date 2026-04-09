# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportArgumentType=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOptionalOperand=false, reportReturnType=false, reportAssignmentType=false, reportPossiblyUnboundVariable=false
from typing import Dict, Any, Optional
import pandas as pd

from tools._tool_compat import tool

try:
    from agents.data_agent import DataRetriever, BusinessLogic
    from agents.response_agent import ResponseFormatter
    from data_sources.repositories import get_piano_repository
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever, BusinessLogic
    from agents.response_agent import ResponseFormatter
    from data_sources.repositories import get_piano_repository


def _build_mismatch_prefix(entity_hint: Optional[str], entity_type: str, piano_code: str) -> str:
    """
    Se l'utente ha esplicitato "piano X" ma X è in realtà un'attività (o viceversa),
    restituisce un avviso conversazionale da anteporre alla risposta. Altrimenti "".
    """
    if not entity_hint or entity_hint == entity_type:
        return ""
    code = (piano_code or "").upper().strip()
    if code.startswith("ATT "):
        code = code[4:]
    if entity_hint == "piano" and entity_type == "attivita":
        return (
            f"> ℹ️ `{code}` non è un piano di controllo, ma un'**attività di monitoraggio**. "
            f"Ti mostro comunque i dati dell'attività corrispondente.\n\n"
        )
    if entity_hint == "attivita" and entity_type == "piano":
        return (
            f"> ℹ️ `{code}` non è un'attività, ma un **piano di controllo**. "
            f"Ti mostro comunque i dati del piano corrispondente.\n\n"
        )
    return ""


def _detect_entity_type(df: pd.DataFrame, piano_code: str = "") -> str:
    """Rileva se i dati si riferiscono a piano o attività.

    Strategia:
    1. Controlla tipo_piano_attivita nel DataFrame (ground truth)
    2. Fallback: prefisso ATT nel piano_code (impostato da _extract_slots
       quando l'utente dice "attività X")
    Il fallback è necessario perché in cu_eseguiti_nc le righe attività
    hanno tipo_piano_attivita NULL (non 'attivita').
    """
    if "tipo_piano_attivita" in df.columns:
        if df["tipo_piano_attivita"].str.lower().eq("attivita").any():
            return "attivita"
    if piano_code and str(piano_code).strip().upper().startswith("ATT"):
        return "attivita"
    return "piano"


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

    # Repository lookup — pandas (default) o sql, governato dal flag
    # data_source.repositories.piano in config.json
    piano_repo = get_piano_repository()
    piano_rows = piano_repo.find_by_alias(piano_code)

    if piano_rows is None or piano_rows.empty:
        return {
            "error": f"Piano {piano_code} non trovato",
            "formatted_response": f"Il piano **{piano_code}** non è presente nel database dei piani di monitoraggio. Verifica il codice e riprova."
        }

    entity_type = _detect_entity_type(piano_rows, piano_code)
    unique_descriptions = BusinessLogic.extract_unique_piano_descriptions(piano_rows)
    total_variants = len(piano_rows)

    response = ResponseFormatter.format_piano_description(
        piano_id=piano_code,
        unique_descriptions=unique_descriptions,
        total_variants=total_variants,
        entity_type=entity_type
    )

    return {
        "piano_code": piano_code,
        "entity_type": entity_type,
        "formatted_response": response,
        "total_variants": total_variants,
        "raw_data": unique_descriptions
    }


@tool("piano_attivita")
def get_piano_attivita(piano_code: str, entity_hint: Optional[str] = None, user_uos: Optional[str] = None) -> Dict[str, Any]:
    """
    Recupera gli stabilimenti controllati per un piano specifico.

    Args:
        piano_code: Codice del piano (es. "A1", "B2")
        entity_hint: "piano" | "attivita" se l'utente lo ha esplicitato nel
            messaggio. Usato per evidenziare eventuali mismatch.
        user_uos: UOS dell'utente collegato. Quando valorizzata, i "controlli
            eseguiti" vengono filtrati sulla sua UOS (scope operativo).

    Returns:
        Dict con analisi stabilimenti o messaggio di errore
    """
    if not piano_code:
        return {
            "error": "Piano code non specificato",
            "formatted_response": "Devi specificare un codice piano valido (es. A1, B2, C3)."
        }

    # Anno corrente per filtro temporale
    try:
        from configs.config_loader import get_config
        current_year = get_config().get_current_year()
    except Exception:
        from datetime import datetime as _dt
        current_year = _dt.now().year

    controlli_df = DataRetriever.get_controlli_by_piano(piano_code)

    # Filtra per anno corrente sulla data_inizio_controllo (se colonna presente)
    if controlli_df is not None and not controlli_df.empty and "data_inizio_controllo" in controlli_df.columns:
        years = pd.to_datetime(controlli_df["data_inizio_controllo"], errors="coerce").dt.year
        controlli_df = controlli_df[years == current_year]

    # Scope UOS utente: i "controlli eseguiti" sono sempre filtrati sulla UOS
    # dell'operatore collegato. Se user_uos non è valorizzato (es. metadata
    # assente in test/dev), nessun filtro viene applicato.
    had_rows_before_uos_filter = controlli_df is not None and not controlli_df.empty
    total_controls_all = controlli_df.shape[0] if had_rows_before_uos_filter else 0
    if user_uos and had_rows_before_uos_filter:
        from agents.utils import filter_by_uos
        controlli_df = filter_by_uos(controlli_df, user_uos, "descrizione_uos")
    uos_scope_label = f" — UOS **{user_uos}**" if user_uos else ""

    if controlli_df is None or controlli_df.empty:
        # Deduci entity_type da piani_monitoraggio per coerenza lessicale
        piano_rows = DataRetriever.get_piano_by_id(piano_code)
        fallback_entity = _detect_entity_type(piano_rows, piano_code) if piano_rows is not None else "piano"
        entity_label = "attività" if fallback_entity == "attivita" else "piano"
        mismatch_prefix = _build_mismatch_prefix(entity_hint, fallback_entity, piano_code)

        # Messaggio: distingui "zero a livello globale" da "zero nella tua UOS"
        if user_uos and had_rows_before_uos_filter:
            body = (
                f"Non risultano controlli eseguiti nel {current_year} per {entity_label} "
                f"**{piano_code}** dalla tua UOS (**{user_uos}**). "
                f"Altri operatori potrebbero averne eseguiti — la vista è limitata al tuo scope operativo."
            )
        else:
            body = (
                f"Non ci sono controlli eseguiti nel {current_year} per {entity_label} "
                f"**{piano_code}**{uos_scope_label}. Questo potrebbe significare che:\n\n"
                f"- Il codice non ha ancora avuto controlli eseguiti\n"
                f"- Il codice non corrisponde esattamente a quelli nei dati\n\n"
                f"Prova a cercare piani simili o chiedi informazioni sui piani disponibili."
            )
        return {
            "error": f"Nessun controllo trovato per {entity_label} {piano_code}",
            "piano_code": piano_code,
            "entity_type": fallback_entity,
            "entity_hint": entity_hint,
            "anno": current_year,
            "user_uos": user_uos,
            "formatted_response": f"{mismatch_prefix}{body}"
        }

    entity_type = _detect_entity_type(controlli_df, piano_code)

    top_stabilimenti = BusinessLogic.aggregate_stabilimenti_by_piano(controlli_df, top_n=10)

    if top_stabilimenti.empty:
        entity_label = "all'attività" if entity_type == "attivita" else "al piano"
        mismatch_prefix = _build_mismatch_prefix(entity_hint, entity_type, piano_code)
        return {
            "error": f"Nessuno stabilimento trovato per {piano_code}",
            "piano_code": piano_code,
            "entity_type": entity_type,
            "entity_hint": entity_hint,
            "anno": current_year,
            "formatted_response": f"{mismatch_prefix}Non ci sono stabilimenti associati {entity_label} **{piano_code}** nei controlli del {current_year}."
        }

    # Per attività, prendi descrizione da piani_monitoraggio (piani_df) dove
    # ATT_B47 ha la descrizione corretta. cu_eseguiti_nc ha solo B47 (piano).
    if entity_type == "attivita":
        piano_rows = DataRetriever.get_piano_by_id(piano_code)
        if piano_rows is not None and not piano_rows.empty:
            att_rows = piano_rows[piano_rows["tipo_piano_attivita"].str.upper() == "ATTIVITA"]
            src = att_rows if not att_rows.empty else piano_rows
            piano_desc = str(src["descrizione_piano_attivita"].iloc[0]) if pd.notna(src["descrizione_piano_attivita"].iloc[0]) else ""
            desc_ind = str(src["descrizione_indicatore"].iloc[0]).strip() if pd.notna(src["descrizione_indicatore"].iloc[0]) else ""
            if piano_desc and desc_ind:
                piano_desc = f"{piano_desc} — {desc_ind}"
        else:
            piano_desc = controlli_df["descrizione_piano"].iloc[0]
    else:
        piano_desc = controlli_df["descrizione_piano"].iloc[0]
    total_controls = controlli_df.shape[0]
    # Coerenza con aggregate_stabilimenti_by_piano: stesse chiavi + stessa
    # normalizzazione whitespace, così il conteggio "Tipologie" combacia col
    # numero di righe mostrate in top_stabilimenti.
    _norm_df = controlli_df[['macroarea_cu', 'aggregazione_cu', 'attivita_cu']].copy()
    for _col in _norm_df.columns:
        _norm_df[_col] = _norm_df[_col].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    unique_establishments = len(_norm_df.drop_duplicates())

    response = ResponseFormatter.format_stabilimenti_analysis(
        piano_id=piano_code,
        piano_desc=piano_desc,
        top_stabilimenti=top_stabilimenti,
        total_controls=total_controls,
        unique_establishments=unique_establishments,
        entity_type=entity_type,
        anno=current_year,
        user_uos=user_uos,
        total_controls_all=total_controls_all,
    )

    mismatch_prefix = _build_mismatch_prefix(entity_hint, entity_type, piano_code)
    if mismatch_prefix:
        response = mismatch_prefix + response

    top_stabilimenti_dict = top_stabilimenti.to_dict(orient='records')

    return {
        "piano_code": piano_code,
        "entity_type": entity_type,
        "entity_hint": entity_hint,
        "anno": current_year,
        "user_uos": user_uos,
        "piano_description": piano_desc,
        "total_controls": total_controls,
        "total_controls_all": total_controls_all,
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
            "formatted_response": ResponseFormatter.format_tool_error("il calcolo delle statistiche")
        }


def piano_tool(action: str, piano_code: Optional[str] = None, piano2_code: Optional[str] = None, entity_hint: Optional[str] = None, user_uos: Optional[str] = None) -> Dict[str, Any]:
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
            return get_att_func(piano_code, entity_hint, user_uos)
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
            "formatted_response": ResponseFormatter.format_tool_error("l'elaborazione della richiesta")
        }
