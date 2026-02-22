"""
Logica two-phase per risposte lunghe.

Se il numero di item supera una soglia, salva la risposta completa
in detail_context e mostra solo un sommario + "Vuoi vedere i dettagli?"
"""

from typing import Dict, Any


TWO_PHASE_THRESHOLDS = {
    "ask_establishment_history": 3,
    "ask_risk_based_priority": 3,
    "ask_priority_establishment": 3,
    "ask_suggest_controls": 3,
    "search_piani_by_topic": 3,
    "ask_piano_stabilimenti": 3,
    "ask_nearby_priority": 10,
}

TWO_PHASE_SUFFIX = "\n\n---\n**Vuoi vedere tutti i dettagli?** (rispondi *sì* o *no*)"


def apply_two_phase_check(
    state: Dict[str, Any],
    intent: str,
    result: Dict[str, Any],
    item_count: int,
    summary_text: str,
    full_formatted_response: str = None
) -> Dict[str, Any]:
    """
    Applica il controllo two-phase: se item_count > threshold,
    salva la risposta completa in detail_context e sostituisce
    formatted_response con il sommario + suffix.

    Args:
        state: ConversationState corrente (modificato in-place)
        intent: Intent corrente
        result: Risultato del tool (deve contenere formatted_response)
        item_count: Numero di item nel risultato
        summary_text: Testo sommario da mostrare
        full_formatted_response: Risposta formattata senza limiti per i dettagli.
            Se fornita, viene salvata in detail_context al posto di
            result["formatted_response"] (che potrebbe essere troncata).

    Returns:
        result (potenzialmente modificato)
    """
    threshold = TWO_PHASE_THRESHOLDS.get(intent, 5)
    if item_count > threshold and isinstance(result, dict) and "formatted_response" in result:
        state["has_more_details"] = True
        state["detail_context"] = {
            "formatted_response": full_formatted_response or result["formatted_response"],
            "intent": intent,
            "item_count": item_count
        }
        result["formatted_response"] = summary_text + TWO_PHASE_SUFFIX
    return result
