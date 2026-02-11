#!/usr/bin/env python3
"""
Tool per analisi del rischio - Top attività rischiose
"""

from typing import Dict, Any
try:
    from langchain_core.tools import tool
except ImportError:
    try:
        from langchain.tools import tool
    except ImportError:
        # Fallback if neither is available
        def tool(name: str):
            """Fallback decorator if langchain is not available"""
            def decorator(func):
                func.name = name
                return func
            return decorator

try:
    from agents.data_agent import RiskAnalyzer
    from agents.response_agent import ResponseFormatter
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import RiskAnalyzer
    from agents.response_agent import ResponseFormatter


@tool("get_top_risk_activities")
def get_top_risk_activities(limit: int = 10) -> Dict[str, Any]:
    """
    Estrae le top N attività con risk score più elevato dal dataset OCSE.

    Args:
        limit: Numero di attività da restituire (default: 10)

    Returns:
        Dict con lista delle attività più rischiose ordinate per risk score
    """
    try:
        # Calcola risk scores per tutte le attività
        risk_scores_df = RiskAnalyzer.calculate_risk_scores()

        if risk_scores_df.empty:
            return {
                "info": "Nessun dato di rischio disponibile",
                "total": 0,
                "formatted_response": "Non sono disponibili dati di rischio per le attività al momento."
            }

        # Limita ai top N
        top_activities = risk_scores_df.head(limit)

        # Prepara dati per response formatter
        activities_data = []
        for rank, row in enumerate(top_activities.itertuples(index=False), 1):
            activity_data = {
                'rank': rank,  # Fix: use sequential rank instead of original index
                'macroarea': str(row.macroarea),
                'aggregazione': str(row.aggregazione),
                'linea_attivita': str(row.linea_attivita),
                'risk_score': float(row.punteggio_rischio_totale),
                'nc_gravi': int(row.tot_nc_gravi),
                'nc_non_gravi': int(row.tot_nc_non_gravi),
                'controlli_totali': int(row.numero_controlli_totali),
                'prob_nc': float(getattr(row, 'prob_nc', 0)),
                'impatto': float(getattr(row, 'impatto', 0))
            }
            activities_data.append(activity_data)

        # Calcola statistiche generali
        total_activities = len(risk_scores_df)
        high_risk_count = len(risk_scores_df[risk_scores_df['punteggio_rischio_totale'] > 20])
        medium_risk_count = len(risk_scores_df[
            (risk_scores_df['punteggio_rischio_totale'] > 5) &
            (risk_scores_df['punteggio_rischio_totale'] <= 20)
        ])
        avg_risk_score = float(risk_scores_df['punteggio_rischio_totale'].mean())

        # Formatta risposta
        formatted_response = ResponseFormatter.format_top_risk_activities(
            activities_data,
            total_activities,
            high_risk_count,
            medium_risk_count,
            avg_risk_score,
            limit
        )

        return {
            "activities": activities_data,
            "total_activities_analyzed": total_activities,
            "high_risk_count": high_risk_count,
            "medium_risk_count": medium_risk_count,
            "average_risk_score": avg_risk_score,
            "limit": limit,
            "formatted_response": formatted_response
        }

    except Exception as e:
        return {
            "error": f"Errore nel calcolo delle attività a rischio: {str(e)}",
            "formatted_response": f"Si è verificato un errore nel recupero delle attività a rischio: {str(e)}"
        }