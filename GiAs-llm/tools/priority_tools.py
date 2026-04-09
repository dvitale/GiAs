# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportArgumentType=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOptionalOperand=false, reportReturnType=false, reportAssignmentType=false, reportPossiblyUnboundVariable=false
from typing import Dict, Any, Optional
import pandas as pd

from tools._tool_compat import tool

try:
    from agents.data_agent import DataRetriever, BusinessLogic, RiskAnalyzer
    from agents.response_agent import ResponseFormatter
    from data_sources.repositories import get_diff_repository
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever, BusinessLogic, RiskAnalyzer
    from agents.response_agent import ResponseFormatter
    from data_sources.repositories import get_diff_repository


@tool("priority_establishment")
def get_priority_establishment(asl: str, uoc: str, piano_code: Optional[str] = None, uos: Optional[str] = None, target_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Identifica stabilimenti prioritari da controllare basandosi su piani in ritardo.

    Args:
        asl: Codice ASL (es. "NA1", "SA1")
        uoc: Nome della UOC (Unità Operativa Complessa)
        piano_code: Codice piano opzionale per filtrare
        uos: Nome della UOS (Unità Operativa Semplice) - opzionale
        target_year: Anno di riferimento (default: anno corrente da config)

    Returns:
        Dict con stabilimenti prioritari o messaggio di errore
    """
    if not asl:
        return {"error": "ASL non specificata", "formatted_response": "Per identificare gli stabilimenti prioritari è necessario specificare l'ASL."}

    if not uoc:
        return {"error": "UOC non specificata", "formatted_response": "Per identificare gli stabilimenti prioritari è necessario conoscere la tua struttura organizzativa (UOC). Assicurati di essere autenticato."}

    try:
        # Repository: pandas (default) o sql via flag data_source.repositories.diff
        diff_repo = get_diff_repository()
        diff_filtered = diff_repo.get_for_struttura(uoc, asl=asl, uos=uos)

        if diff_filtered.empty:
            return {
                "error": f"Nessun dato di programmazione trovato per UOC: {uoc}",
                "asl": asl,
                "uoc": uoc,
                "formatted_response": f"Non sono disponibili dati di programmazione per la struttura **{uoc}**. Verifica che la UOC sia corretta."
            }

        delayed_piani = BusinessLogic.calculate_delayed_plans(diff_filtered, piano_id=piano_code, target_year=target_year)

        # Filtra solo piani (escludi attività con prefisso "ATT ") quando non specificato un piano
        if not piano_code and 'alias_indicatore' in delayed_piani.columns:
            delayed_piani = delayed_piani[~delayed_piani['alias_indicatore'].str.upper().str.startswith('ATT ')].copy()

        if delayed_piani.empty:
            if piano_code:
                return {
                    "info": f"Piano {piano_code} non in ritardo per UOC {uoc}",
                    "asl": asl,
                    "uoc": uoc,
                    "piano_code": piano_code,
                    "formatted_response": f"✅ Il piano **{piano_code}** non risulta in ritardo per la struttura **{uoc}**."
                }
            else:
                return {
                    "info": f"Nessun piano in ritardo per UOC {uoc}",
                    "asl": asl,
                    "uoc": uoc,
                    "formatted_response": ResponseFormatter.format_no_data("piani in ritardo", f"per la struttura **{uoc}**", " Ottima notizia, la programmazione e' in linea! Vuoi controllare un'altra struttura?")
                }

        osa_filtered_by_asl = DataRetriever.get_osa_mai_controllati(asl=asl)

        if osa_filtered_by_asl.empty:
            return {
                "info": f"Nessun stabilimento mai controllato per ASL {asl}",
                "asl": asl,
                "delayed_plans": len(delayed_piani),
                "formatted_response": f"Ci sono **{len(delayed_piani)}** piani in ritardo, ma nessun stabilimento mai controllato per l'ASL **{asl}**."
            }

        priority_df_display, all_data = RiskAnalyzer.find_priority_establishments(
            delayed_plans_df=delayed_piani,
            osa_df=osa_filtered_by_asl
        )

        if not all_data:
            return {
                "info": "Nessuno stabilimento prioritario trovato",
                "asl": asl,
                "uoc": uoc,
                "delayed_plans": len(delayed_piani),
                "formatted_response": f"Ci sono **{len(delayed_piani)}** piani in ritardo per **{uoc}**, ma non sono stati individuati stabilimenti mai controllati nelle linee di attività correlate."
            }

        response = ResponseFormatter.format_priority_establishments(
            user_asl=asl,
            uoc_name=uoc,
            piano_id=piano_code,
            delayed_count=len(delayed_piani),
            total_found=len(all_data),
            priority_df_display=priority_df_display
        )

        return {
            "asl": asl,
            "uoc": uoc,
            "user_asl": asl,
            "uoc_name": uoc,
            "piano_code": piano_code,
            "delayed_plans_count": len(delayed_piani),
            "total_establishments": len(all_data),
            "total_found": len(all_data),
            "priority_establishments": all_data,
            "formatted_response": response
        }

    except Exception as e:
        return {"error": f"Errore nell'analisi priorità: {str(e)}", "formatted_response": ResponseFormatter.format_tool_error("l'analisi delle priorita'")}


def _get_piano_data_from_df(diff_df: pd.DataFrame, piano_code: str, target_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Recupera dati programmati/eseguiti per un piano specifico dal DataFrame.
    Usato per mostrare i dettagli anche quando il piano non è in ritardo.
    """
    if diff_df.empty or not piano_code:
        return {'programmati': 0, 'eseguiti': 0, 'ritardo': 0, 'sottopiani': None}

    # Applica stesso filtro anno di calculate_delayed_plans
    if target_year is None:
        try:
            from configs.config_loader import get_config
            target_year = get_config().get_current_year()
        except ImportError:
            from datetime import datetime as _dt
            target_year = _dt.now().year

    if 'anno' in diff_df.columns:
        diff_df = diff_df[diff_df['anno'] == target_year].copy()

    if diff_df.empty:
        return {'programmati': 0, 'eseguiti': 0, 'ritardo': 0, 'attesi': 0, 'avanzamento_atteso_pct': 100.0, 'sottopiani': None}

    # Calcolo proporzionale (stessa logica di calculate_delayed_plans)
    from datetime import datetime as _dt
    import calendar
    now = _dt.now()

    diff_df['programmati'] = pd.to_numeric(diff_df['programmati'], errors='coerce').fillna(0).astype(int)
    diff_df['eseguiti'] = pd.to_numeric(diff_df['eseguiti'], errors='coerce').fillna(0).astype(int)

    if target_year == now.year:
        days_in_year = 366 if calendar.isleap(target_year) else 365
        fraction = now.timetuple().tm_yday / days_in_year
        diff_df['attesi'] = (diff_df['programmati'] * fraction).round(0).astype(int)
        diff_df['ritardo'] = (diff_df['attesi'] - diff_df['eseguiti']).clip(lower=0).astype(int)
        avanzamento_atteso_pct = round(fraction * 100, 1)
    else:
        diff_df['attesi'] = diff_df['programmati']
        diff_df['ritardo'] = (diff_df['programmati'] - diff_df['eseguiti']).clip(lower=0).astype(int)
        avanzamento_atteso_pct = 100.0

    # Aggrega per piano
    piano_summary = diff_df.groupby('alias_indicatore').agg({
        'ritardo': 'sum',
        'programmati': 'sum',
        'eseguiti': 'sum',
        'attesi': 'sum'
    }).reset_index()

    # Match esatto o sottopiani
    piano_code_upper = piano_code.upper()
    piano_match = piano_summary[
        (piano_summary['alias_indicatore'] == piano_code_upper) |
        (piano_summary['alias_indicatore'].str.startswith(piano_code_upper + '_'))
    ]

    if piano_match.empty:
        return {'programmati': 0, 'eseguiti': 0, 'ritardo': 0, 'attesi': 0, 'avanzamento_atteso_pct': avanzamento_atteso_pct, 'sottopiani': None}

    matched_plans = piano_match['alias_indicatore'].tolist()
    return {
        'programmati': int(piano_match['programmati'].sum()),
        'eseguiti': int(piano_match['eseguiti'].sum()),
        'ritardo': int(piano_match['ritardo'].sum()),
        'attesi': int(piano_match['attesi'].sum()),
        'avanzamento_atteso_pct': avanzamento_atteso_pct,
        'sottopiani': matched_plans if matched_plans else None
    }


@tool("delayed_plans")
def get_delayed_plans(asl: str, uoc: Optional[str] = None, piano_code: Optional[str] = None, uos: Optional[str] = None, tipo: Optional[str] = None, target_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Analizza i piani o le attività in ritardo per una specifica struttura.
    Se piano_code è specificato, verifica solo se quel piano è in ritardo.

    Args:
        asl: Codice ASL (es. "NA1", "SA1")
        uoc: Nome della UOC (Unità Operativa Complessa) - opzionale per query aggregate
        piano_code: Codice piano specifico per verifica (es. "B47")
        uos: Nome della UOS (Unità Operativa Semplice) - opzionale
        tipo: "piano" (default), "attivita" o "tutti" - filtra per tipo indicatore
        target_year: Anno di riferimento (default: anno corrente da config)

    Returns:
        Dict con piani/attività in ritardo o verifica piano specifico
    """
    if not asl:
        return {"error": "ASL non specificata"}

    if not uoc:
        # UOC non disponibile - restituisci messaggio informativo invece di errore
        return {
            "info": "Analisi piani in ritardo non disponibile senza UOC specifica",
            "suggestion": "Per vedere i piani in ritardo della tua struttura, assicurati di essere autenticato correttamente",
            "asl": asl,
            "formatted_response": f"Non posso mostrare i piani in ritardo per l'ASL {asl} senza conoscere la tua struttura organizzativa (UOC). Assicurati di essere autenticato per accedere ai dati della tua unità."
        }

    try:
        diff_repo = get_diff_repository()
        filtered_df = diff_repo.get_for_struttura(uoc, asl=asl, uos=uos)

        if filtered_df.empty:
            return {
                "error": f"Nessun dato di programmazione trovato per UOC: {uoc}",
                "asl": asl,
                "uoc": uoc,
                "formatted_response": f"Non sono disponibili dati di programmazione per la struttura **{uoc}**."
            }

        delayed_df = BusinessLogic.calculate_delayed_plans(filtered_df, piano_id=None, target_year=target_year)

        # Filtra per tipo: "piano" (senza prefisso ATT), "attivita" (con prefisso ATT), "tutti"
        # Gli indicatori con "ATT " sono attività, quelli senza sono piani
        effective_tipo = (tipo or "piano").lower()
        if not piano_code and 'alias_indicatore' in delayed_df.columns and effective_tipo != "tutti":
            is_att = delayed_df['alias_indicatore'].str.upper().str.startswith('ATT ') | delayed_df['alias_indicatore'].str.upper().str.startswith('ATT_')
            if effective_tipo == "attivita":
                delayed_df = delayed_df[is_att].copy()
            else:  # "piano"
                delayed_df = delayed_df[~is_att].copy()

        if delayed_df.empty:
            if piano_code:
                # Recupera dati del piano anche se non in ritardo per mostrare i dettagli
                piano_data = _get_piano_data_from_df(filtered_df, piano_code, target_year=target_year)
                response = ResponseFormatter.format_check_plan_delayed(
                    piano_code=piano_code,
                    is_delayed=False,
                    asl=asl,
                    uoc=uoc,
                    ritardo=piano_data.get('ritardo', 0),
                    programmati=piano_data.get('programmati', 0),
                    eseguiti=piano_data.get('eseguiti', 0),
                    sottopiani=piano_data.get('sottopiani'),
                    attesi=piano_data.get('attesi', 0),
                    avanzamento_atteso_pct=piano_data.get('avanzamento_atteso_pct', 100.0)
                )
                return {
                    "is_delayed": False,
                    "piano_code": piano_code,
                    "asl": asl,
                    "uoc": uoc,
                    "programmati": piano_data.get('programmati', 0),
                    "eseguiti": piano_data.get('eseguiti', 0),
                    "formatted_response": response
                }
            entity_label = "attività" if effective_tipo == "attivita" else "piano"
            return {
                "info": f"Nessun {entity_label} in ritardo",
                "asl": asl,
                "uoc": uoc,
                "delayed_plans": [],
                "formatted_response": ResponseFormatter.format_no_data(f"{entity_label} in ritardo", f"per la struttura **{uoc}**", " Vuoi controllare un'altra struttura?")
            }

        # Se richiesto un piano specifico, verifica solo quello
        if piano_code:
            agg_cols = {'ritardo': 'sum', 'programmati': 'sum', 'eseguiti': 'sum', 'descrizione_indicatore': 'first'}
            if 'attesi' in delayed_df.columns:
                agg_cols['attesi'] = 'sum'
            piano_summary = delayed_df.groupby('alias_indicatore').agg(agg_cols).reset_index()

            # Match esatto o sottopiani (es. AO24 matcha AO24_A, AO24_B)
            piano_code_upper = piano_code.upper()
            piano_match = piano_summary[
                (piano_summary['alias_indicatore'] == piano_code_upper) |
                (piano_summary['alias_indicatore'].str.startswith(piano_code_upper + '_'))
            ]

            if piano_match.empty:
                # Piano non in ritardo - recupera comunque i dati per mostrare i dettagli
                piano_data = _get_piano_data_from_df(filtered_df, piano_code, target_year=target_year)
                response = ResponseFormatter.format_check_plan_delayed(
                    piano_code=piano_code,
                    is_delayed=False,
                    asl=asl,
                    uoc=uoc,
                    ritardo=piano_data.get('ritardo', 0),
                    programmati=piano_data.get('programmati', 0),
                    eseguiti=piano_data.get('eseguiti', 0),
                    sottopiani=piano_data.get('sottopiani'),
                    attesi=piano_data.get('attesi', 0),
                    avanzamento_atteso_pct=piano_data.get('avanzamento_atteso_pct', 100.0)
                )
                return {
                    "is_delayed": False,
                    "piano_code": piano_code,
                    "asl": asl,
                    "uoc": uoc,
                    "programmati": piano_data.get('programmati', 0),
                    "eseguiti": piano_data.get('eseguiti', 0),
                    "formatted_response": response
                }

            # Aggrega tutti i sottopiani matchati
            ritardo = int(piano_match['ritardo'].sum())
            programmati = int(piano_match['programmati'].sum())
            eseguiti = int(piano_match['eseguiti'].sum())
            attesi = int(piano_match['attesi'].sum()) if 'attesi' in piano_match.columns else programmati
            avanzamento_atteso = float(delayed_df['avanzamento_atteso_pct'].iloc[0]) if 'avanzamento_atteso_pct' in delayed_df.columns else 100.0

            # Se trovati sottopiani, includi il dettaglio
            matched_plans = piano_match['alias_indicatore'].tolist()
            sottopiani_list = matched_plans if len(matched_plans) >= 1 else None

            response = ResponseFormatter.format_check_plan_delayed(
                piano_code=piano_code,
                is_delayed=True,
                asl=asl,
                uoc=uoc,
                ritardo=ritardo,
                programmati=programmati,
                eseguiti=eseguiti,
                sottopiani=sottopiani_list,
                attesi=attesi,
                avanzamento_atteso_pct=avanzamento_atteso
            )

            return {
                "is_delayed": True,
                "piano_code": piano_code,
                "asl": asl,
                "uoc": uoc,
                "ritardo": ritardo,
                "programmati": programmati,
                "eseguiti": eseguiti,
                "sottopiani": sottopiani_list,
                "formatted_response": response
            }

        # Lista completa piani in ritardo
        piano_summary = delayed_df.groupby('alias_indicatore').agg({
            'ritardo': 'sum',
            'programmati': 'sum',
            'eseguiti': 'sum',
            'descrizione_indicatore': 'first'
        }).reset_index()

        piano_summary = piano_summary.sort_values('ritardo', ascending=False)

        total_plans_delayed = len(piano_summary)
        total_delay = int(piano_summary['ritardo'].sum())

        top_delayed = piano_summary.head(10)

        worst_plan_id = piano_summary.iloc[0]['alias_indicatore']  # Fix: use 'alias_indicatore' not 'piano'
        worst_plan_details = delayed_df[delayed_df['alias_indicatore'] == worst_plan_id].head(5)

        response, detail_response = ResponseFormatter.format_delayed_plans(
            user_asl=asl,
            uoc_name=uoc,
            total_plans_delayed=total_plans_delayed,
            total_delay=total_delay,
            top_delayed=top_delayed,
            worst_plan_details=worst_plan_details,
            worst_plan_id=worst_plan_id,
            uos_name=uos,
            tipo=effective_tipo
        )

        delayed_plans_list = top_delayed.to_dict(orient='records')

        return {
            "asl": asl,
            "uoc": uoc,
            "total_plans_delayed": total_plans_delayed,
            "total_delay": total_delay,
            "delayed_plans": delayed_plans_list,
            "formatted_response": response,
            "detail_response": detail_response
        }

    except Exception as e:
        return {"error": f"Errore nell'analisi piani in ritardo: {str(e)}", "formatted_response": ResponseFormatter.format_tool_error("l'analisi dei piani in ritardo")}


@tool("suggest_controls")
def suggest_controls(asl: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Suggerisce stabilimenti mai controllati (suggerimento base).

    Args:
        asl: Codice ASL opzionale per filtrare
        limit: Numero massimo di suggerimenti (default 5)

    Returns:
        Dict con suggerimenti controlli
    """
    try:
        filtered_df = DataRetriever.get_osa_mai_controllati(asl=asl)

        if filtered_df.empty:
            asl_text = f" per l'ASL **{asl}**" if asl else ""
            return {
                "info": "Nessun stabilimento mai controllato trovato",
                "asl": asl,
                "total": 0,
                "formatted_response": ResponseFormatter.format_no_data("stabilimenti mai controllati", asl_text, " Vuoi che cerchi quelli a rischio piu' alto?")
            }

        limit = min(limit, len(filtered_df))
        sample_df = filtered_df.head(limit)

        response = ResponseFormatter.format_suggest_controls(
            asl=asl,
            filtered_count=len(filtered_df),
            sample_df=sample_df,
            limit=limit
        )

        establishments_list = sample_df.to_dict(orient='records')

        return {
            "asl": asl,
            "total_never_controlled": len(filtered_df),
            "suggested_establishments": establishments_list,
            "formatted_response": response
        }

    except Exception as e:
        return {"error": f"Errore nei suggerimenti controlli: {str(e)}", "formatted_response": ResponseFormatter.format_tool_error("la ricerca di stabilimenti da controllare")}


def priority_tool(asl: Optional[str] = None, uoc: Optional[str] = None,
                  piano_code: Optional[str] = None, action: str = "priority",
                  uos: Optional[str] = None, tipo: Optional[str] = None,
                  target_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Router per funzionalità di priorità e programmazione.

    Args:
        asl: Codice ASL
        uoc: Nome UOC
        piano_code: Codice piano opzionale
        action: Tipo di azione ("priority", "delayed_plans", "suggest")
        uos: Nome UOS (Unità Operativa Semplice) - opzionale
        tipo: "piano" (default), "attivita" o "tutti" - filtra per tipo indicatore
        target_year: Anno di riferimento (default: anno corrente da config)

    Returns:
        Dict con risultati o messaggio di errore
    """
    try:
        delayed_func = get_delayed_plans.func if hasattr(get_delayed_plans, 'func') else get_delayed_plans
        suggest_func = suggest_controls.func if hasattr(suggest_controls, 'func') else suggest_controls
        priority_func = get_priority_establishment.func if hasattr(get_priority_establishment, 'func') else get_priority_establishment

        if action == "delayed_plans":
            return delayed_func(asl, uoc, uos=uos, tipo=tipo, target_year=target_year)
        elif action == "suggest":
            return suggest_func(asl)
        else:
            return priority_func(asl, uoc, piano_code, uos=uos, target_year=target_year)
    except Exception as e:
        return {"error": f"Errore in priority_tool: {str(e)}"}


def get_programmed_controls_summary(
    piano_code: str,
    asl: Optional[str] = None,
    uos: Optional[str] = None,
    target_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Restituisce il totale dei controlli programmati per un piano specifico,
    filtrato su ASL + UOS dell'utente e anno corrente.

    Replica la query SQL di riferimento:

        SELECT SUM(programmati), SUM(eseguiti)
        FROM cu_diff_programmati_eseguiti
        WHERE anno = :target_year
          AND alias_piano_attivita = :piano_code
          AND descrizione_uos ILIKE '%:uos%'
          AND descrizione_asl ILIKE '%:asl%'

    Nota: il filtro chiave è su `alias_piano_attivita` (es. "A14"), NON su
    `alias_indicatore` (che conterrebbe anche sotto-indicatori A14_A, A14_B).
    SUM aggrega tutti i sotto-indicatori dello stesso piano.
    """
    if not piano_code:
        return {
            "error": "piano_code mancante",
            "formatted_response": "Devi specificare un codice piano (es. A14).",
        }

    try:
        from configs.config_loader import get_config
        current_year = target_year or get_config().get_current_year()
    except Exception:
        from datetime import datetime as _dt
        current_year = target_year or _dt.now().year

    piano_upper = str(piano_code).upper().strip()

    # Repository: ritorna già filtrato per piano + ASL + UOS + anno
    try:
        diff_repo = get_diff_repository()
        work = diff_repo.get_programmati_for_piano(
            piano_code=piano_code,
            asl=asl,
            uos=uos,
            year=current_year,
        )
    except Exception as exc:
        return {
            "error": f"Dati di programmazione non disponibili: {exc}",
            "formatted_response": "I dati di programmazione non sono disponibili al momento.",
        }

    if work is None or work.empty:
        return {
            "piano_code": piano_code,
            "asl": asl,
            "uos": uos,
            "anno": current_year,
            "programmati": 0,
            "eseguiti": 0,
            "n_indicatori": 0,
            "formatted_response": (
                f"Non risultano controlli programmati per il piano **{piano_code}** "
                f"nel {current_year} per la tua struttura"
                + (f" (UOS **{uos}**)" if uos else "")
                + "."
            ),
        }

    programmati = int(pd.to_numeric(work["programmati"], errors="coerce").fillna(0).sum())
    eseguiti = int(pd.to_numeric(work["eseguiti"], errors="coerce").fillna(0).sum())
    residuo = max(programmati - eseguiti, 0)
    n_indicatori = int(work["alias_indicatore"].nunique()) if "alias_indicatore" in work.columns else 0
    completamento = (eseguiti / programmati * 100) if programmati else 0.0

    # Descrizione piano (dalla prima riga disponibile)
    descrizione = ""
    for _col in ("descrizione_piano", "descrizione_indicatore"):
        if _col in work.columns:
            try:
                descrizione = str(work[_col].dropna().iloc[0])
                break
            except Exception:
                continue

    # Formattazione risposta
    scope_bits = [f"anno **{current_year}**"]
    if uos:
        scope_bits.append(f"UOS **{uos}**")
    if asl:
        scope_bits.append(f"ASL **{asl}**")
    scope_line = " · ".join(scope_bits)

    lines = [f"### 📋 Controlli programmati — Piano {piano_upper}"]
    if descrizione:
        lines.append(f"*{descrizione}*")
    lines.append("")
    lines.append(f"*{scope_line}*")
    lines.append("")
    lines.append(f"**Controlli programmati:** {programmati:,}")
    lines.append(f"**Controlli eseguiti:** {eseguiti:,}")
    lines.append(f"**Residuo da eseguire:** {residuo:,}")
    lines.append(f"**Completamento:** {completamento:.0f}%")
    if n_indicatori > 1:
        lines.append("")
        lines.append(f"*Aggregato su {n_indicatori} sotto-indicatori del piano.*")

    return {
        "piano_code": piano_code,
        "asl": asl,
        "uos": uos,
        "anno": current_year,
        "programmati": programmati,
        "eseguiti": eseguiti,
        "residuo": residuo,
        "n_indicatori": n_indicatori,
        "completamento_pct": round(completamento, 1),
        "formatted_response": "\n".join(lines),
    }
