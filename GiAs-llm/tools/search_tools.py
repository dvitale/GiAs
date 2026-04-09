from typing import Dict, Any, List, Optional

from tools._tool_compat import tool

try:
    from agents.data_agent import DataRetriever
    from agents.response_agent import ResponseFormatter
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever
    from agents.response_agent import ResponseFormatter


_hybrid_engine = None


def _get_hybrid_engine():
    global _hybrid_engine
    if _hybrid_engine is None:
        try:
            from tools.hybrid_search import HybridSearchEngine
            from llm.client import LLMClient
            _hybrid_engine = HybridSearchEngine(llm_client=LLMClient())
            print("[SEARCH] HybridSearchEngine inizializzato")
        except Exception as e:
            print(f"[SEARCH] HybridSearchEngine non disponibile: {e}")
    return _hybrid_engine


@tool("search_piani")
def search_piani_by_topic(query: str, similarity_threshold: float = 0.4, sezione: str = None) -> Dict[str, Any]:
    """
    Cerca piani di controllo per argomento sul database in memoria.

    Esegue ricerca testuale (ILIKE) sulle colonne descrizione_piano_attivita e descrizione_indicatore
    del DataFrame piani_monitoraggio gia' caricato in RAM al startup.

    Args:
        query: Termine di ricerca (es. "scrofe", "bovini", "residui")
        similarity_threshold: Non usato, mantenuto per compatibilita'
        sezione: Lettera sezione opzionale (es. "A", "B") per filtrare per colonna sezione

    Returns:
        Dict con piani trovati e risposta formattata
    """
    # Quando c'e' un filtro sezione, salta hybrid search (serve filtro strutturato, non semantico)
    if sezione:
        return _search_piani_by_sezione(query, sezione)

    if not query or not query.strip():
        return {"error": "Query di ricerca non specificata"}

    search_term = query.strip()

    # Prova hybrid search prima del fallback DB ILIKE
    engine = _get_hybrid_engine()
    if engine is not None:
        try:
            result = engine.search(search_term)
            if result.get("matches") and not result.get("error"):
                return result
        except Exception as e:
            print(f"[SEARCH] Hybrid fallback a DB ILIKE: {e}")

    try:
        matches = DataRetriever.search_piani_by_db(search_term)

        if not matches:
            return {
                "error": f"Nessun piano trovato per '{search_term}'",
                "search_term": search_term,
                "total_found": 0,
                "search_strategy": "db_ilike",
                "formatted_response": f"Non ho trovato piani relativi a **'{search_term}'**. Prova con un termine diverso, ad esempio:\n- Bovini, suini, avicoli\n- Latte, carne, mangimi\n- Allevamenti\n- Codice piano (es. A1, B2)"
            }

        # Format response
        response = ResponseFormatter.format_search_results(
            search_term=search_term,
            matches=matches,
            max_display=10
        )

        return {
            "search_term": search_term,
            "total_found": len(matches),
            "matches": matches,
            "search_strategy": "db_ilike",
            "formatted_response": response
        }

    except Exception as e:
        return {
            "error": f"Errore durante la ricerca: {str(e)}",
            "search_strategy": "db_ilike_failed"
        }


def _search_piani_by_sezione(query: str, sezione: str) -> Dict[str, Any]:
    """
    Ricerca piani filtrata per sezione (colonna strutturata del DataFrame).
    Quando l'utente chiede "piani della sezione A", usa il filtro sulla colonna sezione
    invece della ricerca testuale nelle descrizioni.
    """
    try:
        import re

        # Pulisci topic: rimuovi "sezione X" dal topic se presente
        clean_query = None
        campionamento_filter = None
        if query:
            clean_query = re.sub(r'\bsez(?:ione|\.)\s+[A-Z]\b', '', query, flags=re.IGNORECASE).strip()
            # Rileva "campionamento" come filtro strutturale (non keyword)
            # Pattern: "richiedono campionamento", "con campionamento", "campionamento", "senza campionamento"
            camp_match = re.search(r'\b(senza\s+)?campion(?:amento|i)\b', clean_query, re.IGNORECASE)
            if camp_match:
                campionamento_filter = camp_match.group(1) is None  # True se "campionamento", False se "senza campionamento"
                # Rimuovi il pattern campionamento dal topic per non cercare la parola nelle descrizioni
                clean_query = re.sub(r'\b(?:che\s+richiedono|con|senza|che\s+prevedono|di)?\s*campion(?:amento|i)\b', '', clean_query, flags=re.IGNORECASE).strip()
            if not clean_query or len(clean_query) < 2:
                clean_query = None

        matches = DataRetriever.search_piani_by_db(query=clean_query, sezione=sezione, campionamento=campionamento_filter)

        search_label = f"sezione {sezione.upper()}"
        if campionamento_filter is True:
            search_label = f"piani con campionamento nella sezione {sezione.upper()}"
        elif campionamento_filter is False:
            search_label = f"piani senza campionamento nella sezione {sezione.upper()}"
        if clean_query:
            search_label = f"'{clean_query}' nella {search_label}"

        if not matches:
            return {
                "error": f"Nessun piano trovato per {search_label}",
                "search_term": search_label,
                "total_found": 0,
                "search_strategy": "sezione_filter",
                "formatted_response": f"Non ho trovato piani di monitoraggio nella **{search_label}**."
            }

        response = ResponseFormatter.format_search_results(
            search_term=search_label,
            matches=matches,
            max_display=10
        )

        return {
            "search_term": search_label,
            "total_found": len(matches),
            "matches": matches,
            "search_strategy": "sezione_filter",
            "formatted_response": response
        }

    except Exception as e:
        return {
            "error": f"Errore durante la ricerca per sezione: {str(e)}",
            "search_strategy": "sezione_filter_failed"
        }


def search_tool(query: str = None, sezione: str = None) -> Dict[str, Any]:
    """
    Router per funzionalità di ricerca.

    Args:
        query: Termine di ricerca
        sezione: Lettera sezione opzionale (es. "A", "B")

    Returns:
        Dict con risultati ricerca
    """
    try:
        search_func = search_piani_by_topic.func if hasattr(search_piani_by_topic, 'func') else search_piani_by_topic
        return search_func(query, sezione=sezione)
    except Exception as e:
        return {"error": f"Errore in search_tool: {str(e)}"}
