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
    from agents.data_agent import DataRetriever, RiskAnalyzer
    from agents.response_agent import ResponseFormatter
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever, RiskAnalyzer
    from agents.response_agent import ResponseFormatter


@tool("risk_based_priority")
def get_risk_based_priority(asl: Optional[str] = None, piano_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Identifica stabilimenti ad alto rischio storico.
    Se ASL specificata: analizza stabilimenti mai controllati per quella ASL
    Se solo piano: analizza tipologie di stabilimenti controllati per quel piano con NC storiche

    Args:
        asl: Codice ASL opzionale (es. "NA1", "SA1")
        piano_code: Codice piano opzionale per filtrare attività correlate

    Returns:
        Dict con stabilimenti ad alto rischio o messaggio di errore
    """
    # Caso 1: Solo piano specificato, nessuna ASL -> analizza stabilimenti controllati con NC
    if piano_code and not asl:
        return _analyze_controlled_establishments_risk(piano_code)

    # Caso 2: ASL specificata -> analisi stabilimenti mai controllati (comportamento originale)
    if not asl:
        return {"error": "ASL non specificata", "formatted_response": "Per l'analisi del rischio degli stabilimenti mai controllati è necessario specificare l'ASL."}

    try:
        rischio_per_attivita = RiskAnalyzer.calculate_risk_scores()

        if rischio_per_attivita.empty:
            return {
                "error": "Dataset rischio non disponibile",
                "asl": asl,
                "formatted_response": "I dati storici di rischio non sono attualmente disponibili."
            }

        osa_filtered = DataRetriever.get_osa_mai_controllati(asl=asl)

        if osa_filtered.empty:
            return {
                "info": f"Nessun stabilimento mai controllato per ASL {asl}",
                "asl": asl,
                "total": 0,
                "formatted_response": f"✅ Non sono stati trovati stabilimenti mai controllati per l'ASL **{asl}**."
            }

        if piano_code:
            # Delega il matching del codice piano a DataRetriever (regex condivisa, no duplicazione)
            controlli_piano = DataRetriever.get_controlli_by_piano(piano_code)
            attivita_piano = (
                controlli_piano[['macroarea_cu', 'aggregazione_cu', 'attivita_cu']].drop_duplicates()
                if controlli_piano is not None and not controlli_piano.empty
                else pd.DataFrame(columns=['macroarea_cu', 'aggregazione_cu', 'attivita_cu'])
            )

            if attivita_piano.empty:
                return {
                    "error": f"Piano {piano_code} non trovato o senza controlli",
                    "asl": asl,
                    "piano_code": piano_code,
                    "formatted_response": f"Il piano **{piano_code}** non ha controlli registrati nel 2025 per l'ASL **{asl}**."
                }

            attivita_piano.columns = ['macroarea', 'aggregazione', 'linea_attivita']

            rischio_per_attivita = rischio_per_attivita.merge(
                attivita_piano,
                on=['macroarea', 'aggregazione', 'linea_attivita'],
                how='inner'
            )

            if rischio_per_attivita.empty:
                return {
                    "info": f"Nessuna linea di attività a rischio per piano {piano_code}",
                    "asl": asl,
                    "piano_code": piano_code,
                    "formatted_response": f"✅ Le linee di attività correlate al piano **{piano_code}** non mostrano criticità significative nei dati storici."
                }

        osa_rischiosi_display, osa_rischiosi_full = RiskAnalyzer.rank_osa_by_risk(
            osa_df=osa_filtered,
            risk_scores_df=rischio_per_attivita
        )

        all_data = []
        for row in osa_rischiosi_full.itertuples(index=False):
            ragione = getattr(row, 'ragione_sociale', None)
            ragione = str(ragione).strip() if pd.notna(ragione) and str(ragione).strip() else None
            numero_id = row.num_riconoscimento if pd.notna(row.num_riconoscimento) else row.n_reg
            if not numero_id or str(numero_id) == 'nan':
                numero_id = row.codice_fiscale
            comune = str(row.comune).upper() if pd.notna(row.comune) else 'N/D'

            all_data.append({
                'ragione_sociale': ragione or 'N/D',
                'macroarea': str(row.macroarea),
                'aggregazione': str(row.aggregazione),
                'comune': comune,
                'indirizzo': str(row.indirizzo),
                'numero_id': str(numero_id),
                'punteggio_rischio': int(row.punteggio_rischio_totale),
                'nc_gravi': int(row.tot_nc_gravi),
                'nc_non_gravi': int(row.tot_nc_non_gravi),
                'controlli_regionali': int(row.numero_controlli_totali),
                'data_inizio_attivita': str(row.data_inizio_attivita) if pd.notna(row.data_inizio_attivita) else 'N/D'
            })

        has_results = not osa_rischiosi_display.empty

        response = ResponseFormatter.format_risk_based_priority(
            user_asl=asl,
            piano_id=piano_code,
            osa_total_count=len(osa_filtered),
            osa_risky_count=len(all_data),
            activities_count=len(rischio_per_attivita),
            osa_rischiosi=osa_rischiosi_display,
            has_results=has_results
        )

        return {
            "asl": asl,
            "piano_code": piano_code,
            "total_never_controlled": len(osa_filtered),
            "total_risky": len(all_data),
            "activities_at_risk": len(rischio_per_attivita),
            "risky_establishments": all_data,
            "formatted_response": response
        }

    except Exception as e:
        return {"error": f"Errore nell'analisi del rischio: {str(e)}", "formatted_response": f"Si è verificato un errore durante l'analisi del rischio: {str(e)}"}


def _analyze_controlled_establishments_risk(piano_code: str) -> Dict[str, Any]:
    """
    Analizza rischio delle tipologie di stabilimenti controllati per un piano specifico.
    Usa i controlli eseguiti + dati NC storiche.
    """
    try:
        # Recupera controlli per il piano
        from agents.data_agent import DataRetriever, BusinessLogic

        controlli_df = DataRetriever.get_controlli_by_piano(piano_code)

        if controlli_df is None or controlli_df.empty:
            return {
                "error": f"Nessun controllo trovato per il piano {piano_code}",
                "piano_code": piano_code,
                "formatted_response": f"Non ci sono controlli eseguiti per il **piano {piano_code}**."
            }

        # Usa la funzione aggiornata che include NC
        stabilimenti_con_nc = BusinessLogic.aggregate_stabilimenti_by_piano(controlli_df, top_n=10)

        if stabilimenti_con_nc.empty:
            return {
                "error": f"Nessun dato di rischio disponibile per piano {piano_code}",
                "piano_code": piano_code,
                "formatted_response": f"Non sono disponibili dati di rischio per il piano **{piano_code}**."
            }

        # Ordina per punteggio rischio (se disponibile) o per numero controlli
        if 'punteggio_rischio' in stabilimenti_con_nc.columns:
            stabilimenti_con_nc = stabilimenti_con_nc.sort_values('punteggio_rischio', ascending=False)

        piano_desc = controlli_df['descrizione_piano'].iloc[0]
        total_controls = controlli_df.shape[0]

        # Formatta risposta specializzata per analisi rischio
        response = _format_risk_analysis_for_controlled_establishments(
            piano_id=piano_code,
            piano_desc=piano_desc,
            stabilimenti_con_nc=stabilimenti_con_nc,
            total_controls=total_controls
        )

        return {
            "piano_code": piano_code,
            "piano_description": piano_desc,
            "total_controls": total_controls,
            "risk_establishments": stabilimenti_con_nc.to_dict(orient='records'),
            "formatted_response": response
        }

    except Exception as e:
        return {"error": f"Errore nell'analisi del rischio per piano {piano_code}: {str(e)}", "formatted_response": f"Si è verificato un errore durante l'analisi del rischio per il piano {piano_code}: {str(e)}"}


def _format_risk_analysis_for_controlled_establishments(
    piano_id: str,
    piano_desc: str,
    stabilimenti_con_nc: pd.DataFrame,
    total_controls: int
) -> str:
    """
    Formatta l'analisi del rischio per stabilimenti controllati.
    """
    response = f"**🎯 Stabilimenti a Rischio per Piano {piano_id.upper()}**\n\n"
    response += f"**Piano:** {piano_desc}\n\n"

    # Filtra solo quelli con rischio > 0
    stabilimenti_rischiosi = stabilimenti_con_nc[
        stabilimenti_con_nc.get('punteggio_rischio', 0) > 0
    ] if 'punteggio_rischio' in stabilimenti_con_nc.columns else stabilimenti_con_nc

    if stabilimenti_rischiosi.empty:
        response += "✅ **Buone notizie!** Nessuna tipologia di stabilimento controllata per questo piano ha mostrato non conformità significative.\n\n"
        response += f"**Totale controlli eseguiti:** {total_controls}\n"
        return response

    response += f"**Top {len(stabilimenti_rischiosi)} tipologie a rischio** (ordinate per rischio storico):\n\n"

    for i, row in enumerate(stabilimenti_rischiosi.itertuples(index=False), 1):
        response += f"**{i}. {row.macroarea_cu}**\n"
        response += f"   📊 **Aggregazione:** {row.aggregazione_cu}\n"
        response += f"   🏭 **Linea di attività:** {row.attivita_cu}\n"
        response += f"   🔍 **Controlli eseguiti:** {row.count}\n"

        if hasattr(row, 'numero_nc_gravi') and hasattr(row, 'numero_nc_non_gravi'):
            nc_gravi = int(row.numero_nc_gravi)
            nc_non_gravi = int(row.numero_nc_non_gravi)
            punteggio = int(getattr(row, 'punteggio_rischio', 0))

            response += f"   ⚠️ **Non conformità storiche:** {nc_gravi} gravi, {nc_non_gravi} non gravi\n"
            if punteggio > 0:
                response += f"   🎯 **Punteggio rischio:** {punteggio}/100\n"

        response += "\n"

    response += f"**📈 Totale controlli analizzati:** {total_controls}\n"
    response += f"**🏢 Tipologie rischiose identificate:** {len(stabilimenti_rischiosi)}\n\n"

    response += "**💡 Interpretazione:**\n"
    response += "• **Risk Score** = P(NC) × Impatto × 100\n"
    response += "• **P(NC)** = probabilità non conformità (NC totali / controlli)\n"
    response += "• **Impatto** = gravità (NC gravi / controlli)\n"
    response += "• Dati aggregati a livello regionale per linea di attività\n"

    return response


def risk_tool(asl: Optional[str] = None, piano_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Router per funzionalità di analisi rischio (stabilimenti mai controllati).

    Args:
        asl: Codice ASL
        piano_code: Codice piano opzionale

    Returns:
        Dict con risultati analisi rischio
    """
    try:
        risk_func = get_risk_based_priority.func if hasattr(get_risk_based_priority, 'func') else get_risk_based_priority
        return risk_func(asl, piano_code)
    except Exception as e:
        return {"error": f"Errore in risk_tool: {str(e)}"}


@tool("establishments_with_sanctions")
def get_establishments_with_sanctions(asl: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """
    Identifica stabilimenti con più NC/sanzioni storiche.

    Args:
        asl: Codice ASL opzionale per filtrare
        limit: Numero massimo stabilimenti da restituire

    Returns:
        Dict con stabilimenti ordinati per numero totale NC
    """
    try:
        establishments_df = DataRetriever.get_establishments_with_most_sanctions(asl=asl, limit=limit)

        if establishments_df.empty:
            asl_text = f" per l'ASL **{asl}**" if asl else " nel database regionale"
            return {
                "info": f"Nessuno stabilimento con sanzioni trovato{asl_text}",
                "asl": asl,
                "total": 0,
                "formatted_response": f"✅ Non sono stati trovati stabilimenti con non conformità{asl_text}."
            }

        # Prepara dati per output
        establishments_data = []
        for row in establishments_df.itertuples(index=False):
            establishments_data.append({
                'numero_riconoscimento': str(row.numero_riconoscimento),
                'asl': str(row.asl),
                'comune': str(row.comune).upper() if pd.notna(row.comune) else 'N/D',
                'macroarea': str(row.macroarea),
                'aggregazione': str(row.aggregazione),
                'tot_nc_gravi': int(row.tot_nc_gravi),
                'tot_nc_non_gravi': int(row.tot_nc_non_gravi),
                'tot_nc': int(row.tot_nc),
                'controlli_totali': int(row.controlli_totali),
                'percentuale_nc': float(row.percentuale_nc)
            })

        # Formatta risposta
        response = _format_establishments_with_sanctions(
            asl=asl,
            establishments=establishments_data,
            total=len(establishments_df)
        )

        return {
            "asl": asl,
            "total": len(establishments_df),
            "establishments_with_sanctions": establishments_data,
            "formatted_response": response,
            "predictor_type": "sanctions_analysis"
        }

    except Exception as e:
        return {
            "error": f"Errore nell'analisi sanzioni: {str(e)}",
            "formatted_response": f"Si è verificato un errore durante l'analisi degli stabilimenti con sanzioni: {str(e)}"
        }


def _format_establishments_with_sanctions(asl: Optional[str], establishments: list, total: int) -> str:
    """Formatta la risposta per stabilimenti con sanzioni."""
    asl_header = f" - ASL **{asl}**" if asl else " (Regione Campania)"
    response = f"**🚨 Stabilimenti con più Non Conformità**{asl_header}\n\n"

    if not establishments:
        response += "✅ Nessuno stabilimento con non conformità trovato.\n"
        return response

    response += f"**Totale stabilimenti con NC:** {total}\n\n"
    response += "**Top 10 stabilimenti per numero di NC:**\n\n"

    for i, est in enumerate(establishments[:10], 1):
        nc_gravi = est['tot_nc_gravi']
        nc_non_gravi = est['tot_nc_non_gravi']
        tot_nc = est['tot_nc']

        # Emoji basata su gravità
        if nc_gravi >= 5:
            emoji = "🔴"
        elif nc_gravi >= 2:
            emoji = "🟠"
        else:
            emoji = "🟡"

        response += f"**{i}. {emoji} {est['numero_riconoscimento']}**\n"
        response += f"   📍 {est['comune']} ({est['asl']})\n"
        response += f"   🏭 {est['macroarea']} > {est['aggregazione']}\n"
        response += f"   ⚠️ **NC totali: {tot_nc}** ({nc_gravi} gravi, {nc_non_gravi} non gravi)\n"
        response += f"   🔍 Controlli: {est['controlli_totali']} | % NC: {est['percentuale_nc']}%\n\n"

    response += "**💡 Interpretazione:**\n"
    response += "• 🔴 = 5+ NC gravi (criticità alta)\n"
    response += "• 🟠 = 2-4 NC gravi (attenzione)\n"
    response += "• 🟡 = 0-1 NC gravi (monitoraggio)\n"

    return response


