from typing import Dict, Any, Optional
import pandas as pd

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(name):
        def decorator(func):
            return func
        return decorator

try:
    from agents.data_agent import DataRetriever, BusinessLogic, RiskAnalyzer
    from agents.response_agent import ResponseFormatter
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever, BusinessLogic, RiskAnalyzer
    from agents.response_agent import ResponseFormatter


@tool("priority_establishment")
def get_priority_establishment(asl: str, uoc: str, piano_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Identifica stabilimenti prioritari da controllare basandosi su piani in ritardo.

    Args:
        asl: Codice ASL (es. "NA1", "SA1")
        uoc: Nome della UOC (Unità Operativa Complessa)
        piano_code: Codice piano opzionale per filtrare

    Returns:
        Dict con stabilimenti prioritari o messaggio di errore
    """
    if not asl:
        return {"error": "ASL non specificata", "formatted_response": "Per identificare gli stabilimenti prioritari è necessario specificare l'ASL."}

    if not uoc:
        return {"error": "UOC non specificata", "formatted_response": "Per identificare gli stabilimenti prioritari è necessario conoscere la tua struttura organizzativa (UOC). Assicurati di essere autenticato."}

    try:
        diff_filtered = DataRetriever.get_diff_programmati_eseguiti(uoc)

        if diff_filtered.empty:
            return {
                "error": f"Nessun dato di programmazione trovato per UOC: {uoc}",
                "asl": asl,
                "uoc": uoc,
                "formatted_response": f"Non sono disponibili dati di programmazione per la struttura **{uoc}**. Verifica che la UOC sia corretta."
            }

        delayed_piani = BusinessLogic.calculate_delayed_plans(diff_filtered, piano_id=piano_code)

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
                    "formatted_response": f"✅ Nessun piano risulta in ritardo per la struttura **{uoc}**. La programmazione è in linea."
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
            osa_df=osa_filtered_by_asl,
            limit=15
        )

        if not all_data:
            return {
                "info": "Nessuno stabilimento prioritario trovato",
                "asl": asl,
                "uoc": uoc,
                "delayed_plans": len(delayed_piani),
                "formatted_response": f"Ci sono **{len(delayed_piani)}** piani in ritardo per **{uoc}**, ma non sono stati individuati stabilimenti mai controllati nelle attività correlate."
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
            "priority_establishments": all_data[:15],
            "formatted_response": response
        }

    except Exception as e:
        return {"error": f"Errore nell'analisi priorità: {str(e)}", "formatted_response": f"Si è verificato un errore durante l'analisi delle priorità: {str(e)}"}


@tool("delayed_plans")
def get_delayed_plans(asl: str, uoc: Optional[str] = None, piano_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Analizza i piani in ritardo per una specifica struttura.
    Se piano_code è specificato, verifica solo se quel piano è in ritardo.

    Args:
        asl: Codice ASL (es. "NA1", "SA1")
        uoc: Nome della UOC (Unità Operativa Complessa) - opzionale per query aggregate
        piano_code: Codice piano specifico per verifica (es. "B47")

    Returns:
        Dict con piani in ritardo o verifica piano specifico
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
        filtered_df = DataRetriever.get_diff_programmati_eseguiti(uoc)

        if filtered_df.empty:
            return {
                "error": f"Nessun dato di programmazione trovato per UOC: {uoc}",
                "asl": asl,
                "uoc": uoc,
                "formatted_response": f"Non sono disponibili dati di programmazione per la struttura **{uoc}**."
            }

        delayed_df = BusinessLogic.calculate_delayed_plans(filtered_df, piano_id=None)

        if delayed_df.empty:
            if piano_code:
                return {
                    "is_delayed": False,
                    "piano_code": piano_code,
                    "asl": asl,
                    "uoc": uoc,
                    "formatted_response": f"Il piano {piano_code} non è in ritardo per la struttura {uoc}."
                }
            return {
                "info": "Nessun piano in ritardo",
                "asl": asl,
                "uoc": uoc,
                "delayed_plans": [],
                "formatted_response": f"✅ Nessun piano risulta in ritardo per la struttura **{uoc}**."
            }

        # Se richiesto un piano specifico, verifica solo quello
        if piano_code:
            piano_summary = delayed_df.groupby('indicatore').agg({
                'ritardo': 'sum',
                'programmati': 'sum',
                'eseguiti': 'sum',
                'descrizione_indicatore': 'first'
            }).reset_index()

            # Match esatto o sottopiani (es. AO24 matcha AO24_A, AO24_B)
            piano_code_upper = piano_code.upper()
            piano_match = piano_summary[
                (piano_summary['indicatore'] == piano_code_upper) |
                (piano_summary['indicatore'].str.startswith(piano_code_upper + '_'))
            ]

            if piano_match.empty:
                return {
                    "is_delayed": False,
                    "piano_code": piano_code,
                    "asl": asl,
                    "uoc": uoc,
                    "formatted_response": f"Il piano {piano_code} non è in ritardo per la struttura {uoc}."
                }

            # Aggrega tutti i sottopiani matchati
            ritardo = int(piano_match['ritardo'].sum())
            programmati = int(piano_match['programmati'].sum())
            eseguiti = int(piano_match['eseguiti'].sum())

            # Se trovati sottopiani, includi il dettaglio
            matched_plans = piano_match['indicatore'].tolist()
            sottopiani_list = matched_plans if len(matched_plans) >= 1 else None

            response = ResponseFormatter.format_check_plan_delayed(
                piano_code=piano_code,
                is_delayed=True,
                asl=asl,
                uoc=uoc,
                ritardo=ritardo,
                programmati=programmati,
                eseguiti=eseguiti,
                sottopiani=sottopiani_list
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
        piano_summary = delayed_df.groupby('indicatore').agg({
            'ritardo': 'sum',
            'programmati': 'sum',
            'eseguiti': 'sum',
            'descrizione_indicatore': 'first'
        }).reset_index()

        piano_summary = piano_summary.sort_values('ritardo', ascending=False)

        total_plans_delayed = len(piano_summary)
        total_delay = int(piano_summary['ritardo'].sum())

        top_delayed = piano_summary.head(10)

        worst_plan_id = piano_summary.iloc[0]['indicatore']  # Fix: use 'indicatore' not 'piano'
        worst_plan_details = delayed_df[delayed_df['indicatore'] == worst_plan_id].head(5)

        response, detail_response = ResponseFormatter.format_delayed_plans(
            user_asl=asl,
            uoc_name=uoc,
            total_plans_delayed=total_plans_delayed,
            total_delay=total_delay,
            top_delayed=top_delayed,
            worst_plan_details=worst_plan_details,
            worst_plan_id=worst_plan_id
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
        return {"error": f"Errore nell'analisi piani in ritardo: {str(e)}", "formatted_response": f"Si è verificato un errore durante l'analisi dei piani in ritardo: {str(e)}"}


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
                "formatted_response": f"✅ Non sono stati trovati stabilimenti mai controllati{asl_text}."
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
        return {"error": f"Errore nei suggerimenti controlli: {str(e)}", "formatted_response": f"Si è verificato un errore durante la ricerca di stabilimenti da controllare: {str(e)}"}


def priority_tool(asl: Optional[str] = None, uoc: Optional[str] = None,
                  piano_code: Optional[str] = None, action: str = "priority") -> Dict[str, Any]:
    """
    Router per funzionalità di priorità e programmazione.

    Args:
        asl: Codice ASL
        uoc: Nome UOC
        piano_code: Codice piano opzionale
        action: Tipo di azione ("priority", "delayed_plans", "suggest")

    Returns:
        Dict con risultati o messaggio di errore
    """
    try:
        delayed_func = get_delayed_plans.func if hasattr(get_delayed_plans, 'func') else get_delayed_plans
        suggest_func = suggest_controls.func if hasattr(suggest_controls, 'func') else suggest_controls
        priority_func = get_priority_establishment.func if hasattr(get_priority_establishment, 'func') else get_priority_establishment

        if action == "delayed_plans":
            return delayed_func(asl, uoc)
        elif action == "suggest":
            return suggest_func(asl)
        else:
            return priority_func(asl, uoc, piano_code)
    except Exception as e:
        return {"error": f"Errore in priority_tool: {str(e)}"}
